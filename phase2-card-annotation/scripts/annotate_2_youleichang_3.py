import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "2", "游乐场_全部_3.png")
OUTPUT = os.path.join(ROOT, "out", "2", "游乐场_全部_3_annotated.png")

# 仅一次整图 scan_rows；本屏无完整选中态文字 Tab、无图片+文字图筛，均不标。
tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 121, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 299, "w": 1224, "h": 48, "kind": "macro"},
    {"label": "商卡1被截断_border", "x": 18, "y": 371, "w": 1188, "h": 238, "kind": "border"},
    {"label": "商卡1_文字下挂区", "x": 300, "y": 371, "w": 891, "h": 238, "kind": "part"},
    {"label": "商卡2_border", "x": 18, "y": 688, "w": 1188, "h": 316, "kind": "border"},
    {"label": "商卡2_头图区", "x": 28, "y": 688, "w": 256, "h": 258, "kind": "part"},
    {"label": "商卡2_标题区", "x": 300, "y": 688, "w": 891, "h": 71, "kind": "part"},
    {"label": "商卡2_商家信息区", "x": 300, "y": 759, "w": 891, "h": 66, "kind": "part"},
    {"label": "商卡2_标签区", "x": 300, "y": 825, "w": 891, "h": 60, "kind": "part"},
    {"label": "商卡2_文字下挂区", "x": 300, "y": 885, "w": 891, "h": 119, "kind": "part"},
    # 页面内费力度问卷属于异构运营模块，整体标注，不能套用商卡模板。
    {"label": "运营聚合卡_费力度评分", "x": 18, "y": 1108, "w": 1188, "h": 258, "kind": "hetero"},
    {"label": "商卡3_border", "x": 18, "y": 1468, "w": 1188, "h": 333, "kind": "border"},
    {"label": "商卡3_头图区", "x": 28, "y": 1468, "w": 256, "h": 258, "kind": "part"},
    {"label": "商卡3_标题区", "x": 300, "y": 1468, "w": 891, "h": 69, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 300, "y": 1537, "w": 891, "h": 68, "kind": "part"},
    {"label": "商卡3_标签区", "x": 300, "y": 1605, "w": 891, "h": 67, "kind": "part"},
    {"label": "商卡3_文字下挂区", "x": 300, "y": 1672, "w": 891, "h": 129, "kind": "part"},
    # 热门联想关键词为相似推荐模块，整体标注。
    {"label": "相似推荐提示", "x": 18, "y": 1994, "w": 1188, "h": 168, "kind": "hetero"},
    {"label": "商卡4被截断_border", "x": 18, "y": 2255, "w": 1188, "h": 445, "kind": "border"},
    {"label": "商卡4_头图区", "x": 28, "y": 2255, "w": 256, "h": 256, "kind": "part"},
    {"label": "商卡4_标题区", "x": 300, "y": 2255, "w": 891, "h": 62, "kind": "part"},
    {"label": "商卡4_商家信息区", "x": 300, "y": 2317, "w": 891, "h": 70, "kind": "part"},
    {"label": "商卡4_标签区", "x": 300, "y": 2387, "w": 891, "h": 71, "kind": "part"},
    {"label": "商卡4_文字下挂区", "x": 300, "y": 2458, "w": 891, "h": 242, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"DONE: {OUTPUT}; tasks={len(tasks)}")
