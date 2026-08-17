"""啤酒_全部_3 本地标注：基于像素分析的商品卡片+商家卡片混合结构。
- 商卡1: 商家卡片-图文下挂 (y=299-860, h=561, 含下挂区)
- 商卡2: 商品卡片 (y=943-1291, h=348)
- 商卡3: 商家卡片-图文下挂 (y=1374-1723, h=349, 含下挂区)
- 商卡4: 商品卡片 (y=1808-2285, h=477)
- 商卡5: 商品卡片-底部截断 (y=2369-2700, h=331)
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

    # 商卡1: 商家卡片-图文下挂 (y=299-860, h=561, 含下挂区)
    {"label": "商卡1_border", "x": 18, "y": 299, "w": 1188, "h": 561, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 312, "w": 348, "h": 340, "kind": "part"},
    {"label": "商卡1_标题区", "x": 396, "y": 312, "w": 792, "h": 80, "kind": "part"},
    {"label": "商卡1_商家信息区", "x": 396, "y": 420, "w": 792, "h": 40, "kind": "part"},
    {"label": "商卡1_标签区", "x": 396, "y": 500, "w": 792, "h": 100, "kind": "part"},
    {"label": "商卡1_图文下挂区", "x": 18, "y": 660, "w": 1188, "h": 200, "kind": "part"},

    # 商卡2: 商品卡片 (y=943-1291, h=348)
    {"label": "商卡2_border", "x": 18, "y": 943, "w": 1188, "h": 348, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 956, "w": 348, "h": 330, "kind": "part"},
    {"label": "商卡2_标题区", "x": 396, "y": 956, "w": 792, "h": 90, "kind": "part"},
    {"label": "商卡2_基础信息区", "x": 396, "y": 1060, "w": 792, "h": 40, "kind": "part"},
    {"label": "商卡2_价格区", "x": 396, "y": 1100, "w": 450, "h": 80, "kind": "part"},
    {"label": "商卡2_标签区", "x": 396, "y": 1200, "w": 792, "h": 80, "kind": "part"},

    # 商卡3: 商家卡片-图文下挂 (y=1374-1723, h=349, 含下挂区)
    {"label": "商卡3_border", "x": 18, "y": 1374, "w": 1188, "h": 349, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1387, "w": 348, "h": 200, "kind": "part"},
    {"label": "商卡3_标题区", "x": 396, "y": 1387, "w": 792, "h": 70, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 396, "y": 1460, "w": 792, "h": 40, "kind": "part"},
    {"label": "商卡3_标签区", "x": 396, "y": 1510, "w": 792, "h": 60, "kind": "part"},
    {"label": "商卡3_图文下挂区", "x": 18, "y": 1580, "w": 1188, "h": 143, "kind": "part"},

    # 商卡4: 商品卡片 (y=1808-2285, h=477)
    {"label": "商卡4_border", "x": 18, "y": 1808, "w": 1188, "h": 477, "kind": "border"},
    {"label": "商卡4_头图区", "x": 32, "y": 1821, "w": 348, "h": 340, "kind": "part"},
    {"label": "商卡4_标题区", "x": 396, "y": 1821, "w": 792, "h": 100, "kind": "part"},
    {"label": "商卡4_基础信息区", "x": 396, "y": 1921, "w": 792, "h": 40, "kind": "part"},
    {"label": "商卡4_价格区", "x": 396, "y": 1980, "w": 450, "h": 80, "kind": "part"},
    {"label": "商卡4_标签区", "x": 396, "y": 2080, "w": 792, "h": 80, "kind": "part"},
    {"label": "商卡4_商家区", "x": 396, "y": 2180, "w": 792, "h": 105, "kind": "part"},

    # 商卡5: 商品卡片-底部截断 (y=2369-2700, h=331)
    {"label": "商卡5被截断_border", "x": 18, "y": 2369, "w": 1188, "h": 331, "kind": "border"},
    {"label": "商卡5_头图区", "x": 32, "y": 2382, "w": 330, "h": 310, "kind": "part"},
    {"label": "商卡5_标题区", "x": 396, "y": 2382, "w": 792, "h": 100, "kind": "part"},
    {"label": "商卡5_基础信息区", "x": 396, "y": 2482, "w": 792, "h": 40, "kind": "part"},
    {"label": "商卡5_价格区", "x": 396, "y": 2530, "w": 450, "h": 80, "kind": "part"},
    {"label": "商卡5_标签区", "x": 396, "y": 2600, "w": 792, "h": 100, "kind": "part"},
]

if __name__ == "__main__":
    out_dir = os.path.join(ROOT, "out", "1")
    os.makedirs(out_dir, exist_ok=True)
    annotate_image(
        os.path.join(ROOT, "screenshots", "1", "啤酒_全部_3.png"),
        os.path.join(out_dir, "啤酒_全部_3_annotated.png"),
        TASKS
    )
    print(f"OK: {len(TASKS)} regions -> {out_dir}/啤酒_全部_3_annotated.png")
