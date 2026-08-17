import numpy as np
from PIL import Image
import json

img = np.array(Image.open('screenshots/喜力啤酒整箱_全部_1.png').convert('RGB'))
h, w = img.shape[:2]

manifest = json.loads(open('screenshots-out/elements_喜力啤酒整箱.json').read())

def ink_ratio(x, y, bw, bh):
    region = img[y:y+bh, x:x+bw]
    non_white = np.sum(~((region[:,:,0]>240)&(region[:,:,1]>240)&(region[:,:,2]>240)))
    return round(non_white / (bw * bh), 4) if bw * bh > 0 else 0

print("=== Element ink ratios ===")
for card in manifest['cards']:
    cid = card['cardId']
    for region in card['regions']:
        rn = region['name']
        for elem in region['elements']:
            x, y, bw, bh = elem['坐标']
            ir = ink_ratio(x, y, bw, bh)
            print(f"{elem['id']}: region={rn} coord=({x},{y},{bw},{bh}) inkRatio={ir}")

print("\n=== Card-level stats ===")
for card in manifest['cards']:
    cid = card['cardId']
    coord = card['coord']
    x, y, bw, bh = coord
    ir = ink_ratio(x, y, bw, bh)
    
    # Left image vs right text
    left_ir = ink_ratio(32, y+6, 331, 331)
    right_ir = ink_ratio(396, y+4, 793, bh-8)
    
    print(f"{cid}: card_ir={ir} left_img_ir={left_ir} right_text_ir={right_ir}")

print("\n=== Page-level stats ===")
# Top modules
modules = manifest['pageFacts']['modules']
for m in modules:
    x, y, bw, bh = m['coord']
    ir = ink_ratio(x, y, bw, bh)
    print(f"{m['id']} ({m['moduleType']}): coord=({x},{y},{bw},{bh}) inkRatio={ir}")

# Color distribution per card
print("\n=== Color distribution per card ===")
red_mask = (img[:,:,0]>180) & (img[:,:,1]<100) & (img[:,:,2]<100)
green_mask = (img[:,:,1]>120) & (img[:,:,0]<150) & (img[:,:,2]<150)
yellow_mask = (img[:,:,0]>200) & (img[:,:,1]>140) & (img[:,:,2]<100)

for card in manifest['cards']:
    cid = card['cardId']
    x, y, bw, bh = card['coord']
    card_img = img[y:y+bh, x:x+bw]
    r = np.sum(red_mask[y:y+bh, x:x+bw])
    g = np.sum(green_mask[y:y+bh, x:x+bw])
    y_ = np.sum(yellow_mask[y:y+bh, x:x+bw])
    print(f"{cid}: red={r} green={g} yellow={y_}")

# Check inter-card alignment
print("\n=== Alignment check ===")
for region_name in ['标题区', '价格区', '标签区']:
    coords = []
    for card in manifest['cards']:
        for r in card['regions']:
            if r['name'] == region_name:
                coords.append(r['coord'])
    print(f"{region_name}: x_positions={[c[0] for c in coords]}, y_offsets={[c[1]-manifest['cards'][0]['coord'][1] for c in coords]}")
