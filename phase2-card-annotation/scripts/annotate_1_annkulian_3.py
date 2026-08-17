"""安睡裤搜索结果第 3 页标注脚本。

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
INPUT = os.path.join(ROOT, "screenshots", "1", "安睡裤_全部_3.png")
OUTPUT = os.path.join(ROOT, "out", "1", "安睡裤_全部_3_annotated.png")

tasks = [
    # ===== 宏观组件 =====
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 179, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 299, "w": 1224, "h": 180, "kind": "macro"},
    {"label": "图筛", "x": 0, "y": 479, "w": 1224, "h": 348, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 827, "w": 1224, "h": 215, "kind": "macro"},

    # ===== 商卡 1 =====
    {"label": "商卡1_border", "x": 18, "y": 1042, "w": 1188, "h": 353, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 1042, "w": 328, "h": 332, "kind": "part"},
    {"label": "商卡1_标签区", "x": 360, "y": 1048, "w": 832, "h": 45, "kind": "part"},
    {"label": "商卡1_标题区", "x": 360, "y": 1117, "w": 832, "h": 40, "kind": "part"},
    {"label": "商卡1_价格区", "x": 360, "y": 1277, "w": 832, "h": 48, "kind": "part"},
    {"label": "商卡1_商家区", "x": 360, "y": 1360, "w": 832, "h": 35, "kind": "part"},

    # ===== 商卡 2 =====
    {"label": "商卡2_border", "x": 18, "y": 1544, "w": 1188, "h": 348, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 1544, "w": 328, "h": 332, "kind": "part"},
    {"label": "商卡2_标签区", "x": 360, "y": 1550, "w": 832, "h": 45, "kind": "part"},
    {"label": "商卡2_标题区", "x": 360, "y": 1620, "w": 832, "h": 35, "kind": "part"},
    {"label": "商卡2_价格区", "x": 360, "y": 1783, "w": 832, "h": 47, "kind": "part"},
    {"label": "商卡2_商家区", "x": 360, "y": 1857, "w": 832, "h": 35, "kind": "part"},

    # ===== 商卡 3 =====
    {"label": "商卡3_border", "x": 18, "y": 2107, "w": 1188, "h": 353, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 2107, "w": 328, "h": 332, "kind": "part"},
    {"label": "商卡3_标签区", "x": 360, "y": 2113, "w": 832, "h": 45, "kind": "part"},
    {"label": "商卡3_标题区", "x": 360, "y": 2185, "w": 832, "h": 35, "kind": "part"},
    {"label": "商卡3_价格区", "x": 360, "y": 2343, "w": 832, "h": 49, "kind": "part"},
    {"label": "商卡3_商家区", "x": 360, "y": 2425, "w": 832, "h": 35, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"DONE: {OUTPUT}; tasks={len(tasks)}")
