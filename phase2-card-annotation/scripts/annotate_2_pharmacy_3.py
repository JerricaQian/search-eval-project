"""药店_全部_3 独立标注任务表。"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
from annotate_image import annotate_image
# 本图仅纯文字 Tab/快筛，未出现图标图筛或营销横幅。
tasks=[
 {"label":"状态栏","x":0,"y":0,"w":1224,"h":120,"kind":"macro"},{"label":"顶部导航搜索框","x":18,"y":120,"w":1188,"h":121,"kind":"macro"},{"label":"Tab","x":18,"y":302,"w":1188,"h":40,"kind":"macro"},{"label":"快筛排序筛选器","x":18,"y":371,"w":1188,"h":30,"kind":"macro"},
 {"label":"商卡1_叮当快药_border","x":18,"y":512,"w":1188,"h":480,"kind":"border"},{"label":"商卡1_头图区","x":32,"y":512,"w":320,"h":177,"kind":"part"},{"label":"商卡1_标题区_叮当快药","x":365,"y":512,"w":825,"h":47,"kind":"part"},{"label":"商卡1_商家信息区","x":365,"y":588,"w":825,"h":36,"kind":"part"},{"label":"商卡1_标签区","x":365,"y":653,"w":825,"h":36,"kind":"part"},{"label":"商卡1_图文下挂区","x":32,"y":728,"w":1162,"h":264,"kind":"part"},
 {"label":"商卡2_叮当智慧药房_border","x":18,"y":1012,"w":1188,"h":695,"kind":"border"},{"label":"商卡2_头图区","x":32,"y":1012,"w":320,"h":392,"kind":"part"},{"label":"商卡2_标题区_叮当智慧药房","x":365,"y":1012,"w":825,"h":40,"kind":"part"},{"label":"商卡2_商家信息区","x":365,"y":1064,"w":825,"h":43,"kind":"part"},{"label":"商卡2_标签区","x":365,"y":1124,"w":825,"h":35,"kind":"part"},{"label":"商卡2_图文下挂区","x":32,"y":1227,"w":1162,"h":480,"kind":"part"},
 {"label":"商卡3_民生大药房_border","x":18,"y":1727,"w":1188,"h":695,"kind":"border"},{"label":"商卡3_头图区","x":32,"y":1727,"w":320,"h":195,"kind":"part"},{"label":"商卡3_标题区_民生大药房","x":365,"y":1727,"w":825,"h":43,"kind":"part"},{"label":"商卡3_商家信息区","x":365,"y":1779,"w":825,"h":43,"kind":"part"},{"label":"商卡3_标签区","x":365,"y":1839,"w":825,"h":34,"kind":"part"},{"label":"商卡3_图文下挂区","x":32,"y":1942,"w":1162,"h":480,"kind":"part"},
 {"label":"商卡4被截断_border","x":18,"y":2442,"w":1188,"h":258,"kind":"border"},{"label":"商卡4_头图区","x":32,"y":2442,"w":320,"h":258,"kind":"part"},{"label":"商卡4_标题区","x":365,"y":2442,"w":825,"h":38,"kind":"part"},{"label":"商卡4_商家信息区","x":365,"y":2487,"w":825,"h":55,"kind":"part"},{"label":"商卡4_标签区","x":365,"y":2554,"w":825,"h":35,"kind":"part"}]
if __name__=='__main__':
 out=ROOT/'out/2/药店_全部_3_annotated.png'; out.parent.mkdir(parents=True,exist_ok=True)
 annotate_image(str(ROOT/'screenshots/2/药店_全部_3.png'),str(out),tasks); print(out)
