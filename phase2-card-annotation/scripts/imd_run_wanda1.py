import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imd_annotate_api import run_scene

# 坐标来源：读图内容逐卡判定（头图/标题/基础信息/标签/价格/下挂的类型与边界）+
# scan_rows.py 一次性找卡间留白补宏观边界。禁止逐卡 scan_card_regions/scan_textrows
# 调参重扫（见 SKILL.md「核心原则」）。

FX, FY = 3229, 12357  # 万达广场_全部_1 画板偏移

# 像素坐标 (scale=1)。顶部原型信息栏(约115~160)不标注。
tasks = [
    # —— 宏观组件（通栏）——
    {"label": "状态栏",          "x": 0,   "y": 0,    "w": 1224, "h": 112, "kind": "macro"},
    {"label": "顶部导航搜索框",   "x": 0,   "y": 165,  "w": 1224, "h": 120, "kind": "macro"},
    {"label": "Tab",            "x": 0,   "y": 285,  "w": 1224, "h": 100, "kind": "macro"},
    # 商卡1（地标/商场卡）
    {"label": "地标卡_border",    "x": 18,  "y": 520,  "w": 1188, "h": 445, "kind": "border"},
    {"label": "地标卡_头图区",     "x": 32,  "y": 531,  "w": 278,  "h": 274, "kind": "part"},
    {"label": "地标卡_标题区",     "x": 330, "y": 531,  "w": 861,  "h": 75,  "kind": "part"},
    {"label": "地标卡_基础信息区",  "x": 330, "y": 610,  "w": 861,  "h": 160, "kind": "part"},
    # 注：此区域实际为神券/满减等文字型下挂内容，应判为「文字下挂区」而非「标签区」
    {"label": "地标卡_文字下挂区",   "x": 330, "y": 815,  "w": 861,  "h": 150, "kind": "part"},
    # 图筛
    {"label": "图筛",            "x": 0,   "y": 1041, "w": 1224, "h": 160, "kind": "macro"},
    # 快筛/排序/筛选器
    {"label": "快筛排序筛选器",    "x": 0,   "y": 1201, "w": 1224, "h": 111, "kind": "macro"},
    # 商卡2（沙胆彪炭炉牛杂煲，商家卡片）
    {"label": "商卡2_border",     "x": 18,  "y": 1312, "w": 1188, "h": 808, "kind": "border"},
    {"label": "商卡2_头图区",      "x": 32,  "y": 1312, "w": 278,  "h": 274, "kind": "part"},
    {"label": "商卡2_标题区",      "x": 330, "y": 1372, "w": 861,  "h": 80,  "kind": "part"},
    {"label": "商卡2_基础信息区",   "x": 330, "y": 1460, "w": 861,  "h": 120, "kind": "part"},
    {"label": "商卡2_标签区",      "x": 330, "y": 1588, "w": 861,  "h": 66,  "kind": "part"},
    {"label": "商卡2_下挂区图文下挂","x": 18,  "y": 1662, "w": 1188, "h": 458, "kind": "part"},
    # 商卡3（四川饭店，商家卡片，底部被截断）
    {"label": "商卡3被截断_border", "x": 18,  "y": 2191, "w": 1188, "h": 509, "kind": "border"},
    {"label": "商卡3_头图区",      "x": 32,  "y": 2191, "w": 278,  "h": 274, "kind": "part"},
    {"label": "商卡3_标题区",      "x": 330, "y": 2191, "w": 861,  "h": 72,  "kind": "part"},
    {"label": "商卡3_基础信息区",   "x": 330, "y": 2265, "w": 861,  "h": 120, "kind": "part"},
    {"label": "商卡3_标签区",      "x": 330, "y": 2390, "w": 861,  "h": 60,  "kind": "part"},
    {"label": "商卡3_下挂区图文下挂","x": 18,  "y": 2480, "w": 1188, "h": 220, "kind": "part"},
]

created = run_scene(FX, FY, tasks, "万达_1")
with open('/tmp/anno_wanda1.json', 'w') as f:
    json.dump(created, f, ensure_ascii=False, indent=2)
print("DONE wanda1, count=", len(created))
