#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
页面级色彩运用逻辑性评测脚本（eval-3-page-color-logic）

统计口径：整页（按「搜索词 × 页面」颗粒度），非逐组件/逐元素。

两个指标：
- 总颜色数量：按 36 色 HSV 标准（9 色相 家族），统计占比 ≥ 1% 的色系数量。
- 主导色数量：按 7 色 HSV 标准（9 色相合并为 7 个基础色相），统计占比 > 5% 的色系数量。

两者共用同一套排除规则：
- 黑白灰中性色（饱和度 S < 12）不计入任一指标。
- 商家图片 / 商品图片 / 营销类元素（营销图片、banner、腰封）/ 金刚 icon 通过人工标定的矩形
  区域（exclude_regions）排除，不参与统计。标签本身不排除。
- 面积占比 < 1% 的颜色不计入总颜色数量；占比 ≤ 5% 的颜色不计入主导色数量。

用法（单张截图）：
    python3 page_color_analysis.py '{
        "image": "path/to/page.png",
        "exclude_regions": [[y1, y2, x1, x2], ...],
        "out_debug": "path/to/debug.png"
    }'

用法（同一搜索词的多屏滚动截图，合并统计为一条结论）：
    python3 page_color_analysis.py '{
        "pages": [
            {"image": "path/to/page1.png", "exclude_regions": [[y1,y2,x1,x2]], "out_debug": "debug1.png"},
            {"image": "path/to/page2.png", "exclude_regions": [[y1,y2,x1,x2]], "out_debug": "debug2.png"}
        ]
    }'

exclude_regions 中的每个矩形用 [y1, y2, x1, x2] 表示（像素坐标，y 为纵向、x 为横向，
左上角为原点），由人工核对截图后标定，覆盖商家/商品图片、营销 banner/腰封、金刚 icon 等区域。
多屏模式下，每张截图单独生成调试图供核对，但总颜色数量/主导色数量按所有截图的有效像素合并计算
（等价于把多张截图的有效像素拼接成一份样本再统计占比，不是简单对每张图的评级结果取平均）。

注意：本脚本不做自动化照片检测（不同页面版式差异大，自动检测容易误伤标签或漏检图片），
排除区域必须由人工在截图上核对坐标后传入。建议先用 grid_overlay.py 生成带坐标网格线的
辅助图，人工读取矩形坐标，再运行本脚本，并通过 out_debug 生成的调试图二次核对排除是否准确。
"""
import cv2
import numpy as np
import json
import sys
import os

np.random.seed(42)

# ---------------- 色彩分类定义 ----------------

# 36 色标准的 9 个色相区间（每个区间再按明度分深浅两档，深浅合并计为 1 个色系，
# 因此统计层面只需按下列 9 个色相家族计数）
HUE_FAMILIES_36 = [
    ("red", [(0, 15), (330, 360)]),
    ("orange", [(15, 45)]),
    ("yellow", [(45, 68)]),
    ("yellow-green", [(68, 85)]),
    ("green", [(85, 150)]),
    ("cyan", [(150, 195)]),
    ("blue", [(195, 250)]),
    ("purple", [(250, 290)]),
    ("magenta", [(290, 330)]),
]

# 7 色标准：在 36 色的 9 个色相基础上，将黄绿并入绿、品红并入红，得到 7 个基础色相
HUE_FAMILIES_7 = [
    ("red", [(0, 15), (330, 360), (290, 330)]),  # 红 + 品红
    ("orange", [(15, 45)]),
    ("yellow", [(45, 68)]),
    ("green", [(68, 150)]),  # 黄绿 + 绿
    ("cyan", [(150, 195)]),
    ("blue", [(195, 250)]),
    ("purple", [(250, 290)]),
]

ACHROMATIC_S_THRESHOLD = 12  # 饱和度低于该值视为黑白灰中性色，不参与任一指标
TOTAL_COLOR_RATIO_THRESHOLD = 0.01   # 总颜色数量：占比 >= 1% 才计入
DOMINANT_COLOR_RATIO_THRESHOLD = 0.05  # 主导色数量：占比 > 5% 才计入
WHITE_BG_THRESHOLD = 247  # RGB 三通道均 >= 该值视为白色背景
MAX_SAMPLE_PIXELS = 300000  # 有效像素超过此数则随机采样，保证性能与可复现性


def detect_white_bg_mask(img_bgr):
    """检测白色背景像素：RGB 三通道均 >= 247"""
    b, g, r = cv2.split(img_bgr)
    return (b >= WHITE_BG_THRESHOLD) & (g >= WHITE_BG_THRESHOLD) & (r >= WHITE_BG_THRESHOLD)


def build_manual_exclude_mask(shape, exclude_regions):
    """根据人工标定的矩形区域列表构建排除 mask。exclude_regions: [[y1,y2,x1,x2], ...]"""
    h, w = shape[:2]
    mask = np.zeros((h, w), dtype=bool)
    for region in exclude_regions or []:
        y1, y2, x1, x2 = region
        y1, y2 = max(0, y1), min(h, y2)
        x1, x2 = max(0, x1), min(w, x2)
        if y2 > y1 and x2 > x1:
            mask[y1:y2, x1:x2] = True
    return mask


def count_families(H_values, families, denom):
    """统计各色相家族的像素占比（相对 denom，即全部有效像素数，含中性色）"""
    ratios = {}
    if H_values.size == 0:
        return ratios
    for name, ranges in families:
        m = np.zeros(H_values.shape, dtype=bool)
        for lo, hi in ranges:
            m |= (H_values >= lo) & (H_values < hi)
        cnt = int(m.sum())
        if cnt > 0:
            ratios[name] = cnt / denom
    return ratios


def extract_valid_hsv(img_path, exclude_regions=None, out_debug_path=None):
    """读取单张图片，构建排除 mask，返回该图有效像素的 H/S/V 数组（未采样、未做色系统计）。
    同时按需生成该图的调试图。供单图模式和多图合并模式共用。
    """
    img = cv2.imread(img_path)
    if img is None:
        raise FileNotFoundError(f"无法读取图片：{img_path}")

    manual_mask = build_manual_exclude_mask(img.shape, exclude_regions)
    white_mask = detect_white_bg_mask(img)
    valid_mask = ~(manual_mask | white_mask)

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    Hh = hsv[:, :, 0].astype(np.float32) * 2  # opencv H: 0-179 -> 映射到 0-358
    Ss = hsv[:, :, 1].astype(np.float32) / 255 * 100
    Vv = hsv[:, :, 2].astype(np.float32) / 255 * 100

    valid_H = Hh[valid_mask]
    valid_S = Ss[valid_mask]
    valid_V = Vv[valid_mask]

    if out_debug_path:
        debug = img.copy()
        alpha = 0.45
        yellow = np.zeros_like(debug)
        yellow[:, :] = (0, 255, 255)
        debug[manual_mask] = (debug[manual_mask] * (1 - alpha) + yellow[manual_mask] * alpha).astype(np.uint8)
        cv2.imwrite(out_debug_path, debug)

    meta = {
        "image": os.path.basename(img_path),
        "width": int(img.shape[1]),
        "height": int(img.shape[0]),
        "n_valid_pixels_before_sample": int(valid_H.size),
    }
    return valid_H, valid_S, valid_V, meta


def summarize(valid_H, valid_S, valid_V):
    """对给定的（可能来自单张或多张图合并的）有效像素 H/S/V 数组做采样、色系占比统计与评级。"""
    n_valid = int(valid_H.size)
    if n_valid == 0:
        raise ValueError("有效像素为 0，请检查排除区域是否覆盖了整张图片，或图片是否读取正确。")

    if n_valid > MAX_SAMPLE_PIXELS:
        idx = np.random.choice(n_valid, MAX_SAMPLE_PIXELS, replace=False)
        valid_H = valid_H[idx]
        valid_S = valid_S[idx]
        n_valid = MAX_SAMPLE_PIXELS

    achromatic = valid_S < ACHROMATIC_S_THRESHOLD
    chromatic = ~achromatic
    n_chromatic = int(chromatic.sum())
    ch_H = valid_H[chromatic]

    ratio_36 = count_families(ch_H, HUE_FAMILIES_36, n_valid)
    ratio_36_kept = {k: v for k, v in ratio_36.items() if v >= TOTAL_COLOR_RATIO_THRESHOLD}
    total_color_count = len(ratio_36_kept)

    ratio_7 = count_families(ch_H, HUE_FAMILIES_7, n_valid)
    ratio_7_kept = {k: v for k, v in ratio_7.items() if v > DOMINANT_COLOR_RATIO_THRESHOLD}
    dominant_color_count = len(ratio_7_kept)

    rating = rate(total_color_count, dominant_color_count)

    return {
        "n_valid_pixels": n_valid,
        "n_chromatic_pixels": n_chromatic,
        "total_color_count_36": total_color_count,
        "total_color_families_36": {
            k: f"{v * 100:.2f}%" for k, v in sorted(ratio_36_kept.items(), key=lambda x: -x[1])
        },
        "dominant_color_count_7": dominant_color_count,
        "dominant_color_families_7": {
            k: f"{v * 100:.2f}%" for k, v in sorted(ratio_7_kept.items(), key=lambda x: -x[1])
        },
        "all_7_family_ratios_debug": {
            k: f"{v * 100:.2f}%" for k, v in sorted(ratio_7.items(), key=lambda x: -x[1])
        },
        "rating": rating,
    }


def analyze_page(img_path, exclude_regions=None, out_debug_path=None):
    """单张截图模式：分析一张整页截图，返回该页面的评测结果。"""
    valid_H, valid_S, valid_V, meta = extract_valid_hsv(img_path, exclude_regions, out_debug_path)
    summary = summarize(valid_H, valid_S, valid_V)
    return {**meta, **summary}


def analyze_pages_merged(pages_config):
    """多屏合并模式：pages_config 为 [{"image":..., "exclude_regions":..., "out_debug":...}, ...]。
    将各张截图的有效像素拼接后统一统计占比与评级，代表「同一搜索词的完整页面」的一条结论。
    """
    all_H, all_S, all_V = [], [], []
    per_page_meta = []
    for page in pages_config:
        valid_H, valid_S, valid_V, meta = extract_valid_hsv(
            page["image"], page.get("exclude_regions", []), page.get("out_debug")
        )
        all_H.append(valid_H)
        all_S.append(valid_S)
        all_V.append(valid_V)
        per_page_meta.append(meta)

    merged_H = np.concatenate(all_H) if all_H else np.array([], dtype=np.float32)
    merged_S = np.concatenate(all_S) if all_S else np.array([], dtype=np.float32)
    merged_V = np.concatenate(all_V) if all_V else np.array([], dtype=np.float32)

    summary = summarize(merged_H, merged_S, merged_V)
    return {
        "pages": per_page_meta,
        "n_pages": len(pages_config),
        **summary,
    }


def rate(total_color_count, dominant_color_count):
    """按评估标准评级，判定优先级固定为「不达标 -> 优秀 -> 达标」，命中即停止：

    1. 不达标：总颜色数量 > 10，或主导色数量 = 0，或主导色数量 > 4。
    2. 优秀（需在未命中不达标的前提下判断）：总颜色数量 属于 [0,6] 且 主导色数量 属于 [1,2]。
    3. 其余情况一律归入达标（含总颜色数量属于 [7,10]、主导色数量 = 3，以及两条规则都未覆盖到的
       交叉组合，例如总颜色数量=5 但主导色数量=4 这种"非不达标、非优秀"的边界情况）。

    注意：total_color_count 恰好等于 6 时优先按优秀区间的闭区间上限处理（只要 dominant 也落在
    [1,2] 就判优秀），而不是套用"达标：total属于[7,10]"——两者本身在数值上并不重叠（[0,6] 与
    [7,10] 首尾相接、没有交叉），但主导色维度仍存在交叉地带（如 total=5 属于优秀区间但
    dominant=3，命中达标规则的"主导色=3"而不满足优秀所需的 dominant∈[1,2]），必须靠本函数固定的
    判定顺序来消歧。
    """
    if total_color_count > 10 or dominant_color_count == 0 or dominant_color_count > 4:
        return "🔴 不达标"
    if total_color_count <= 6 and 1 <= dominant_color_count <= 2:
        return "🟢 优秀"
    return "🟡 达标"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": (
                "请传入 JSON 参数。单图模式示例：'{\"image\": \"a.png\", "
                "\"exclude_regions\": [[y1,y2,x1,x2]], \"out_debug\": \"debug.png\"}'；"
                "多屏合并模式示例：'{\"pages\": [{\"image\": \"a.png\", \"exclude_regions\": [...], "
                "\"out_debug\": \"debug_a.png\"}, {\"image\": \"b.png\", ...}]}'"
            )
        }, ensure_ascii=False))
        sys.exit(1)
    config = json.loads(sys.argv[1])
    try:
        if "pages" in config:
            # 多屏合并模式：同一搜索词的多张滚动截图，合并为一条结论
            result = analyze_pages_merged(config["pages"])
        else:
            # 单图模式
            img_path = config["image"]
            exclude_regions = config.get("exclude_regions", [])
            out_debug = config.get("out_debug")
            result = analyze_page(img_path, exclude_regions=exclude_regions, out_debug_path=out_debug)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)
