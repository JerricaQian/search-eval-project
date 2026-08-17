import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imd_annotate_api import run_scene

# 坐标来源：读图内容逐卡判定（头图/标题/基础信息/标签/价格/下挂的类型与边界）+
# scan_rows.py 一次性找卡间留白补宏观边界。禁止逐卡 scan_card_regions/scan_textrows
# 调参重扫（见 SKILL.md「核心原则」）。

FX, FY = 10535, 401  # 电竞房_全部_1 画板偏移（双列瀑布流）

tasks = [
    # 宏观组件
    {"label": "状态栏",         "x": 0, "y": 0,   "w": 1224, "h": 112, "kind": "macro"},
    {"label": "顶部导航搜索框",  "x": 0, "y": 165, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "Tab",           "x": 0, "y": 285, "w": 1224, "h": 100, "kind": "macro"},
    {"label": "快筛排序筛选器",  "x": 0, "y": 413, "w": 1224, "h": 100, "kind": "macro"},
]

# 竖版酒店卡分区（左列卡为基准，相对绝对像素）
def card_parts(cname, ox, oy):
    return [
        {"label": f"{cname}_border",   "x": 15+ox,  "y": 515+oy, "w": 582, "h": 772, "kind": "border"},
        {"label": f"{cname}_头图区",    "x": 15+ox,  "y": 515+oy, "w": 582, "h": 411, "kind": "part"},
        {"label": f"{cname}_标题区",    "x": 30+ox,  "y": 950+oy, "w": 555, "h": 75,  "kind": "part"},
        {"label": f"{cname}_基础信息区", "x": 30+ox,  "y": 1030+oy,"w": 555, "h": 155, "kind": "part"},
        {"label": f"{cname}_价格区",    "x": 30+ox,  "y": 1160+oy,"w": 500, "h": 78,  "kind": "part"},
        {"label": f"{cname}_评分区",    "x": 30+ox,  "y": 1242+oy,"w": 555, "h": 50,  "kind": "part"},
    ]

COL_DX = 607   # 右列相对左列的 x 偏移
ROW_DY = 838   # 下一行的 y 偏移

# 第1行：左列卡1 + 右列卡1
tasks += card_parts("左1_特惠双人电竞兄弟房", 0, 0)
tasks += card_parts("右1_畅游电竞臻品商旅", COL_DX, 0)
# 第2行：左列卡2 + 右列卡2
tasks += card_parts("左2_畅享电竞双床房", 0, ROW_DY)
tasks += card_parts("右2_望京soho合生麒麟社", COL_DX, ROW_DY)
# 第3行左列卡3（底部截断，仅露头图）；右列为"大家还在搜"推荐词模块
tasks += [
    {"label": "左3_可长租4070显卡PS5被截断_border", "x": 15, "y": 2191, "w": 582, "h": 509, "kind": "border"},
    {"label": "左3_头图区", "x": 15, "y": 2191, "w": 582, "h": 411, "kind": "part"},
    {"label": "左3_标题区", "x": 30, "y": 2620, "w": 555, "h": 80, "kind": "part"},
    # 右列：搜索推荐词模块（大家还在搜）
    {"label": "运营聚合卡_大家还在搜", "x": 622, "y": 2130, "w": 590, "h": 570, "kind": "hetero"},
]

created = run_scene(FX, FY, tasks, "电竞房_1")
with open('/tmp/anno_dianjing1.json', 'w') as f:
    json.dump(created, f, ensure_ascii=False, indent=2)
print("DONE dianjing1, count=", len(created))
