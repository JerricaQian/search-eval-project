"""生理盐水搜索结果页第 3 屏：独立标注任务表。"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from annotate_image import annotate_image

# 搜索框下直接为纯文字快筛；无 Tab、无图筛。四张主体为商品卡；末尾费力度评分卡为运营模块。
tasks = [
 {"label":"状态栏","x":0,"y":0,"w":1224,"h":120,"kind":"macro"},
 {"label":"顶部导航搜索框","x":18,"y":120,"w":1188,"h":95,"kind":"macro"},
 {"label":"快筛排序筛选器","x":18,"y":215,"w":1188,"h":194,"kind":"macro"},
 {"label":"商卡1_border","x":18,"y":409,"w":1188,"h":353,"kind":"border"},
 {"label":"商卡1_头图区","x":32,"y":409,"w":332,"h":332,"kind":"part"},
 {"label":"商卡1_标题区","x":365,"y":414,"w":825,"h":114,"kind":"part"},
 {"label":"商卡1_标签区","x":365,"y":556,"w":825,"h":36,"kind":"part"},
 {"label":"商卡1_价格区","x":365,"y":645,"w":825,"h":51,"kind":"part"},
 {"label":"商卡1_商家区","x":365,"y":700,"w":825,"h":62,"kind":"part"},
 {"label":"商卡2_border","x":18,"y":790,"w":1188,"h":469,"kind":"border"},
 {"label":"商卡2_头图区","x":32,"y":911,"w":332,"h":332,"kind":"part"},
 {"label":"商卡2_标题区","x":365,"y":790,"w":825,"h":240,"kind":"part"},
 {"label":"商卡2_标签区","x":365,"y":1058,"w":825,"h":36,"kind":"part"},
 {"label":"商卡2_价格区","x":365,"y":1147,"w":825,"h":51,"kind":"part"},
 {"label":"商卡2_商家区","x":365,"y":1222,"w":825,"h":37,"kind":"part"},
 {"label":"商卡3_border","x":18,"y":1474,"w":1188,"h":355,"kind":"border"},
 {"label":"商卡3_头图区","x":33,"y":1565,"w":331,"h":187,"kind":"part"},
 {"label":"商卡3_标题区","x":365,"y":1474,"w":825,"h":114,"kind":"part"},
 {"label":"商卡3_标签区","x":365,"y":1616,"w":825,"h":36,"kind":"part"},
 {"label":"商卡3_价格区","x":365,"y":1705,"w":825,"h":51,"kind":"part"},
 {"label":"商卡3_商家区","x":365,"y":1780,"w":825,"h":49,"kind":"part"},
 {"label":"商卡4_border","x":18,"y":1976,"w":1188,"h":353,"kind":"border"},
 {"label":"商卡4_头图区","x":32,"y":1976,"w":332,"h":332,"kind":"part"},
 {"label":"商卡4_标题区","x":365,"y":1981,"w":825,"h":114,"kind":"part"},
 {"label":"商卡4_标签区","x":365,"y":2123,"w":825,"h":36,"kind":"part"},
 {"label":"商卡4_价格区","x":365,"y":2212,"w":825,"h":51,"kind":"part"},
 {"label":"商卡4_商家区","x":365,"y":2292,"w":825,"h":37,"kind":"part"},
 {"label":"运营聚合卡_费力度评分","x":18,"y":2483,"w":1188,"h":217,"kind":"macro"},
]
if __name__ == "__main__":
 out=ROOT/"out/2/生理盐水_全部_3_annotated.png"; out.parent.mkdir(parents=True,exist_ok=True)
 annotate_image(str(ROOT/"screenshots/2/生理盐水_全部_3.png"),str(out),tasks); print(out)
