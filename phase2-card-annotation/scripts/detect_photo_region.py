"""Detect photo regions (头图/商品图/菜品图/营销大图) in a full-page search-result
screenshot by pure pixel analysis — NO image reading / NO visual tokens. Ports
eval-3-color-logic Step 3 Strategy A (整页截图轮廓分类合并法).

用法:
  python detect_photo_region.py <img>                 # 纯文本，每个 photo bbox 一行
  python detect_photo_region.py <img> --json          # JSON 数组
  python detect_photo_region.py <img> --min-area 5000 # 只报面积≥该值的(便于筛头图)

输出每个照片区域的 bbox (绝对像素坐标)。配合 scan_rows.py（留白带定卡 Y 边界），
把 photo bbox 按 y 落入对应卡即得该卡头图区——全程不读图，主/sub 上下文都不进图。

算法 (eval-3 策略A):
  1. 白底(RGB≥247)→内容 mask→3×3 开运算去噪→findContours 外轮廓(面积≥30)
  2. 逐轮廓 photo/ui 分类:
     - 快速排除 UI: 面积<300 / 高<15 / y<100(状态栏) / 宽高比>3.5 窄条 /
       hue_std<10 且 面积<20000 纯色标签
     - photo(满足其一): 面积≥3000 且 active_bins≥3 且 RGB std≥25;
       或 面积≥1500 且 active_bins≥5 且 RGB std≥35;
       或 icon(30-160px 近正方形)且 有彩占比≥0.3 且 面积≥2000
  3. 合并邻近 photo bbox: 水平间距≤20 且纵向有交叠，或 垂直间距≤15 且横向有交叠
  4. 输出 bbox (mask 精确填充仅色彩统计用，这里只取 bbox)

依赖: opencv-python (cv2), numpy, Pillow.
"""
import sys, json, argparse
import numpy as np
import cv2
from PIL import Image


def _contour_stats(crop_rgb):
    """对单轮廓的 RGB 裁剪区算 hue active bins / RGB std / 有彩占比 / hue std。
    crop_rgb: HxWx3 uint8 (RGB 顺序)。"""
    if crop_rgb.size == 0:
        return dict(active_bins=0, rgb_std=0.0, chrom_ratio=0.0, hue_std=0.0)
    hsv = cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    chrom = s > 30  # S>=12/100 → cv2 S>=30.6，有彩像素
    chrom_ratio = float(chrom.mean())
    # hue active bins: 18 bins over 0-180, 计占比>2% 的 bin 数（仅在有彩像素上）
    h_chrom = h[chrom] if chrom.any() else h.flatten()
    if len(h_chrom) == 0:
        active_bins = 0
        hue_std = 0.0
    else:
        hist = np.histogram(h_chrom, bins=18, range=(0, 180))[0]
        active_bins = int((hist / max(1, hist.sum()) > 0.02).sum())
        hue_std = float(h_chrom.std())
    rgb_std = float(crop_rgb.reshape(-1, 3).std())  # 整体 RGB 变化
    return dict(active_bins=active_bins, rgb_std=rgb_std,
                chrom_ratio=chrom_ratio, hue_std=hue_std)


def _classify(x, y, w, h, area, stats):
    """返回 (kind, rule): kind∈{photo,ui}, rule=命中条件字符串。"""
    # 快速排除明显 UI
    if area < 300:
        return "ui", "tiny_area"
    if h < 15:
        return "ui", "too_short"
    if y < 100:  # 状态栏区域
        return "ui", "status_bar"
    aspect = max(w, h) / max(1, min(w, h))
    if aspect > 3.5:
        return "ui", "narrow_bar"
    if stats["hue_std"] < 10 and area < 20000:
        return "ui", "pure_color_label"
    # photo 规则
    ab, rs, cr = stats["active_bins"], stats["rgb_std"], stats["chrom_ratio"]
    # Real product/merchant photos can be nearly monochromatic (durian,
    # medicine packaging, dark storefronts).  Keep this behind strong area,
    # texture, chroma, and geometry requirements so flat badges do not pass.
    if area >= 20000 and ab < 3 and aspect <= 2.0 and rs >= 45 and cr >= 0.2:
        return "photo", "low_hue_textured"
    if area >= 3000 and ab >= 3 and rs >= 25:
        return "photo", "large"
    if area >= 1500 and ab >= 5 and rs >= 35:
        return "photo", "colorful"
    # icon 尺寸范围 30-160px 近正方形
    if 30 <= w <= 160 and 30 <= h <= 160 and 0.7 <= (w / max(1, h)) <= 1.4 \
            and cr >= 0.3 and area >= 2000:
        return "photo", "icon"
    return "ui", "no_rule"


def _gap_axis(a, b, axis):
    """axis 维度上 a/b 的间距(负=有交叠)。a,b=(x,y,w,h)。axis=0→x,1→y。"""
    a0 = a[axis]; a1 = a0 + a[axis + 2]
    b0 = b[axis]; b1 = b0 + b[axis + 2]
    return max(a0, b0) - min(a1, b1)  # >0 间隙, <0 交叠


def _merge_nearby(boxes, h_gap=20, v_gap=15):
    """合并邻近 photo bbox: 水平间距≤h_gap 且纵向有交叠，
    或 垂直间距≤v_gap 且横向有交叠。迭代到稳定。"""
    merged = True
    while merged:
        merged = False
        out = []
        used = [False] * len(boxes)
        for i, b in enumerate(boxes):
            if used[i]:
                continue
            cur = list(b)
            for j in range(i + 1, len(boxes)):
                if used[j]:
                    continue
                c = boxes[j]
                gx = _gap_axis(cur, c, 0)  # 横向间距
                gy = _gap_axis(cur, c, 1)  # 纵向间距
                # 水平近 且 纵向交叠 / 垂直近 且 横向交叠
                if (0 <= gx <= h_gap and gy < 0) or (0 <= gy <= v_gap and gx < 0):
                    cur[0] = min(cur[0], c[0]); cur[1] = min(cur[1], c[1])
                    cur[2] = max(cur[0] + cur[2], c[0] + c[2]) - cur[0]
                    cur[3] = max(cur[1] + cur[3], c[1] + c[3]) - cur[1]
                    used[j] = True
                    merged = True
            out.append(tuple(cur))
            used[i] = True
        boxes = out
    return boxes


def detect_photos(img_path, min_area=0, h_gap=20, v_gap=15):
    """返回 [(x,y,w,h,area,rule)] 列表（绝对像素坐标），已合并邻近。
    h_gap/v_gap: 合并邻近 photo 的横向/纵向间距阈值（烧烤横幅被拆左右两块
    是因间距 32>默认 20，可 --h-gap 35 合并整块横幅）。"""
    pil = Image.open(img_path).convert("RGB")
    arr = np.asarray(pil)
    W, H = arr.shape[1], arr.shape[0]

    # 1) 白底→内容 mask→3×3 开运算去噪
    white = (arr[:, :, 0] >= 247) & (arr[:, :, 1] >= 247) & (arr[:, :, 2] >= 247)
    content = (~white).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    content = cv2.morphologyEx(content, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(content, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)

    photos = []
    for cnt in contours:
        area = float(cv2.contourArea(cnt))
        if area < 30:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        crop = arr[y:y + h, x:x + w, :]
        stats = _contour_stats(crop)
        kind, rule = _classify(x, y, w, h, area, stats)
        if kind != "photo":
            continue
        photos.append((x, y, w, h, area, rule))

    # 3) 合并邻近
    merged = _merge_nearby([(p[0], p[1], p[2], p[3]) for p in photos],
                           h_gap=h_gap, v_gap=v_gap)
    # 合并后重算 area 用 bbox 面积，rule 取被合并成员
    by_member = {}
    for (x, y, w, h) in merged:
        # 找落在该合并框内的原成员 rule
        members = [p for p in photos
                   if p[0] >= x - 1 and p[1] >= y - 1
                   and p[0] + p[2] <= x + w + 1 and p[1] + p[3] <= y + h + 1]
        rules = "+".join(sorted({m[5] for m in members})) or "?"
        by_member[(x, y, w, h)] = (w * h, rules)

    out = []
    for (x, y, w, h), (area, rule) in by_member.items():
        if area < min_area:
            continue
        out.append(dict(x=int(x), y=int(y), w=int(w), h=int(h),
                        area=int(area), rule=rule))
    out.sort(key=lambda d: (d["y"], d["x"]))
    return out, (W, H)


def main():
    ap = argparse.ArgumentParser(description="纯像素照片区检测(头图/商品图)，不读图")
    ap.add_argument("img", help="整页截图路径")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--min-area", type=int, default=0,
                    help="只报面积≥该值的 photo(便于筛头图，如 5000)")
    ap.add_argument("--h-gap", type=int, default=20,
                    help="合并邻近 photo 的横向间距阈值(烧烤横幅拆2块可调 35)")
    ap.add_argument("--v-gap", type=int, default=15,
                    help="合并邻近 photo 的纵向间距阈值")
    args = ap.parse_args()

    photos, (W, H) = detect_photos(args.img, min_area=args.min_area,
                                   h_gap=args.h_gap, v_gap=args.v_gap)
    if args.json:
        print(json.dumps(dict(W=W, H=H, count=len(photos), photos=photos),
                         ensure_ascii=False, indent=2))
        return
    print(f"Image {W}x{H}, photos={len(photos)} (min_area={args.min_area})")
    print("photo bboxes (x,y,w,h,area,rule) — 按y升序:")
    for p in photos:
        print(f"  x={p['x']:5d} y={p['y']:5d} w={p['w']:5d} h={p['h']:5d} "
              f"area={p['area']:7d} rule={p['rule']}")


if __name__ == "__main__":
    main()
