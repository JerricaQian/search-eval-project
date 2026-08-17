import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(__file__))
INPUT = os.path.join(ROOT, "screenshots", "2", "西瓜_全部_2.png")
OUTPUT = os.path.join(ROOT, "out", "2", "西瓜_全部_2_annotated.png")

# 本图没有图筛或营销横幅：搜索栏后直接是纯文字快筛与商品列表。
tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 95, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 299, "w": 1224, "h": 48, "kind": "macro"},

    {"label": "商卡1_border", "x": 16, "y": 399, "w": 1192, "h": 417, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 399, "w": 332, "h": 332, "kind": "part"},
    {"label": "商卡1_标题区", "x": 396, "y": 399, "w": 794, "h": 119, "kind": "part"},
    {"label": "商卡1_价格区", "x": 396, "y": 576, "w": 794, "h": 49, "kind": "part"},
    {"label": "商卡1_标签区", "x": 396, "y": 644, "w": 794, "h": 42, "kind": "part"},
    {"label": "商卡1_商家信息区", "x": 396, "y": 715, "w": 794, "h": 101, "kind": "part"},

    {"label": "商卡2_border", "x": 16, "y": 898, "w": 1192, "h": 410, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 898, "w": 332, "h": 332, "kind": "part"},
    {"label": "商卡2_标题区", "x": 396, "y": 898, "w": 794, "h": 115, "kind": "part"},
    {"label": "商卡2_价格区", "x": 396, "y": 1068, "w": 794, "h": 48, "kind": "part"},
    {"label": "商卡2_标签区", "x": 396, "y": 1123, "w": 794, "h": 64, "kind": "part"},
    {"label": "商卡2_商家信息区", "x": 396, "y": 1207, "w": 794, "h": 101, "kind": "part"},

    {"label": "商卡3_border", "x": 16, "y": 1393, "w": 1192, "h": 417, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1393, "w": 332, "h": 332, "kind": "part"},
    {"label": "商卡3_标题区", "x": 396, "y": 1393, "w": 794, "h": 162, "kind": "part"},
    {"label": "商卡3_价格区", "x": 396, "y": 1623, "w": 794, "h": 64, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 396, "y": 1705, "w": 794, "h": 105, "kind": "part"},

    {"label": "商卡4_border", "x": 16, "y": 1895, "w": 1192, "h": 442, "kind": "border"},
    {"label": "商卡4_头图区", "x": 32, "y": 1895, "w": 332, "h": 332, "kind": "part"},
    {"label": "商卡4_标题区", "x": 396, "y": 1895, "w": 794, "h": 119, "kind": "part"},
    {"label": "商卡4_价格区", "x": 396, "y": 2133, "w": 794, "h": 49, "kind": "part"},
    {"label": "商卡4_标签区", "x": 396, "y": 2187, "w": 794, "h": 67, "kind": "part"},
    {"label": "商卡4_商家信息区", "x": 396, "y": 2268, "w": 794, "h": 69, "kind": "part"},

    {"label": "商卡5_border", "x": 16, "y": 2458, "w": 1192, "h": 242, "kind": "border"},
    {"label": "商卡5_头图区", "x": 32, "y": 2458, "w": 332, "h": 242, "kind": "part"},
    {"label": "商卡5_标题区", "x": 396, "y": 2462, "w": 794, "h": 113, "kind": "part"},
    {"label": "商卡5_价格区", "x": 396, "y": 2606, "w": 794, "h": 35, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"{OUTPUT}\n任务数: {len(tasks)}")
