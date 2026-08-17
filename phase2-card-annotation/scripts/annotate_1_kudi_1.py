"""
库迪咖啡 搜索结果第 1 页 标注脚本
=====================================
宏观组件：状态栏 + 顶部导航搜索框 + Tab + 快筛排序筛选器
商卡：3 张商家卡片（图文下挂 + 文字下挂）
每张商卡结构：头图区 + 标题区 + 商家信息区 + 标签区 + 图文下挂区 + 文字下挂区

坐标通过读图内容 + scan_rows 辅助定位（卡间留白）。
卡内分区边界按读图内容判定（标题/信息/标签/下挂各有独立行）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "1", "库迪_全部_1.png")
OUTPUT = os.path.join(ROOT, "out", "1", "库迪_全部_1_annotated.png")

tasks = [
    # ====== 宏观组件 ======
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 140, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 260, "w": 1224, "h": 100, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 360, "w": 1224, "h": 130, "kind": "macro"},

    # ====== 商卡1 (y=551-1196, h=645) ======
    # 头图区左侧纵跨(y=554-801)，右侧信息行row1-3(y=552-728)
    {"label": "商卡1_border", "x": 18, "y": 551, "w": 1188, "h": 645, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 551, "w": 248, "h": 250, "kind": "part"},
    {"label": "商卡1_标题区", "x": 290, "y": 551, "w": 900, "h": 50, "kind": "part"},
    {"label": "商卡1_商家信息区", "x": 290, "y": 610, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡1_标签区", "x": 290, "y": 675, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡1_图文下挂区", "x": 18, "y": 740, "w": 1188, "h": 291, "kind": "part"},
    {"label": "商卡1_文字下挂区", "x": 290, "y": 1051, "w": 900, "h": 145, "kind": "part"},

    # ====== 商卡2 (y=1266-1911, h=645) ======
    {"label": "商卡2_border", "x": 18, "y": 1266, "w": 1188, "h": 645, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 1266, "w": 248, "h": 250, "kind": "part"},
    {"label": "商卡2_标题区", "x": 290, "y": 1266, "w": 900, "h": 50, "kind": "part"},
    {"label": "商卡2_商家信息区", "x": 290, "y": 1325, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡2_标签区", "x": 290, "y": 1390, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡2_图文下挂区", "x": 18, "y": 1455, "w": 1188, "h": 291, "kind": "part"},
    {"label": "商卡2_文字下挂区", "x": 290, "y": 1766, "w": 900, "h": 145, "kind": "part"},

    # ====== 商卡3 (y=1981-2592, h=611) ======
    {"label": "商卡3_border", "x": 18, "y": 1981, "w": 1188, "h": 611, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1981, "w": 248, "h": 250, "kind": "part"},
    {"label": "商卡3_标题区", "x": 290, "y": 1981, "w": 900, "h": 50, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 290, "y": 2040, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡3_标签区", "x": 290, "y": 2105, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡3_图文下挂区", "x": 18, "y": 2170, "w": 1188, "h": 291, "kind": "part"},
    {"label": "商卡3_文字下挂区", "x": 290, "y": 2481, "w": 900, "h": 111, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"DONE: {OUTPUT}; tasks={len(tasks)}")
