"""手机维修全部_3：基于本图 scan_rows 与文案独立判定的本地标注任务表。"""
from annotate_image import annotate_image

TASKS = [
    {"label":"状态栏", "x":0,"y":0,"w":1224,"h":120,"kind":"macro"},
    {"label":"顶部导航搜索框", "x":18,"y":120,"w":1188,"h":121,"kind":"macro"},
    {"label":"快筛排序筛选器", "x":18,"y":299,"w":1188,"h":48,"kind":"macro"},
    # “手机·电脑硬盘 / 企电脑 找速达”是服务入口组件，含图标与两行文案，不归为快筛。
    {"label":"营销横幅", "x":18,"y":371,"w":1188,"h":108,"kind":"macro"},

    {"label":"商卡1_border", "x":18,"y":632,"w":1188,"h":732,"kind":"border"},
    {"label":"商卡1_头图区", "x":32,"y":632,"w":320,"h":245,"kind":"part"},
    {"label":"商卡1_标题区", "x":365,"y":632,"w":825,"h":245,"kind":"part"},
    {"label":"商卡1_商家信息区", "x":365,"y":916,"w":825,"h":39,"kind":"part"},
    {"label":"商卡1_标签区", "x":365,"y":987,"w":825,"h":39,"kind":"part"},
    {"label":"商卡1_文字下挂区", "x":365,"y":1107,"w":825,"h":257,"kind":"part"},

    {"label":"商卡2_border", "x":18,"y":1517,"w":1188,"h":668,"kind":"border"},
    {"label":"商卡2_头图区", "x":32,"y":1517,"w":320,"h":258,"kind":"part"},
    {"label":"商卡2_标题区", "x":365,"y":1517,"w":825,"h":258,"kind":"part"},
    {"label":"商卡2_商家信息区", "x":365,"y":1809,"w":825,"h":42,"kind":"part"},
    {"label":"商卡2_标签区", "x":365,"y":1927,"w":825,"h":258,"kind":"part"},

    {"label":"商卡3_border", "x":18,"y":2256,"w":1188,"h":347,"kind":"border"},
    {"label":"商卡3_头图区", "x":32,"y":2256,"w":320,"h":131,"kind":"part"},
    {"label":"商卡3_标题区", "x":365,"y":2256,"w":825,"h":131,"kind":"part"},
    {"label":"商卡3_商家信息区", "x":365,"y":2463,"w":825,"h":94,"kind":"part"},
    {"label":"商卡3_文字下挂区", "x":365,"y":2567,"w":825,"h":36,"kind":"part"},
]

if __name__ == "__main__":
    annotate_image("screenshots/2/手机维修_全部_3.png", "out/2/手机维修_全部_3_annotated.png", TASKS)
    print(f"OK: {len(TASKS)} tasks")
