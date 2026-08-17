"""独立标注 screenshots/2/全季酒店_全部_2.png（酒店搜索续页）。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "2", "全季酒店_全部_2.png")
OUTPUT = os.path.join(ROOT, "out", "2", "全季酒店_全部_2_annotated.png")

# 本页 scan_rows 的酒店/商品内容带独立为 387-654、703-1094、1144-1604、1666-2064、2487-2700。
tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 121, "kind": "macro"},
    {"label": "日期区", "x": 18, "y": 241, "w": 390, "h": 123, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 408, "y": 241, "w": 798, "h": 123, "kind": "macro"},
    {"label": "商卡1_上方续卡被截断_border", "x": 18, "y": 387, "w": 1188, "h": 267, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 401, "w": 330, "h": 253, "kind": "part"},
    {"label": "商卡1_标题区", "x": 385, "y": 390, "w": 800, "h": 46, "kind": "part"},
    {"label": "商卡1_评分区推荐理由", "x": 385, "y": 436, "w": 800, "h": 48, "kind": "part"},
    {"label": "商卡1_位置信息区", "x": 385, "y": 484, "w": 800, "h": 42, "kind": "part"},
    {"label": "商卡1_标签区", "x": 385, "y": 526, "w": 800, "h": 48, "kind": "part"},
    {"label": "商卡1_价格区动态推荐", "x": 385, "y": 574, "w": 800, "h": 70, "kind": "part"},
    {"label": "商卡2_酒店商家卡_border", "x": 18, "y": 703, "w": 1188, "h": 391, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 717, "w": 330, "h": 350, "kind": "part"},
    {"label": "商卡2_标题区", "x": 385, "y": 706, "w": 800, "h": 55, "kind": "part"},
    {"label": "商卡2_评分区推荐理由", "x": 385, "y": 761, "w": 800, "h": 61, "kind": "part"},
    {"label": "商卡2_位置信息区", "x": 385, "y": 822, "w": 800, "h": 60, "kind": "part"},
    {"label": "商卡2_标签区", "x": 385, "y": 882, "w": 800, "h": 61, "kind": "part"},
    {"label": "商卡2_价格区", "x": 385, "y": 943, "w": 800, "h": 65, "kind": "part"},
    {"label": "商卡2_价格区动态推荐", "x": 385, "y": 1008, "w": 800, "h": 76, "kind": "part"},
    {"label": "商卡3_全季望京店_border", "x": 18, "y": 1144, "w": 1188, "h": 460, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1158, "w": 330, "h": 344, "kind": "part"},
    {"label": "商卡3_标题区", "x": 385, "y": 1152, "w": 800, "h": 55, "kind": "part"},
    {"label": "商卡3_评分区推荐理由", "x": 385, "y": 1207, "w": 800, "h": 62, "kind": "part"},
    {"label": "商卡3_位置信息区", "x": 385, "y": 1269, "w": 800, "h": 65, "kind": "part"},
    {"label": "商卡3_标签区", "x": 385, "y": 1334, "w": 800, "h": 68, "kind": "part"},
    {"label": "商卡3_价格区", "x": 385, "y": 1402, "w": 800, "h": 75, "kind": "part"},
    {"label": "商卡3_价格区动态推荐", "x": 385, "y": 1477, "w": 800, "h": 70, "kind": "part"},
    {"label": "商卡3_价格区优惠标签", "x": 385, "y": 1547, "w": 800, "h": 48, "kind": "part"},
    {"label": "商品卡4_全季酒仙桥路店房型_border", "x": 18, "y": 1666, "w": 1188, "h": 398, "kind": "border"},
    {"label": "商品卡4_头图区", "x": 32, "y": 1680, "w": 330, "h": 300, "kind": "part"},
    {"label": "商品卡4_标题区", "x": 385, "y": 1675, "w": 800, "h": 65, "kind": "part"},
    {"label": "商品卡4_基础信息区", "x": 385, "y": 1740, "w": 800, "h": 80, "kind": "part"},
    {"label": "商品卡4_价格区", "x": 385, "y": 1820, "w": 800, "h": 83, "kind": "part"},
    {"label": "商品卡4_评分区酒店名称", "x": 385, "y": 1903, "w": 800, "h": 150, "kind": "part"},
    {"label": "大家还在搜_运营聚合卡", "x": 18, "y": 2134, "w": 1188, "h": 256, "kind": "hetero"},
    {"label": "商卡5_北京会议中心店被截断_border", "x": 18, "y": 2487, "w": 1188, "h": 213, "kind": "border"},
    {"label": "商卡5_头图区", "x": 32, "y": 2501, "w": 330, "h": 199, "kind": "part"},
    {"label": "商卡5_标题区", "x": 385, "y": 2493, "w": 800, "h": 58, "kind": "part"},
    {"label": "商卡5_评分区推荐理由", "x": 385, "y": 2551, "w": 800, "h": 149, "kind": "part"},
]
if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    annotate_image(INPUT, OUTPUT, tasks)
    print(f"DONE: {OUTPUT}\nregions = {len(tasks)}")
