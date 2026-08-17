"""标注 screenshots/1/剧本杀_全部_1.png 的商卡结构。
复用 imd_run_jubensha1.py 的读图判定坐标（1224x2700 像素直接对应）。
卡片类型：商家卡片（左图右文 + 图文下挂）。
宏观组件：状态栏/顶部导航/Tab/运营聚合卡x2/快筛排序筛选器。
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from annotate_image import annotate_image

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "screenshots/1/剧本杀_全部_1.png"
OUTPUT = ROOT / "out/1/剧本杀_全部_1_annotated.png"

tasks = [
    # 宏观组件
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 112, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 165, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "Tab", "x": 0, "y": 285, "w": 1224, "h": 100, "kind": "macro"},
    # 顶部双并排运营聚合卡
    {"label": "运营聚合卡_剧本好评榜", "x": 18, "y": 410, "w": 585, "h": 426, "kind": "hetero"},
    {"label": "运营聚合卡_人气推荐场次", "x": 624, "y": 410, "w": 582, "h": 426, "kind": "hetero"},
    {"label": "快筛排序筛选器", "x": 0, "y": 920, "w": 1224, "h": 120, "kind": "macro"},
]

# 商卡结构：头图(左) + 标题 + 评分 + 基础信息 + 标签 + 图文下挂
# 坐标来源：imd_run_jubensha1.py 读图判定
sm_cards = [
    ("商卡1", 1055, 1055, 1130, 1200, 1265, 1420, 1548),
    ("商卡2", 1615, 1615, 1690, 1760, 1825, 1980, 2103),
    ("商卡3被截断", 2175, 2175, 2250, 2320, 2385, 2540, 2700),
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

if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    annotate_image(INPUT, OUTPUT, tasks)
    print(f"OK: {OUTPUT} ({len(tasks)} tasks)")
