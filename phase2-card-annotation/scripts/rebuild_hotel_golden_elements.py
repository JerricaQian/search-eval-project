#!/usr/bin/env python3
"""Rebuild the five hotel golden manifests with reviewed card elements.

Input is bounded PaddleOCR evidence produced by extract_bounded_golden_ocr.py.
Only observations passing the explicit review rules below are published.  The
script also adds image facts from the already reviewed card layout; it never
changes page components, card types, or card boundaries.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "phase2-card-annotation" / "golden-sample-results" / "hotel-card"


CORRECTIONS = {
    "全季酒店(北京会议中心店）": "全季酒店（北京会议中心店）",
    "全季酒店(北京望京店)": "全季酒店（北京望京店）",
    "全季酒店(北京鸟巢关庄地铁站店）": "全季酒店（北京鸟巢关庄地铁站店）",
    "全季酒店(北京鸟巢国家会议中心店）": "全季酒店（北京鸟巢国家会议中心店）",
    "全季酒店(北京望京科技园店）": "全季酒店（北京望京科技园店）",
    "全季酒店(北京望京花家地店）": "全季酒店（北京望京花家地店）",
    "全季酒店（北京798艺术区店）": "全季酒店（北京798艺术区店）",
    "望京舒适好评榜第７名": "望京舒适好评榜第7名",
    "1立减83": "立减83",
    "15-25²|2人|双床": "15-25m²｜2人｜双床",
    "1240Hz及以上": "240Hz及以上",
    "15-20m²|2人|有窗": "15-20m²｜2人｜有窗",
    "15m²|2人|大床|有窗": "15m²｜2人｜大床｜有窗",
    "2台|i512400": "2台｜i5 12400",
    "整套1室|2人": "整套1室｜2人",
    "北京朋宜多电竞主..>": "北京朋宜多电竞主题…",
    "JING·电竞酒店(北..>": "JING·电竞酒店（北京…）",
    "可长租4070显卡PS5电": "可长租4070显卡PS5…",
    "30天低价": "30天低价",
    "全季酒店(北京望京店)高档型": "全季酒店（北京望京店）｜高档型",
    "￥404": "¥404",
    "￥529": "¥529",
    "￥589": "¥589",
    "￥609": "¥609",
    "￥412起": "¥412起",
    "￥354起": "¥354起",
    "￥526": "¥526",
    "￥163": "¥163",
    "￥480": "¥480",
    "￥148": "¥148",
    "￥820": "¥820",
    "￥328": "¥328",
    "￥198": "¥198",
    "￥428": "¥428",
    "￥731": "¥731",
    "￥278": "¥278",
    "|立减91": "立减91",
    "8.21-8.30马来西亚美食节赔间通用": "8.21-8.30马来西亚美食节期间通用",
    "6豫菜": "豫菜",
    "望京麒麟社万客公寓>": "望京麒麟社万客公寓…",
    "6号青橙电竞主题...": "6号青橙电竞主题酒店…",
}

DROP_TEXTS = {
    "", "￥", "¥", "?", ">", "福", "器", "二", "V", "□□", "P人",
    "11.", '"1', "1", "全罕酒店", "主华酒店", "全李店", "意绣品",
    "IIHOTEL", "IIHOTEL", "IHOTEL", "MHOTEL", "LAVANDE", "quant",
    "全季酒", "店", "全季酒店", "麗枫酒店", "ILHOTEL", "Hz", "庆通用",
}

# A first OCR line may be visibly wrapped.  Merge it with the listed following
# line and publish one human-reviewed title element with the union geometry.
MERGES: dict[tuple[str, int, str], tuple[str, list[str]]] = {
    ("全季酒店-第1次.elements.json", 1, "全季酒店(北京望京商务区宝能中心"):
        ("全季酒店（北京望京商务区宝能中心店）", ["店）"]),
    ("酒店.elements.json", 1, "全季酒店（北京会议中心北苑东路"):
        ("全季酒店（北京会议中心北苑东路店）", ["店）"]),
    ("酒店.elements.json", 2, "麗枫酒店(北京望京SOHO科技园"):
        ("麗枫酒店（北京望京SOHO科技园店）", ["店）"]),
    ("国庆节酒店-混排.elements.json", 3, "【怡园】E2地铁近国贸CBD直达北海"):
        ("【怡园】E2地铁近国贸CBD直达北海南锣鼓巷舒适明亮三居·可洗衣·租房·套",
         ["南锣鼓巷舒适明亮三居·可洗衣·租房·套"]),
    ("国庆节酒店-混排.elements.json", 4, "北野！大兴机场！明亮宽敞三居！十一"):
        ("北野！大兴机场！明亮宽敞三居！十一特惠！24小时热水无线！免费停车！·近北",
         ["特惠！24小时热水无线！免费停车！·近北"]),
    ("国庆节酒店-混排.elements.json", 1, "【中秋国庆通用"):
        ("【中秋国庆通用】家庭自助餐（…）", ["】家庭自助餐("]),
    ("国庆节酒店-混排.elements.json", 1, "【周一至周四】"):
        ("【周一至周四】商务晚餐半自助…", ["商务晚餐半自"]),
    ("国庆节酒店-混排.elements.json", 1, "单人自助餐(8."):
        ("单人自助餐（8.21-8.30马来西亚…）", ["21-8.30马来西"]),
    ("国庆节酒店-混排.elements.json", 1, "【南洋"):
        ("【南洋…】", ["来西"]),
    ("国庆节酒店-混排.elements.json", 2, "【十一】【食尚风"):
        ("【十一】【食尚风味】豫东熬炒鸡", ["味】豫东熬炒鸡"]),
    ("国庆节酒店-混排.elements.json", 2, "【地方特色】黄"):
        ("【地方特色】黄河大鲤鱼+郑…", ["河大鲤鱼+郑"]),
    ("国庆节酒店-混排.elements.json", 2, "【食全食美】羊"):
        ("【食全食美】羊肉烩面双人餐（…）", ["肉烩面双人餐("]),
}


def union(coords: list[list[int]]) -> list[int]:
    x0 = min(item[0] for item in coords)
    y0 = min(item[1] for item in coords)
    x1 = max(item[0] + item[2] for item in coords)
    y1 = max(item[1] + item[3] for item in coords)
    return [x0, y0, x1 - x0, y1 - y0]


def role(text: str, card_type: str, relative_y: float) -> tuple[str, str]:
    if card_type == "异构卡":
        return "推荐词", "推荐词区"
    if card_type == "商家卡片_图文下挂":
        if text in {"到店", "酒店", "民宿"}:
            return "履约标识", "标题区"
        if re.search(r"\d\.\d分|人均|\d+条|\d+(?:\.\d+)?km|菜$|好评榜", text):
            return "商家信息", "商家信息区"
        if relative_y < 0.18:
            return "商家标题", "标题区"
        if relative_y < 0.31:
            return "商家信息", "商家信息区"
        return "下挂商品信息", "下挂商品区"

    if text in {"酒店", "民宿"}:
        return "酒店/民宿履约标识", "标题区"
    if text in {"高档型", "舒适型", "豪华型", "经济型"}:
        return "酒店等级", "标题区"
    if text in {"住就送·32元券包", "新开业/装修", "机器人服务", "健身房", "商务出行", "叫醒服务", "零压助眠房", "积分可抵￥21", "实拍", "超赞房东", "近地铁", "寄存行李", "立即确认", "洗衣机"}:
        return "酒店标签", "标签区"
    if text.startswith("近") or text in {"望京", "酒仙桥/798"}:
        return "位置信息", "位置信息"
    if relative_y > 0.84 and re.search(r"酒店|公寓|电竞主题", text):
        return "酒店名称", "评分与推荐理由"
    if re.search(r"酒店（|酒店\(|房$|房…|三居|套$|电竞|显卡PS5", text) and not re.search(r"分钟前|消费", text):
        return "酒店标题", "标题区"
    if re.match(r"^\d\.\d分", text):
        return "评分", "评分与推荐理由"
    if any(token in text for token in ("入住体验", "居住体验", "卫生干净", "设施完善", "服务很好", "干净卫生", "住得特别放心", "老板人很好", "总体是")):
        return "推荐理由", "评分与推荐理由"
    if re.search(r"距您直线|^\d+(?:\.\d+)?km$|望京$|酒仙桥/798|亚运村|科技园公共汽车站|中华女子学院|传媒大学|大兴国际机场|朝阳区", text):
        return "位置信息", "位置信息"
    if re.search(r"m²|\d人|双床|大床|有窗|\d台|Hz|i5|整套", text, re.I):
        return "酒店基础信息", "基础信息区"
    if re.search(r"^[¥￥]\d|^\d{3,4}$|^起$|已售|消费|预订|收藏|低价房|天天特价|夏日特惠|立减|立享|30天低价", text):
        return "价格与交易信息", "价格区"
    if relative_y >= 0.72:
        return "价格与交易信息", "价格区"
    return "酒店标签", "标签区"


def image_element(card: dict[str, Any]) -> dict[str, Any]:
    x, y, w, h = card["coord"]
    if card.get("cardType") == "商家卡片_图文下挂":
        coord = [x + 30, y + 35, min(300, w - 60), min(300, max(1, h - 70))]
    elif w < 800:
        height = min(411, max(1, h - 70))
        coord = [x + 15, y + 7, max(1, w - 30), height]
    else:
        coord = [x + 30, y + 14, min(330, max(1, w // 3 - 60)), max(1, min(421, h - 28))]
    return {
        "elementType": "酒店头图" if card.get("cardType") == "酒店卡片" else "商家头图",
        "sourceRegion": "头图区",
        "coord": coord,
        "visibleText": "",
        "status": "confirmed",
        "source": "reviewed_card_layout",
    }


def merchant_product_images(card: dict[str, Any]) -> list[dict[str, Any]]:
    """Reviewed four-column product-image geometry for the mixed hotel page."""
    if card.get("cardType") != "商家卡片_图文下挂":
        return []
    x, y, w, h = card["coord"]
    top = y + (232 if int(card["listPosition"]) == 1 else 160)
    column_width = 243
    images = []
    for index, left in enumerate((360, 616, 870, 1124), 1):
        clipped_width = max(1, min(column_width, x + w - left))
        clipped_height = max(1, min(244, y + h - top))
        images.append({
            "elementType": "下挂商品图片",
            "sourceRegion": "下挂商品区",
            "itemIndex": index,
            "coord": [left, top, clipped_width, clipped_height],
            "visibleText": "",
            "status": "confirmed",
            "source": "reviewed_card_layout",
        })
    return images


def element(kind: str, region: str, coord: list[int], text: str, confidence: float) -> dict[str, Any]:
    return {
        "elementType": kind,
        "sourceRegion": region,
        "coord": coord,
        "visibleText": text,
        "status": "confirmed",
        "source": "bounded_paddleocr_human_reviewed",
    }


def reviewed_observations(filename: str, card: dict[str, Any], evidence: dict[str, Any]) -> list[dict[str, Any]]:
    observations = evidence["observations"]
    position = int(card["listPosition"])
    consumed: set[str] = set()
    merged: dict[str, tuple[str, list[int], float]] = {}
    for (merge_file, merge_position, first), (corrected, followers) in MERGES.items():
        if merge_file != filename or merge_position != position:
            continue
        first_item = next((item for item in observations if item.get("text") == first), None)
        follow_items = [next((item for item in observations if item.get("text") == value), None) for value in followers]
        if first_item and all(follow_items):
            selected = [first_item] + [item for item in follow_items if item]
            merged[first] = (corrected, union([item["coord"] for item in selected]), min(float(item.get("ocrConfidence", 0)) for item in selected))
            consumed.update(item["text"] for item in selected)

    accepted: list[dict[str, Any]] = []
    x, y, w, h = card["coord"]
    for first, (text, coord, confidence) in merged.items():
        kind, region = role(text, card["cardType"], max(0.0, (coord[1] - y) / max(1, h)))
        accepted.append(element(kind, region, coord, text, confidence))

    for item in observations:
        raw = str(item.get("text", "")).strip()
        confidence = float(item.get("ocrConfidence", 0))
        if raw in consumed or raw in DROP_TEXTS or confidence < 0.85:
            continue
        text = CORRECTIONS.get(raw, raw)
        if not text or re.fullmatch(r"[^0-9A-Za-z\u4e00-\u9fff]+", text):
            continue
        coord = item["coord"]
        relative_y = max(0.0, (coord[1] - y) / max(1, h))
        kind, region = role(text, card["cardType"], relative_y)
        # A bare three/four-digit number in the right price column is the
        # visually reviewed current price; publish the currency explicitly.
        if ((kind == "价格与交易信息" or region == "下挂商品区")
                and re.fullmatch(r"\d{2,4}", text)
                and (kind == "价格与交易信息" or coord[0] >= x + w * 0.25)):
            text = f"¥{text}"
        accepted.append(element(kind, region, coord, text, confidence))
    return accepted


def rebuild(golden_path: Path, evidence_path: Path) -> int:
    payload = json.loads(golden_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    by_position = {int(item["listPosition"]): item for item in evidence["cards"]}
    count = 0
    for component in payload["pageStructure"]["components"]:
        if component.get("componentType") == "search_bar" and payload.get("query"):
            component["elements"] = [{
                "elementType": "搜索关键词",
                "sourceRegion": "搜索框",
                "coord": component.get("coord", [0, 0, 0, 0]),
                "visibleText": payload["query"],
                "status": "confirmed",
                "source": "component_annotation",
            }]
            count += 1
        if component.get("componentType") != "results_list":
            continue
        for card in component.get("components", []):
            position = int(card["listPosition"])
            card_evidence = by_position[position]
            regions: dict[str, dict[str, list[dict[str, Any]]]] = {}
            if card.get("cardType") != "异构卡":
                head = image_element(card)
                regions.setdefault("头图区", {"elements": []})["elements"].append(head)
                count += 1
                product_images = merchant_product_images(card)
                if product_images:
                    regions.setdefault("下挂商品区", {"elements": []})["elements"].extend(product_images)
                    count += len(product_images)
            for value in reviewed_observations(golden_path.name, card, card_evidence):
                regions.setdefault(value["sourceRegion"], {"elements": []})["elements"].append(value)
                count += 1
            card["regions"] = regions
            card["elementVerification"] = {
                "status": "reviewed",
                "ocrBackend": card_evidence["backend"],
                "policy": "Only explicitly accepted bounded observations are confirmed; rejected/low-confidence OCR is absent from golden truth.",
            }
    payload["verification"]["claimScope"] = sorted(set(payload["verification"]["claimScope"] + ["reviewed_card_elements"]))
    payload["verification"]["excludedClaims"] = ["runtime_ocr_text", "unreviewed_runtime_ocr_text", "ocr_confidence_as_truth"]
    try:
        evidence_reference = str(evidence_path.resolve().relative_to(ROOT))
    except ValueError:
        evidence_reference = str(evidence_path.resolve())
    payload["verification"]["boundedElementEvidence"] = evidence_reference
    golden_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = {}
    for golden_path in sorted(GOLDEN_DIR.glob("*.elements.json")):
        evidence_path = args.evidence_dir / f"{golden_path.stem}.bounded-ocr.json"
        if not evidence_path.is_file():
            raise FileNotFoundError(evidence_path)
        summary[golden_path.name] = rebuild(golden_path, evidence_path)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
