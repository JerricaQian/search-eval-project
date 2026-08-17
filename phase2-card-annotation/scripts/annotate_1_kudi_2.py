"""
库迪咖啡 搜索结果第 2 页 标注脚本
=====================================
宏观组件：状态栏 + 顶部导航搜索框 + Tab + 快筛排序筛选器
商卡：3 张商家卡片（图文下挂 + 文字下挂）
每张商卡：头图区 + 标题区 + 商家信息区 + 标签区 + 图文下挂区 + 文字下挂区

库迪_全部_2.png 卡1 头部含"新店"标识，右text行比卡2/3多一个 row4（小图文下挂前置短行）。
卡1：下挂区跨 row4+row5(y=809-1010)；文字下挂随后两行(row6+row7)。
卡2、卡3：图文下挂区集中在 row5(y=1571-1726、y=2286-2440)。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "1", "库迪_全部_2.png")
OUTPUT = os.path.join(ROOT, "out", "1", "库迪_全部_2_annotated.png")

tasks = [
    # ====== 宏观组件 (top area y=0-365; filters y=365-566) ======
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 140, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 260, "w": 1224, "h": 105, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 365, "w": 1224, "h": 201, "kind": "macro"},

    # ====== 商卡1 (y=566-1219, h=653) ======
    # row4(y=809-841,h=32)是图文下挂首行短图；row5(y=874-1010,h=136)是主图文下挂
    # 下挂区合并为 y=809-1010 (h=201)；文字下挂随后两行(y=1066-1155)
    {"label": "商卡1_border", "x": 18, "y": 566, "w": 1188, "h": 653, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 566, "w": 248, "h": 230, "kind": "part"},
    {"label": "商卡1_标题区", "x": 290, "y": 566, "w": 900, "h": 50, "kind": "part"},
    {"label": "商卡1_商家信息区", "x": 290, "y": 625, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡1_标签区", "x": 290, "y": 690, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡1_图文下挂区", "x": 18, "y": 809, "w": 1188, "h": 201, "kind": "part"},
    {"label": "商卡1_文字下挂区", "x": 290, "y": 1066, "w": 900, "h": 153, "kind": "part"},

    # ====== 商卡2 (y=1281-1934, h=653) ======
    # row5(y=1571-1726,h=155)是图文下挂主区；文字下挂随后两行(y=1781-1926)
    {"label": "商卡2_border", "x": 18, "y": 1281, "w": 1188, "h": 653, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 1281, "w": 248, "h": 200, "kind": "part"},
    {"label": "商卡2_标题区", "x": 290, "y": 1281, "w": 900, "h": 50, "kind": "part"},
    {"label": "商卡2_商家信息区", "x": 290, "y": 1340, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡2_标签区", "x": 290, "y": 1405, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡2_图文下挂区", "x": 18, "y": 1470, "w": 1188, "h": 256, "kind": "part"},
    {"label": "商卡2_文字下挂区", "x": 290, "y": 1740, "w": 900, "h": 194, "kind": "part"},

    # ====== 商卡3 (y=1996-2649, h=653) ======
    # row5(y=2286-2440,h=154)是图文下挂；文字下挂随后三行(y=2487-2641)
    {"label": "商卡3_border", "x": 18, "y": 1996, "w": 1188, "h": 653, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1996, "w": 248, "h": 200, "kind": "part"},
    {"label": "商卡3_标题区", "x": 290, "y": 1996, "w": 900, "h": 50, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 290, "y": 2055, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡3_标签区", "x": 290, "y": 2120, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡3_图文下挂区", "x": 18, "y": 2185, "w": 1188, "h": 255, "kind": "part"},
    {"label": "商卡3_文字下挂区", "x": 290, "y": 2487, "w": 900, "h": 162, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"DONE: {OUTPUT}; tasks={len(tasks)}")
