import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imd_annotate_api import run_scene

# 坐标来源：读图内容逐卡判定（头图/标题/基础信息/标签/价格/下挂的类型与边界）+
# scan_rows.py 一次性找卡间留白补宏观边界。禁止逐卡 scan_card_regions/scan_textrows
# 调参重扫（见 SKILL.md「核心原则」）。

FX, FY = 10535, 24313  # 剧本杀_全部_1 画板偏移

tasks = [
    # 宏观组件
    {"label": "状态栏",         "x": 0, "y": 0,   "w": 1224, "h": 112, "kind": "macro"},
    {"label": "顶部导航搜索框",  "x": 0, "y": 165, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "Tab",           "x": 0, "y": 285, "w": 1224, "h": 100, "kind": "macro"},
    # 顶部双并排运营聚合卡
    {"label": "运营聚合卡_剧本好评榜",  "x": 18,  "y": 410, "w": 585, "h": 426, "kind": "hetero"},
    {"label": "运营聚合卡_人气推荐场次", "x": 624, "y": 410, "w": 582, "h": 426, "kind": "hetero"},
    # 快筛/排序/筛选器
    {"label": "快筛排序筛选器",  "x": 0, "y": 920, "w": 1224, "h": 120, "kind": "macro"},
]

# 剧本杀商卡：头图(左) + 标题 + 评分 + 基础信息 + 标签 + 图文下挂
sm_cards = [
    ("商卡1", 1041, 1055, 1130, 1200, 1265, 1420, 1548),
    ("商卡2", 1601, 1615, 1690, 1760, 1825, 1980, 2103),
    ("商卡3被截断", 2161, 2175, 2250, 2320, 2385, 2540, 2700),
]
for cname, y_img, y_title, y_score, y_info, y_tag, y_hang, y_bottom in sm_cards:
    img_h = 290
    tasks.append({"label": f"{cname}_border", "x": 18, "y": y_img, "w": 1188, "h": y_bottom - y_img, "kind": "border"})
    tasks.append({"label": f"{cname}_头图区", "x": 32, "y": y_img, "w": 278, "h": img_h, "kind": "part"})
    tasks.append({"label": f"{cname}_标题区", "x": 330, "y": y_title, "w": 861, "h": 66, "kind": "part"})
    tasks.append({"label": f"{cname}_评分区", "x": 330, "y": y_score, "w": 861, "h": 60, "kind": "part"})
    tasks.append({"label": f"{cname}_基础信息区", "x": 330, "y": y_info, "w": 861, "h": 58, "kind": "part"})
    tasks.append({"label": f"{cname}_标签区", "x": 330, "y": y_tag, "w": 861, "h": 130, "kind": "part"})
    tasks.append({"label": f"{cname}_下挂区图文下挂", "x": 18, "y": y_hang, "w": 1188, "h": y_bottom - y_hang, "kind": "part"})

created = run_scene(FX, FY, tasks, "剧本杀_1")
with open('/tmp/anno_jubensha1.json', 'w') as f:
    json.dump(created, f, ensure_ascii=False, indent=2)
print("DONE jubensha1, count=", len(created))
