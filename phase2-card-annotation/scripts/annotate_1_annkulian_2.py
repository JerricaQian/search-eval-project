"""安睡裤搜索结果第 2 页标注脚本。

读图判定：
- 宏观组件：状态栏、顶部导航搜索框、Tab、图筛、快筛排序筛选器
- 商卡类型：商品卡片（左图右文），共 3 张
- 商卡内部分区：头图区、标签区（黄色高亮）、标题区、价格区（红色）、商家区
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "1", "安睡裤_全部_2.png")
OUTPUT = os.path.join(ROOT, "out", "1", "安睡裤_全部_2_annotated.png")

tasks = [
    # ===== 宏观组件 =====
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 179, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 299, "w": 1224, "h": 92, "kind": "macro"},
    {"label": "图筛", "x": 0, "y": 391, "w": 1224, "h": 275, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 666, "w": 1224, "h": 216, "kind": "macro"},

    # ===== 商卡 1 =====
    {"label": "商卡1_border", "x": 18, "y": 882, "w": 1188, "h": 353, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 882, "w": 328, "h": 324, "kind": "part"},
    {"label": "商卡1_标签区", "x": 360, "y": 888, "w": 832, "h": 45, "kind": "part"},
    {"label": "商卡1_标题区", "x": 360, "y": 1032, "w": 832, "h": 27, "kind": "part"},
    {"label": "商卡1_价格区", "x": 360, "y": 1117, "w": 832, "h": 47, "kind": "part"},
    {"label": "商卡1_商家区", "x": 360, "y": 1200, "w": 832, "h": 35, "kind": "part"},

    # ===== 商卡 2 =====
    {"label": "商卡2_border", "x": 18, "y": 1384, "w": 1188, "h": 353, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 1384, "w": 328, "h": 332, "kind": "part"},
    {"label": "商卡2_标签区", "x": 360, "y": 1390, "w": 832, "h": 45, "kind": "part"},
    {"label": "商卡2_标题区", "x": 360, "y": 1482, "w": 832, "h": 27, "kind": "part"},
    {"label": "商卡2_价格区", "x": 360, "y": 1562, "w": 832, "h": 46, "kind": "part"},
    {"label": "商卡2_商家区", "x": 360, "y": 1702, "w": 832, "h": 35, "kind": "part"},

    # ===== 商卡 3 =====
    {"label": "商卡3_border", "x": 18, "y": 1886, "w": 1188, "h": 353, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1886, "w": 328, "h": 332, "kind": "part"},
    {"label": "商卡3_标签区", "x": 360, "y": 1892, "w": 832, "h": 45, "kind": "part"},
    {"label": "商卡3_标题区", "x": 360, "y": 1961, "w": 832, "h": 40, "kind": "part"},
    {"label": "商卡3_价格区", "x": 360, "y": 2070, "w": 832, "h": 40, "kind": "part"},
    {"label": "商卡3_商家区", "x": 360, "y": 2204, "w": 832, "h": 35, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"DONE: {OUTPUT}; tasks={len(tasks)}")
