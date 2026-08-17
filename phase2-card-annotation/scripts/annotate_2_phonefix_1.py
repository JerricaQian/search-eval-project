"""手机维修全部_1：基于本图 scan_rows 与文案独立判定的本地标注任务表。"""
from annotate_image import annotate_image

TASKS = [
    {"label":"状态栏", "x":0,"y":0,"w":1224,"h":120,"kind":"macro"},
    {"label":"顶部导航搜索框", "x":18,"y":120,"w":1188,"h":121,"kind":"macro"},
    {"label":"Tab", "x":18,"y":299,"w":1188,"h":56,"kind":"macro"},
    # 该模块是带服务图标+文字的入口，不是纯文字快筛。
    {"label":"图筛", "x":18,"y":422,"w":1188,"h":152,"kind":"macro"},
    {"label":"快筛排序筛选器", "x":18,"y":605,"w":1188,"h":33,"kind":"macro"},

    {"label":"商卡1_border", "x":18,"y":750,"w":1188,"h":372,"kind":"border"},
    {"label":"商卡1_头图区", "x":32,"y":750,"w":320,"h":372,"kind":"part"},
    {"label":"商卡1_标题区", "x":365,"y":750,"w":825,"h":48,"kind":"part"},
    {"label":"商卡1_商家信息区", "x":365,"y":878,"w":825,"h":48,"kind":"part"},
    {"label":"商卡1_标签区", "x":365,"y":953,"w":825,"h":37,"kind":"part"},
    {"label":"商卡1_文字下挂区", "x":365,"y":1018,"w":825,"h":37,"kind":"part"},

    {"label":"商卡2_border", "x":18,"y":1164,"w":1188,"h":431,"kind":"border"},
    {"label":"商卡2_头图区", "x":32,"y":1164,"w":320,"h":431,"kind":"part"},
    {"label":"商卡2_标题区", "x":365,"y":1164,"w":825,"h":37,"kind":"part"},
    {"label":"商卡2_商家信息区", "x":365,"y":1235,"w":825,"h":37,"kind":"part"},
    {"label":"商卡2_标签区", "x":365,"y":1353,"w":825,"h":48,"kind":"part"},
    {"label":"商卡2_AI推荐理由", "x":365,"y":1428,"w":825,"h":37,"kind":"part"},
    {"label":"商卡2_文字下挂区", "x":365,"y":1493,"w":825,"h":37,"kind":"part"},

    {"label":"商卡3_border", "x":18,"y":1639,"w":1188,"h":439,"kind":"border"},
    {"label":"商卡3_头图区", "x":32,"y":1639,"w":320,"h":439,"kind":"part"},
    {"label":"商卡3_标题区", "x":365,"y":1639,"w":825,"h":36,"kind":"part"},
    {"label":"商卡3_商家信息区", "x":365,"y":1710,"w":825,"h":36,"kind":"part"},
    {"label":"商卡3_标签区", "x":365,"y":1828,"w":825,"h":48,"kind":"part"},
    {"label":"商卡3_文字下挂区", "x":365,"y":1903,"w":825,"h":102,"kind":"part"},

    {"label":"商卡4_border", "x":18,"y":2114,"w":1188,"h":447,"kind":"border"},
    {"label":"商卡4_头图区", "x":32,"y":2114,"w":320,"h":447,"kind":"part"},
    {"label":"商卡4_标题区", "x":365,"y":2114,"w":825,"h":36,"kind":"part"},
    {"label":"商卡4_商家信息区", "x":365,"y":2185,"w":825,"h":36,"kind":"part"},
    {"label":"商卡4_标签区", "x":365,"y":2303,"w":825,"h":48,"kind":"part"},
    {"label":"商卡4_文字下挂区", "x":365,"y":2378,"w":825,"h":102,"kind":"part"},
    {"label":"商卡5被截断_border", "x":18,"y":2595,"w":1188,"h":105,"kind":"border"},
    {"label":"商卡5_标题区", "x":365,"y":2595,"w":825,"h":37,"kind":"part"},
]

if __name__ == "__main__":
    annotate_image("screenshots/2/手机维修_全部_1.png", "out/2/手机维修_全部_1_annotated.png", TASKS)
    print(f"OK: {len(TASKS)} tasks")
