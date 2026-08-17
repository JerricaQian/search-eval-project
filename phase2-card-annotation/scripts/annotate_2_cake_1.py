"""生日蛋糕第 1 屏：按当前截图独立校准。"""
from annotate_image import annotate_image

# Tab 下方是异构运营卡（含双列商品与品类入口），不是图筛。
# 该事实由当前截图读图确认；后续通用流程在 SceneSpec.page_context 中强制声明。
tasks = [
    {"label": "状态栏", "x": 0, "y": 0, "w": 1224, "h": 120, "kind": "macro"},
    {"label": "顶部导航搜索框", "x": 18, "y": 120, "w": 1188, "h": 121, "kind": "macro"},
    {"label": "Tab", "x": 18, "y": 241, "w": 1188, "h": 106, "kind": "macro"},
    {"label": "运营聚合卡", "x": 18, "y": 404, "w": 1188, "h": 866, "kind": "hetero"},
    {"label": "快筛排序筛选器", "x": 18, "y": 1392, "w": 1188, "h": 48, "kind": "macro"},
    {"label": "商卡1_border", "x": 18, "y": 1440, "w": 1188, "h": 746, "kind": "border"},
    {"label": "商卡1_头图区", "x": 58, "y": 1516, "w": 163, "h": 163, "kind": "part"},
    {"label": "商卡1_标题区", "x": 247, "y": 1508, "w": 940, "h": 56, "kind": "part"},
    {"label": "商卡1_基础信息区", "x": 247, "y": 1578, "w": 940, "h": 46, "kind": "part"},
    {"label": "商卡1_标签区", "x": 247, "y": 1640, "w": 940, "h": 45, "kind": "part"},
    {"label": "商卡1_下挂区", "x": 18, "y": 1745, "w": 1188, "h": 441, "kind": "part"},
    {"label": "商卡2被截断_border", "x": 18, "y": 2269, "w": 1188, "h": 431, "kind": "border"},
    {"label": "商卡2_头图区", "x": 58, "y": 2269, "w": 163, "h": 163, "kind": "part"},
    {"label": "商卡2_标题区", "x": 247, "y": 2260, "w": 940, "h": 58, "kind": "part"},
    {"label": "商卡2_基础信息区", "x": 247, "y": 2335, "w": 940, "h": 45, "kind": "part"},
    {"label": "商卡2_标签区", "x": 247, "y": 2404, "w": 940, "h": 45, "kind": "part"},
    {"label": "商卡2_下挂区", "x": 18, "y": 2567, "w": 1188, "h": 133, "kind": "part"},
]

if __name__ == "__main__":
    annotate_image(
        "/Users/qianjing/Desktop/search-eval-project/screenshots/生日蛋糕_全部_1.png",
        "/Users/qianjing/Desktop/search-eval-project/screenshots-out/生日蛋糕_全部_1_annotated.png",
        tasks,
    )
