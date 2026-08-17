import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "2", "万达广场_全部_3.png")
OUTPUT = os.path.join(ROOT, "out", "2", "万达广场_全部_3_annotated.png")

# 语义以原图文字和图片边缘判定；整图 scan_rows 只执行一次并仅辅助纵向边界。
tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 121, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 241, "w": 1224, "h": 58, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 299, "w": 1224, "h": 48, "kind": "macro"},
    # 首行内容是商品小卡横滑区，归入上方首张商家卡的图文下挂，不独立计为商卡。
    {"label": "商卡1被截断_border", "x": 18, "y": 371, "w": 1188, "h": 317, "kind": "border"},
    {"label": "商卡1_下挂区图文下挂", "x": 18, "y": 371, "w": 1188, "h": 317, "kind": "part"},
    {"label": "商卡2_border", "x": 18, "y": 750, "w": 1188, "h": 653, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 750, "w": 278, "h": 257, "kind": "part"},
    {"label": "商卡2_标题区", "x": 330, "y": 750, "w": 861, "h": 70, "kind": "part"},
    {"label": "商卡2_商家信息区", "x": 330, "y": 820, "w": 861, "h": 100, "kind": "part"},
    {"label": "商卡2_标签区", "x": 330, "y": 920, "w": 861, "h": 87, "kind": "part"},
    {"label": "商卡2_下挂区图文下挂", "x": 18, "y": 1007, "w": 1188, "h": 396, "kind": "part"},
    {"label": "商卡3_border", "x": 18, "y": 1465, "w": 1188, "h": 480, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1465, "w": 278, "h": 258, "kind": "part"},
    {"label": "商卡3_标题区", "x": 330, "y": 1465, "w": 861, "h": 70, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 330, "y": 1535, "w": 861, "h": 100, "kind": "part"},
    {"label": "商卡3_标签区", "x": 330, "y": 1635, "w": 861, "h": 88, "kind": "part"},
    {"label": "商卡3_下挂区图文下挂", "x": 18, "y": 1723, "w": 1188, "h": 222, "kind": "part"},
    {"label": "商卡4_border", "x": 18, "y": 1965, "w": 1188, "h": 150, "kind": "border"},
    {"label": "商卡4_头图区", "x": 32, "y": 1965, "w": 278, "h": 150, "kind": "part"},
    {"label": "商卡4_标题区", "x": 330, "y": 1965, "w": 861, "h": 48, "kind": "part"},
    {"label": "商卡4_商家信息区", "x": 330, "y": 2013, "w": 861, "h": 48, "kind": "part"},
    {"label": "商卡4_文字下挂区", "x": 330, "y": 2061, "w": 861, "h": 54, "kind": "part"},
    {"label": "商卡5_border", "x": 18, "y": 2185, "w": 1188, "h": 258, "kind": "border"},
    {"label": "商卡5_头图区", "x": 32, "y": 2185, "w": 278, "h": 258, "kind": "part"},
    {"label": "商卡5_标题区", "x": 330, "y": 2185, "w": 861, "h": 65, "kind": "part"},
    {"label": "商卡5_商家信息区", "x": 330, "y": 2250, "w": 861, "h": 96, "kind": "part"},
    {"label": "商卡5_文字下挂区", "x": 330, "y": 2346, "w": 861, "h": 97, "kind": "part"},
    {"label": "商卡6被截断_border", "x": 18, "y": 2595, "w": 1188, "h": 105, "kind": "border"},
    {"label": "商卡6_头图区", "x": 32, "y": 2595, "w": 278, "h": 105, "kind": "part"},
    {"label": "商卡6_标题区", "x": 330, "y": 2595, "w": 861, "h": 48, "kind": "part"},
    {"label": "商卡6_商家信息区", "x": 330, "y": 2643, "w": 861, "h": 57, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"DONE: {OUTPUT}; tasks={len(tasks)}")
