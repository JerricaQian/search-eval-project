"""体检_全部_1：逐图语义识别后的本地标注任务表。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "2", "体检_全部_1.png")
OUTPUT = os.path.join(ROOT, "out", "2", "体检_全部_1_annotated.png")

tasks = [
    {"label":"状态栏","x":0,"y":0,"w":1224,"h":120,"kind":"macro"},
    {"label":"顶部导航搜索框","x":18,"y":120,"w":1188,"h":121,"kind":"macro"},
    {"label":"Tab","x":18,"y":299,"w":1188,"h":56,"kind":"macro"},
    # 女性/男性/父母体检等是带图标的分类项，完整覆盖图标和文字两行。
    {"label":"图筛","x":18,"y":414,"w":1188,"h":175,"kind":"macro"},
    {"label":"快筛排序筛选器","x":18,"y":605,"w":1188,"h":33,"kind":"macro"},

    # 京东体检(望京店)：商品套餐行属于纯文字下挂，并非独立价格区。
    {"label":"商卡1_border","x":18,"y":750,"w":1188,"h":385,"kind":"border"},
    {"label":"商卡1_头图区","x":32,"y":750,"w":320,"h":385,"kind":"part"},
    {"label":"商卡1_标题区","x":365,"y":750,"w":825,"h":48,"kind":"part"},
    {"label":"商卡1_商家信息区","x":365,"y":798,"w":825,"h":80,"kind":"part"},
    {"label":"商卡1_标签区","x":365,"y":878,"w":825,"h":45,"kind":"part"},
    {"label":"商卡1_文字下挂区","x":365,"y":923,"w":825,"h":212,"kind":"part"},

    # 爱康国宾体检中心(望京首开广场分院)。
    {"label":"商卡2_border","x":18,"y":1170,"w":1188,"h":376,"kind":"border"},
    {"label":"商卡2_头图区","x":32,"y":1170,"w":320,"h":376,"kind":"part"},
    {"label":"商卡2_标题区","x":365,"y":1170,"w":825,"h":36,"kind":"part"},
    {"label":"商卡2_商家信息区","x":365,"y":1206,"w":825,"h":82,"kind":"part"},
    {"label":"商卡2_标签区","x":365,"y":1288,"w":825,"h":45,"kind":"part"},
    {"label":"商卡2_文字下挂区","x":365,"y":1333,"w":825,"h":213,"kind":"part"},

    # 慈铭体检(望京南湖东园店)。
    {"label":"商卡3_border","x":18,"y":1580,"w":1188,"h":376,"kind":"border"},
    {"label":"商卡3_头图区","x":32,"y":1580,"w":320,"h":376,"kind":"part"},
    {"label":"商卡3_标题区","x":365,"y":1580,"w":825,"h":37,"kind":"part"},
    {"label":"商卡3_商家信息区","x":365,"y":1617,"w":825,"h":81,"kind":"part"},
    {"label":"商卡3_标签区","x":365,"y":1698,"w":825,"h":48,"kind":"part"},
    {"label":"商卡3_文字下挂区","x":365,"y":1746,"w":825,"h":210,"kind":"part"},

    # 美年大健康体检中心(酒仙桥分院)。
    {"label":"商卡4_border","x":18,"y":1990,"w":1188,"h":375,"kind":"border"},
    {"label":"商卡4_头图区","x":32,"y":2045,"w":320,"h":320,"kind":"part"},
    {"label":"商卡4_标题区","x":365,"y":1990,"w":825,"h":37,"kind":"part"},
    {"label":"商卡4_商家信息区","x":365,"y":2027,"w":825,"h":81,"kind":"part"},
    {"label":"商卡4_标签区","x":365,"y":2108,"w":825,"h":48,"kind":"part"},
    {"label":"商卡4_文字下挂区","x":365,"y":2156,"w":825,"h":209,"kind":"part"},

    # 底部下一卡仅保留原图中可见部分。
    {"label":"商卡5被截断_border","x":18,"y":2400,"w":1188,"h":300,"kind":"border"},
    {"label":"商卡5_头图区","x":32,"y":2518,"w":320,"h":182,"kind":"part"},
    {"label":"商卡5_标题区","x":365,"y":2400,"w":825,"h":36,"kind":"part"},
    {"label":"商卡5_商家信息区","x":365,"y":2436,"w":825,"h":82,"kind":"part"},
    {"label":"商卡5_标签区","x":365,"y":2518,"w":825,"h":45,"kind":"part"},
    {"label":"商卡5_文字下挂区","x":365,"y":2563,"w":825,"h":137,"kind":"part"},
]
if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    annotate_image(INPUT, OUTPUT, tasks)
    print(f"DONE: {OUTPUT}; regions={len(tasks)}")
