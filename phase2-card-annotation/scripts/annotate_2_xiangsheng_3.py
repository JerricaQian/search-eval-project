"""标注 screenshots/2/相声_全部_3.png 的演出票务卡。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from annotate_image import annotate_image

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "screenshots/2/相声_全部_3.png"
OUTPUT = ROOT / "out/2/相声_全部_3_annotated.png"

tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 121, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 241, "w": 1224, "h": 58, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 0, "y": 299, "w": 1224, "h": 56, "kind": "macro"},
]

# 本图前三张规则演出卡后，出现独立的预约聚合模块；它作为异构运营组件完整取框。
regular = [
    ("商卡1", 436, 837, 436, 484, 513, 548, 580, 678, 719, 767),
    ("商卡2", 837, 1238, 837, 885, 913, 949, 978, 1079, 1120, 1168),
    ("商卡3", 1238, 1629, 1238, 1286, 1314, 1350, 1382, 1480, 1521, 1569),
]
for name, top, bottom, title0, title1, score0, score1, info0, info1, price0, price1 in regular:
    tasks += [
        {"label": f"{name}_border", "x": 18, "y": top, "w": 1188, "h": bottom - top, "kind": "border"},
        {"label": f"{name}_头图区", "x": 32, "y": title0, "w": 278, "h": price1 - title0, "kind": "part"},
        {"label": f"{name}_标题区", "x": 330, "y": title0, "w": 860, "h": title1 - title0, "kind": "part"},
        {"label": f"{name}_评分区", "x": 330, "y": score0, "w": 860, "h": score1 - score0, "kind": "part"},
        {"label": f"{name}_演出信息区", "x": 330, "y": info0, "w": 860, "h": info1 - info0, "kind": "part"},
        {"label": f"{name}_价格区", "x": 330, "y": price0, "w": 860, "h": price1 - price0, "kind": "part"},
        {"label": f"{name}_预约抢票文字下挂区", "x": 330, "y": price1, "w": 860, "h": bottom - price1 - 12, "kind": "part"},
    ]

tasks += [
    {"label": "运营聚合卡", "x": 18, "y": 1646, "w": 1188, "h": 288, "kind": "hetero"},
    {"label": "商卡4被截断_border", "x": 18, "y": 2012, "w": 1188, "h": 688, "kind": "border"},
    {"label": "商卡4_头图区", "x": 32, "y": 2016, "w": 278, "h": 337, "kind": "part"},
    {"label": "商卡4_标题区", "x": 330, "y": 2016, "w": 860, "h": 47, "kind": "part"},
    {"label": "商卡4_评分区", "x": 330, "y": 2084, "w": 860, "h": 45, "kind": "part"},
    {"label": "商卡4_演出信息区", "x": 330, "y": 2167, "w": 860, "h": 97, "kind": "part"},
    {"label": "商卡4_价格区", "x": 330, "y": 2305, "w": 860, "h": 48, "kind": "part"},
    {"label": "商卡4_预约抢票文字下挂区", "x": 330, "y": 2487, "w": 860, "h": 201, "kind": "part"},
]

if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    annotate_image(INPUT, OUTPUT, tasks)
    print(f"OK: {OUTPUT} ({len(tasks)} tasks)")
