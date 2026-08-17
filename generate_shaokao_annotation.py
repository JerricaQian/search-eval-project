#!/usr/bin/env python3
"""Generate two-level annotation for 烧烤_全部_1.png screenshot.

Two levels:
  - Macro components (状态栏/导航/Tab/图筛/快筛)
  - Card internal partitions (头图区/标题区/基础信息区/下挂区)

Each card is calibrated independently per the 禁止跨卡复用坐标 rule.
"""
import sys
import os

sys.path.insert(0, "/Users/qianjing/Desktop/search-eval-project/phase2-card-annotation/scripts")
from annotate_image import annotate_image

IN_PATH = "/Users/qianjing/Desktop/search-eval-project/screenshots/sm_烧烤_全部_1.png"
OUT_DIR = "/Users/qianjing/Desktop/search-eval-project/screenshots-out"
OUT_PATH = os.path.join(OUT_DIR, "烧烤_全部_1_annotated.png")

os.makedirs(OUT_DIR, exist_ok=True)

# Image dimensions: 348 x 768
# scan_rows whitespace bands: 0-11, 23-34, 69-85, 102-120, 134-157,
#   207-217, 328-345, 396-406, 517-534, 584-594, 705-722

tasks = [
    # ---- Macro components (kind=macro) ----
    {"label": "状态栏", "x": 0, "y": 0, "w": 348, "h": 23, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 23, "w": 348, "h": 46, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 69, "w": 348, "h": 33, "kind": "macro"},
    {"label": "图筛", "x": 0, "y": 102, "w": 348, "h": 32, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 134, "w": 348, "h": 23, "kind": "macro"},

    # ---- Card 1 (y 157-328) - independently calibrated ----
    # scan_card_regions: 头图区 y=(218,324) x=(10,336);
    #   text rows y157-170 h13, y179-187 h8, y218-292 h74, y300-308 h8, y316-325 h9
    {"label": "商卡1_border", "x": 6, "y": 157, "w": 336, "h": 171, "kind": "border"},
    {"label": "商卡1_标题区", "x": 10, "y": 159, "w": 328, "h": 16, "kind": "part"},
    {"label": "商卡1_基础信息区", "x": 10, "y": 176, "w": 328, "h": 38, "kind": "part"},
    {"label": "商卡1_头图区", "x": 10, "y": 218, "w": 328, "h": 74, "kind": "part"},
    {"label": "商卡1_文字下挂区", "x": 10, "y": 296, "w": 328, "h": 30, "kind": "part"},

    # ---- Card 2 (y 345-517) - independently calibrated ----
    # scan_card_regions: 头图区 y=(371,512) x=(10,335);
    #   text rows y346-358 h12, y407-481 h74, y488-497 h9, y505-513 h8
    {"label": "商卡2_border", "x": 6, "y": 345, "w": 336, "h": 172, "kind": "border"},
    {"label": "商卡2_标题区", "x": 10, "y": 347, "w": 328, "h": 14, "kind": "part"},
    {"label": "商卡2_基础信息区", "x": 10, "y": 362, "w": 328, "h": 43, "kind": "part"},
    {"label": "商卡2_头图区", "x": 10, "y": 407, "w": 328, "h": 74, "kind": "part"},
    {"label": "商卡2_文字下挂区", "x": 10, "y": 485, "w": 328, "h": 30, "kind": "part"},

    # ---- Card 3 (y 534-705) - independently calibrated ----
    # scan_card_regions: 头图区 y=(538,701) x=(10,334);
    #   text rows y534-546 h12, y556-564 h8, y595-669 h74, y676-686 h10, y693-701 h8
    {"label": "商卡3_border", "x": 6, "y": 534, "w": 336, "h": 171, "kind": "border"},
    {"label": "商卡3_标题区", "x": 10, "y": 536, "w": 328, "h": 14, "kind": "part"},
    {"label": "商卡3_基础信息区", "x": 10, "y": 552, "w": 328, "h": 41, "kind": "part"},
    {"label": "商卡3_头图区", "x": 10, "y": 595, "w": 328, "h": 74, "kind": "part"},
    {"label": "商卡3_文字下挂区", "x": 10, "y": 673, "w": 328, "h": 30, "kind": "part"},

    # ---- Card 4 (y 722-768, truncated) - independently calibrated ----
    # scan_card_regions: text rows y723-735 h12, y744-752 h8
    # Truncated card - only partial content visible, mark border only
    {"label": "商卡4_border_被截断", "x": 6, "y": 722, "w": 336, "h": 46, "kind": "border"},
    {"label": "商卡4_标题区_被截断", "x": 10, "y": 724, "w": 328, "h": 12, "kind": "part"},
]

annotate_image(IN_PATH, OUT_PATH, tasks)
print(f"Annotation saved to: {OUT_PATH}")
print(f"Total tasks: {len(tasks)}")
