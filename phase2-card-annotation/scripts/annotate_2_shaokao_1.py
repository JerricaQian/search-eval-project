"""烧烤_全部_1 本地标注：基于原图语义及单次 scan_rows 的独立任务表。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 121, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 299, "w": 1224, "h": 56, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 423, "w": 1224, "h": 48, "kind": "macro"},
    # 锦州烧烤（悠乐汇店）：下方有商品缩略图，故为图文下挂而不是营销横幅。
    {"label": "商卡1_border", "x": 18, "y": 551, "w": 1188, "h": 601, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 554, "w": 163, "h": 163, "kind": "part"},
    {"label": "商卡1_标题区", "x": 227, "y": 551, "w": 962, "h": 47, "kind": "part"},
    {"label": "商卡1_商家信息区", "x": 227, "y": 627, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡1_标签区", "x": 227, "y": 692, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡1_图文下挂区", "x": 18, "y": 765, "w": 1188, "h": 387, "kind": "part"},
    # 锦州烧烤（望京店）
    {"label": "商卡2_border", "x": 18, "y": 1214, "w": 1188, "h": 601, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 1217, "w": 163, "h": 163, "kind": "part"},
    {"label": "商卡2_标题区", "x": 227, "y": 1214, "w": 962, "h": 47, "kind": "part"},
    {"label": "商卡2_商家信息区", "x": 227, "y": 1290, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡2_标签区", "x": 227, "y": 1355, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡2_图文下挂区", "x": 18, "y": 1428, "w": 1188, "h": 387, "kind": "part"},
    # 招牌烤羊肉对应的烧烤商家卡。
    {"label": "商卡3_border", "x": 18, "y": 1877, "w": 1188, "h": 601, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1880, "w": 163, "h": 163, "kind": "part"},
    {"label": "商卡3_标题区", "x": 227, "y": 1877, "w": 962, "h": 47, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 227, "y": 1953, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡3_标签区", "x": 227, "y": 2018, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡3_图文下挂区", "x": 18, "y": 2091, "w": 1188, "h": 387, "kind": "part"},
    # 京司肉串汪（望京店）在底部截断。
    {"label": "商卡4被截断_border", "x": 18, "y": 2540, "w": 1188, "h": 160, "kind": "border"},
    {"label": "商卡4_头图区", "x": 32, "y": 2543, "w": 163, "h": 157, "kind": "part"},
    {"label": "商卡4_标题区", "x": 227, "y": 2540, "w": 962, "h": 47, "kind": "part"},
    {"label": "商卡4_商家信息区", "x": 227, "y": 2616, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡4_标签区", "x": 227, "y": 2681, "w": 962, "h": 19, "kind": "part"},
]

if __name__ == "__main__":
    out_dir = os.path.join(ROOT, "out", "2")
    os.makedirs(out_dir, exist_ok=True)
    annotate_image(os.path.join(ROOT, "screenshots", "2", "烧烤_全部_1.png"), os.path.join(out_dir, "烧烤_全部_1_annotated.png"), TASKS)
    print(f"OK: {len(TASKS)} regions")
