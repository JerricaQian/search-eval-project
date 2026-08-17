"""体检_全部_3：逐图语义识别后的本地标注任务表。"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from annotate_image import annotate_image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(ROOT, "screenshots", "2", "体检_全部_3.png")
OUTPUT = os.path.join(ROOT, "out", "2", "体检_全部_3_annotated.png")

tasks = [
    {"label":"状态栏","x":0,"y":0,"w":1224,"h":120,"kind":"macro"},
    {"label":"顶部导航搜索框","x":18,"y":120,"w":1188,"h":121,"kind":"macro"},
    {"label":"Tab","x":18,"y":299,"w":1188,"h":48,"kind":"macro"},
    {"label":"快筛排序筛选器","x":18,"y":381,"w":1188,"h":270,"kind":"macro"},
    # 无图片化分类图筛；快筛下方没有独立促销文案通栏，故不虚构营销横幅。

    # 五洲妇儿医院：预约挂号是服务入口；两条套餐是文字下挂。
    {"label":"商卡1_border","x":18,"y":702,"w":1188,"h":449,"kind":"border"},
    {"label":"商卡1_头图区","x":32,"y":702,"w":320,"h":449,"kind":"part"},
    {"label":"商卡1_标题区","x":365,"y":702,"w":825,"h":41,"kind":"part"},
    {"label":"商卡1_商家信息区","x":365,"y":743,"w":825,"h":70,"kind":"part"},
    {"label":"商卡1_标签区","x":365,"y":813,"w":825,"h":80,"kind":"part"},
    {"label":"商卡1_服务入口","x":365,"y":893,"w":825,"h":75,"kind":"part"},
    {"label":"商卡1_文字下挂区","x":365,"y":968,"w":825,"h":183,"kind":"part"},

    # 爱康国宾体检中心(北京亚运村分院)。
    {"label":"商卡2_border","x":18,"y":1183,"w":1188,"h":377,"kind":"border"},
    {"label":"商卡2_头图区","x":32,"y":1183,"w":320,"h":377,"kind":"part"},
    {"label":"商卡2_标题区","x":365,"y":1183,"w":825,"h":39,"kind":"part"},
    {"label":"商卡2_商家信息区","x":365,"y":1222,"w":825,"h":81,"kind":"part"},
    {"label":"商卡2_标签区","x":365,"y":1303,"w":825,"h":48,"kind":"part"},
    {"label":"商卡2_文字下挂区","x":365,"y":1351,"w":825,"h":209,"kind":"part"},

    # 北京来广营中医医院-健康检查中心。
    {"label":"商卡3_border","x":18,"y":1593,"w":1188,"h":370,"kind":"border"},
    {"label":"商卡3_头图区","x":32,"y":1720,"w":320,"h":243,"kind":"part"},
    {"label":"商卡3_标题区","x":365,"y":1593,"w":825,"h":39,"kind":"part"},
    {"label":"商卡3_商家信息区","x":365,"y":1632,"w":825,"h":88,"kind":"part"},
    {"label":"商卡3_标签区","x":365,"y":1720,"w":825,"h":53,"kind":"part"},
    {"label":"商卡3_文字下挂区","x":365,"y":1773,"w":825,"h":190,"kind":"part"},

    # 满意度调研为页面中插独立组件，不是商卡也不是营销横幅。
    {"label":"运营聚合卡","x":18,"y":1986,"w":1188,"h":298,"kind":"hetero"},

    # 中国中医科学院望京医院体检：在底部被截断，仅标可见区域。
    {"label":"商卡4被截断_border","x":18,"y":2375,"w":1188,"h":236,"kind":"border"},
    {"label":"商卡4_头图区","x":32,"y":2487,"w":320,"h":124,"kind":"part"},
    {"label":"商卡4_标题区","x":365,"y":2375,"w":825,"h":38,"kind":"part"},
    {"label":"商卡4_商家信息区","x":365,"y":2413,"w":825,"h":74,"kind":"part"},
    {"label":"商卡4_标签区","x":365,"y":2487,"w":825,"h":56,"kind":"part"},
    {"label":"商卡4_文字下挂区","x":365,"y":2543,"w":825,"h":68,"kind":"part"},

    {"label":"相似推荐提示","x":18,"y":2611,"w":1188,"h":89,"kind":"macro"},
]
if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    annotate_image(INPUT, OUTPUT, tasks)
    print(f"DONE: {OUTPUT}; regions={len(tasks)}")
