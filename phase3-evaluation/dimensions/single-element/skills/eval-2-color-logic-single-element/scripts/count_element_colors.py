#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
count_element_colors.py — 单一元素颜色数量统计（指标 1.2.2 色彩运用有逻辑）

用途：
    输入「一个单一元素」的裁剪图（标签/标题/价格/提示条/按钮等），按七色标准
    统计该元素内的有彩色数量（底色、文字色、icon 均扫描），黑、白、灰中性色排除，剔除面积
    占比 < 1% 的颜色，最后给出评级：总颜色数 ≤ 2 优秀🟢 / = 3 达标🟡 / > 3 不达标🔴。

    渐变无需特判：渐变像素会自然落入其跨越的多个色格，若各格占比均 ≥ 阈值即计为多色。

边界：
    评测目标必须先由 Skill 直接读取 Phase2 JSON 确定；本脚本只测量已经选中的单个候选，
    不遍历 Phase2 全量原子、不建立目标账本，也不替代候选/排除/复核分流。

用法：
    python3 count_element_colors.py <元素裁剪图.png> [--min-ratio 1.0] [--json] [--debug out.png] [--output result.json]
    # 也可对整图只统计一个矩形框：
    python3 count_element_colors.py <图.png> --box x,y,w,h

    <元素裁剪图> 应「紧贴元素边界」，不要混入相邻元素或大片页面背景。

依赖：Pillow, numpy （可选 --debug 需要 Pillow 已足够）

注意：黑/白/灰中性色只保留在诊断色谱中，不计入最终色数；同一有彩色相的深浅合并为一个色系。
"""
import sys
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[6]
PHASE3_SCRIPTS = PROJECT_ROOT / "phase3-evaluation" / "common" / "scripts"
if str(PHASE3_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PHASE3_SCRIPTS))
from color_taxonomy import (
    ACHROMATIC_RGB_CHROMA_THRESHOLD,
    ACHROMATIC_S_THRESHOLD,
    ACHROMATIC_V_THRESHOLD,
    HUE7_BINS,
    HUE7_ZH,
)


# ---- 七色标准（红、橙、黄、绿、青、蓝、紫）----
# 无彩色：S < S_ACHROMATIC，按明度 V 分 5 格
S_ACHROMATIC = ACHROMATIC_S_THRESHOLD
# 有彩色：S >= S_ACHROMATIC，按色相 H 分 7 区间，每区间按 V 分深/浅（V>60 浅 / <=60 深）
V_LIGHT = 60.0

# 色相区间 (名称, H下限, H上限)。红色跨 0/360，用两段表示。
HUE_BINS = list(HUE7_BINS)

ACHROMATIC_LABELS = {
    "white": "白色",
    "light-gray": "浅灰",
    "mid-gray": "中灰",
    "dark-gray": "深灰",
    "black": "黑色",
}
HUE_ZH = HUE7_ZH


def rgb_to_hsv_arr(rgb):
    """rgb: (N,3) uint8 -> (H[0-360], S[0-100], V[0-100]) 各 (N,)"""
    arr = rgb.astype(np.float64) / 255.0
    r, g, b = arr[:, 0], arr[:, 1], arr[:, 2]
    mx = np.max(arr, axis=1)
    mn = np.min(arr, axis=1)
    diff = mx - mn

    h = np.zeros_like(mx)
    mask = diff > 1e-9
    # 计算色相
    rc = np.where(mask & (mx == r))
    gc = np.where(mask & (mx == g))
    bc = np.where(mask & (mx == b))
    h[rc] = (60 * ((g[rc] - b[rc]) / diff[rc]) + 360) % 360
    h[gc] = (60 * ((b[gc] - r[gc]) / diff[gc]) + 120) % 360
    h[bc] = (60 * ((r[bc] - g[bc]) / diff[bc]) + 240) % 360

    s = np.zeros_like(mx)
    np.divide(diff, mx, out=s, where=mx > 1e-9)
    s *= 100.0
    v = mx * 100.0
    return h, s, v


def classify(h, s, v):
    """返回每个像素的七色归并诊断 key 与中文名。"""
    n = len(h)
    keys = np.empty(n, dtype=object)
    names = np.empty(n, dtype=object)

    rgb_chroma = 255.0 * (s / 100.0) * (v / 100.0)
    achro = (
        (s < ACHROMATIC_S_THRESHOLD)
        | (v < ACHROMATIC_V_THRESHOLD)
        | (rgb_chroma < ACHROMATIC_RGB_CHROMA_THRESHOLD)
    )
    # 无彩色分 5 级
    for idx in np.where(achro)[0]:
        vv = v[idx]
        if vv > 90:
            k = "white"
        elif vv > 65:
            k = "light-gray"
        elif vv > 40:
            k = "mid-gray"
        elif vv > 15:
            k = "dark-gray"
        else:
            k = "black"
        keys[idx] = k
        names[idx] = ACHROMATIC_LABELS[k]

    # 有彩色
    for idx in np.where(~achro)[0]:
        hv = h[idx]
        fam = None
        for name, lo, hi in HUE_BINS:
            if lo <= hv < hi:
                fam = name
                break
        if fam is None:
            fam = "red"
        shade = "light" if v[idx] > V_LIGHT else "dark"
        keys[idx] = f"{fam}-{shade}"
        names[idx] = f"{'浅' if shade == 'light' else '深'}{HUE_ZH[fam]}"
    return keys, names


def background_keep_mask(img_rgb, tol=18):
    """返回圆角/非矩形元素的可复核背景排除 mask。"""
    h, w = img_rgb.shape[:2]
    k = max(2, min(h, w) // 12)
    corners = [img_rgb[:k, :k], img_rgb[:k, -k:], img_rgb[-k:, :k], img_rgb[-k:, -k:]]
    corner_means = [c.reshape(-1, 3).mean(axis=0) for c in corners]
    # 判断四角是否一致（互相接近的角 >= 3 个）
    base = None
    for i, cm in enumerate(corner_means):
        close = sum(1 for other in corner_means if np.abs(cm - other).max() <= tol)
        if close >= 3:
            base = cm
            break
    pixels = img_rgb.reshape(-1, 3).astype(np.int32)
    if base is None:
        return np.ones((h, w), dtype=bool)  # 四角不一致，无可确认外围背景
    bg = base.astype(np.int32)
    dist = np.abs(pixels - bg).max(axis=1)
    keep = dist > tol
    if keep.sum() < len(pixels) * 0.02:
        return np.ones((h, w), dtype=bool)  # 剔除后几乎没剩，放弃（避免误删）
    return keep.reshape(h, w)


def drop_background(img_rgb, tol=18):
    """剔除元素外围背景色，返回过滤后的 (N,3) 像素数组。"""
    return img_rgb[background_keep_mask(img_rgb, tol=tol)]


def save_debug_mask(img_rgb, output_path, drop_bg=False):
    """保存取样 mask：彩色取样像素保留原色，中性色/外围背景置为浅灰。"""
    keep = background_keep_mask(img_rgb) if drop_bg else np.ones(img_rgb.shape[:2], dtype=bool)
    pixels = img_rgb.reshape(-1, 3)
    _, saturation, value = rgb_to_hsv_arr(pixels)
    rgb_chroma = 255.0 * (saturation / 100.0) * (value / 100.0)
    chromatic = (
        (saturation >= ACHROMATIC_S_THRESHOLD)
        & (value >= ACHROMATIC_V_THRESHOLD)
        & (rgb_chroma >= ACHROMATIC_RGB_CHROMA_THRESHOLD)
    ).reshape(img_rgb.shape[:2])
    sample_mask = keep & chromatic
    debug = np.full_like(img_rgb, 238)
    debug[sample_mask] = img_rgb[sample_mask]
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(debug).save(path)
    return int(sample_mask.sum())


def count_colors(img_rgb, min_ratio_pct=1.0, drop_bg=False):
    """img_rgb: (H,W,3) uint8. 返回统计结果 dict。"""
    if drop_bg:
        pixels = drop_background(img_rgb)
    else:
        pixels = img_rgb.reshape(-1, 3)
    total = len(pixels)
    if total == 0:
        return {"total_pixels": 0, "colors": [], "color_count": 0}

    # 采样以控制计算量，固定随机种子保证可复现
    if total > 300000:
        rng = np.random.default_rng(42)
        sel = rng.choice(total, 300000, replace=False)
        sample = pixels[sel]
    else:
        sample = pixels
    ns = len(sample)

    h, s, v = rgb_to_hsv_arr(sample)
    rgb_chroma = 255.0 * (s / 100.0) * (v / 100.0)
    chromatic = (
        (s >= ACHROMATIC_S_THRESHOLD)
        & (v >= ACHROMATIC_V_THRESHOLD)
        & (rgb_chroma >= ACHROMATIC_RGB_CHROMA_THRESHOLD)
    )
    keys, names = classify(h, s, v)
    chromatic_denominator = int(chromatic.sum())

    # 统计各色格占比
    from collections import Counter
    cnt = Counter(keys)
    name_map = {}
    for k, nm in zip(keys, names):
        name_map[k] = nm

    colors = []
    for k, c in cnt.items():
        # Neutral pixels never become colour families, but remain part of the
        # element-area denominator.  Otherwise a tiny coloured mark inside a
        # mostly neutral element could be inflated into a dominant colour.
        ratio = c / ns * 100.0
        colors.append({"key": k, "name": name_map[k], "ratio": round(ratio, 2)})
    colors.sort(key=lambda x: -x["ratio"])

    # 明暗细分结果只作诊断；最终评分按七色归并
    kept_fine = [c for c in colors if c["ratio"] >= min_ratio_pct]

    # —— 感知合并：把「同一视觉颜色被抗锯齿/明暗拆成多格」的情况并回一色 ——
    # 规则：
    #  1) 同一有彩色相的深/浅两格合并为「该色相」一色（浅黄+深黄=黄）。
    #     这不影响渐变跨色相的判定——跨到不同色相(青→蓝)仍是两色。
    #  2) 无彩色：黑/白/灰保留在诊断色谱中，但不进入最终计数。
    from collections import defaultdict
    fam_ratio = defaultdict(float)
    fam_zh = {}
    for c in colors:
        key = c["key"]
        if "-" in key and key.split("-")[0] in HUE_ZH:
            fam = key.split("-")[0]                    # 有彩色相
            fam_ratio[fam] += c["ratio"]
            fam_zh[fam] = HUE_ZH[fam]
        else:
            fam_ratio[key] += c["ratio"]               # 无彩色各明度级
            fam_zh[key] = ACHROMATIC_LABELS.get(key, key)

    merged = [{"key": k, "name": fam_zh[k], "ratio": round(v, 2)}
              for k, v in fam_ratio.items()]
    merged.sort(key=lambda x: -x["ratio"])

    kept = []
    for c in merged:
        if c["ratio"] < min_ratio_pct:
            continue
        if c["key"] in ACHROMATIC_LABELS:
            continue
        kept.append(c)

    return {
        "total_pixels": total,
        "sampled": ns,
        "chromatic_pixels": chromatic_denominator,
        "neutral_pixels": ns - chromatic_denominator,
        "neutral_rule": {
            "minSaturationPct": ACHROMATIC_S_THRESHOLD,
            "minValuePct": ACHROMATIC_V_THRESHOLD,
            "minRgbChroma": ACHROMATIC_RGB_CHROMA_THRESHOLD,
        },
        "min_ratio_pct": min_ratio_pct,
        "colors_all": colors,          # 细粒度 36 格全量（诊断）
        "colors_fine": kept_fine,      # 细粒度过阈（诊断）
        "colors": kept,                # 感知合并后（最终计数用）
        "color_count": len(kept),
    }


def grade(color_count):
    if color_count <= 2:
        return "🟢 优秀", "excellent"
    if color_count == 3:
        return "🟡 达标", "pass"
    return "🔴 不达标", "fail"


def main():
    ap = argparse.ArgumentParser(description="测量 Phase2 JSON 已确定的单一元素颜色候选（指标 1.2.2）")
    ap.add_argument("image", help="元素裁剪图路径")
    ap.add_argument("--min-ratio", type=float, default=1.0,
                    help="面积占比阈值(%%)，低于此值的颜色不计入，默认 1.0")
    ap.add_argument("--box", default=None,
                    help="只统计图中某矩形，格式 x,y,w,h（像素）")
    ap.add_argument("--drop-bg", action="store_true",
                    help="剔除元素外围背景色（圆角/非矩形元素、方形框四角露出页面背景时用）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--debug", help="保存彩色取样 mask 调试图")
    ap.add_argument("--output", help="将完整测量 JSON 保存到指定路径")
    args = ap.parse_args()

    img = Image.open(args.image).convert("RGB")
    arr = np.array(img)
    if args.box:
        x, y, w, h = [int(t) for t in args.box.split(",")]
        arr = arr[y:y + h, x:x + w]

    res = count_colors(arr, args.min_ratio, drop_bg=args.drop_bg)
    g_label, g_key = grade(res["color_count"])
    res["grade"] = g_label
    res["grade_key"] = g_key
    res["input"] = {
        "image": str(Path(args.image).resolve()),
        "box": args.box,
        "drop_bg": bool(args.drop_bg),
    }
    if args.debug:
        res["debug_image"] = str(Path(args.debug).resolve())
        res["debug_chromatic_pixel_count"] = save_debug_mask(arr, args.debug, drop_bg=args.drop_bg)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        res["artifact_path"] = str(output.resolve())
        output.write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    print(f"图片: {args.image}  尺寸: {arr.shape[1]}x{arr.shape[0]}  像素: {res['total_pixels']}")
    print(f"占比阈值: ≥ {args.min_ratio}%   （低于此值的颜色已剔除）")
    print("-" * 52)
    print("计入的有彩色（七色标准，黑/白/灰中性色已排除）:")
    for c in res["colors"]:
        print(f"  {c['name']:<6} ({c['key']:<14}) {c['ratio']:>6.2f}%")
    dropped = [c for c in res["colors_all"] if c["ratio"] < args.min_ratio]
    if dropped:
        print("已剔除(<阈值):")
        for c in dropped:
            print(f"  {c['name']:<6} ({c['key']:<14}) {c['ratio']:>6.2f}%  ← 排除")
    print("-" * 52)
    print(f"总颜色数量 = {res['color_count']}   评级: {g_label}")


if __name__ == "__main__":
    main()
