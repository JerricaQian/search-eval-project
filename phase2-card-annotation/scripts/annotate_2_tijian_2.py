"""体检_全部_2：逐图语义识别后的本地标注任务表。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "2", "体检_全部_2.png")
OUTPUT = os.path.join(ROOT, "out", "2", "体检_全部_2_annotated.png")

tasks = [
    {"label":"状态栏","x":0,"y":0,"w":1224,"h":120,"kind":"macro"},
    {"label":"顶部导航搜索框","x":18,"y":120,"w":1188,"h":121,"kind":"macro"},
    {"label":"Tab","x":18,"y":299,"w":1188,"h":48,"kind":"macro"},
    # 健康证等带插画的分类项构成图筛，纯文字排序项另取快筛框。
    {"label":"图筛","x":18,"y":391,"w":1188,"h":126,"kind":"macro"},
    {"label":"快筛排序筛选器","x":18,"y":552,"w":1188,"h":36,"kind":"macro"},

    {"label":"商卡1_border","x":18,"y":670,"w":1188,"h":258,"kind":"border"},
    {"label":"商卡1_头图区","x":32,"y":670,"w":320,"h":258,"kind":"part"},
    {"label":"商卡1_标题区","x":365,"y":670,"w":825,"h":55,"kind":"part"},
    {"label":"商卡1_商家信息区","x":365,"y":725,"w":825,"h":70,"kind":"part"},
    {"label":"商卡1_标签区","x":365,"y":795,"w":825,"h":45,"kind":"part"},
    {"label":"商卡1_文字下挂区","x":365,"y":840,"w":825,"h":88,"kind":"part"},

    {"label":"商卡2_border","x":18,"y":960,"w":1188,"h":378,"kind":"border"},
    {"label":"商卡2_头图区","x":32,"y":960,"w":320,"h":258,"kind":"part"},
    {"label":"商卡2_标题区","x":365,"y":960,"w":825,"h":39,"kind":"part"},
    {"label":"商卡2_商家信息区","x":365,"y":999,"w":825,"h":81,"kind":"part"},
    {"label":"商卡2_标签区","x":365,"y":1080,"w":825,"h":48,"kind":"part"},
    {"label":"商卡2_文字下挂区","x":365,"y":1128,"w":825,"h":210,"kind":"part"},

    {"label":"商卡3_border","x":18,"y":1365,"w":1188,"h":386,"kind":"border"},
    {"label":"商卡3_头图区","x":32,"y":1365,"w":320,"h":261,"kind":"part"},
    {"label":"商卡3_标题区","x":365,"y":1365,"w":825,"h":44,"kind":"part"},
    {"label":"商卡3_商家信息区","x":365,"y":1409,"w":825,"h":81,"kind":"part"},
    {"label":"商卡3_标签区","x":365,"y":1490,"w":825,"h":45,"kind":"part"},
    {"label":"商卡3_文字下挂区","x":365,"y":1535,"w":825,"h":216,"kind":"part"},

    {"label":"商卡4_border","x":18,"y":1781,"w":1188,"h":404,"kind":"border"},
    {"label":"商卡4_头图区","x":32,"y":1781,"w":320,"h":285,"kind":"part"},
    {"label":"商卡4_标题区","x":365,"y":1781,"w":825,"h":37,"kind":"part"},
    {"label":"商卡4_商家信息区","x":365,"y":1818,"w":825,"h":82,"kind":"part"},
    {"label":"商卡4_标签区","x":365,"y":1900,"w":825,"h":50,"kind":"part"},
    {"label":"商卡4_文字下挂区","x":365,"y":1950,"w":825,"h":235,"kind":"part"},

    {"label":"商卡5被截断_border","x":18,"y":2228,"w":1188,"h":411,"kind":"border"},
    {"label":"商卡5_头图区","x":32,"y":2228,"w":320,"h":258,"kind":"part"},
    {"label":"商卡5_标题区","x":365,"y":2228,"w":825,"h":48,"kind":"part"},
    {"label":"商卡5_商家信息区","x":365,"y":2276,"w":825,"h":82,"kind":"part"},
    {"label":"商卡5_标签区","x":365,"y":2358,"w":825,"h":48,"kind":"part"},
    {"label":"商卡5_文字下挂区","x":365,"y":2406,"w":825,"h":233,"kind":"part"},
]
if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    annotate_image(INPUT, OUTPUT, tasks)
    print(f"DONE: {OUTPUT}; regions={len(tasks)}")
