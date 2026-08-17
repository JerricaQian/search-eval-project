#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
坐标网格线辅助工具（eval-3-page-color-logic）

用于在标定 exclude_regions 前，给整页截图叠加水平网格线和 y 坐标刻度，
方便人工读取商家图片/营销 banner/腰封/金刚icon 等待排除区域的精确 y 坐标范围。
建议先用较大 step（如 100）看整体分布，再对需要精细定位的局部区间用较小 step（如 20）
生成放大网格图核对边界。

用法：
    python3 grid_overlay.py <input_image> <output_image> [step]

示例：
    python3 grid_overlay.py page.png page_grid.png 100
"""
import cv2
import sys


def draw_grid(path, out, step=100):
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"无法读取图片：{path}")
    h, w = img.shape[:2]
    for y in range(0, h, step):
        cv2.line(img, (0, y), (w, y), (0, 0, 255), 1)
        cv2.putText(img, str(y), (2, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    cv2.imwrite(out, img)
    print(f"已生成网格图：{out}（原图尺寸 {w}x{h}，网格间距 {step}px）")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法：python3 grid_overlay.py <input_image> <output_image> [step]")
        sys.exit(1)
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    step = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    draw_grid(input_path, output_path, step)
