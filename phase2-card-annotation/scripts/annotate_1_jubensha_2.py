"""标注 screenshots/1/剧本杀_全部_2.png 的商卡结构。
卡片类型：商家卡片（左图右文 + 图文下挂）。
逐卡读图判定：5张商卡（第5张被截断）。
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from annotate_image import annotate_image

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "screenshots/1/剧本杀_全部_2.png"
OUTPUT = ROOT / "out/1/剧本杀_全部_2_annotated.png"

tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 127, "kind": "macro"},
]

# 商卡：头图(左) + 标题 + 评分 + 基础信息 + 标签 + 图文下挂
# 逐卡读图判定分区坐标
cards = [
    # (name, top, bottom, title_y, title_h, score_y, score_h, info_y, info_h, tag_y, tag_h, hang_y)
    ("商卡1", 579, 906, 579, 47, 655, 34, 720, 34, 800, 36, 871),
    ("商卡2", 996, 1282, 1075, 97, 1185, 97, 0, 0, 0, 0, 0),  # 信息稀疏卡
    ("商卡3", 1364, 1692, 1364, 47, 1441, 33, 1505, 34, 1584, 37, 1656),
    ("商卡4", 1774, 2096, 1774, 47, 1850, 34, 1915, 35, 1981, 33, 2060),
    ("商卡5被截断", 2130, 2576, 2130, 37, 2249, 47, 2325, 34, 2389, 35, 2470),
]
for name, top, bottom, title_y, title_h, score_y, score_h, info_y, info_h, tag_y, tag_h, hang_y in cards:
    tasks.append({"label": f"{name}_border", "x": 18, "y": top, "w": 1188, "h": bottom - top, "kind": "border"})
    tasks.append({"label": f"{name}_头图区", "x": 32, "y": top, "w": 278, "h": 290, "kind": "part"})
    tasks.append({"label": f"{name}_标题区", "x": 330, "y": title_y, "w": 861, "h": title_h, "kind": "part"})
    if score_h > 0:
        tasks.append({"label": f"{name}_评分区", "x": 330, "y": score_y, "w": 861, "h": score_h, "kind": "part"})
    if info_h > 0:
        tasks.append({"label": f"{name}_基础信息区", "x": 330, "y": info_y, "w": 861, "h": info_h, "kind": "part"})
    if tag_h > 0:
        tasks.append({"label": f"{name}_标签区", "x": 330, "y": tag_y, "w": 861, "h": tag_h, "kind": "part"})
    tasks.append({"label": f"{name}_下挂区图文下挂", "x": 18, "y": hang_y, "w": 1188, "h": bottom - hang_y, "kind": "part"})

if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    annotate_image(INPUT, OUTPUT, tasks)
    print(f"OK: {OUTPUT} ({len(tasks)} tasks)")
