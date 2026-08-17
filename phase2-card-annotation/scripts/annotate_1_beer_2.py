"""啤酒_全部_2 本地标注：基于像素分析的商品卡片结构。
- 商卡1: 商品卡片 (y=464-811, h=347)
- 商卡2: 商品卡片 (y=897-1374, h=477)
- 商卡3: 商品卡片 (y=1464-1938, h=474)
- 商卡4: 商家卡片-图文下挂 (y=2012-2338, h=326, 含下挂区)
- 商卡5: 商品卡片-底部截断 (y=2408-2554, h=146)
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TASKS = [
    # 宏观组件
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 100, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 220, "w": 1224, "h": 79, "kind": "macro"},

    # 商卡1: 商品卡片 (y=464-811, h=347)
    {"label": "商卡1_border", "x": 18, "y": 464, "w": 1188, "h": 347, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 476, "w": 348, "h": 330, "kind": "part"},
    {"label": "商卡1_标题区", "x": 396, "y": 476, "w": 792, "h": 90, "kind": "part"},
    {"label": "商卡1_基础信息区", "x": 396, "y": 580, "w": 792, "h": 40, "kind": "part"},
    {"label": "商卡1_价格区", "x": 396, "y": 640, "w": 450, "h": 80, "kind": "part"},
    {"label": "商卡1_标签区", "x": 396, "y": 740, "w": 792, "h": 70, "kind": "part"},

    # 商卡2: 商品卡片 (y=897-1374, h=477)
    {"label": "商卡2_border", "x": 18, "y": 897, "w": 1188, "h": 477, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 910, "w": 348, "h": 340, "kind": "part"},
    {"label": "商卡2_标题区", "x": 396, "y": 910, "w": 792, "h": 100, "kind": "part"},
    {"label": "商卡2_基础信息区", "x": 396, "y": 1020, "w": 792, "h": 40, "kind": "part"},
    {"label": "商卡2_价格区", "x": 396, "y": 1080, "w": 450, "h": 80, "kind": "part"},
    {"label": "商卡2_标签区", "x": 396, "y": 1180, "w": 792, "h": 80, "kind": "part"},
    {"label": "商卡2_商家区", "x": 396, "y": 1280, "w": 792, "h": 94, "kind": "part"},

    # 商卡3: 商品卡片 (y=1464-1938, h=474)
    {"label": "商卡3_border", "x": 18, "y": 1464, "w": 1188, "h": 474, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1477, "w": 348, "h": 340, "kind": "part"},
    {"label": "商卡3_标题区", "x": 396, "y": 1477, "w": 792, "h": 100, "kind": "part"},
    {"label": "商卡3_基础信息区", "x": 396, "y": 1577, "w": 792, "h": 40, "kind": "part"},
    {"label": "商卡3_价格区", "x": 396, "y": 1640, "w": 450, "h": 80, "kind": "part"},
    {"label": "商卡3_标签区", "x": 396, "y": 1740, "w": 792, "h": 80, "kind": "part"},
    {"label": "商卡3_商家区", "x": 396, "y": 1838, "w": 792, "h": 100, "kind": "part"},

    # 商卡4: 商家卡片-图文下挂 (y=2012-2338, h=326, 含下挂区)
    {"label": "商卡4_border", "x": 18, "y": 2012, "w": 1188, "h": 326, "kind": "border"},
    {"label": "商卡4_头图区", "x": 32, "y": 2025, "w": 348, "h": 200, "kind": "part"},
    {"label": "商卡4_标题区", "x": 396, "y": 2025, "w": 792, "h": 70, "kind": "part"},
    {"label": "商卡4_商家信息区", "x": 396, "y": 2100, "w": 792, "h": 40, "kind": "part"},
    {"label": "商卡4_标签区", "x": 396, "y": 2150, "w": 792, "h": 60, "kind": "part"},
    {"label": "商卡4_图文下挂区", "x": 18, "y": 2220, "w": 1188, "h": 118, "kind": "part"},

    # 商卡5: 商品卡片-底部截断 (y=2408-2554, h=146)
    {"label": "商卡5被截断_border", "x": 18, "y": 2408, "w": 1188, "h": 146, "kind": "border"},
    {"label": "商卡5_头图区", "x": 32, "y": 2420, "w": 348, "h": 130, "kind": "part"},
    {"label": "商卡5_标题区", "x": 396, "y": 2420, "w": 792, "h": 90, "kind": "part"},
    {"label": "商卡5_基础信息区", "x": 396, "y": 2515, "w": 792, "h": 39, "kind": "part"},
]

if __name__ == "__main__":
    out_dir = os.path.join(ROOT, "out", "1")
    os.makedirs(out_dir, exist_ok=True)
    annotate_image(
        os.path.join(ROOT, "screenshots", "1", "啤酒_全部_2.png"),
        os.path.join(out_dir, "啤酒_全部_2_annotated.png"),
        TASKS
    )
    print(f"OK: {len(TASKS)} regions -> {out_dir}/啤酒_全部_2_annotated.png")
