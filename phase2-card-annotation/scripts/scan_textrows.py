"""Detect text rows within a given x range by finding rows with dark ink.
Usage: python scan_textrows.py <img> <x0> <x1> <y0> <y1>
Reports bands of 'ink' rows (text lines) and gaps.
"""
import sys, numpy as np
from PIL import Image

img = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(np.int16)
x0, x1, y0, y1 = map(int, sys.argv[2:6])
sub = img[y0:y1, x0:x1, :]
# ink = dark-ish OR colorful pixel (not near white bg)
mean = sub.mean(axis=2)
mx = sub.max(axis=2); mn = sub.min(axis=2)
colorful = (mx - mn) > 40
dark = mean < 200
ink = dark | colorful
ink_per_row = ink.sum(axis=1)
thresh = max(3, (x1-x0)//80)
is_text = ink_per_row > thresh
H = sub.shape[0]; bands=[]; i=0
while i<H:
    if is_text[i]:
        j=i
        while j<H and is_text[j]: j+=1
        bands.append((y0+i, y0+j))
        i=j
    else: i+=1
print(f"Text rows in x[{x0}:{x1}] y[{y0}:{y1}] (merged >=4px shown):")
for b in bands:
    if b[1]-b[0] >= 4:
        print(f"  {b[0]:5d} - {b[1]:5d}  h={b[1]-b[0]}")
