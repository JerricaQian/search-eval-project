"""生理盐水搜索结果页第 1 屏：独立标注任务表。"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from annotate_image import annotate_image

# 本图：搜索框下存在完整文字 Tab（全部/外卖/团购/地点/攻略），其下是纯文字快筛；无图筛、无营销横幅。
tasks = [
 {"label":"状态栏","x":0,"y":0,"w":1224,"h":120,"kind":"macro"},
 {"label":"顶部导航搜索框","x":18,"y":120,"w":1188,"h":95,"kind":"macro"},
 {"label":"Tab","x":18,"y":215,"w":1188,"h":140,"kind":"macro"},
 {"label":"快筛排序筛选器","x":18,"y":355,"w":1188,"h":116,"kind":"macro"},
 {"label":"商卡1_border","x":18,"y":471,"w":1188,"h":436,"kind":"border"},
 {"label":"商卡1_头图区","x":32,"y":554,"w":332,"h":332,"kind":"part"},
 {"label":"商卡1_标题区","x":365,"y":558,"w":825,"h":113,"kind":"part"},
 {"label":"商卡1_标签区","x":365,"y":701,"w":825,"h":36,"kind":"part"},
 {"label":"商卡1_价格区","x":365,"y":790,"w":825,"h":51,"kind":"part"},
 {"label":"商卡1_商家区","x":365,"y":870,"w":825,"h":37,"kind":"part"},
 {"label":"商卡2_border","x":18,"y":935,"w":1188,"h":474,"kind":"border"},
 {"label":"商卡2_头图区","x":32,"y":1056,"w":332,"h":332,"kind":"part"},
 {"label":"商卡2_标题区","x":365,"y":935,"w":825,"h":240,"kind":"part"},
 {"label":"商卡2_标签区","x":365,"y":1203,"w":825,"h":36,"kind":"part"},
 {"label":"商卡2_价格区","x":365,"y":1292,"w":825,"h":51,"kind":"part"},
 {"label":"商卡2_商家区","x":365,"y":1372,"w":825,"h":37,"kind":"part"},
 {"label":"商卡3_border","x":18,"y":1437,"w":1188,"h":474,"kind":"border"},
 {"label":"商卡3_头图区","x":32,"y":1558,"w":332,"h":332,"kind":"part"},
 {"label":"商卡3_标题区","x":365,"y":1437,"w":825,"h":240,"kind":"part"},
 {"label":"商卡3_标签区","x":365,"y":1705,"w":825,"h":36,"kind":"part"},
 {"label":"商卡3_价格区","x":365,"y":1794,"w":825,"h":51,"kind":"part"},
 {"label":"商卡3_商家区","x":365,"y":1874,"w":825,"h":37,"kind":"part"},
 {"label":"商卡4_border","x":18,"y":1939,"w":1188,"h":474,"kind":"border"},
 {"label":"商卡4_头图区","x":32,"y":2088,"w":332,"h":276,"kind":"part"},
 {"label":"商卡4_标题区","x":365,"y":1939,"w":825,"h":246,"kind":"part"},
 {"label":"商卡4_标签区","x":365,"y":2207,"w":825,"h":36,"kind":"part"},
 {"label":"商卡4_价格区","x":365,"y":2296,"w":825,"h":51,"kind":"part"},
 {"label":"商卡4_商家区","x":365,"y":2376,"w":825,"h":37,"kind":"part"},
 {"label":"商卡5被截断_border","x":18,"y":2441,"w":1188,"h":259,"kind":"border"},
 {"label":"商卡5_头图区","x":32,"y":2562,"w":332,"h":138,"kind":"part"},
 {"label":"商卡5_标题区","x":365,"y":2441,"w":825,"h":172,"kind":"part"},
 {"label":"商卡5_标签区","x":365,"y":2634,"w":825,"h":47,"kind":"part"},
]
if __name__ == "__main__":
 out=ROOT/"out/2/生理盐水_全部_1_annotated.png"; out.parent.mkdir(parents=True,exist_ok=True)
 annotate_image(str(ROOT/"screenshots/2/生理盐水_全部_1.png"),str(out),tasks); print(out)
