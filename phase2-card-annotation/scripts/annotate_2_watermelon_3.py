import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from annotate_image import annotate_image

ROOT = os.path.dirname(os.path.dirname(__file__))
INPUT = os.path.join(ROOT, "screenshots", "2", "西瓜_全部_3.png")
OUTPUT = os.path.join(ROOT, "out", "2", "西瓜_全部_3_annotated.png")

# 本图的快筛后依次为一张矮商品卡、真实冰品促销横幅和“大家还在搜”推荐模块；
# 它们均不按普通商卡模板套框。
tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 95, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 299, "w": 1224, "h": 48, "kind": "macro"},

    {"label": "商卡1_border", "x": 16, "y": 371, "w": 1192, "h": 267, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 371, "w": 332, "h": 121, "kind": "part"},
    {"label": "商卡1_标题区", "x": 396, "y": 398, "w": 794, "h": 49, "kind": "part"},
    {"label": "商卡1_标签区", "x": 396, "y": 471, "w": 794, "h": 37, "kind": "part"},
    {"label": "商卡1_商家信息区", "x": 396, "y": 537, "w": 794, "h": 101, "kind": "part"},

    # “冰品节·享超低价·立即抢购”为独立促销视觉，非商卡。
    {"label": "营销横幅", "x": 0, "y": 684, "w": 1224, "h": 270, "kind": "macro"},
    {"label": "运营聚合卡", "x": 0, "y": 982, "w": 1224, "h": 322, "kind": "macro"},

    {"label": "商卡2_border", "x": 16, "y": 1368, "w": 1192, "h": 353, "kind": "border"},
    {"label": "商卡2_头图区", "x": 32, "y": 1411, "w": 332, "h": 289, "kind": "part"},
    {"label": "商卡2_标题区", "x": 396, "y": 1421, "w": 794, "h": 143, "kind": "part"},
    {"label": "商卡2_价格区", "x": 396, "y": 1599, "w": 794, "h": 64, "kind": "part"},
    {"label": "商卡2_商家信息区", "x": 396, "y": 1680, "w": 794, "h": 41, "kind": "part"},

    {"label": "商卡3_border", "x": 16, "y": 1867, "w": 1192, "h": 346, "kind": "border"},
    {"label": "商卡3_头图区", "x": 32, "y": 1870, "w": 332, "h": 332, "kind": "part"},
    {"label": "商卡3_标题区", "x": 396, "y": 1867, "w": 794, "h": 134, "kind": "part"},
    {"label": "商卡3_价格区", "x": 396, "y": 2037, "w": 794, "h": 49, "kind": "part"},
    {"label": "商卡3_标签区", "x": 396, "y": 2092, "w": 794, "h": 62, "kind": "part"},
    {"label": "商卡3_商家信息区", "x": 396, "y": 2176, "w": 794, "h": 37, "kind": "part"},

    {"label": "商卡4_border", "x": 16, "y": 2366, "w": 1192, "h": 334, "kind": "border"},
    # 原图实际彩色商品图边界为 x=53..315、y=2396..2661；不把左侧留白并入头图。
    {"label": "商卡4_头图区", "x": 53, "y": 2396, "w": 262, "h": 265, "kind": "part"},
    {"label": "商卡4_标题区", "x": 396, "y": 2366, "w": 794, "h": 115, "kind": "part"},
    {"label": "商卡4_价格区", "x": 396, "y": 2600, "w": 794, "h": 49, "kind": "part"},
    {"label": "商卡4_标签区", "x": 396, "y": 2673, "w": 794, "h": 27, "kind": "part"},
]

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
annotate_image(INPUT, OUTPUT, tasks)
print(f"{OUTPUT}\n任务数: {len(tasks)}")
