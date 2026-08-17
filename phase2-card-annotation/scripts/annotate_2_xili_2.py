"""喜力啤酒整箱_全部_2 本地标注；本图 scan_rows 已独立执行一次。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from annotate_image import annotate_image

ROOT = Path('/Users/qianjing/Desktop/search-eval-project')
IN = ROOT / 'screenshots/喜力啤酒整箱_全部_2.png'
OUT = ROOT / 'screenshots-out/喜力啤酒整箱_全部_2_annotated.png'
OUT.parent.mkdir(parents=True, exist_ok=True)

def product(card, top, bottom, image_h=350, truncated=False):
    tasks = [
        {'label': f'商卡{card}{"被截断" if truncated else ""}_border', 'x': 18, 'y': top, 'w': 1188, 'h': bottom-top, 'kind': 'border'},
        {'label': f'商卡{card}_头图区', 'x': 32, 'y': top+15, 'w': 330, 'h': min(image_h, bottom-top-15), 'kind': 'part'},
        {'label': f'商卡{card}_标题区', 'x': 385, 'y': top+38, 'w': 800, 'h': 41, 'kind': 'part'},
        {'label': f'商卡{card}_副标题区', 'x': 385, 'y': top+120, 'w': 800, 'h': 91, 'kind': 'part'},
        {'label': f'商卡{card}_价格区', 'x': 385, 'y': top+299, 'w': 450, 'h': 48, 'kind': 'part'},
        {'label': f'商卡{card}_标签区', 'x': 385, 'y': top+391, 'w': 800, 'h': 16, 'kind': 'part'},
    ]
    merchant_y = top + 435
    if bottom > merchant_y:
        tasks.append({'label': f'商卡{card}_商家区', 'x': 385, 'y': merchant_y, 'w': 800, 'h': bottom-merchant_y, 'kind': 'part'})
    return tasks

# 续页顶部仍有状态栏/搜索/Tab/快筛，未见图筛或独立营销横幅；商品卡以红色价、底部商家文字判定。
tasks = [
    {'label': '状态栏', 'x': 0, 'y': 0, 'w': 1224, 'h': 112, 'kind': 'macro'},
    {'label': '顶部导航搜索框', 'x': 0, 'y': 112, 'w': 1224, 'h': 108, 'kind': 'macro'},
    {'label': 'Tab', 'x': 0, 'y': 299, 'w': 1224, 'h': 48, 'kind': 'macro'},
    {'label': '快筛排序筛选器', 'x': 0, 'y': 391, 'w': 1224, 'h': 80, 'kind': 'macro'},
]
tasks += product(5, 0, 471)
tasks += product(6, 560, 1010)
tasks += product(7, 1058, 1504, image_h=320)
tasks += product(8, 1551, 1985, image_h=320)
# 2001-2067 是卡间留白，后续已转入相关搜索模块，不虚构被截断商品卡。
tasks += [
    {'label': '大家还在搜', 'x': 18, 'y': 2067, 'w': 1188, 'h': 146, 'kind': 'macro'},
    {'label': '相关搜索推荐', 'x': 18, 'y': 2213, 'w': 1188, 'h': 487, 'kind': 'macro'},
]
annotate_image(str(IN), str(OUT), tasks)
print(f'DONE regions={len(tasks)} output={OUT}')
