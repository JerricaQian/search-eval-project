"""药店_全部_2 独立标注任务表。"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
from annotate_image import annotate_image
# 无图筛；快筛后首张上半部分是商品横滑下挂，非营销横幅。
tasks=[
 {"label":"状态栏","x":0,"y":0,"w":1224,"h":120,"kind":"macro"},{"label":"顶部导航搜索框","x":18,"y":120,"w":1188,"h":121,"kind":"macro"},{"label":"Tab","x":18,"y":302,"w":1188,"h":40,"kind":"macro"},{"label":"快筛排序筛选器","x":18,"y":391,"w":1188,"h":152,"kind":"macro"},
 {"label":"商卡1_border","x":18,"y":563,"w":1188,"h":442,"kind":"border"},{"label":"商卡1_图文下挂区","x":32,"y":563,"w":1162,"h":147,"kind":"part"},{"label":"商卡1_头图区","x":32,"y":778,"w":320,"h":177,"kind":"part"},{"label":"商卡1_标题区_叮当优品器械健康用品店","x":365,"y":778,"w":825,"h":177,"kind":"part"},{"label":"商卡1_商家信息区","x":365,"y":955,"w":825,"h":50,"kind":"part"},
 {"label":"商卡2_好药师大药房_border","x":18,"y":1054,"w":1188,"h":480,"kind":"border"},{"label":"商卡2_头图区","x":32,"y":1054,"w":320,"h":177,"kind":"part"},{"label":"商卡2_标题区_好药师大药房","x":365,"y":1054,"w":825,"h":177,"kind":"part"},{"label":"商卡2_商家信息区","x":365,"y":1270,"w":825,"h":264,"kind":"part"},
 {"label":"商卡3_好一生大药房_border","x":18,"y":1554,"w":1188,"h":392,"kind":"border"},{"label":"商卡3_头图区","x":32,"y":1554,"w":320,"h":392,"kind":"part"},{"label":"商卡3_标题区_好一生大药房","x":365,"y":1554,"w":825,"h":38,"kind":"part"},{"label":"商卡3_商家信息区","x":365,"y":1603,"w":825,"h":44,"kind":"part"},{"label":"商卡3_标签区","x":365,"y":1666,"w":825,"h":34,"kind":"part"},{"label":"商卡3_图文下挂区","x":32,"y":1769,"w":1162,"h":177,"kind":"part"},
 {"label":"相似推荐提示","x":18,"y":1983,"w":1188,"h":266,"kind":"macro"},{"label":"大家还在搜","x":18,"y":2487,"w":1188,"h":151,"kind":"macro"}]
if __name__=='__main__':
 out=ROOT/'out/2/药店_全部_2_annotated.png'; out.parent.mkdir(parents=True,exist_ok=True)
 annotate_image(str(ROOT/'screenshots/2/药店_全部_2.png'),str(out),tasks); print(out)
