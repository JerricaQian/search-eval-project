import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "2", "游乐场_全部_2.png")
OUTPUT = os.path.join(ROOT, "out", "2", "游乐场_全部_2_annotated.png")

# 仅一次整图 scan_rows；本屏无完整选中态文字 Tab、无图片+文字图筛，均不标。
tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 121, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 299, "w": 1224, "h": 48, "kind": "macro"},
    {"label": "商卡1被截断_border", "x": 18, "y": 371, "w": 1188, "h": 118, "kind": "border"},
    {"label": "商卡1_文字下挂区", "x": 300, "y": 371, "w": 891, "h": 118, "kind": "part"},
    {"label": "运营聚合卡", "x": 18, "y": 568, "w": 1188, "h": 330, "kind": "hetero"},
    {"label": "相似推荐提示_大家还在搜", "x": 18, "y": 969, "w": 1188, "h": 367, "kind": "hetero"},
    {"label": "商卡2_border", "x": 18, "y": 1355, "w": 1188, "h": 348, "kind": "border"},
    {"label": "商卡2_头图区", "x": 28, "y": 1355, "w": 256, "h": 258, "kind": "part"},
    {"label": "商卡2_标题区", "x": 300, "y": 1355, "w": 891, "h": 68, "kind": "part"},
    {"label": "商卡2_商家信息区", "x": 300, "y": 1423, "w": 891, "h": 69, "kind": "part"},
    {"label": "商卡2_标签区", "x": 300, "y": 1492, "w": 891, "h": 70, "kind": "part"},
    {"label": "商卡2_文字下挂区", "x": 300, "y": 1562, "w": 891, "h": 141, "kind": "part"},
    {"label": "商卡3_border", "x": 18, "y": 1764, "w": 1188, "h": 341, "kind": "border"},
    {"label": "商卡3_头图区", "x": 28, "y": 1764, "w": 256, "h": 258, "kind": "part"},
    {"label": "商卡3_标题区", "x": 300, "y": 1764, "w": 891, "h": 62, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 300, "y": 1826, "w": 891, "h": 72, "kind": "part"},
    {"label": "商卡3_标签区", "x": 300, "y": 1898, "w": 891, "h": 71, "kind": "part"},
    {"label": "商卡3_文字下挂区", "x": 300, "y": 1969, "w": 891, "h": 136, "kind": "part"},
    {"label": "商卡4被截断_border", "x": 18, "y": 2175, "w": 1188, "h": 525, "kind": "border"},
    {"label": "商卡4_头图区", "x": 28, "y": 2175, "w": 256, "h": 258, "kind": "part"},
    {"label": "商卡4_标题区", "x": 300, "y": 2175, "w": 891, "h": 69, "kind": "part"},
    {"label": "商卡4_商家信息区", "x": 300, "y": 2244, "w": 891, "h": 65, "kind": "part"},
    {"label": "商卡4_标签区", "x": 300, "y": 2309, "w": 891, "h": 71, "kind": "part"},
    {"label": "商卡4_文字下挂区", "x": 300, "y": 2380, "w": 891, "h": 320, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"DONE: {OUTPUT}; tasks={len(tasks)}")
