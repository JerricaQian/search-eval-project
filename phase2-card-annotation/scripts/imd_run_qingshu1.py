import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imd_annotate_api import run_scene

# 坐标来源：读图内容逐卡判定（头图/标题/基础信息/标签/价格/下挂的类型与边界）+
# scan_rows.py 一次性找卡间留白补宏观边界。禁止逐卡 scan_card_regions/scan_textrows
# 调参重扫（见 SKILL.md「核心原则」）。

FX, FY = 10535, 9368  # 给阿嬷的情书_全部_1 画板偏移（电影影院场次页）

tasks = [
    # 宏观组件
    {"label": "状态栏",         "x": 0, "y": 0,   "w": 1224, "h": 112, "kind": "macro"},
    {"label": "顶部导航搜索框",  "x": 0, "y": 165, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "Tab",           "x": 0, "y": 285, "w": 1224, "h": 100, "kind": "macro"},
    # 影片信息卡（头部聚合卡）
    {"label": "影片卡_border",   "x": 18,  "y": 355, "w": 1188, "h": 515, "kind": "border"},
    {"label": "影片卡_头图区",    "x": 60,  "y": 405, "w": 310,  "h": 429, "kind": "part"},
    {"label": "影片卡_标题区",    "x": 400, "y": 400, "w": 720,  "h": 78,  "kind": "part"},
    {"label": "影片卡_评分区",    "x": 400, "y": 485, "w": 500,  "h": 70,  "kind": "part"},
    {"label": "影片卡_基础信息区", "x": 400, "y": 585, "w": 730,  "h": 255, "kind": "part"},
    # 场次日期Tab（日期选择横滑条）
    {"label": "场次日期Tab",     "x": 18,  "y": 912, "w": 1188, "h": 95,  "kind": "macro"},
]

# 影院场次卡：影院名(含右侧距离)+价格+基础信息(地址/时间)，纯文字卡无头图
show_cards = [
    ("场次卡1", 1050, 1057, 1139, 1212),
    ("场次卡2", 1300, 1330, 1409, 1483),
    ("场次卡3", 1575, 1602, 1682, 1759),
    ("场次卡4", 1850, 1882, 1961, 2035),
    ("场次卡5", 2120, 2154, 2233, 2307),
    ("场次卡6被截断", 2400, 2434, 2514, 2586),
]
for cname, ctop, y_name, y_price, y_info in show_cards:
    cbottom = min(ctop + 277, 2700)
    tasks.append({"label": f"{cname}_border", "x": 18, "y": ctop, "w": 1188, "h": cbottom - ctop, "kind": "border"})
    tasks.append({"label": f"{cname}_影院名基础信息区", "x": 40, "y": y_name, "w": 1100, "h": 56, "kind": "part"})
    tasks.append({"label": f"{cname}_价格区", "x": 40, "y": y_price, "w": 500, "h": 56, "kind": "part"})
    tasks.append({"label": f"{cname}_基础信息区", "x": 40, "y": y_info, "w": 900, "h": 46, "kind": "part"})

created = run_scene(FX, FY, tasks, "给阿嬷_1")
with open('/tmp/anno_qingshu1.json', 'w') as f:
    json.dump(created, f, ensure_ascii=False, indent=2)
print("DONE qingshu1, count=", len(created))
