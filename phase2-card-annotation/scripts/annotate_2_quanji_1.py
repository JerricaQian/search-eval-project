"""独立标注 screenshots/2/全季酒店_全部_1.png（酒店商家卡）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "2", "全季酒店_全部_1.png")
OUTPUT = os.path.join(ROOT, "out", "2", "全季酒店_全部_1_annotated.png")

# 第 1 页整页 scan_rows：卡片为 1480-1937、1989-2446、2498-2700；
# 卡 1 文本列另行扫描，按可见酒店文案独立划分各字段。
tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 96, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 96, "w": 1224, "h": 172, "kind": "macro"},
    {"label": "运营聚合卡", "x": 18, "y": 278, "w": 1188, "h": 847, "kind": "hetero"},
    {"label": "日期区", "x": 18, "y": 1150, "w": 390, "h": 133, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 410, "y": 1150, "w": 796, "h": 133, "kind": "macro"},
    {"label": "营销横幅", "x": 18, "y": 1283, "w": 1188, "h": 152, "kind": "macro"},
    {"label": "商卡1_全季望京科技园店_border", "x": 18, "y": 1480, "w": 1188, "h": 457, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 1494, "w": 330, "h": 344, "kind": "part"},
    {"label": "商卡1_标题区", "x": 385, "y": 1490, "w": 800, "h": 48, "kind": "part"},
    {"label": "商卡1_评分区推荐理由", "x": 385, "y": 1560, "w": 800, "h": 36, "kind": "part"},
    {"label": "商卡1_位置信息区", "x": 385, "y": 1625, "w": 800, "h": 35, "kind": "part"},
    {"label": "商卡1_标签区", "x": 385, "y": 1689, "w": 800, "h": 36, "kind": "part"},
    {"label": "商卡1_价格区", "x": 385, "y": 1754, "w": 800, "h": 36, "kind": "part"},
    {"label": "商卡1_价格区动态推荐", "x": 385, "y": 1821, "w": 800, "h": 49, "kind": "part"},
    {"label": "商卡1_价格区优惠标签", "x": 385, "y": 1897, "w": 800, "h": 33, "kind": "part"},
    {"label": "商卡2_全季望京花家地店_border", "x": 18, "y": 1989, "w": 1188, "h": 457, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 2003, "w": 328, "h": 341, "kind": "part"},
    {"label": "商卡2_标题区", "x": 385, "y": 2000, "w": 800, "h": 55, "kind": "part"},
    {"label": "商卡2_评分区推荐理由", "x": 385, "y": 2055, "w": 800, "h": 62, "kind": "part"},
    {"label": "商卡2_位置信息区", "x": 385, "y": 2117, "w": 800, "h": 57, "kind": "part"},
    {"label": "商卡2_标签区", "x": 385, "y": 2174, "w": 800, "h": 65, "kind": "part"},
    {"label": "商卡2_价格区", "x": 385, "y": 2239, "w": 800, "h": 70, "kind": "part"},
    {"label": "商卡2_价格区动态推荐", "x": 385, "y": 2309, "w": 800, "h": 68, "kind": "part"},
    {"label": "商卡2_价格区优惠标签", "x": 385, "y": 2377, "w": 800, "h": 60, "kind": "part"},
    {"label": "商卡3_全季798艺术区店被截断_border", "x": 18, "y": 2498, "w": 1188, "h": 202, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 2511, "w": 330, "h": 189, "kind": "part"},
    {"label": "商卡3_标题区", "x": 385, "y": 2501, "w": 800, "h": 67, "kind": "part"},
    {"label": "商卡3_评分区推荐理由", "x": 385, "y": 2568, "w": 800, "h": 132, "kind": "part"},
]

if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    annotate_image(INPUT, OUTPUT, tasks)
    print(f"DONE: {OUTPUT}\nregions = {len(tasks)}")
