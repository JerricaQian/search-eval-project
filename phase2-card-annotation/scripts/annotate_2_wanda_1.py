import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "2", "万达广场_全部_1.png")
OUTPUT = os.path.join(ROOT, "out", "2", "万达广场_全部_1_annotated.png")

# 语义由原图文字/元素判定；本图仅执行过一次整图 scan_rows 扫描，扫描结果只用于卡间边界辅助。
tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 121, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 241, "w": 1224, "h": 58, "kind": "macro"},
    {"label": "地标卡_border", "x": 18, "y": 388, "w": 1188, "h": 667, "kind": "border"},
    {"label": "地标卡_头图区", "x": 32, "y": 473, "w": 278, "h": 323, "kind": "part"},
    {"label": "地标卡_标题区", "x": 330, "y": 473, "w": 861, "h": 83, "kind": "part"},
    {"label": "地标卡_基础信息区", "x": 330, "y": 556, "w": 861, "h": 180, "kind": "part"},
    {"label": "地标卡_文字下挂区", "x": 330, "y": 796, "w": 861, "h": 259, "kind": "part"},
    # 圆形/图标分类与文字分类共同组成图筛，完整覆盖两行。
    {"label": "图筛", "x": 0, "y": 1055, "w": 1224, "h": 133, "kind": "macro"},
    # 此行仅含“全部分类、综合排序、距离、美食、休闲娱乐”等纯文字快筛。
    {"label": "快筛排序筛选器", "x": 0, "y": 1188, "w": 1224, "h": 48, "kind": "macro"},
    {"label": "商卡1_border", "x": 18, "y": 1316, "w": 1188, "h": 653, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 1316, "w": 278, "h": 257, "kind": "part"},
    {"label": "商卡1_标题区", "x": 330, "y": 1316, "w": 861, "h": 70, "kind": "part"},
    {"label": "商卡1_商家信息区", "x": 330, "y": 1386, "w": 861, "h": 95, "kind": "part"},
    {"label": "商卡1_标签区", "x": 330, "y": 1481, "w": 861, "h": 92, "kind": "part"},
    {"label": "商卡1_下挂区图文下挂", "x": 18, "y": 1578, "w": 1188, "h": 391, "kind": "part"},
    {"label": "商卡2被截断_border", "x": 18, "y": 2031, "w": 1188, "h": 669, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 2031, "w": 278, "h": 257, "kind": "part"},
    {"label": "商卡2_标题区", "x": 330, "y": 2031, "w": 861, "h": 70, "kind": "part"},
    {"label": "商卡2_商家信息区", "x": 330, "y": 2101, "w": 861, "h": 95, "kind": "part"},
    {"label": "商卡2_标签区", "x": 330, "y": 2196, "w": 861, "h": 80, "kind": "part"},
    {"label": "商卡2_下挂区图文下挂", "x": 18, "y": 2280, "w": 1188, "h": 420, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"DONE: {OUTPUT}; tasks={len(tasks)}")
