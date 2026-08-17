"""烧烤_全部_2 本地标注：仅标原图确有的顶部模块与逐卡图文下挂结构。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 121, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 299, "w": 1224, "h": 48, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 391, "w": 1224, "h": 35, "kind": "macro"},
    # 首卡顶部仅保留了信息/标签行；463 起是真实商品图横滑下挂，不将其误称为营销横幅。
    {"label": "商卡1被截断_border", "x": 18, "y": 426, "w": 1188, "h": 424, "kind": "border"},
    {"label": "商卡1_标签区", "x": 227, "y": 391, "w": 962, "h": 35, "kind": "part"},
    {"label": "商卡1_图文下挂区", "x": 18, "y": 463, "w": 1188, "h": 387, "kind": "part"},
    # 第二张完整商家卡：头图只有 163x163，商品大图归属下挂区。
    {"label": "商卡2_border", "x": 18, "y": 912, "w": 1188, "h": 601, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 915, "w": 163, "h": 163, "kind": "part"},
    {"label": "商卡2_标题区", "x": 227, "y": 912, "w": 962, "h": 43, "kind": "part"},
    {"label": "商卡2_商家信息区", "x": 227, "y": 988, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡2_标签区", "x": 227, "y": 1053, "w": 962, "h": 38, "kind": "part"},
    {"label": "商卡2_图文下挂区", "x": 18, "y": 1126, "w": 1188, "h": 387, "kind": "part"},
    # 管氏翅吧（望京东店）
    {"label": "商卡3_border", "x": 18, "y": 1575, "w": 1188, "h": 601, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1578, "w": 163, "h": 163, "kind": "part"},
    {"label": "商卡3_标题区", "x": 227, "y": 1575, "w": 962, "h": 43, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 227, "y": 1651, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡3_标签区", "x": 227, "y": 1716, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡3_图文下挂区", "x": 18, "y": 1789, "w": 1188, "h": 387, "kind": "part"},
    # 美团拼好饭商卡（底部下挂被截图截断）。
    {"label": "商卡4被截断_border", "x": 18, "y": 2238, "w": 1188, "h": 462, "kind": "border"},
    {"label": "商卡4_头图区", "x": 32, "y": 2241, "w": 163, "h": 163, "kind": "part"},
    {"label": "商卡4_标题区", "x": 227, "y": 2238, "w": 962, "h": 43, "kind": "part"},
    {"label": "商卡4_商家信息区", "x": 227, "y": 2314, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡4_标签区", "x": 227, "y": 2379, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡4_图文下挂区", "x": 18, "y": 2454, "w": 1188, "h": 246, "kind": "part"},
]

if __name__ == "__main__":
    out_dir = os.path.join(ROOT, "out", "2")
    os.makedirs(out_dir, exist_ok=True)
    annotate_image(os.path.join(ROOT, "screenshots", "2", "烧烤_全部_2.png"), os.path.join(out_dir, "烧烤_全部_2_annotated.png"), TASKS)
    print(f"OK: {len(TASKS)} regions")
