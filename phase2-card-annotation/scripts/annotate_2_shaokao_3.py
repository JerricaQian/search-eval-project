"""烧烤_全部_3 本地标注：按原图识别顶部快筛、真实商品横滑下挂与底部相关搜索。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 121, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 299, "w": 1224, "h": 48, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 391, "w": 1224, "h": 40, "kind": "macro"},
    # 顶部“奥尔良烤肉拌饭”等为首卡横滑商品，非独立营销横幅。
    {"label": "商卡1_border", "x": 18, "y": 431, "w": 1188, "h": 413, "kind": "border"},
    {"label": "商卡1_图文下挂区", "x": 18, "y": 431, "w": 1188, "h": 166, "kind": "part"},
    {"label": "商卡1_头图区", "x": 32, "y": 669, "w": 163, "h": 163, "kind": "part"},
    {"label": "商卡1_标题区", "x": 227, "y": 666, "w": 962, "h": 42, "kind": "part"},
    {"label": "商卡1_商家信息区", "x": 227, "y": 742, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡1_标签区", "x": 227, "y": 807, "w": 962, "h": 37, "kind": "part"},
    # 第二张仅截到下挂前段。
    {"label": "商卡2被截断_border", "x": 18, "y": 880, "w": 1188, "h": 447, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 880, "w": 163, "h": 387, "kind": "part"},
    {"label": "商卡2_图文下挂区", "x": 18, "y": 880, "w": 1188, "h": 387, "kind": "part"},
    # 管氏翅吧（望京店）。
    {"label": "商卡3_border", "x": 18, "y": 1627, "w": 1188, "h": 601, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1707, "w": 163, "h": 163, "kind": "part"},
    {"label": "商卡3_标题区", "x": 227, "y": 1703, "w": 962, "h": 47, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 227, "y": 1780, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡3_标签区", "x": 227, "y": 1845, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡3_图文下挂区", "x": 18, "y": 1918, "w": 1188, "h": 310, "kind": "part"},
    # 锦州烧烤（望花路西里店），底部下挂被截断。
    {"label": "商卡4被截断_border", "x": 18, "y": 2305, "w": 1188, "h": 239, "kind": "border"},
    {"label": "商卡4_头图区", "x": 32, "y": 2370, "w": 163, "h": 163, "kind": "part"},
    {"label": "商卡4_标题区", "x": 227, "y": 2367, "w": 962, "h": 47, "kind": "part"},
    {"label": "商卡4_商家信息区", "x": 227, "y": 2443, "w": 962, "h": 36, "kind": "part"},
    {"label": "商卡4_标签区", "x": 227, "y": 2508, "w": 962, "h": 36, "kind": "part"},
    {"label": "大家还在搜", "x": 18, "y": 1326, "w": 1188, "h": 57, "kind": "macro"},
    {"label": "相关搜索推荐", "x": 18, "y": 1383, "w": 1188, "h": 244, "kind": "macro"},
    {"label": "大家还在搜", "x": 18, "y": 2544, "w": 1188, "h": 156, "kind": "macro"},
]

if __name__ == "__main__":
    out_dir = os.path.join(ROOT, "out", "2")
    os.makedirs(out_dir, exist_ok=True)
    annotate_image(os.path.join(ROOT, "screenshots", "2", "烧烤_全部_3.png"), os.path.join(out_dir, "烧烤_全部_3_annotated.png"), TASKS)
    print(f"OK: {len(TASKS)} regions")
