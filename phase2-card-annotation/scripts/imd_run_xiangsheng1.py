import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imd_annotate_api import run_scene

# 坐标来源：读图内容逐卡判定（头图/标题/基础信息/标签/价格/下挂的类型与边界）+
# scan_rows.py 一次性找卡间留白补宏观边界。禁止逐卡 scan_card_regions/scan_textrows
# 调参重扫（见 SKILL.md「核心原则」）。

FX, FY = 10535, 6379  # 相声_全部_1 画板偏移

# 宏观组件
tasks = [
    {"label": "状态栏",         "x": 0, "y": 0,   "w": 1224, "h": 112, "kind": "macro"},
    {"label": "顶部导航搜索框",  "x": 0, "y": 165, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "Tab",           "x": 0, "y": 285, "w": 1224, "h": 100, "kind": "macro"},
]

# 5 张演出票务商卡；卡间距约 465px。基准=卡1，其余整体平移。
# 卡1 各分区（绝对像素，来自文字行扫描）
base = {
    "border": (18, 355, 1188, 465),
    "头图区":  (32, 426, 278, 401),
    "标题区":  (330, 428, 861, 70),
    "评分区":  (330, 506, 500, 56),
    "日期区":  (330, 575, 600, 46),
    "价格区":  (330, 712, 500, 60),
    "场馆名":  (330, 782, 700, 52),  # 归入基础信息区语义
}
CARD_STEP = 465
CARD_NAMES = ["商卡1", "商卡2", "商卡3", "商卡4", "商卡5被截断"]
for idx, cname in enumerate(CARD_NAMES):
    dy = idx * CARD_STEP
    # border 先
    bx, by, bw, bh = base["border"]
    if idx == 4:  # 末卡截断，高度到画板底
        bh = 2700 - (by + dy)
    tasks.append({"label": f"{cname}_border", "x": bx, "y": by + dy, "w": bw, "h": bh, "kind": "border"})
    for part, key in [("头图区", "头图区"), ("标题区", "标题区"), ("评分区", "评分区"),
                      ("日期区", "日期区"), ("价格区", "价格区")]:
        px, py, pw, ph = base[key]
        tasks.append({"label": f"{cname}_{part}", "x": px, "y": py + dy, "w": pw, "h": ph, "kind": "part"})
    # 场馆名 归入 基础信息区
    px, py, pw, ph = base["场馆名"]
    tasks.append({"label": f"{cname}_基础信息区", "x": px, "y": py + dy, "w": pw, "h": ph, "kind": "part"})

created = run_scene(FX, FY, tasks, "相声_1")
with open('/tmp/anno_xiangsheng1.json', 'w') as f:
    json.dump(created, f, ensure_ascii=False, indent=2)
print("DONE xiangsheng1, count=", len(created))
