import numpy as np
from PIL import Image

img = np.array(Image.open('screenshots/喜力啤酒整箱_全部_1.png').convert('RGB'))
h, w = img.shape[:2]

cards = [
    (710, 1056, 'Card1'),
    (1273, 1619, 'Card2'),
    (1836, 2187, 'Card3'),
    (2335, 2683, 'Card4'),
]

# Color masks
red_mask = (img[:,:,0]>180) & (img[:,:,1]<100) & (img[:,:,2]<100)
green_mask = (img[:,:,1]>120) & (img[:,:,0]<150) & (img[:,:,2]<150)
yellow_mask = (img[:,:,0]>200) & (img[:,:,1]>140) & (img[:,:,2]<100)

for ys, ye, name in cards:
    print(f'\n=== {name}: y={ys}-{ye} (h={ye-ys}) ===')
    band = img[ys:ye+1]
    
    # X-axis content distribution
    col_has_content = []
    for x in range(w):
        col = band[:, x]
        non_white = np.sum(~((col[:,0]>240)&(col[:,1]>240)&(col[:,2]>240)))
        if non_white > (ye-ys+1) * 0.01:
            col_has_content.append(x)
    
    if col_has_content:
        print(f'  Content x: {col_has_content[0]}-{col_has_content[-1]}')
        
        # Find gap between left image and right text
        # Look for a vertical white gap around x=360-400
        for x in range(340, 420):
            col = band[:, x]
            non_white = np.sum(~((col[:,0]>240)&(col[:,1]>240)&(col[:,2]>240)))
            if non_white < (ye-ys+1) * 0.02:
                print(f'  Gap at x={x} (non_white={non_white})')
    
    # Red pixels (price)
    band_red = red_mask[ys:ye+1]
    red_rows = []
    for y in range(band_red.shape[0]):
        cnt = np.sum(band_red[y])
        if cnt > 3:
            red_rows.append((y + ys, cnt, np.where(band_red[y])[0].min(), np.where(band_red[y])[0].max()))
    if red_rows:
        print(f'  Red (price): y={red_rows[0][0]}-{red_rows[-1][0]}, x={red_rows[0][2]}-{red_rows[0][3]}')
    
    # Green pixels (tags/fulfillment)
    band_green = green_mask[ys:ye+1]
    green_rows = []
    for y in range(band_green.shape[0]):
        cnt = np.sum(band_green[y])
        if cnt > 3:
            green_rows.append((y + ys, cnt, np.where(band_green[y])[0].min(), np.where(band_green[y])[0].max()))
    if green_rows:
        print(f'  Green (tags): y={green_rows[0][0]}-{green_rows[-1][0]}')
    
    # Yellow pixels (title/badge)
    band_yellow = yellow_mask[ys:ye+1]
    yellow_rows = []
    for y in range(band_yellow.shape[0]):
        cnt = np.sum(band_yellow[y])
        if cnt > 3:
            yellow_rows.append((y + ys, cnt, np.where(band_yellow[y])[0].min(), np.where(band_yellow[y])[0].max()))
    if yellow_rows:
        print(f'  Yellow (title): y={yellow_rows[0][0]}-{yellow_rows[-1][0]}')
    
    # Scan Y-axis for row breaks within card
    row_densities = []
    for y in range(band.shape[0]):
        row = band[y]
        non_white = np.sum(~((row[:,0]>240)&(row[:,1]>240)&(row[:,2]>240)))
        row_densities.append(non_white)
    
    # Find sparse rows (potential separators within card)
    sparse_rows = [y + ys for y, d in enumerate(row_densities) if d < w * 0.005]
    if sparse_rows:
        # Group consecutive sparse rows
        groups = []
        start = sparse_rows[0]
        prev = sparse_rows[0]
        for s in sparse_rows[1:]:
            if s - prev > 3:
                groups.append((start, prev))
                start = s
            prev = s
        groups.append((start, prev))
        print(f'  Sparse rows (separators): {groups}')
