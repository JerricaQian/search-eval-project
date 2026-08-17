#!/usr/bin/env python3
"""Generate element manifest for 喜力啤酒整箱 screenshot."""
import json
from pathlib import Path

PROJECT = Path("/Users/qianjing/Desktop/workproject_2/search-eval-project")
SCREENSHOT = str(PROJECT / "screenshots/喜力啤酒整箱_全部_1.png")

CARDS = [
    {"id": "C1", "ys": 710, "ye": 1056, "price": "89", "merchant": "超市便利"},
    {"id": "C2", "ys": 1273, "ye": 1619, "price": "95", "merchant": "便利店"},
    {"id": "C3", "ys": 1836, "ye": 2187, "price": "99", "merchant": "酒水专营"},
    {"id": "C4", "ys": 2335, "ye": 2683, "price": "109", "merchant": "超市便利"},
]

IMG_X, IMG_W = 32, 331
TXT_X, TXT_W = 396, 793
CARD_X, CARD_W = 18, 1206

def build_card(c):
    cid = c["id"]
    ys = c["ys"]
    ye = c["ye"]
    card_h = ye - ys + 1
    
    img_region = [IMG_X, ys + 6, IMG_W, IMG_W]
    title_region = [TXT_X, ys + 4, TXT_W, 47]
    meta_region = [TXT_X, ys + 72, TXT_W, 44]
    tag_region = [TXT_X, ys + 147, TXT_W, 36]
    price_region = [TXT_X, ys + 239, TXT_W, 48]
    merch_region = [TXT_X, ys + 312, TXT_W, 34]
    card_coord = [CARD_X, ys, CARD_W, card_h]
    
    elements_by_region = {
        "头图区": [{
            "id": f"{cid}-img-head",
            "所属组件": cid,
            "元素类型": "图片",
            "内容简述": "原文:喜力啤酒整箱商品主图",
            "坐标": img_region,
            "isExcluded": False,
            "excludeReason": "",
            "render": {"visibleStatus": "confirmed", "renderState": "normal", "sourceRegion": "头图区", "isPhoto": True, "isSystemUi": False}
        }],
        "标题区": [{
            "id": f"{cid}-title",
            "所属组件": cid,
            "元素类型": "文本",
            "内容简述": "原文:喜力Heineken啤酒拉格330ml*24罐整箱装",
            "坐标": title_region,
            "isExcluded": False,
            "excludeReason": "",
            "render": {"visibleStatus": "confirmed", "renderState": "normal", "sourceRegion": "标题区", "isPhoto": False, "isSystemUi": False},
            "textFacts": {"rawText": "喜力Heineken啤酒拉格330ml*24罐整箱装", "textStatus": "confirmed", "semanticRole": "title", "emphasisLevel": "high", "fontSizeBucket": "medium", "fontWeightBucket": "bold", "textColorRole": "neutral"}
        }],
        "基础信息区": [{
            "id": f"{cid}-meta-info",
            "所属组件": cid,
            "元素类型": "文本",
            "内容简述": "原文:规格330ml*24罐原麦汁浓度",
            "坐标": meta_region,
            "isExcluded": False,
            "excludeReason": "",
            "render": {"visibleStatus": "confirmed", "renderState": "normal", "sourceRegion": "基础信息区", "isPhoto": False, "isSystemUi": False},
            "textFacts": {"rawText": "规格330ml*24罐原麦汁浓度", "textStatus": "confirmed", "semanticRole": "specification", "emphasisLevel": "low", "fontSizeBucket": "small", "fontWeightBucket": "normal", "textColorRole": "neutral"}
        }],
        "标签区": [{
            "id": f"{cid}-tag-fulfillment",
            "所属组件": cid,
            "元素类型": "标签",
            "内容简述": "原文:闪购",
            "坐标": tag_region,
            "isExcluded": False,
            "excludeReason": "",
            "render": {"visibleStatus": "confirmed", "renderState": "normal", "sourceRegion": "标签区", "isPhoto": False, "isSystemUi": False},
            "visual": {"entityKind": "tag", "visualStatus": "confirmed", "isColored": True, "isShaped": True, "colorRole": "green", "backgroundColor": "green", "textColor": "white", "borderColor": "transparent", "hasGraphicAssist": False, "graphicType": "无", "styleKey": "tag|green|fulfillment|rect|无", "sourceRegion": "标签区", "semanticRole": "fulfillment", "containerShape": "rect", "graphicAssistRole": "无", "countedInComplexity": True, "countDecision": "counted", "dedupDecision": "unique", "dedupWithElementIds": []}
        }],
        "价格区": [{
            "id": f"{cid}-price",
            "所属组件": cid,
            "元素类型": "文本",
            "内容简述": f"原文:¥{c['price']}起",
            "坐标": price_region,
            "isExcluded": False,
            "excludeReason": "",
            "render": {"visibleStatus": "confirmed", "renderState": "normal", "sourceRegion": "价格区", "isPhoto": False, "isSystemUi": False},
            "textFacts": {"rawText": f"¥{c['price']}起", "textStatus": "confirmed", "semanticRole": "price", "emphasisLevel": "high", "fontSizeBucket": "large", "fontWeightBucket": "bold", "textColorRole": "red"}
        }],
        "商家区": [{
            "id": f"{cid}-merchant",
            "所属组件": cid,
            "元素类型": "文本",
            "内容简述": f"原文:{c['merchant']}附近门店",
            "坐标": merch_region,
            "isExcluded": False,
            "excludeReason": "",
            "render": {"visibleStatus": "confirmed", "renderState": "normal", "sourceRegion": "商家区", "isPhoto": False, "isSystemUi": False},
            "textFacts": {"rawText": f"{c['merchant']}附近门店", "textStatus": "confirmed", "semanticRole": "merchant", "emphasisLevel": "low", "fontSizeBucket": "small", "fontWeightBucket": "normal", "textColorRole": "neutral"}
        }]
    }
    
    region_order = ["头图区", "标题区", "基础信息区", "标签区", "价格区", "商家区"]
    region_coords = {"头图区": img_region, "标题区": title_region, "基础信息区": meta_region, "标签区": tag_region, "价格区": price_region, "商家区": merch_region}
    regions = [{"name": rn, "coord": region_coords[rn], "elements": elements_by_region[rn]} for rn in region_order]
    
    all_ids = [e["id"] for rn in region_order for e in elements_by_region[rn]]
    
    return {
        "cardId": cid,
        "卡片类型": "商品卡片",
        "coord": card_coord,
        "ownershipScope": "business",
        "businessCode": "flash_delivery",
        "businessName": "闪购",
        "businessConfidence": "high",
        "cardTypeCode": "product_left_image_right_text",
        "cardTypeName": "商品卡-左图右文",
        "classificationEvidence": ["左图右文商品卡布局", "即时零售闪购业态", "商品主图左置331px", "右侧含标题价格商家信息", "卡片高度约346-351px"],
        "structure": {
            "visibleStatus": "complete",
            "cardTypeCode": "product_left_image_right_text",
            "layoutMode": "left_image_right_text",
            "layoutSignature": "left_image_right_text|title>meta>tag>price>merchant",
            "comparisonGroupKey": "flash_delivery|product_left_image_right_text",
            "isResultListItem": True,
            "isHeterogeneous": False,
            "listPosition": int(cid[1]),
            "regions": [{"region": rn, "coord": region_coords[rn]} for rn in region_order],
            "layoutAnchors": {
                "image": img_region,
                "title": title_region,
                "primaryInfo": price_region
            },
            "layoutAnchorRelation": "image_left_of_text; title_above_primaryInfo"
        },
        "visualInventory": {
            "complete": True,
            "regions": {
                "头图区": [{"elementId": f"{cid}-img-head", "styleKey": "image|neutral|商品主图|rect|无", "countedInComplexity": True}],
                "标题区": [{"elementId": f"{cid}-title", "styleKey": "text|neutral|title|normal|无", "countedInComplexity": False}],
                "基础信息区": [{"elementId": f"{cid}-meta-info", "styleKey": "text|neutral|specification|normal|无", "countedInComplexity": False}],
                "标签区": [{"elementId": f"{cid}-tag-fulfillment", "styleKey": "tag|green|fulfillment|rect|无", "countedInComplexity": True}],
                "价格区": [{"elementId": f"{cid}-price", "styleKey": "text|red|price|large|无", "countedInComplexity": False}],
                "商家区": [{"elementId": f"{cid}-merchant", "styleKey": "text|neutral|merchant|normal|无", "countedInComplexity": False}],
            },
            "tagScanChecklist": [
                {"candidate": "闪购履约标", "status": "found", "checkedRegions": ["标签区", "基础信息区"], "elementIds": [f"{cid}-tag-fulfillment"], "visualBasis": "标签区检测到绿色闪购标签"},
                {"candidate": "保障标", "status": "not_found", "checkedRegions": ["标签区"], "elementIds": [], "visualBasis": "标签区未检测到保障相关标签"}
            ]
        },
        "factInventory": {"complete": True, "scanned": all_ids, "uncertainElementIds": []},
        "regions": regions
    }

page_facts = {
    "screen": 1,
    "isContinuation": False,
    "viewport": {"width": 1224, "height": 2700},
    "modules": [
        {"id": "M1", "moduleType": "search_bar", "coord": [0, 38, 1224, 41], "visibleStatus": "confirmed", "contentRole": "搜索框/返回导航", "isListPrefix": False, "isListItem": False},
        {"id": "M2", "moduleType": "tab", "coord": [0, 120, 1224, 91], "visibleStatus": "confirmed", "contentRole": "频道切换 全部/外卖/团购", "isListPrefix": False, "isListItem": False},
        {"id": "M3", "moduleType": "image_filter", "coord": [0, 296, 1224, 59], "visibleStatus": "confirmed", "contentRole": "图筛：啤酒整箱品类筛选", "isListPrefix": False, "isListItem": False},
        {"id": "M4", "moduleType": "quick_filter", "coord": [0, 423, 1224, 46], "visibleStatus": "confirmed", "contentRole": "排序/筛选条", "isListPrefix": False, "isListItem": False},
        {"id": "M5", "moduleType": "marketing_banner", "coord": [0, 528, 1224, 117], "visibleStatus": "confirmed", "contentRole": "营销横幅/优惠信息", "isListPrefix": True, "isListItem": False},
        {"id": "M6", "moduleType": "result_list", "coord": [0, 710, 1224, 1974], "visibleStatus": "confirmed", "contentRole": "商品搜索结果列表", "isListPrefix": False, "isListItem": False},
    ]
}

page_fact_inventory = {"complete": True, "scanned": ["M1", "M2", "M3", "M4", "M5", "M6"], "totalModules": 6, "resultListStart": 710, "firstCardY": 710, "uncertainModuleIds": []}

cards = [build_card(c) for c in CARDS]

relations = []
for c in cards:
    cid = c["cardId"]
    relations.append({"relationType": "title_to_image", "from": f"{cid}-title", "to": f"{cid}-img-head", "status": "confirmed", "evidence": f"{cid}商品标题与左侧商品主图对应同一商品"})
    relations.append({"relationType": "title_to_append", "from": f"{cid}-title", "to": f"{cid}-merchant", "status": "confirmed", "evidence": f"{cid}商家信息与商品标题属同一商品"})
for i in range(len(cards)-1):
    relations.append({"relationType": "same_field_across_cards", "from": f"C{i+1}-price", "to": f"C{i+2}-price", "status": "confirmed", "evidence": "相邻卡片价格区位于同一纵向位置"})

manifest = {
    "query": "喜力啤酒整箱",
    "screenshot": SCREENSHOT,
    "annotatedImage": "",
    "pageFacts": page_facts,
    "pageFactInventory": page_fact_inventory,
    "relations": relations,
    "cards": cards
}

out_path = PROJECT / "screenshots-out/elements_喜力啤酒整箱.json"
out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Written: {out_path}")
print(f"Cards: {len(cards)}, Relations: {len(relations)}")
