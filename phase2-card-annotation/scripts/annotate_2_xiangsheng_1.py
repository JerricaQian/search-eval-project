"""标注 screenshots/2/相声_全部_1.png 的演出票务卡。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from annotate_image import annotate_image

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "screenshots/2/相声_全部_1.png"
OUTPUT = ROOT / "out/2/相声_全部_1_annotated.png"

# 逐图的整图与右侧文本列 scan_rows 加读图语义，顶部没有虚构图筛或营销横幅。
tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 121, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 241, "w": 1224, "h": 58, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 299, "w": 1224, "h": 56, "kind": "macro"},
]
# 每张演出卡均为：竖版海报、演出标题、评分、日期/场馆、价格、预约抢票下挂。
cards = [
    ("商卡1", 414, 818, 414, 462, 491, 526, 558, 656, 697, 745),
    ("商卡2", 818, 1232, 822, 869, 891, 935, 972, 1070, 1111, 1159),
    ("商卡3", 1232, 1631, 1236, 1283, 1305, 1351, 1377, 1475, 1506, 1543),
    ("商卡4", 1704, 2115, 1708, 1755, 1777, 1821, 1858, 1956, 1997, 2045),
    ("商卡5被截断", 2115, 2700, 2115, 2163, 2192, 2227, 2259, 2357, 2398, 2446),
]
for name, top, bottom, title0, title1, score0, score1, info0, info1, price0, price1 in cards:
    tasks += [
        {"label": f"{name}_border", "x": 18, "y": top, "w": 1188, "h": bottom - top, "kind": "border"},
        {"label": f"{name}_头图区", "x": 32, "y": title0, "w": 278, "h": min(bottom - 12, price1) - title0, "kind": "part"},
        {"label": f"{name}_标题区", "x": 330, "y": title0, "w": 860, "h": title1 - title0, "kind": "part"},
        {"label": f"{name}_评分区", "x": 330, "y": score0, "w": 860, "h": score1 - score0, "kind": "part"},
        {"label": f"{name}_演出信息区", "x": 330, "y": info0, "w": 860, "h": info1 - info0, "kind": "part"},
        {"label": f"{name}_价格区", "x": 330, "y": price0, "w": 860, "h": price1 - price0, "kind": "part"},
        {"label": f"{name}_预约抢票文字下挂区", "x": 330, "y": price1, "w": 860, "h": max(0, bottom - price1 - 12), "kind": "part"},
    ]

if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    annotate_image(INPUT, OUTPUT, tasks)
    print(f"OK: {OUTPUT} ({len(tasks)} tasks)")
