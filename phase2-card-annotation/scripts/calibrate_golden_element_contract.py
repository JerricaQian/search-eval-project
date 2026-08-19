#!/usr/bin/env python3
"""Calibrate all golden JSON files to the shared element-level contract.

Golden-only policy:
* bounded Paddle observations and model/human visual review may correct truth;
* every complete known card owns a title element;
* appended supply is grouped per item, never flattened across products/rows;
* basic information and tags are semantic atoms, never one-character atoms.

This script is intentionally not imported by the Phase2 production runner.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "phase2-card-annotation" / "golden-sample-results"
TRUTH = ROOT / "phase2-card-annotation" / "references" / "golden_page_truth.v2.json"


TITLE_REVIEWS: dict[tuple[str, int], tuple[str, list[str]]] = {
    ("烧烤.elements.json", 1): ("锦州烧烤（悠乐汇店）", ["锦州烧烤(悠乐汇店)"]),
    ("烧烤.elements.json", 2): ("锦州烧烤（望京店）", ["锦州烧烤(望京店)"]),
    ("蜜雪冰城.elements.json", 1): ("蜜雪冰城（东辛店）", ["蜜雪冰城(东辛店)"]),
    ("商家卡片-文下挂-搜索词为按摩.elements.json", 1): ("云驰运动康复（望京SOHO店）", ["云驰运动康复(望京SOHO店)"]),
    ("商家卡片-文下挂-搜索词为按摩.elements.json", 2): ("北派修脚·采耳·养生（望京SOHO店）", ["北派修脚·采耳·养生(望京SOHO店)"]),
    ("商家卡片-文下挂-搜索词为理发.elements.json", 3): ("PAYA HAIR（望京旗舰店）", ["PAYA", "HAIR(望京旗舰店)"]),
    ("喜力啤酒整箱.elements.json", 2): ("喜力（Heineken）11.4°P啤酒 500ml*12听/箱", ["喜力(Heineken)11.4°P啤酒", "500ml*12听/箱"]),
    ("榴莲.elements.json", 1): ("泰国金枕榴莲（约）2kg 称重", ["泰国金枕榴莲(约)2ka称重"]),
    ("榴莲.elements.json", 2): ("【下单现剥】AA泰国树上熟金枕榴莲3-6斤（大果默认剥肉装盒）", ["【下单现剥】AA泰国树上熟金枕", "榴莲3-6斤(大果默认剥肉装盒)"]),
    ("榴莲.elements.json", 3): ("【世界杯特惠榴莲】（鲜AA果）3-4斤泰国进口树熟【金枕榴莲】3-4斤（香", ["【世界杯特惠榴莲】(鲜AA 果)3-4", "斤泰国进口树熟【金枕榴莲】3-4斤(香"]),
    ("生理盐水.elements.json", 3): ("【霖恩盐水】清洗液（0.9%NaCl）（生理盐水）15ml*20支/盒 伤口清洁温和", ["[霖恩盐水]清洗液(0.9%NaCl(生", "理盐水)15ml*20支/盒伤口清洁温和"]),
    ("生理盐水.elements.json", 4): ("【KL】生理氯化钠溶液（0.9%）*500ml/瓶", ["[KL]生理氯化钠溶液(", ")*500ml/瓶"]),
}

MANUAL_PIXEL_TITLE_REVIEWS: dict[tuple[str, int], tuple[str, list[int]]] = {
    ("隆江猪脚饭.elements.json", 3): ("粤知一二隆江猪脚饭烧腊（保利广场店）", [330, 1932, 650, 50]),
    ("烧烤.elements.json", 3): ("望京小腰·烧烤（望京店）", [322, 1880, 475, 52]),
    ("库迪.elements.json", 3): ("库迪咖啡（望京金辉国际大厦店）", [394, 1984, 625, 60]),
    ("蜜雪冰城.elements.json", 2): ("茶山季（合生汇店）", [314, 2064, 374, 58]),
    ("商家卡片-文下挂-搜索词为露营.elements.json", 1): ("圣露庄园·露营·烤肉·亲子", [407, 910, 605, 50]),
}

MANUAL_TITLE_REGION_ELEMENTS: dict[tuple[str, int], list[tuple[str, str, list[int]]]] = {
    ("烧烤.elements.json", 1): [("履约标识", "外卖", [227, 554, 78, 58])],
    ("烧烤.elements.json", 3): [
        ("履约标识", "外卖", [227, 1880, 78, 58]),
        ("配送时长", "34分钟", [1034, 1880, 180, 60]),
    ],
    ("榴莲.elements.json", 1): [("履约标签", "外卖", [396, 1100, 82, 58])],
}

# Pixel-reviewed canonical visible titles.  These replace OCR character errors
# (for example U8→08 and NaCl→NaCI) but preserve the detected title box.
REVIEWED_TITLE_TEXT: dict[tuple[str, int], str] = {
    ("啤酒.elements.json", 1): "泰山原浆啤酒10度7天新鲜 720ml*3瓶",
    ("啤酒.elements.json", 2): "【特殊品勿拍】燕京U8啤酒8°P 瓶装500ml*1+歪马定制无纺布袋*1（",
    ("啤酒.elements.json", 3): "燕京U8啤酒8°P瓶装500ml",
    ("喜力啤酒整箱.elements.json", 1): "【整箱】喜力啤酒500ml*12瓶 11.4°P",
    ("喜力啤酒整箱.elements.json", 2): "喜力（Heineken）11.4°P啤酒 500ml*12听/箱",
    ("喜力啤酒整箱.elements.json", 3): "【整箱】喜力11.4度听装啤酒 500ml*12罐/箱",
    ("喜力啤酒整箱.elements.json", 4): "喜力啤酒11.4°P听装500ml*12",
    ("安睡裤.elements.json", 1): "【L号】苏菲 超熟睡安心裤5片/包 超薄裤型卫生巾",
    ("安睡裤.elements.json", 2): "她研社春眠小裤安睡裤M-L码/XL码3条",
    ("安睡裤.elements.json", 3): "全棉时代奈丝公主M码安睡裤3片/包",
    ("安睡裤.elements.json", 4): "【M-L号】她研社 深藏BLUE安睡裤3条/包",
    ("布洛芬.elements.json", 2): "[芬必得]布洛芬咀嚼片0.2g*10片/板/盒",
    ("布洛芬.elements.json", 3): "[芬必得]布洛芬缓释胶囊0.3g*12粒*2板/盒",
    ("布洛芬.elements.json", 4): "[芬必得]布洛芬缓释胶囊0.3g*12粒*2板/盒",
    ("生理盐水.elements.json", 1): "海氏海诺英诺威医用生理盐水清洗液250ml 0.9%氯化钠清洗液清洁",
    ("生理盐水.elements.json", 2): "[霖恩盐水]清洗液(0.9%NaCl)(生理盐水)15ml*20支/盒 生理盐水棒清",
    ("生理盐水.elements.json", 3): "[霖恩盐水]清洗液(0.9%NaCl)(生理盐水)15ml*20支/盒 伤口清洁温和",
    ("生理盐水.elements.json", 4): "[KL]生理氯化钠溶液(0.9%)*500ml/瓶",
    ("西瓜.elements.json", 1): "【爆品半斤瓜切】店长推荐 一包糖 麒麟/吊秧/庞各庄 西瓜切5g/份 50份",
    ("西瓜.elements.json", 2): "一桶西瓜 含桶1斤装（爆品）",
    ("西瓜.elements.json", 3): "【果切】一斤西瓜吃到爽(500g) 爆品",
}


def union(coords: list[list[int]]) -> list[int]:
    x0, y0 = min(item[0] for item in coords), min(item[1] for item in coords)
    x1 = max(item[0] + item[2] for item in coords)
    y1 = max(item[1] + item[3] for item in coords)
    return [x0, y0, x1 - x0, y1 - y0]


def cards(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for component in payload.get("pageStructure", {}).get("components", []):
        if component.get("componentType") == "results_list":
            for card in component.get("components", []):
                if card.get("componentType") == "result_card":
                    yield card


def sync_existing_card_geometry(payload: dict[str, Any]) -> int:
    truth = json.loads(TRUTH.read_text(encoding="utf-8"))["pages"]
    expected = truth[payload["verification"]["rawScreenshot"]]["resultCards"]
    changed = 0
    def iou(left: list[int], right: list[int]) -> float:
        lx, ly, lw, lh = left; rx, ry, rw, rh = right
        intersection = max(0, min(lx + lw, rx + rw) - max(lx, rx)) * max(0, min(ly + lh, ry + rh) - max(ly, ry))
        total = lw * lh + rw * rh - intersection
        return intersection / total if total else 0.0

    for component in payload.get("pageStructure", {}).get("components", []):
        if component.get("componentType") != "results_list":
            continue
        claimed: set[int] = set()
        for card in component.get("components", []):
            if card.get("componentType") not in {"result_card", "heterogeneous_card"} or not isinstance(card.get("coord"), list):
                continue
            ranked = sorted(((iou(card["coord"], target["coord"]), index) for index, target in enumerate(expected)), reverse=True)
            score, matched_index = next(((score, index) for score, index in ranked if index not in claimed), (0.0, -1))
            position = int(card.get("listPosition", 0))
            if score >= 0.20:
                position = matched_index + 1
                claimed.add(matched_index)
            elif not 1 <= position <= len(expected):
                continue
            target = expected[position - 1]
            if card.get("listPosition") != position or card.get("coord") != target["coord"] or card.get("visibleStatus") != target["visibleStatus"]:
                changed += 1
            card["listPosition"] = position
            card["coord"] = target["coord"]
            card["visibleStatus"] = target["visibleStatus"]
            card.pop("cropped", None)
            card["cardType"] = target["cardType"]
            if target.get("variant"):
                card["variant"] = target["variant"]
        component["components"] = sorted(component.get("components", []), key=lambda item: int(item.get("listPosition", 0)))
    return changed


def element_lists(value: Any) -> Iterator[list[dict[str, Any]]]:
    if isinstance(value, dict):
        for child in value.values():
            if isinstance(child, list) and any(isinstance(item, dict) and "elementType" in item for item in child):
                yield child
            yield from element_lists(child)
    elif isinstance(value, list):
        for child in value:
            yield from element_lists(child)


def clean_title(text: str) -> str:
    return text.replace("(", "（").replace(")", "）")


def evidence_for(path: Path, evidence_dir: Path) -> dict[str, Any]:
    evidence = evidence_dir / f"{path.parent.name}--{path.stem}.contract-evidence.json"
    return json.loads(evidence.read_text(encoding="utf-8")) if evidence.is_file() else {"requests": []}


def add_missing_title(path: Path, card: dict[str, Any], evidence: dict[str, Any]) -> bool:
    title_region = card.setdefault("regions", {}).setdefault("标题区", {"elements": []})
    current = title_region.setdefault("elements", [])
    key = (path.name, int(card.get("listPosition", 0)))
    manual_review = MANUAL_PIXEL_TITLE_REVIEWS.get(key)
    valid_titles = [
        item for item in current
        if "标题" in str(item.get("elementType", "")) and len(str(item.get("visibleText", "")).strip()) >= 2
    ]
    if valid_titles and manual_review is None:
        return False
    if manual_review is not None:
        current[:] = [item for item in current if "标题" not in str(item.get("elementType", ""))]
        title, coord = manual_review
        element_type = "商品标题" if card.get("cardType") == "商品卡片" else "商家标题"
        current.append({
            "elementType": element_type,
            "sourceRegion": "标题区",
            "coord": coord,
            "visibleText": title,
            "status": "confirmed",
            "source": "model_pixel_calibrated",
        })
        current.sort(key=lambda item: (item.get("coord", [0, 0])[0], item.get("coord", [0, 0])[1]))
        return True
    current[:] = [
        item for item in current
        if not ("标题" in str(item.get("elementType", "")) and len(str(item.get("visibleText", "")).strip()) < 2)
    ]
    # Movie goldens already have pixel-verified cinema names in the title row.
    cinema = next((item for item in current if item.get("elementType") == "影院名"), None)
    if cinema:
        cinema["elementType"] = "电影标题"
        cinema["source"] = "model_reviewed_existing_title_element"
        return True
    review = TITLE_REVIEWS.get(key)
    if review is None:
        return False
    title, source_texts = review
    request = next(item for item in evidence.get("requests", []) if item.get("kind") == "missing_title" and int(item.get("listPosition", 0)) == key[1])
    observations = [item for item in request.get("observations", []) if item.get("text") in source_texts]
    if len(observations) != len(source_texts):
        raise RuntimeError(f"reviewed title evidence mismatch: {key}: {source_texts}")
    element_type = "商品标题" if card.get("cardType") == "商品卡片" else "商家标题"
    current.append({
        "elementType": element_type,
        "sourceRegion": "标题区",
        "coord": union([item["coord"] for item in observations]),
        "visibleText": title,
        "status": "confirmed",
        "source": "bounded_paddleocr_model_calibrated",
    })
    current.sort(key=lambda item: (item.get("coord", [0, 0])[0], item.get("coord", [0, 0])[1]))
    return True


def add_reviewed_title_region_elements(path: Path, card: dict[str, Any]) -> int:
    key = (path.name, int(card.get("listPosition", 0)))
    reviewed = MANUAL_TITLE_REGION_ELEMENTS.get(key, [])
    current = card.setdefault("regions", {}).setdefault("标题区", {"elements": []}).setdefault("elements", [])
    changed = 0
    for element_type, text, coord in reviewed:
        if any(item.get("elementType") == element_type and str(item.get("visibleText", "")).strip() == text for item in current):
            continue
        current.append({
            "elementType": element_type,
            "sourceRegion": "标题区",
            "coord": coord,
            "visibleText": text,
            "status": "confirmed",
            "source": "model_pixel_calibrated",
        })
        changed += 1
    current.sort(key=lambda item: (item.get("coord", [0, 0])[0], item.get("coord", [0, 0])[1]))
    return changed


def apply_reviewed_title_text(path: Path, card: dict[str, Any]) -> int:
    reviewed = REVIEWED_TITLE_TEXT.get((path.name, int(card.get("listPosition", 0))))
    if reviewed is None:
        return 0
    values = card.get("regions", {}).get("标题区", {}).get("elements", [])
    title = next((item for item in values if "标题" in str(item.get("elementType", ""))), None)
    if title is None or title.get("visibleText") == reviewed:
        return 0
    title["visibleText"] = reviewed
    title["source"] = "model_pixel_calibrated"
    return 1


def semantic_kind(text: str, default: str) -> str:
    if re.search(r"m²", text):
        return "房间面积"
    if re.fullmatch(r"\d+人", text):
        return "入住人数"
    if text in {"双床", "大床", "单床"}:
        return "床型"
    if "窗" in text:
        return "窗型"
    if re.fullmatch(r"\d+台", text):
        return "设备数量"
    if re.search(r"i[357]|显卡|Hz", text, re.I):
        return "设备配置"
    if re.search(r"室|整套", text):
        return "户型"
    return default


def proportional_segments(item: dict[str, Any]) -> list[dict[str, Any]]:
    text = str(item.get("visibleText", ""))
    parts = [part.strip() for part in re.split(r"[｜|；]", text) if part.strip()]
    if len(parts) <= 1:
        return [item]
    x, y, width, height = item["coord"]
    total = sum(len(part) for part in parts) + len(parts) - 1
    cursor = 0
    output = []
    for part in parts:
        start = round(width * cursor / total)
        cursor += len(part)
        end = round(width * cursor / total)
        value = copy.deepcopy(item)
        value.update({
            "elementType": semantic_kind(part, str(item.get("elementType", "基础信息"))),
            "coord": [x + start, y, max(1, end - start), height],
            "visibleText": part,
            "source": "model_semantic_split_from_pixel_verified_line",
        })
        output.append(value)
        cursor += 1
    return output


def split_merged_elements(card: dict[str, Any], requests: list[dict[str, Any]]) -> int:
    by_key = {(tuple(item.get("coord", [])), str(item.get("legacyText", ""))): item for item in requests if item.get("kind") == "merged_semantic_region" and item.get("listPosition") == card.get("listPosition")}
    changed = 0
    for values in list(element_lists(card.get("regions", {}))):
        replacement: list[dict[str, Any]] = []
        for item in values:
            request = by_key.get((tuple(item.get("coord", [])), str(item.get("visibleText", ""))))
            if request is None:
                replacement.extend(proportional_segments(item))
                changed += int(len(replacement) > 1)
                continue
            observations = [obs for obs in request.get("observations", []) if float(obs.get("ocrConfidence", 0)) >= 0.85 and len(re.sub(r"\s+", "", str(obs.get("text", "")))) > 1]
            if len(observations) >= 2:
                for obs in sorted(observations, key=lambda value: (value["coord"][0], value["coord"][1])):
                    value = copy.deepcopy(item)
                    value.update({"coord": obs["coord"], "visibleText": obs["text"], "source": "bounded_paddleocr_model_calibrated", "status": "confirmed"})
                    replacement.append(value)
                changed += 1
            elif any(mark in str(item.get("visibleText", "")) for mark in ("｜", "|", "；")):
                parts = proportional_segments(item)
                replacement.extend(parts)
                changed += int(len(parts) > 1)
            elif observations:
                value = copy.deepcopy(item)
                value.update({"coord": observations[0]["coord"], "visibleText": observations[0]["text"], "source": "bounded_paddleocr_model_calibrated", "status": "confirmed"})
                replacement.append(value)
                changed += int(value != item)
            else:
                replacement.append(item)
        values[:] = replacement
    return changed


def valid_semantic_element(item: Any) -> bool:
    if not isinstance(item, dict) or "elementType" not in item:
        return False
    coord = item.get("coord")
    if not isinstance(coord, list) or len(coord) != 4 or coord[2] <= 0 or coord[3] <= 0:
        return False
    text = re.sub(r"\s+", "", str(item.get("visibleText", "")))
    return not text or len(text) > 1


def normalize_item(raw: dict[str, Any], index: int) -> dict[str, Any]:
    image = raw.get("imageElements", raw.get("image"))
    text = raw.get("textElements", raw.get("text", raw.get("name")))
    price = raw.get("priceElements", raw.get("price"))
    auxiliary = raw.get("auxiliaryElements", [raw.get("discount"), raw.get("sales")])
    as_list = lambda value: value if isinstance(value, list) else ([] if value is None else [value])
    image_elements = [item for item in as_list(image) if valid_semantic_element(item)]
    text_elements = [item for item in as_list(text) if valid_semantic_element(item)]
    price_elements = [item for item in as_list(price) if valid_semantic_element(item)]
    auxiliary_elements = [item for item in as_list(auxiliary) if valid_semantic_element(item) and str(item.get("visibleText", "")).strip()]
    all_elements = image_elements + text_elements + price_elements + auxiliary_elements
    coord = union([item["coord"] for item in all_elements]) if all_elements else raw.get("coord", [0, 0, 1, 1])
    return {
        "itemIndex": index,
        **({"itemType": raw["itemType"]} if raw.get("itemType") else {}),
        "coord": coord,
        "imageElements": image_elements,
        "textElements": text_elements,
        "priceElements": price_elements,
        "auxiliaryElements": auxiliary_elements,
        "visibleStatus": raw.get("visibleStatus", "naturally_cropped" if raw.get("cropped") else raw.get("status", "confirmed")),
    }


def group_flat_graphic_elements(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    anchors = sorted([item for item in values if item.get("itemIndex") and "图片" in str(item.get("elementType", ""))], key=lambda item: int(item["itemIndex"]))
    if not anchors:
        return []
    buckets = {int(anchor["itemIndex"]): [anchor] for anchor in anchors}
    for item in values:
        if item in anchors:
            continue
        center = item["coord"][0] + item["coord"][2] / 2
        anchor = min(anchors, key=lambda value: abs(center - (value["coord"][0] + value["coord"][2] / 2)))
        buckets[int(anchor["itemIndex"])].append(item)
    output = []
    for index, members in sorted(buckets.items()):
        raw = {
            "itemIndex": index,
            "imageElements": [item for item in members if "图片" in str(item.get("elementType", ""))],
            "priceElements": [item for item in members if "价格" in str(item.get("elementType", "")) or re.search(r"^[¥￥]\d", str(item.get("visibleText", "")))],
        }
        owned = raw["imageElements"] + raw["priceElements"]
        raw["textElements"] = [item for item in members if item not in owned]
        output.append(normalize_item(raw, index))
    return output


def normalize_downhang(card: dict[str, Any]) -> int:
    changed = 0
    for region_name in ("下挂商品区", "文字下挂区", "下挂区", "服务下挂"):
        region = card.get("regions", {}).get(region_name)
        if not isinstance(region, dict):
            continue
        raw_items = region.pop("products", None)
        if raw_items is None:
            raw_items = region.get("items")
        if isinstance(raw_items, list):
            region["items"] = [normalize_item(item, index) for index, item in enumerate(raw_items, 1)]
            changed += 1
        elif isinstance(region.get("elements"), list):
            grouped = group_flat_graphic_elements(region["elements"])
            if grouped:
                region.pop("elements")
                region["items"] = grouped
                changed += 1
    return changed


def calibrated_element(kind: str, region: str, observations: list[dict[str, Any]], text: str) -> dict[str, Any]:
    return {
        "elementType": kind,
        "sourceRegion": region,
        "coord": union([item["coord"] for item in observations]),
        "visibleText": text,
        "status": "confirmed",
        "source": "bounded_paddleocr_model_calibrated",
    }


def fill_incomplete_downhang(card: dict[str, Any], requests: list[dict[str, Any]]) -> int:
    region_name = "下挂商品区"
    region = card.get("regions", {}).get(region_name)
    if not isinstance(region, dict) or not isinstance(region.get("items"), list):
        return 0
    changed = 0
    request_by_item = {
        int(item["itemIndex"]): item
        for item in requests
        if item.get("kind") == "incomplete_downhang_item"
        and item.get("listPosition") == card.get("listPosition")
        and item.get("itemIndex") is not None
    }
    for item in region["items"]:
        request = request_by_item.get(int(item["itemIndex"]))
        if request is None or not item.get("imageElements"):
            continue
        image = item["imageElements"][0]
        image_bottom = image["coord"][1] + image["coord"][3]
        observations = [
            value for value in request.get("observations", [])
            if value["coord"][1] >= image_bottom - 3
            and float(value.get("ocrConfidence", 0)) >= 0.8
            and len(re.sub(r"\s+", "", str(value.get("text", "")))) > 1
        ]
        price_values = [value for value in observations if re.search(r"^[¥￥YyVv#]?\s*\d{1,4}(?:\.\d+)?(?:\s*(?:元|起|神|新客|亲))?", str(value.get("text", "")))]
        text_values = [value for value in observations if value not in price_values]
        if not item.get("textElements") and text_values:
            # Product names may wrap; they are one semantic text block, not
            # character fragments.  Keep visual reading order and union box.
            text_values.sort(key=lambda value: (value["coord"][1], value["coord"][0]))
            text = "".join(str(value["text"]) for value in text_values)
            item["textElements"] = [calibrated_element("下挂商品名", region_name, text_values, text)]
            changed += 1
        if not item.get("priceElements") and price_values:
            value = max(price_values, key=lambda candidate: (candidate["coord"][1], float(candidate.get("ocrConfidence", 0))))
            text = re.sub(r"^[YyVv#￥]", "¥", str(value["text"]).strip())
            item["priceElements"] = [calibrated_element("下挂商品价格", region_name, [value], text)]
            changed += 1
        owned = item.get("imageElements", []) + item.get("textElements", []) + item.get("priceElements", []) + item.get("auxiliaryElements", [])
        if owned:
            item["coord"] = union([value["coord"] for value in owned])
    return changed


def merge_price_suffixes_and_drop_singletons(card: dict[str, Any]) -> int:
    changed = 0
    for values in list(element_lists(card.get("regions", {}))):
        suffixes = [item for item in values if str(item.get("visibleText", "")).strip() == "起"]
        for suffix in suffixes:
            prices = [item for item in values if item is not suffix and re.search(r"[¥￥]\d+$", str(item.get("visibleText", "")).strip())]
            if prices:
                nearest = min(prices, key=lambda item: abs(item["coord"][1] - suffix["coord"][1]) + abs(item["coord"][0] + item["coord"][2] - suffix["coord"][0]))
                nearest["visibleText"] = nearest["visibleText"] + "起"
                nearest["coord"] = union([nearest["coord"], suffix["coord"]])
                nearest["source"] = "bounded_paddleocr_model_calibrated"
            values.remove(suffix)
            changed += 1
        before = len(values)
        values[:] = [item for item in values if len(re.sub(r"\s+", "", str(item.get("visibleText", "")))) != 1]
        changed += before - len(values)
    return changed


def clip_card_elements(card: dict[str, Any]) -> int:
    bounds = card.get("coord")
    if not isinstance(bounds, list) or len(bounds) != 4:
        return 0
    bx, by, bw, bh = bounds
    changed = 0

    def clip(coord: list[int]) -> list[int] | None:
        x0, y0 = max(coord[0], bx), max(coord[1], by)
        x1, y1 = min(coord[0] + coord[2], bx + bw), min(coord[1] + coord[3], by + bh)
        return [x0, y0, x1 - x0, y1 - y0] if x1 > x0 and y1 > y0 else None

    def visit(value: Any) -> None:
        nonlocal changed
        if isinstance(value, dict):
            for key, child in list(value.items()):
                if isinstance(child, list):
                    output = []
                    for item in child:
                        if isinstance(item, dict) and "elementType" in item and isinstance(item.get("coord"), list):
                            clipped = clip(item["coord"])
                            if clipped is None:
                                changed += 1
                                continue
                            if clipped != item["coord"]:
                                item["coord"] = clipped; changed += 1
                        visit(item)
                        if key == "items" and isinstance(item, dict):
                            owned = list(elements_in(item))
                            if not owned:
                                changed += 1
                                continue
                            item["coord"] = union([element["coord"] for element in owned])
                        output.append(item)
                    value[key] = output
                else:
                    visit(child)

    def elements_in(value: Any) -> Iterator[dict[str, Any]]:
        if isinstance(value, dict):
            if "elementType" in value and isinstance(value.get("coord"), list):
                yield value
            for child in value.values():
                yield from elements_in(child)
        elif isinstance(value, list):
            for child in value:
                yield from elements_in(child)

    visit(card.get("regions", {}))
    return changed


def calibrate(path: Path, evidence_dir: Path) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    evidence = evidence_for(path, evidence_dir)
    summary = {"geometry": sync_existing_card_geometry(payload), "titles": 0, "reviewedTitleText": 0, "titleRegionElements": 0, "semanticSplits": 0, "downhangs": 0, "downhangFields": 0, "singletons": 0, "clipped": 0}
    for card in cards(payload):
        summary["titles"] += int(add_missing_title(path, card, evidence))
        summary["reviewedTitleText"] += apply_reviewed_title_text(path, card)
        summary["titleRegionElements"] += add_reviewed_title_region_elements(path, card)
        summary["semanticSplits"] += split_merged_elements(card, evidence.get("requests", []))
        summary["singletons"] += merge_price_suffixes_and_drop_singletons(card)
        summary["downhangs"] += normalize_downhang(card)
        # Do not backfill missing graphic-item fields from legacy whole-card
        # requests.  Those observations can cross item columns or come from a
        # clipped crop.  Complete graphic items must instead be rebuilt from
        # per-item bounded OCR; naturally cropped items remain explicitly
        # cropped rather than receiving guessed text or prices.
        summary["clipped"] += clip_card_elements(card)
        card["elementContract"] = {
            "version": "golden.element-level.v3",
            "titleRequiredForCompleteKnownCard": True,
            "downhangGrouping": "one item owns imageElements/textElements/priceElements/auxiliaryElements",
            "semanticAtomicity": "basic-info and tags split by semantic field; one-character elements forbidden",
        }
    verification = payload.setdefault("verification", {})
    verification["claimScope"] = sorted(set(verification.get("claimScope", []) + ["element_level_title", "element_level_downhang_grouping", "semantic_atomicity"]))
    verification["elementCalibration"] = {
        "status": "bounded_paddleocr_and_model_visual_reviewed",
        "evidence": str((evidence_dir / f"{path.parent.name}--{path.stem}.contract-evidence.json").relative_to(ROOT)),
        "policy": "Golden-only calibration; never injected into Phase2 production recognition.",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "phase2-card-annotation" / "references" / "golden-contract-evidence")
    args = parser.parse_args()
    output = {str(path.relative_to(ROOT)): calibrate(path, args.evidence_dir) for path in sorted(RESULTS.rglob("*.elements.json"))}
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
