"""
库迪咖啡 搜索结果第 3 页 标注脚本
=====================================
宏观组件：状态栏 + 顶部导航搜索框 + Tab + 快筛排序筛选器
商卡：3 张完整商家卡片 + 1 张底部截断卡
每张商卡：头图区 + 标题区 + 商家信息区 + 标签区 + 图文下挂区 + 文字下挂区

库迪_全部_3.png 特征：
- 顶部有粉/红色品牌色块（库迪品牌主题）贯穿状态栏+导航
- Tab 区(y=260-380)含深色文字行
- 快筛排序筛选器(y=430-560)紧接 Tab
- 首卡从 y=459 开始（Tab 末端略有留白）

Card structure (从 tmp_scan_cards.py 提取):
Card1: title(y=460-507), info(y=535-570), tag(y=600-636), short_row(y=702-715),
       xiagua_img(y=749-903,h=154), text_xiagua(y=959-1072)
Card2: title(y=1174-1222), info(y=1250-1286), tag(y=1315-1351), short_row(y=1417-1430),
       xiagua_img(y=1464-1618,h=154), text_xiagua(y=1674-1819)
Card3: title(y=1889-1937), info(y=1965-2001), tag(y=2030-2066), short_row(y=2132-2145),
       xiagua_img(y=2179-2332,h=153), text_xiagua(y=2389-2541)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "1", "库迪_全部_3.png")
OUTPUT = os.path.join(ROOT, "out", "1", "库迪_全部_3_annotated.png")

tasks = [
    # ====== 宏观组件 ======
    # 顶部品牌色块（粉/红）覆盖 状态栏+导航
    {"label": "顶部导航搜索框", "x": 0, "y": 0, "w": 1224, "h": 280, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 280, "w": 1224, "h": 100, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 380, "w": 1224, "h": 180, "kind": "macro"},

    # ====== 商卡1 (y=459-1112, h=653) ======
    # row5(y=749-903,h=154)是图文下挂；随后两行(y=959-1104)是文字下挂
    {"label": "商卡1_border", "x": 18, "y": 459, "w": 1188, "h": 653, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 459, "w": 248, "h": 210, "kind": "part"},
    {"label": "商卡1_标题区", "x": 290, "y": 459, "w": 900, "h": 50, "kind": "part"},
    {"label": "商卡1_商家信息区", "x": 290, "y": 518, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡1_标签区", "x": 290, "y": 583, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡1_图文下挂区", "x": 18, "y": 650, "w": 1188, "h": 253, "kind": "part"},
    {"label": "商卡1_文字下挂区", "x": 290, "y": 959, "w": 900, "h": 153, "kind": "part"},

    # ====== 商卡2 (y=1173-1827, h=654) ======
    {"label": "商卡2_border", "x": 18, "y": 1173, "w": 1188, "h": 654, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 1173, "w": 248, "h": 250, "kind": "part"},
    {"label": "商卡2_标题区", "x": 290, "y": 1173, "w": 900, "h": 50, "kind": "part"},
    {"label": "商卡2_商家信息区", "x": 290, "y": 1232, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡2_标签区", "x": 290, "y": 1297, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡2_图文下挂区", "x": 18, "y": 1365, "w": 1188, "h": 253, "kind": "part"},
    {"label": "商卡2_文字下挂区", "x": 290, "y": 1674, "w": 900, "h": 153, "kind": "part"},

    # ====== 商卡3 (y=1888-2542, h=654) ======
    {"label": "商卡3_border", "x": 18, "y": 1888, "w": 1188, "h": 654, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1888, "w": 248, "h": 250, "kind": "part"},
    {"label": "商卡3_标题区", "x": 290, "y": 1888, "w": 900, "h": 50, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 290, "y": 1947, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡3_标签区", "x": 290, "y": 2012, "w": 900, "h": 55, "kind": "part"},
    {"label": "商卡3_图文下挂区", "x": 18, "y": 2080, "w": 1188, "h": 252, "kind": "part"},
    {"label": "商卡3_文字下挂区", "x": 290, "y": 2389, "w": 900, "h": 153, "kind": "part"},

    # ====== 商卡4 (被截断, y=2604-2700, h=96) ======
    # 仅可见头图与标题顶部 — 按截断卡标注
    {"label": "商卡4被截断_border", "x": 18, "y": 2604, "w": 1188, "h": 96, "kind": "border"},
    {"label": "商卡4_头图区", "x": 32, "y": 2604, "w": 248, "h": 96, "kind": "part"},
    {"label": "商卡4_标题区", "x": 290, "y": 2604, "w": 900, "h": 60, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"DONE: {OUTPUT}; tasks={len(tasks)}")
