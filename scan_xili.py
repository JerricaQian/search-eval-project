import numpy as np
from PIL import Image

img = np.array(Image.open('screenshots/喜力啤酒整箱_全部_1.png').convert('RGB'))
h, w = img.shape[:2]
print(f'Image size: {w}x{h}')

# Detect non-white rows
row_nonwhite = []
for y in range(h):
    row = img[y]
    non_white = np.sum(~((row[:,0]>240)&(row[:,1]>240)&(row[:,2]>240)))
    if non_white > w * 0.02:
        row_nonwhite.append(y)

# Find card boundaries (gaps)
gaps = []
if row_nonwhite:
    prev = row_nonwhite[0]
    start = prev
    for i in range(1, len(row_nonwhite)):
        if row_nonwhite[i] - prev > 10:
            gaps.append((start, prev))
            start = row_nonwhite[i]
        prev = row_nonwhite[i]
    gaps.append((start, prev))

print('Content bands:')
for g in gaps:
    print(f'  y={g[0]}-{g[1]} (height={g[1]-g[0]})')

# Scan x-axis for each band to find left/right boundaries
for i, (ys, ye) in enumerate(gaps):
    band = img[ys:ye+1]
    col_nonwhite = []
    for x in range(w):
        col = band[:, x]
        non_white = np.sum(~((col[:,0]>240)&(col[:,1]>240)&(col[:,2]>240)))
        if non_white > (ye-ys+1) * 0.01:
            col_nonwhite.append(x)
    if col_nonwhite:
        print(f'  Band {i}: x={col_nonwhite[0]}-{col_nonwhite[-1]}')

# Red pixel scan (price areas)
red_mask = (img[:,:,0]>180) & (img[:,:,1]<100) & (img[:,:,2]<100)
for i, (ys, ye) in enumerate(gaps):
    band_red = red_mask[ys:ye+1]
    red_rows = [y + ys for y in range(band_red.shape[0]) if np.sum(band_red[y]) > 5]
    if red_rows:
        print(f'  Band {i} red rows: y={red_rows[0]}-{red_rows[-1]}')
    else:
        print(f'  Band {i} red rows: none')

# Green pixel scan (tag/fulfillment areas)
green_mask = (img[:,:,1]>120) & (img[:,:,0]<150) & (img[:,:,2]<150)
for i, (ys, ye) in enumerate(gaps):
    band_green = green_mask[ys:ye+1]
    green_rows = [y + ys for y in range(band_green.shape[0]) if np.sum(band_green[y]) > 5]
    if green_rows:
        print(f'  Band {i} green rows: y={green_rows[0]}-{green_rows[-1]}')
    else:
        print(f'  Band {i} green rows: none')

# Yellow/orange pixel scan (title/badge areas)
yellow_mask = (img[:,:,0]>200) & (img[:,:,1]>140) & (img[:,:,2]<100)
for i, (ys, ye) in enumerate(gaps):
    band_yellow = yellow_mask[ys:ye+1]
    yellow_rows = [y + ys for y in range(band_yellow.shape[0]) if np.sum(band_yellow[y]) > 5]
    if yellow_rows:
        print(f'  Band {i} yellow rows: y={yellow_rows[0]}-{yellow_rows[-1]}')
    else:
        print(f'  Band {i} yellow rows: none')
