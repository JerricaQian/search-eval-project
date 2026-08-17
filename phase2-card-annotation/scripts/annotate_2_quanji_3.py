"""独立标注 screenshots/2/全季酒店_全部_3.png（酒店商家卡续页）。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "2", "全季酒店_全部_3.png")
OUTPUT = os.path.join(ROOT, "out", "2", "全季酒店_全部_3_annotated.png")

def hotel_tasks(index, name, top, bottom, image_h):
    # 本页每张卡按自己的实际顶/底及独立头图高度生成，不平移复用前页坐标。
    x, tw = 385, 800
    return [
        {"label": f"商卡{index}_{name}_border", "x": 18, "y": top, "w": 1188, "h": bottom-top, "kind": "border"},
        {"label": f"商卡{index}_头图区", "x": 32, "y": top+14, "w": 330, "h": image_h, "kind": "part"},
        {"label": f"商卡{index}_标题区", "x": x, "y": top+8, "w": tw, "h": 55, "kind": "part"},
        {"label": f"商卡{index}_评分区推荐理由", "x": x, "y": top+63, "w": tw, "h": 62, "kind": "part"},
        {"label": f"商卡{index}_位置信息区", "x": x, "y": top+125, "w": tw, "h": 62, "kind": "part"},
        {"label": f"商卡{index}_标签区", "x": x, "y": top+187, "w": tw, "h": 65, "kind": "part"},
        {"label": f"商卡{index}_价格区", "x": x, "y": top+252, "w": tw, "h": 70, "kind": "part"},
        {"label": f"商卡{index}_价格区动态推荐", "x": x, "y": top+322, "w": tw, "h": 65, "kind": "part"},
        {"label": f"商卡{index}_价格区优惠标签", "x": x, "y": top+387, "w": tw, "h": max(35, bottom-top-395), "kind": "part"},
    ]

tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 0, "y": 120, "w": 1224, "h": 121, "kind": "macro"},
    {"label": "日期区", "x": 18, "y": 241, "w": 390, "h": 123, "kind": "macro"},
    {"label": "快筛排序筛选器", "x": 408, "y": 241, "w": 798, "h": 123, "kind": "macro"},
    # scan_rows 给出：上方续卡 371-752；本页完整卡 804-1261、1313-1770、1822-2279；底部截断卡 2328-2700。
    {"label": "商卡1_上方续卡被截断_border", "x": 18, "y": 371, "w": 1188, "h": 381, "kind": "border"},
    {"label": "商卡1_头图区", "x": 32, "y": 385, "w": 330, "h": 350, "kind": "part"},
    {"label": "商卡1_标题区", "x": 385, "y": 380, "w": 800, "h": 55, "kind": "part"},
    {"label": "商卡1_评分区推荐理由", "x": 385, "y": 435, "w": 800, "h": 62, "kind": "part"},
    {"label": "商卡1_位置信息区", "x": 385, "y": 497, "w": 800, "h": 62, "kind": "part"},
    {"label": "商卡1_标签区", "x": 385, "y": 559, "w": 800, "h": 65, "kind": "part"},
    {"label": "商卡1_价格区", "x": 385, "y": 624, "w": 800, "h": 70, "kind": "part"},
    {"label": "商卡1_价格区动态推荐", "x": 385, "y": 694, "w": 800, "h": 48, "kind": "part"},
]
tasks += hotel_tasks(2, "全季芍药居对外经贸店", 804, 1261, 343)
tasks += hotel_tasks(3, "全季奥林匹克国家会议中心店", 1313, 1770, 343)
tasks += hotel_tasks(4, "全季国展三元桥地铁站店", 1822, 2279, 343)
tasks += [
    {"label": "商卡5_北京会议中心店被截断_border", "x": 18, "y": 2328, "w": 1188, "h": 372, "kind": "border"},
    {"label": "商卡5_头图区", "x": 32, "y": 2342, "w": 330, "h": 344, "kind": "part"},
    {"label": "商卡5_标题区", "x": 385, "y": 2336, "w": 800, "h": 55, "kind": "part"},
    {"label": "商卡5_评分区推荐理由", "x": 385, "y": 2391, "w": 800, "h": 62, "kind": "part"},
    {"label": "商卡5_位置信息区", "x": 385, "y": 2453, "w": 800, "h": 62, "kind": "part"},
    {"label": "商卡5_标签区", "x": 385, "y": 2515, "w": 800, "h": 65, "kind": "part"},
    {"label": "商卡5_价格区", "x": 385, "y": 2580, "w": 800, "h": 65, "kind": "part"},
    {"label": "商卡5_价格区动态推荐", "x": 385, "y": 2645, "w": 800, "h": 55, "kind": "part"},
]
if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    annotate_image(INPUT, OUTPUT, tasks)
    print(f"DONE: {OUTPUT}\nregions = {len(tasks)}")
