import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "2", "游乐场_全部_1.png")
OUTPUT = os.path.join(ROOT, "out", "2", "游乐场_全部_1_annotated.png")

# 仅一次整图 scan_rows；本屏原图有完整选中态文字 Tab 与图片+文字图筛。
tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 121, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 299, "w": 1224, "h": 56, "kind": "macro"},
    {"label": "图筛", "x": 0, "y": 397, "w": 1224, "h": 166, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 634, "w": 1224, "h": 48, "kind": "macro"},
    {"label": "商卡1_border", "x": 18, "y": 762, "w": 1188, "h": 328, "kind": "border"},
    {"label": "商卡1_头图区", "x": 28, "y": 762, "w": 256, "h": 258, "kind": "part"},
    {"label": "商卡1_标题区", "x": 300, "y": 762, "w": 891, "h": 70, "kind": "part"},
    {"label": "商卡1_商家信息区", "x": 300, "y": 832, "w": 891, "h": 58, "kind": "part"},
    {"label": "商卡1_标签区", "x": 300, "y": 890, "w": 891, "h": 63, "kind": "part"},
    {"label": "商卡1_文字下挂区", "x": 300, "y": 953, "w": 891, "h": 137, "kind": "part"},
    {"label": "商卡2_border", "x": 18, "y": 1172, "w": 1188, "h": 329, "kind": "border"},
    {"label": "商卡2_头图区", "x": 28, "y": 1172, "w": 256, "h": 258, "kind": "part"},
    {"label": "商卡2_标题区", "x": 300, "y": 1172, "w": 891, "h": 69, "kind": "part"},
    {"label": "商卡2_商家信息区", "x": 300, "y": 1241, "w": 891, "h": 65, "kind": "part"},
    {"label": "商卡2_标签区", "x": 300, "y": 1306, "w": 891, "h": 69, "kind": "part"},
    {"label": "商卡2_文字下挂区", "x": 300, "y": 1375, "w": 891, "h": 126, "kind": "part"},
    {"label": "商卡3_border", "x": 18, "y": 1582, "w": 1188, "h": 329, "kind": "border"},
    {"label": "商卡3_头图区", "x": 28, "y": 1582, "w": 256, "h": 258, "kind": "part"},
    {"label": "商卡3_标题区", "x": 300, "y": 1582, "w": 891, "h": 69, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 300, "y": 1651, "w": 891, "h": 64, "kind": "part"},
    {"label": "商卡3_标签区", "x": 300, "y": 1715, "w": 891, "h": 69, "kind": "part"},
    {"label": "商卡3_文字下挂区", "x": 300, "y": 1784, "w": 891, "h": 127, "kind": "part"},
    {"label": "商卡4_border", "x": 18, "y": 1992, "w": 1188, "h": 329, "kind": "border"},
    {"label": "商卡4_头图区", "x": 28, "y": 1992, "w": 256, "h": 258, "kind": "part"},
    {"label": "商卡4_标题区", "x": 300, "y": 1992, "w": 891, "h": 69, "kind": "part"},
    {"label": "商卡4_商家信息区", "x": 300, "y": 2061, "w": 891, "h": 67, "kind": "part"},
    {"label": "商卡4_标签区", "x": 300, "y": 2128, "w": 891, "h": 69, "kind": "part"},
    {"label": "商卡4_文字下挂区", "x": 300, "y": 2197, "w": 891, "h": 124, "kind": "part"},
    {"label": "商卡5被截断_border", "x": 18, "y": 2402, "w": 1188, "h": 298, "kind": "border"},
    {"label": "商卡5_头图区", "x": 28, "y": 2402, "w": 256, "h": 258, "kind": "part"},
    {"label": "商卡5_标题区", "x": 300, "y": 2402, "w": 891, "h": 70, "kind": "part"},
    {"label": "商卡5_商家信息区", "x": 300, "y": 2472, "w": 891, "h": 68, "kind": "part"},
    {"label": "商卡5_标签区", "x": 300, "y": 2540, "w": 891, "h": 69, "kind": "part"},
    {"label": "商卡5_文字下挂区", "x": 300, "y": 2609, "w": 891, "h": 91, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"DONE: {OUTPUT}; tasks={len(tasks)}")
