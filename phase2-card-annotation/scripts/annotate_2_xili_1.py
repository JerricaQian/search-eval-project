"""喜力啤酒整箱_全部_1 本地标注；本图 scan_rows 已独立执行一次。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from annotate_image import annotate_image

ROOT = Path('/Users/qianjing/Desktop/search-eval-project')
IN = ROOT / 'screenshots/喜力啤酒整箱_全部_1.png'
OUT = ROOT / 'screenshots-out/喜力啤酒整箱_全部_1_annotated.png'
OUT.parent.mkdir(parents=True, exist_ok=True)

def product(card, top, bottom, image_h, truncated=False):
    tasks = [
        {'label': f'商卡{card}{"被截断" if truncated else ""}_border', 'x': 18, 'y': top, 'w': 1188, 'h': bottom-top, 'kind': 'border'},
        {'label': f'商卡{card}_头图区', 'x': 32, 'y': top+15, 'w': 330, 'h': min(image_h, bottom-top-15), 'kind': 'part'},
        {'label': f'商卡{card}_标题区', 'x': 385, 'y': top+4, 'w': 800, 'h': 109, 'kind': 'part'},
        {'label': f'商卡{card}_基础信息区', 'x': 385, 'y': top+147, 'w': 800, 'h': 36, 'kind': 'part'},
        {'label': f'商卡{card}_价格区', 'x': 385, 'y': top+239, 'w': 450, 'h': 48, 'kind': 'part'},
        {'label': f'商卡{card}_标签区', 'x': 385, 'y': top+312, 'w': 800, 'h': 36, 'kind': 'part'},
    ]
    merchant_y = top + 377
    if bottom > merchant_y:
        tasks.append({'label': f'商卡{card}_商家区', 'x': 385, 'y': merchant_y, 'w': 800, 'h': bottom-merchant_y, 'kind': 'part'})
    return tasks

# Tab 下未出现图片+文字的图筛；快筛下的“恭喜获得满60减9闪购优惠券”是独立营销横幅。
tasks = [
    {'label': '状态栏', 'x': 0, 'y': 0, 'w': 1224, 'h': 112, 'kind': 'macro'},
    {'label': '顶部导航搜索框', 'x': 0, 'y': 112, 'w': 1224, 'h': 108, 'kind': 'macro'},
    {'label': 'Tab', 'x': 0, 'y': 299, 'w': 1224, 'h': 56, 'kind': 'macro'},
    {'label': '快筛排序筛选器', 'x': 0, 'y': 423, 'w': 1224, 'h': 48, 'kind': 'macro'},
    {'label': '营销横幅', 'x': 18, 'y': 528, 'w': 1188, 'h': 117, 'kind': 'macro'},
]
tasks += product(1, 710, 1188, 350)
tasks += product(2, 1273, 1750, 350)
tasks += product(3, 1836, 2253, 320)
tasks += product(4, 2335, 2684, 320, truncated=True)
annotate_image(str(IN), str(OUT), tasks)
print(f'DONE regions={len(tasks)} output={OUT}')
