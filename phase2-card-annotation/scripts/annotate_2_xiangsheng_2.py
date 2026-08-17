"""标注 screenshots/2/相声_全部_2.png 的演出票务卡。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from annotate_image import annotate_image

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "screenshots/2/相声_全部_2.png"
OUTPUT = ROOT / "out/2/相声_全部_2_annotated.png"

tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 121, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 241, "w": 1224, "h": 58, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 299, "w": 1224, "h": 56, "kind": "macro"},
    {"label": "运营聚合卡", "x": 18, "y": 378, "w": 1188, "h": 550, "kind": "hetero"},
]

cards = [
    ("商卡1", 928, 1408, 986, 1036, 1054, 1101, 1126, 1226, 1256, 1293),
    ("商卡2", 1408, 1837, 1333, 1381, 1458, 1505, 1524, 1706, 1747, 1800),
    ("商卡3", 1837, 2282, 1872, 1919, 1940, 1988, 2022, 2120, 2161, 2209),
    ("商卡4被截断", 2282, 2700, 2286, 2333, 2355, 2398, 2436, 2542, 2575, 2623),
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
