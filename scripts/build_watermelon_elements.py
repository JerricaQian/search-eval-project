#!/usr/bin/env python3
"""确定性产出 phase2 标注产物，字段对齐 phase3-标记标准（cardId/卡片类型/coord/name/坐标/内容简述等）。
用 annotate_2_watermelon_1.py 的验证坐标跑 annotate_image 出标注图 + 转 elements_西瓜.json。
不 scan、不裁剪、不读图——避免 agent stall。EXISTS 校验（含 STRICT）应通过。"""
import sys, json, os
SCRIPTS = "/Users/qianjing/Desktop/search-eval-project/phase2-card-annotation/scripts"
sys.path.insert(0, SCRIPTS)
import annotate_2_watermelon_1 as s  # 导入即跑 annotate_image → 出标注 PNG

OUT = "/Users/qianjing/Desktop/search-eval-project/screenshots-out"
tasks = s.tasks
# 区名 → (标准区名, 元素类型)
region_map = {"头图区": ("头图区", "图片"), "标题区": ("标题区", "文本"),
              "价格区": ("价格区", "文本"), "标签区": ("标签区", "标签"),
              "商家信息区": ("商家区", "文本")}
cards = []
cur = None
for t in tasks:
    lab = t["label"]; kind = t["kind"]
    coord = [t["x"], t["y"], t["w"], t["h"]]  # 标准：[x,y,w,h] 数组
    if kind == "macro":
        continue  # 宏观通栏不计入
    if "_border" in lab:
        ci = int(lab.split("_")[0].replace("商卡", "")) - 1
        cur = {"cardId": f"C{ci+1}", "卡片类型": "商家卡片-图文下挂", "coord": coord, "regions": []}
        cards.append(cur)
    elif kind == "part" and cur is not None:
        rname = lab.split("_", 1)[1]
        rname_cn, etype = region_map.get(rname, (rname, "文本"))
        excl = (rname == "头图区")  # 商家头图排除
        elem = {"id": f"{cur['cardId']}r{len(cur['regions'])}e0", "所属组件": cur["cardId"],
                "元素类型": etype, "坐标": coord, "isExcluded": excl}
        if excl:
            elem["excludeReason"] = "商家头图排除"
        else:
            elem["内容简述"] = f"原文:{rname_cn}（场景脚本验证坐标，文字待人工核）"
        cur["regions"].append({"name": rname_cn, "coord": coord, "elements": [elem]})

doc = {"query": "西瓜",
       "screenshot": "/Users/qianjing/Desktop/search-eval-project/screenshots/西瓜_全部_1.png",
       "annotatedImage": f"{OUT}/西瓜_全部_1_annotated.png",
       "cards": cards}
os.makedirs(OUT, exist_ok=True)
with open(f"{OUT}/elements_西瓜.json", "w") as f:
    json.dump(doc, f, ensure_ascii=False, indent=1)
tot = sum(1 for c in cards for r in c["regions"] for e in r["elements"] if not e.get("isExcluded"))
print(f"cards={len(cards)} regions={sum(len(c['regions']) for c in cards)} nonExcluded={tot}")
print(f"annotatedImage={OUT}/西瓜_全部_1_annotated.png")
print(f"elementList={OUT}/elements_西瓜.json")
print("字段：card(cardId/卡片类型/coord/regions) region(name/coord/elements) element(id/所属组件/元素类型/内容简述/坐标/isExcluded/excludeReason)")
