"""Scan a screenshot region to find horizontal whitespace bands (行间留白)
and content rows (内容行), to assist locating region / card-internal Y boundaries.

用法（两种粒度）:
  宏观卡间留白:  python scan_rows.py <img> [x0 x1]
  商卡内行间留白: python scan_rows.py <img> <x0> <x1> <y0> <y1>

不给 x/y 范围则扫描全图。给 y 范围时输出的 y 坐标已换算回原图绝对坐标。
同时输出留白带（行间间隙）和内容行（留白带之间的内容块），方便对照读图定分区边界。
"""
import sys, numpy as np
from PIL import Image

img = Image.open(sys.argv[1]).convert('RGB')
arr = np.asarray(img).astype(np.int16)
H, W, _ = arr.shape
x0 = int(sys.argv[2]) if len(sys.argv) > 2 else 0
x1 = int(sys.argv[3]) if len(sys.argv) > 3 else W
y0 = int(sys.argv[4]) if len(sys.argv) > 4 else 0
y1 = int(sys.argv[5]) if len(sys.argv) > 5 else H
sub = arr[y0:y1, x0:x1, :]
Hh = y1 - y0

# per-row: near white / uniform background? low std AND bright
row_std = sub.reshape(Hh, -1).std(axis=1)
row_mean = sub.reshape(Hh, -1).mean(axis=1)
is_ws = (row_std < 6) & (row_mean > 240)

# find whitespace bands (留白带)
bands = []
i = 0
while i < Hh:
    if is_ws[i]:
        j = i
        while j < Hh and is_ws[j]:
            j += 1
        if j - i >= 4:
            bands.append((i, j, j - i))
        i = j
    else:
        i += 1

print(f"Image {W}x{H}, scan x[{x0}:{x1}] y[{y0}:{y1}] (局部高{Hh})")
print("Whitespace bands (留白带, 绝对y):")
for b in bands:
    print(f"  {b[0]+y0:5d} - {b[1]+y0:5d}  (h={b[2]})")

# find content rows (内容行 = 留白带之间的非留白段)
print("Content rows (内容行, 绝对y):")
# 顶部边界
edges = [0] + [b[1] for b in bands] + [Hh]
# 实际内容行 = 相邻留白带之间 / 顶底边界之间
rows = []
prev = 0
for b in bands:
    if b[0] - prev >= 4:
        rows.append((prev, b[0]))
    prev = b[1]
if Hh - prev >= 4:
    rows.append((prev, Hh))
for r in rows:
    h = r[1] - r[0]
    print(f"  y={r[0]+y0:5d}-{r[1]+y0:5d}  h={h}")
