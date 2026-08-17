"""药店_全部_1 独立标注任务表。"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
from annotate_image import annotate_image
# 本图：Tab 下为图标图筛，随后为纯文字快筛；没有独立营销横幅。
tasks=[
 {"label":"状态栏","x":0,"y":0,"w":1224,"h":120,"kind":"macro"},
 {"label":"顶部导航搜索框","x":18,"y":120,"w":1188,"h":121,"kind":"macro"},
 {"label":"Tab","x":18,"y":299,"w":1188,"h":56,"kind":"macro"},
 {"label":"图筛","x":18,"y":428,"w":1188,"h":154,"kind":"macro"},
 {"label":"快筛排序筛选器","x":18,"y":605,"w":1188,"h":33,"kind":"macro"},
 {"label":"商卡1_border","x":18,"y":638,"w":1188,"h":417,"kind":"border"},
 {"label":"商卡1_头图区","x":32,"y":638,"w":320,"h":417,"kind":"part"},
 {"label":"商卡1_标题区","x":365,"y":638,"w":825,"h":115,"kind":"part"},
 {"label":"商卡1_商家信息区","x":365,"y":753,"w":825,"h":37,"kind":"part"},
 {"label":"商卡1_标签区","x":365,"y":878,"w":825,"h":47,"kind":"part"},
 {"label":"商卡1_图文下挂区","x":32,"y":925,"w":1162,"h":130,"kind":"part"},
 {"label":"商卡2_叮当智慧药房_border","x":18,"y":1094,"w":1188,"h":676,"kind":"border"},
 {"label":"商卡2_头图区","x":32,"y":1094,"w":320,"h":264,"kind":"part"},
 {"label":"商卡2_标题区_叮当智慧药房","x":365,"y":1094,"w":825,"h":264,"kind":"part"},
 {"label":"商卡2_商家信息区","x":365,"y":1378,"w":825,"h":38,"kind":"part"},
 {"label":"商卡2_标签区","x":365,"y":1430,"w":825,"h":42,"kind":"part"},
 {"label":"商卡2_图文下挂区","x":32,"y":1490,"w":1162,"h":280,"kind":"part"},
 {"label":"商卡3_叮当快药_border","x":18,"y":1812,"w":1188,"h":676,"kind":"border"},
 {"label":"商卡3_头图区","x":32,"y":1812,"w":320,"h":376,"kind":"part"},
 {"label":"商卡3_标题区_叮当快药","x":365,"y":1812,"w":825,"h":376,"kind":"part"},
 {"label":"商卡3_图文下挂区","x":32,"y":2205,"w":1162,"h":280,"kind":"part"},
 {"label":"商卡4被截断_border","x":18,"y":2524,"w":1188,"h":176,"kind":"border"},
 {"label":"商卡4_头图区","x":32,"y":2524,"w":320,"h":176,"kind":"part"},
 {"label":"商卡4_标题区","x":365,"y":2524,"w":825,"h":176,"kind":"part"},]
if __name__=='__main__':
 out=ROOT/'out/2/药店_全部_1_annotated.png'; out.parent.mkdir(parents=True,exist_ok=True)
 annotate_image(str(ROOT/'screenshots/2/药店_全部_1.png'),str(out),tasks); print(out)
