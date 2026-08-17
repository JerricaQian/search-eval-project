"""啤酒_全部_1 本地标注：基于像素分析识别的商家卡片+商品卡片混合结构。
- 商卡1: 商家卡片-图文下挂 (y=296-1024, 含下挂区)
- 商卡2: 商品卡片 (y=1108-1586)
- 商卡3: 商品卡片 (y=1675-2149)
- 商卡4: 商品卡片-底部截断 (y=2233-2700)
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

    # 商卡1: 商家卡片-图文下挂 (含下挂区，整体 border 从 296 到 1024)
    {"label": "商卡1_border", "x": 18, "y": 296, "w": 1188, "h": 728, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 310, "w": 348, "h": 340, "kind": "part"},
    {"label": "商卡1_标题区", "x": 396, "y": 310, "w": 792, "h": 80, "kind": "part"},
    {"label": "商卡1_商家信息区", "x": 396, "y": 420, "w": 792, "h": 40, "kind": "part"},
    {"label": "商卡1_标签区", "x": 396, "y": 500, "w": 792, "h": 100, "kind": "part"},
    {"label": "商卡1_图文下挂区", "x": 18, "y": 765, "w": 1188, "h": 259, "kind": "part"},

    # 商卡2: 商品卡片 (y=1108-1586, h=478)
    {"label": "商卡2_border", "x": 18, "y": 1108, "w": 1188, "h": 478, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 1120, "w": 348, "h": 340, "kind": "part"},
    {"label": "商卡2_标题区", "x": 396, "y": 1120, "w": 792, "h": 100, "kind": "part"},
    {"label": "商卡2_基础信息区", "x": 396, "y": 1220, "w": 792, "h": 40, "kind": "part"},
    {"label": "商卡2_价格区", "x": 396, "y": 1280, "w": 450, "h": 80, "kind": "part"},
    {"label": "商卡2_标签区", "x": 396, "y": 1380, "w": 792, "h": 80, "kind": "part"},
    {"label": "商卡2_商家区", "x": 396, "y": 1490, "w": 792, "h": 96, "kind": "part"},

    # 商卡3: 商品卡片 (y=1675-2149, h=474)
    {"label": "商卡3_border", "x": 18, "y": 1675, "w": 1188, "h": 474, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1688, "w": 348, "h": 340, "kind": "part"},
    {"label": "商卡3_标题区", "x": 396, "y": 1688, "w": 792, "h": 100, "kind": "part"},
    {"label": "商卡3_基础信息区", "x": 396, "y": 1788, "w": 792, "h": 40, "kind": "part"},
    {"label": "商卡3_价格区", "x": 396, "y": 1860, "w": 450, "h": 80, "kind": "part"},
    {"label": "商卡3_标签区", "x": 396, "y": 1960, "w": 792, "h": 80, "kind": "part"},
    {"label": "商卡3_商家区", "x": 396, "y": 2048, "w": 792, "h": 101, "kind": "part"},

    # 商卡4: 商品卡片-底部截断 (y=2233-2700, h=467)
    {"label": "商卡4被截断_border", "x": 18, "y": 2233, "w": 1188, "h": 467, "kind": "border"},
    {"label": "商卡4_头图区", "x": 32, "y": 2245, "w": 330, "h": 340, "kind": "part"},
    {"label": "商卡4_标题区", "x": 396, "y": 2245, "w": 792, "h": 100, "kind": "part"},
    {"label": "商卡4_基础信息区", "x": 396, "y": 2345, "w": 792, "h": 40, "kind": "part"},
    {"label": "商卡4_价格区", "x": 396, "y": 2380, "w": 450, "h": 80, "kind": "part"},
    {"label": "商卡4_标签区", "x": 396, "y": 2470, "w": 792, "h": 80, "kind": "part"},
    {"label": "商卡4_商家区", "x": 396, "y": 2550, "w": 792, "h": 150, "kind": "part"},
]

if __name__ == "__main__":
    out_dir = os.path.join(ROOT, "out", "1")
    os.makedirs(out_dir, exist_ok=True)
    annotate_image(
        os.path.join(ROOT, "screenshots", "1", "啤酒_全部_1.png"),
        os.path.join(out_dir, "啤酒_全部_1_annotated.png"),
        TASKS
    )
    print(f"OK: {len(TASKS)} regions -> {out_dir}/啤酒_全部_1_annotated.png")
