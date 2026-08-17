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

# For each card, scan the right text area (x=396-1188) row by row
for ys, ye, name in cards:
    print(f'\n=== {name}: y={ys}-{ye} ===')
    # Right text area
    right_area = img[ys:ye+1, 396:1189]
    rh = right_area.shape[0]
    
    # Row density for right area
    row_dens = []
    for y in range(rh):
        row = right_area[y]
        non_white = np.sum(~((row[:,0]>240)&(row[:,1]>240)&(row[:,2]>240)))
        row_dens.append(non_white)
    
    # Find content rows and group them
    content_rows = [y for y, d in enumerate(row_dens) if d > 3]
    if not content_rows:
        print('  Right area: no content')
        continue
    
    # Group consecutive rows
    groups = []
    start = content_rows[0]
    prev = content_rows[0]
    for r in content_rows[1:]:
        if r - prev > 5:
            groups.append((start, prev))
            start = r
        prev = r
    groups.append((start, prev))
    
    print(f'  Right area text groups ({len(groups)}):')
    for g in groups:
        abs_ys = g[0] + ys
        abs_ye = g[1] + ys
        # Check colors in this group
        grp = img[abs_ys:abs_ye+1, 396:1189]
        red_cnt = np.sum((grp[:,:,0]>180) & (grp[:,:,1]<100) & (grp[:,:,2]<100))
        green_cnt = np.sum((grp[:,:,1]>120) & (grp[:,:,0]<150) & (grp[:,:,2]<150))
        yellow_cnt = np.sum((grp[:,:,0]>200) & (grp[:,:,1]>140) & (grp[:,:,2]<100))
        gray_cnt = np.sum((grp[:,:,0]>60) & (grp[:,:,0]<180) & (abs(grp[:,:,0].astype(int)-grp[:,:,1].astype(int))<20) & (abs(grp[:,:,1].astype(int)-grp[:,:,2].astype(int))<20))
        color_info = []
        if red_cnt > 10: color_info.append(f'red={red_cnt}')
        if green_cnt > 10: color_info.append(f'green={green_cnt}')
        if yellow_cnt > 10: color_info.append(f'yellow={yellow_cnt}')
        if gray_cnt > 10: color_info.append(f'gray={gray_cnt}')
        print(f'    y={abs_ys}-{abs_ye} (h={abs_ye-abs_ys}) colors: {", ".join(color_info) if color_info else "mixed"}')
    
    # Left image area
    left_area = img[ys:ye+1, 32:363]
    lh = left_area.shape[0]
    left_nonwhite = np.sum(~((left_area[:,:,0]>240)&(left_area[:,:,1]>240)&(left_area[:,:,2]>240)))
    print(f'  Left image area: nonwhite={left_nonwhite} ({left_nonwhite/(lh*331)*100:.1f}%)')
    
    # Check for round corners / white borders in left image area
    # Check bottom of left area for possible missing image (large white region)
    bottom_white = 0
    for y in range(lh-1, max(0, lh-30), -1):
        row = left_area[y]
        white = np.sum((row[:,0]>240)&(row[:,1]>240)&(row[:,2]>240))
        if white > 331 * 0.9:
            bottom_white += 1
        else:
            break
    if bottom_white > 5:
        print(f'    Bottom white: {bottom_white}px (possible blank image bottom)')
