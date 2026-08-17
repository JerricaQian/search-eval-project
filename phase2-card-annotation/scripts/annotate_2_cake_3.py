"""生日蛋糕第 3 屏：列表续屏，不继承 Tab/图筛。"""
from annotate_image import annotate_image

# 顶部为上一张商卡的续段：快筛行后是该卡的横滑商品下挂。
tasks = [
    {"label": "商卡1被截断_border", "x": 18, "y": 0, "w": 1188, "h": 1080, "kind": "border"},
    {"label": "商卡1_下挂区", "x": 18, "y": 404, "w": 1188, "h": 650, "kind": "part"},
    {"label": "商卡2_border", "x": 18, "y": 842, "w": 1188, "h": 711, "kind": "border"},
    {"label": "商卡2_标题区", "x": 247, "y": 850, "w": 940, "h": 62, "kind": "part"},
    {"label": "商卡2_基础信息区", "x": 247, "y": 930, "w": 940, "h": 50, "kind": "part"},
    {"label": "商卡2_标签区", "x": 247, "y": 1000, "w": 940, "h": 110, "kind": "part"},
    {"label": "商卡2_下挂区", "x": 18, "y": 1158, "w": 1188, "h": 395, "kind": "part"},
    {"label": "商卡3_border", "x": 18, "y": 1599, "w": 1188, "h": 724, "kind": "border"},
    {"label": "商卡3_标题区", "x": 247, "y": 1625, "w": 940, "h": 58, "kind": "part"},
    {"label": "商卡3_基础信息区", "x": 247, "y": 1700, "w": 940, "h": 50, "kind": "part"},
    {"label": "商卡3_标签区", "x": 247, "y": 1775, "w": 940, "h": 100, "kind": "part"},
    {"label": "商卡3_下挂区", "x": 18, "y": 1928, "w": 1188, "h": 395, "kind": "part"},
    {"label": "商卡4被截断_border", "x": 18, "y": 2403, "w": 1188, "h": 297, "kind": "border"},
    {"label": "商卡4_标题区", "x": 247, "y": 2392, "w": 940, "h": 62, "kind": "part"},
    {"label": "商卡4_基础信息区", "x": 247, "y": 2468, "w": 940, "h": 50, "kind": "part"},
    {"label": "商卡4_标签区", "x": 247, "y": 2545, "w": 940, "h": 100, "kind": "part"},
]

if __name__ == "__main__":
    annotate_image(
        "/Users/qianjing/Desktop/search-eval-project/screenshots/生日蛋糕_全部_3.png",
        "/Users/qianjing/Desktop/search-eval-project/screenshots-out/生日蛋糕_全部_3_annotated.png",
        tasks,
    )
