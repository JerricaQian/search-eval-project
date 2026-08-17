"""历史审计脚本：安睡裤搜索结果第 1 页标注坐标快照。

此文件仅保留原始交付的可追溯记录，禁止作为新任务或默认工作流入口。
对应的统一 SceneSpec 为 ``scenes/安睡裤_全部_1.scene.json``，必须通过
``scripts/annotation_scene.py`` 执行。

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
INPUT = os.path.join(ROOT, "screenshots", "1", "安睡裤_全部_1.png")
OUTPUT = os.path.join(ROOT, "out", "1", "安睡裤_全部_1_annotated.png")

tasks = [
    # ===== 宏观组件 =====
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 179, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 299, "w": 1224, "h": 116, "kind": "macro"},
    {"label": "图筛", "x": 0, "y": 415, "w": 1224, "h": 261, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 676, "w": 1224, "h": 193, "kind": "macro"},

    # ===== 商卡 1 =====
    {"label": "商卡1_border", "x": 18, "y": 952, "w": 1188, "h": 353, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 952, "w": 328, "h": 332, "kind": "part"},
    {"label": "商卡1_标签区", "x": 360, "y": 958, "w": 832, "h": 45, "kind": "part"},
    {"label": "商卡1_标题区", "x": 360, "y": 1027, "w": 832, "h": 41, "kind": "part"},
    {"label": "商卡1_价格区", "x": 360, "y": 1130, "w": 832, "h": 47, "kind": "part"},
    {"label": "商卡1_商家区", "x": 360, "y": 1204, "w": 832, "h": 99, "kind": "part"},

    # ===== 商卡 2 =====
    {"label": "商卡2_border", "x": 18, "y": 1454, "w": 1188, "h": 347, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 1454, "w": 328, "h": 328, "kind": "part"},
    {"label": "商卡2_标签区", "x": 360, "y": 1460, "w": 832, "h": 45, "kind": "part"},
    {"label": "商卡2_标题区", "x": 360, "y": 1532, "w": 832, "h": 35, "kind": "part"},
    {"label": "商卡2_价格区", "x": 360, "y": 1699, "w": 832, "h": 41, "kind": "part"},
    {"label": "商卡2_商家区", "x": 360, "y": 1767, "w": 832, "h": 34, "kind": "part"},

    # ===== 商卡 3 =====
    {"label": "商卡3_border", "x": 18, "y": 2017, "w": 1188, "h": 347, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 2017, "w": 328, "h": 328, "kind": "part"},
    {"label": "商卡3_标签区", "x": 360, "y": 2023, "w": 832, "h": 45, "kind": "part"},
    {"label": "商卡3_标题区", "x": 360, "y": 2105, "w": 832, "h": 45, "kind": "part"},
    {"label": "商卡3_价格区", "x": 360, "y": 2256, "w": 832, "h": 47, "kind": "part"},
    {"label": "商卡3_商家区", "x": 360, "y": 2330, "w": 832, "h": 34, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"DONE: {OUTPUT}; tasks={len(tasks)}")
