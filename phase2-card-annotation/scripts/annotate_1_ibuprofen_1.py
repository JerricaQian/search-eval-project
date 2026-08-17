"""布洛芬搜索结果页第 1 屏：独立标注任务表。"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from annotate_image import annotate_image

# 本图：搜索框下存在完整文字 Tab + 图标图筛（品牌筛选）+ 纯文字快筛；主体为 4 张商品卡。
# 扫描分析：状态栏0-120, 顶部导航120-215, Tab 299-355, 图筛410-581, 快筛605-638,
#   商卡1: 638-1142, 商卡2: 1256-1758, 商卡3: 1758-2260, 商卡4(截断): 2260-2613
tasks = [
    # ====== 顶部宏观组件 ======
    {"label": "状态栏",        "x": 0,    "y": 0,    "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 18,   "y": 120,  "w": 1188, "h": 95,  "kind": "macro"},
    {"label": "Tab",          "x": 18,   "y": 299,  "w": 1188, "h": 56,  "kind": "macro"},
    {"label": "图筛",          "x": 18,   "y": 410,  "w": 1188, "h": 171, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 18,   "y": 605,  "w": 1188, "h": 33,  "kind": "macro"},

    # ====== 商卡1: 商品卡-左图右文 ======
    {"label": "商卡1_border",         "x": 18,   "y": 638,  "w": 1188, "h": 504, "kind": "border"},
    {"label": "商卡1_头图区",          "x": 32,   "y": 638,  "w": 320,  "h": 504, "kind": "part"},
    {"label": "商卡1_标题区",          "x": 365,  "y": 750,  "w": 825,  "h": 48,  "kind": "part"},
    {"label": "商卡1_标签区",          "x": 365,  "y": 996,  "w": 825,  "h": 36,  "kind": "part"},
    {"label": "商卡1_价格区",          "x": 365,  "y": 1106, "w": 825,  "h": 36,  "kind": "part"},

    # ====== 商卡2: 商品卡-左图右文 ======
    {"label": "商卡2_border",         "x": 18,   "y": 1256, "w": 1188, "h": 502, "kind": "border"},
    {"label": "商卡2_头图区",          "x": 32,   "y": 1256, "w": 320,  "h": 332, "kind": "part"},
    {"label": "商卡2_标题区",          "x": 365,  "y": 1260, "w": 825,  "h": 53,  "kind": "part"},
    {"label": "商卡2_标签区",          "x": 365,  "y": 1491, "w": 825,  "h": 52,  "kind": "part"},
    {"label": "商卡2_价格区",          "x": 365,  "y": 1637, "w": 825,  "h": 36,  "kind": "part"},
    {"label": "商卡2_商家区",          "x": 365,  "y": 1572, "w": 825,  "h": 37,  "kind": "part"},

    # ====== 商卡3: 商品卡-左图右文 ======
    {"label": "商卡3_border",         "x": 18,   "y": 1758, "w": 1188, "h": 502, "kind": "border"},
    {"label": "商卡3_头图区",          "x": 32,   "y": 1758, "w": 320,  "h": 332, "kind": "part"},
    {"label": "商卡3_标题区",          "x": 365,  "y": 1762, "w": 825,  "h": 53,  "kind": "part"},
    {"label": "商卡3_标签区",          "x": 365,  "y": 1905, "w": 825,  "h": 36,  "kind": "part"},
    {"label": "商卡3_价格区",          "x": 365,  "y": 1993, "w": 825,  "h": 192, "kind": "part"},

    # ====== 商卡4: 被截断 ======
    {"label": "商卡4_border",         "x": 18,   "y": 2260, "w": 1188, "h": 353, "kind": "border"},
    {"label": "商卡4_头图区",          "x": 32,   "y": 2260, "w": 320,  "h": 353, "kind": "part"},
    {"label": "商卡4_标题区",          "x": 365,  "y": 2260, "w": 825,  "h": 38,  "kind": "part"},
    {"label": "商卡4_标签区",          "x": 365,  "y": 2379, "w": 825,  "h": 37,  "kind": "part"},
    {"label": "商卡4_价格区",          "x": 365,  "y": 2475, "w": 825,  "h": 138, "kind": "part"},
]
if __name__ == "__main__":
    out = ROOT / "out/1/布洛芬_全部_1_annotated.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    annotate_image(str(ROOT / "screenshots/1/布洛芬_全部_1.png"), str(out), tasks)
    print(out)
