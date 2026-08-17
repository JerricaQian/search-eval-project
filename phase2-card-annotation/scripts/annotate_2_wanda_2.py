import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "2", "万达广场_全部_2.png")
OUTPUT = os.path.join(ROOT, "out", "2", "万达广场_全部_2_annotated.png")

# 语义以原图为准；本图只做过一次整图 scan_rows，用于辅助卡片之间的纵向切分。
tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 121, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 241, "w": 1224, "h": 58, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 299, "w": 1224, "h": 48, "kind": "macro"},
    # 无促销文案的空白/细条不作为营销横幅标注。
    {"label": "商卡1_border", "x": 18, "y": 464, "w": 1188, "h": 653, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 464, "w": 278, "h": 257, "kind": "part"},
    {"label": "商卡1_标题区", "x": 330, "y": 464, "w": 861, "h": 70, "kind": "part"},
    {"label": "商卡1_商家信息区", "x": 330, "y": 534, "w": 861, "h": 104, "kind": "part"},
    {"label": "商卡1_标签区", "x": 330, "y": 638, "w": 861, "h": 83, "kind": "part"},
    {"label": "商卡1_下挂区图文下挂", "x": 18, "y": 722, "w": 1188, "h": 395, "kind": "part"},
    {"label": "商卡2_border", "x": 18, "y": 1179, "w": 1188, "h": 653, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 1179, "w": 278, "h": 257, "kind": "part"},
    {"label": "商卡2_标题区", "x": 330, "y": 1179, "w": 861, "h": 70, "kind": "part"},
    {"label": "商卡2_商家信息区", "x": 330, "y": 1249, "w": 861, "h": 102, "kind": "part"},
    {"label": "商卡2_标签区", "x": 330, "y": 1351, "w": 861, "h": 85, "kind": "part"},
    {"label": "商卡2_下挂区图文下挂", "x": 18, "y": 1436, "w": 1188, "h": 396, "kind": "part"},
    {"label": "商卡3_border", "x": 18, "y": 1894, "w": 1188, "h": 258, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1894, "w": 278, "h": 258, "kind": "part"},
    {"label": "商卡3_标题区", "x": 330, "y": 1894, "w": 861, "h": 66, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 330, "y": 1960, "w": 861, "h": 92, "kind": "part"},
    {"label": "商卡3_文字下挂区", "x": 330, "y": 2052, "w": 861, "h": 100, "kind": "part"},
    {"label": "商卡4被截断_border", "x": 18, "y": 2304, "w": 1188, "h": 396, "kind": "border"},
    {"label": "商卡4_头图区", "x": 32, "y": 2304, "w": 278, "h": 257, "kind": "part"},
    {"label": "商卡4_标题区", "x": 330, "y": 2304, "w": 861, "h": 70, "kind": "part"},
    {"label": "商卡4_商家信息区", "x": 330, "y": 2374, "w": 861, "h": 98, "kind": "part"},
    {"label": "商卡4_标签区", "x": 330, "y": 2472, "w": 861, "h": 89, "kind": "part"},
    {"label": "商卡4_下挂区图文下挂", "x": 18, "y": 2561, "w": 1188, "h": 139, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"DONE: {OUTPUT}; tasks={len(tasks)}")
