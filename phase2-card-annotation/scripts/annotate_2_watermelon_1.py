import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(__file__))
INPUT = "/Users/qianjing/Desktop/search-eval-project/screenshots/西瓜_全部_1.png"
OUTPUT = "/Users/qianjing/Desktop/search-eval-project/screenshots-out/西瓜_全部_1_annotated.png"

# 逐图读图、整图一次 scan_rows 与各卡右侧文本列一次 scan_rows 后的语义任务表。
tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 95, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 299, "w": 1224, "h": 56, "kind": "macro"},
    # 图筛含商品图片行和分类文字行，作为同一个完整模块。
    {"label": "图筛", "x": 0, "y": 439, "w": 1224, "h": 199, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 750, "w": 1224, "h": 48, "kind": "macro"},
    {"label": "营销横幅", "x": 0, "y": 855, "w": 1224, "h": 117, "kind": "macro"},

    {"label": "商卡1_border", "x": 16, "y": 1037, "w": 1192, "h": 478, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 1037, "w": 332, "h": 332, "kind": "part"},
    {"label": "商卡1_标题区", "x": 396, "y": 1037, "w": 794, "h": 183, "kind": "part"},
    {"label": "商卡1_价格区", "x": 396, "y": 1275, "w": 794, "h": 49, "kind": "part"},
    {"label": "商卡1_标签区", "x": 396, "y": 1348, "w": 794, "h": 37, "kind": "part"},
    {"label": "商卡1_商家信息区", "x": 396, "y": 1414, "w": 794, "h": 101, "kind": "part"},

    {"label": "商卡2_border", "x": 16, "y": 1600, "w": 1192, "h": 407, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 1600, "w": 332, "h": 332, "kind": "part"},
    {"label": "商卡2_标题区", "x": 396, "y": 1600, "w": 794, "h": 110, "kind": "part"},
    {"label": "商卡2_价格区", "x": 396, "y": 1767, "w": 794, "h": 48, "kind": "part"},
    {"label": "商卡2_标签区", "x": 396, "y": 1835, "w": 794, "h": 50, "kind": "part"},
    {"label": "商卡2_商家信息区", "x": 396, "y": 1906, "w": 794, "h": 101, "kind": "part"},

    {"label": "商卡3_border", "x": 16, "y": 2092, "w": 1192, "h": 478, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 2092, "w": 332, "h": 332, "kind": "part"},
    {"label": "商卡3_标题区", "x": 396, "y": 2092, "w": 794, "h": 183, "kind": "part"},
    {"label": "商卡3_价格区", "x": 396, "y": 2315, "w": 794, "h": 71, "kind": "part"},
    {"label": "商卡3_标签区", "x": 396, "y": 2398, "w": 794, "h": 42, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 396, "y": 2469, "w": 794, "h": 101, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"{OUTPUT}\n任务数: {len(tasks)}")
