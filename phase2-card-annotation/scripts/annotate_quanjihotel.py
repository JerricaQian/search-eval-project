"""全季酒店_全部_1_副本 本地截图标注。

识别为酒店商家卡（左图右文）：每卡按实际可见内容独立标注头图、标题、
评分区、基础信息、标签、价格与动态推荐；第 3 张卡在底部被截图截断。
营销/内容运营聚合区独立标为宏观组件，不计入商卡。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "全季酒店_全部_1_副本.png")
OUTPUT_DIR = os.path.join(ROOT, "out")
OUTPUT = os.path.join(OUTPUT_DIR, "全季酒店_全部_1_副本_annotated.png")

# 坐标均以本截图实际画面内容为准。先画宏观组件/商卡边界，再画各卡分区。
tasks = [
    # 顶部宏观组件
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 96, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 96, "w": 1224, "h": 172, "kind": "macro"},
    # 北京酒店指南、酒店内容卡及预约入口是独立内容运营聚合，不是商卡。
    {"label": "运营聚合卡", "x": 18, "y": 278, "w": 1188, "h": 847, "kind": "hetero"},
    {"label": "日期区", "x": 18, "y": 1150, "w": 390, "h": 133, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 410, "y": 1150, "w": 796, "h": 133, "kind": "macro"},
    {"label": "营销横幅", "x": 18, "y": 1283, "w": 1188, "h": 152, "kind": "macro"},

    # 商卡1：全季酒店(北京望京科技园店)，酒店商家卡，左图右文。
    {"label": "商卡1_border", "x": 18, "y": 1480, "w": 1188, "h": 457, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 1494, "w": 330, "h": 344, "kind": "part"},
    {"label": "商卡1_标题区", "x": 385, "y": 1482, "w": 800, "h": 65, "kind": "part"},
    {"label": "商卡1_评分区", "x": 385, "y": 1547, "w": 800, "h": 121, "kind": "part"},
    {"label": "商卡1_基础信息区", "x": 385, "y": 1668, "w": 800, "h": 63, "kind": "part"},
    {"label": "商卡1_标签区", "x": 385, "y": 1731, "w": 800, "h": 70, "kind": "part"},
    {"label": "商卡1_价格区", "x": 385, "y": 1801, "w": 800, "h": 72, "kind": "part"},
    {"label": "商卡1_价格区动态推荐", "x": 385, "y": 1873, "w": 800, "h": 64, "kind": "part"},

    # 商卡2：全季酒店(北京望京花家地店)，与上一卡独立量取的 457px 高卡。
    {"label": "商卡2_border", "x": 18, "y": 1989, "w": 1188, "h": 457, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 2003, "w": 328, "h": 341, "kind": "part"},
    {"label": "商卡2_标题区", "x": 385, "y": 1992, "w": 800, "h": 65, "kind": "part"},
    {"label": "商卡2_评分区", "x": 385, "y": 2057, "w": 800, "h": 121, "kind": "part"},
    {"label": "商卡2_基础信息区", "x": 385, "y": 2178, "w": 800, "h": 63, "kind": "part"},
    {"label": "商卡2_标签区", "x": 385, "y": 2241, "w": 800, "h": 69, "kind": "part"},
    {"label": "商卡2_价格区", "x": 385, "y": 2310, "w": 800, "h": 72, "kind": "part"},
    {"label": "商卡2_价格区动态推荐", "x": 385, "y": 2382, "w": 800, "h": 64, "kind": "part"},

    # 商卡3：全季酒店(北京798艺术区店)，仅标实际可见的截断内容。
    {"label": "商卡3被截断_border", "x": 18, "y": 2498, "w": 1188, "h": 202, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 2511, "w": 330, "h": 189, "kind": "part"},
    {"label": "商卡3_标题区", "x": 385, "y": 2501, "w": 800, "h": 67, "kind": "part"},
    {"label": "商卡3_评分区", "x": 385, "y": 2568, "w": 800, "h": 132, "kind": "part"},
]


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    annotate_image(INPUT, OUTPUT, tasks)
    print(f"DONE: {OUTPUT}")
    print(f"regions = {len(tasks)}")
