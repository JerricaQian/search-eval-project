"""生日蛋糕第 2 屏：列表续屏，不继承 Tab/图筛。"""
from annotate_image import annotate_image

# 顶部为上一张商卡的可见下挂续段；第一张完整可见商卡从 y=833 起。
tasks = [
    {"label": "商卡1被截断_border", "x": 18, "y": 0, "w": 1188, "h": 790, "kind": "border"},
    {"label": "商卡1_下挂区", "x": 18, "y": 391, "w": 1188, "h": 365, "kind": "part"},
    {"label": "商卡2_border", "x": 18, "y": 790, "w": 1188, "h": 771, "kind": "border"},
    {"label": "商卡2_头图区", "x": 58, "y": 833, "w": 163, "h": 163, "kind": "part"},
    {"label": "商卡2_标题区", "x": 247, "y": 836, "w": 940, "h": 55, "kind": "part"},
    {"label": "商卡2_基础信息区", "x": 247, "y": 905, "w": 940, "h": 50, "kind": "part"},
    {"label": "商卡2_标签区", "x": 247, "y": 970, "w": 940, "h": 43, "kind": "part"},
    {"label": "商卡2_下挂区", "x": 18, "y": 1120, "w": 1188, "h": 441, "kind": "part"},
    {"label": "商卡3_border", "x": 18, "y": 1603, "w": 1188, "h": 761, "kind": "border"},
    {"label": "商卡3_头图区", "x": 58, "y": 1644, "w": 163, "h": 163, "kind": "part"},
    {"label": "商卡3_标题区", "x": 247, "y": 1638, "w": 940, "h": 55, "kind": "part"},
    {"label": "商卡3_基础信息区", "x": 247, "y": 1710, "w": 940, "h": 45, "kind": "part"},
    {"label": "商卡3_标签区", "x": 247, "y": 1780, "w": 940, "h": 110, "kind": "part"},
    {"label": "商卡3_下挂区", "x": 18, "y": 1937, "w": 1188, "h": 400, "kind": "part"},
    {"label": "商卡4被截断_border", "x": 18, "y": 2414, "w": 1188, "h": 286, "kind": "border"},
    {"label": "商卡4_头图区", "x": 58, "y": 2414, "w": 163, "h": 163, "kind": "part"},
    {"label": "商卡4_标题区", "x": 247, "y": 2408, "w": 940, "h": 58, "kind": "part"},
    {"label": "商卡4_基础信息区", "x": 247, "y": 2480, "w": 940, "h": 45, "kind": "part"},
    {"label": "商卡4_标签区", "x": 247, "y": 2550, "w": 940, "h": 110, "kind": "part"},
]

if __name__ == "__main__":
    annotate_image(
        "/Users/qianjing/Desktop/search-eval-project/screenshots/生日蛋糕_全部_2.png",
        "/Users/qianjing/Desktop/search-eval-project/screenshots-out/生日蛋糕_全部_2_annotated.png",
        tasks,
    )
