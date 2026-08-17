"""喜力啤酒整箱_全部_3 本地标注；本图 scan_rows 已独立执行一次。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from annotate_image import annotate_image

ROOT = Path('/Users/qianjing/Desktop/search-eval-project')
IN = ROOT / 'screenshots/喜力啤酒整箱_全部_3.png'
OUT = ROOT / 'screenshots-out/喜力啤酒整箱_全部_3_annotated.png'
OUT.parent.mkdir(parents=True, exist_ok=True)

def product(card, top, bottom, image_h=353, truncated=False):
    merchant_y = top + 396
    tasks = [
        {'label': f'商卡{card}{"被截断" if truncated else ""}_border', 'x': 18, 'y': top, 'w': 1188, 'h': bottom-top, 'kind': 'border'},
        {'label': f'商卡{card}_头图区', 'x': 32, 'y': top, 'w': 330, 'h': min(image_h, bottom-top-15), 'kind': 'part'},
        {'label': f'商卡{card}_标题区', 'x': 385, 'y': top+4, 'w': 800, 'h': 54, 'kind': 'part'},
        {'label': f'商卡{card}_副标题区', 'x': 385, 'y': top+67, 'w': 800, 'h': 54, 'kind': 'part'},
        {'label': f'商卡{card}_价格区', 'x': 385, 'y': top+260, 'w': 450, 'h': 48, 'kind': 'part'},
        {'label': f'商卡{card}_标签区', 'x': 385, 'y': top+352, 'w': 800, 'h': 36, 'kind': 'part'},
    ]
    if bottom > merchant_y:
        tasks.append({'label': f'商卡{card}_商家区', 'x': 385, 'y': merchant_y, 'w': 800, 'h': bottom-merchant_y, 'kind': 'part'})
    return tasks

# 本图快筛为纯文字/图标行；未读到带图片的分类图筛，也没有独立营销横幅。
tasks = [
    {'label': '状态栏', 'x': 0, 'y': 0, 'w': 1224, 'h': 112, 'kind': 'macro'},
    {'label': '顶部导航搜索框', 'x': 0, 'y': 112, 'w': 1224, 'h': 108, 'kind': 'macro'},
    {'label': 'Tab', 'x': 0, 'y': 299, 'w': 1224, 'h': 48, 'kind': 'macro'},
    {'label': '快筛排序筛选器', 'x': 0, 'y': 418, 'w': 1224, 'h': 36, 'kind': 'macro'},
]
tasks += product(1, 539, 1021)
tasks += product(2, 1041, 1502)
tasks += product(3, 1543, 1999)
tasks += product(4, 2045, 2542)
# 页面底部可见卡按截图边界处理；不虚构图片外的商品区。
tasks += product(5, 2547, 2700, truncated=True)
annotate_image(str(IN), str(OUT), tasks)
print(f'DONE regions={len(tasks)} output={OUT}')
