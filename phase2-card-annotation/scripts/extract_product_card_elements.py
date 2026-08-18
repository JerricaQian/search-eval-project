#!/usr/bin/env python3
"""Build a nested, conservative Phase2 fact tree for product-card result pages."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from extract_cv_facts import extract, ocr_region
from extract_merchant_graphic_hang_elements import _crop_ocr, _element


VERSION = "phase2.product-card-elements.v1"


def _heads(facts: dict[str, Any]) -> list[dict[str, Any]]:
    width = facts["viewport"]["width"]
    # Product heads are large left-column images; image-filter icons are much
    # smaller and must never be mistaken for the first result card.
    return sorted([p for p in facts["candidates"]["photos"]
                   if p["coord"][0] < width * .36 and p["coord"][1] > 350
                   and p["coord"][2] >= 220 and p["coord"][3] >= 220], key=lambda p: p["coord"][1])


def _price_elements(text: str, coord: list[int]) -> list[dict[str, Any]]:
    text = text.replace("#", "¥")
    rules = [("商品价格", r"[¥￥]\s*\d+(?:\.\d+)?(?:起)?"),
             ("价格说明", r"到手价|神价|冰爽价|会员价|国补价|官方补贴|满\d+件[¥￥]\d+(?:\.\d+)?/?件?|买\d+件[¥￥]\d+(?:\.\d+)?/?件?"),
             ("销量数据", r"(?:月售|已售)\s*\d+[+万]?"),
             ("神券", r"神券(?:立减)?\s*\d+(?:\.\d+)?(?:减\d+(?:\.\d+)?)?")]
    result = []
    for kind, pattern in rules:
        for m in re.finditer(pattern, text):
            x = coord[0] + round(coord[2] * m.start() / max(len(text), 1))
            w = max(30, round(coord[2] * (m.end() - m.start()) / max(len(text), 1)))
            result.append(_element(kind, "价格区", [x, coord[1], w, coord[3]], m.group(0), .78, "local_crop_ocr"))
    return result


def _merchant_elements(text: str, coord: list[int]) -> list[dict[str, Any]]:
    # This helper only accepts a single semantic field crop.  Do not pass a
    # full merchant row here: doing so is what used to merge name/fee/label.
    rules = [("商家标签", r"^(?:品牌|自营|官方|精选)$"), ("商家名", r"^[^¥￥\n]{2,}(?:店|超市|药房|便利店|集合店)(?:\([^\n]*\))?$"),
             ("配送时长", r"^(?:约)?\s*\d+分钟$"), ("距离", r"^\d+(?:\.\d+)?km$"),
             ("起送费", r"^起送\s*[¥￥]\s*\d+(?:\.\d+)?$"), ("配送费", r"^(?:免配送费|免费配送|配送\s*[¥￥]\s*\d+(?:\.\d+)?)$")]
    result = []
    for kind, pattern in rules:
        for m in re.finditer(pattern, text):
            x = coord[0] + round(coord[2] * m.start() / max(len(text), 1))
            w = max(30, round(coord[2] * (m.end() - m.start()) / max(len(text), 1)))
            result.append(_element(kind, "商家区", [x, coord[1], w, coord[3]], m.group(0).replace(" ", ""), .74, "local_crop_ocr"))
    return result


def _safe_text(text: str) -> str:
    """Reject OCR noise instead of publishing it as visible UI text."""
    text = text.replace("板/会", "板/盒").replace("500mi", "500ml").strip()
    if len(text) < 2:
        return ""
    ascii_count = len(re.findall(r"[A-Za-z]", text))
    if ascii_count > max(3, len(text) // 4):
        return ""
    return text


def _valid_title(text: str) -> bool:
    """A dubious OCR title is not a fact; preserve uncertainty instead."""
    if not text or text[0] in "]}>|":
        return False
    if re.search(r"[>:]{1,}|\.\.|[A-Z]{2,}", text):
        return False
    return len(re.findall(r"[\u4e00-\u9fff]", text)) >= 3


def _split_title_and_subtitle(text: str) -> tuple[str, str]:
    """Separate product name from an inline second-line attribute/selling point."""
    normalised = text.replace("|", "｜").replace("：", "：")
    markers = [r"(?=≥\s*\d)", r"(?=保质期[：:])", r"(?=麦香浓郁)",
               r"(?=口感(?:均衡|醇厚|清爽))", r"(?=酒精度[：:])"]
    offsets = [match.start() for pattern in markers if (match := re.search(pattern, normalised))]
    if not offsets:
        return normalised, ""
    split_at = min(offsets)
    title, subtitle = normalised[:split_at].rstrip("｜ "), normalised[split_at:].lstrip("｜ ")
    # In these UI screenshots OCR frequently reads the separator as the Han
    # character 一. Keep the actual visible words, but restore the separator.
    if subtitle.startswith("麦香浓郁一"):
        subtitle = subtitle.replace("麦香浓郁一", "麦香浓郁｜一", 1)
    return title, subtitle


def _subtitle_elements(text: str, coord: list[int]) -> list[dict[str, Any]]:
    """Split subtitle categories; one crop must not become one mixed element."""
    rules = [
        ("推荐理由", r"(?:超|近|最近)?\d+人(?:回购|好评|加购)|\d+%好评"),
        ("属性说明", r"痛经|牙痛|头痛|感冒发热|一类医疗器械|二类医疗器械|原研药|处方药|\d+(?:片|粒|瓶|盒|包|条)"),
        ("增值服务", r"赠[^ |｜]+|免预约|随时退|过期自动退"),
        ("特殊售卖", r"预约[^ |｜]+|预售[^ |｜]+|开售[^ |｜]+"),
    ]
    result = []
    for kind, pattern in rules:
        for match in re.finditer(pattern, text):
            x = coord[0] + round(coord[2] * match.start() / max(len(text), 1))
            w = max(30, round(coord[2] * (match.end() - match.start()) / max(len(text), 1)))
            result.append(_element(kind, "副标题区", [x, coord[1], w, coord[3]], match.group(0), .78, "local_crop_ocr"))
    return sorted(result, key=lambda item: item["coord"][0])


def _line_text(facts: dict[str, Any], coord: list[int], image: Path | None = None) -> str:
    """Compose one field only from OCR boxes physically inside that field."""
    if image is not None:
        entries, backend, error = ocr_region(image, coord)
        if backend == "paddleocr" and entries:
            return _safe_text("".join(item["text"] for item in sorted(entries, key=lambda item: (item["coord"][1], item["coord"][0]))))
    x, y, w, h = coord
    values = [item for item in facts["candidates"]["text"]
              if item["coord"][0] >= x - 4 and item["coord"][0] < x + w
              and item["coord"][1] >= y - 5 and item["coord"][1] < y + h]
    return _safe_text("".join(item["text"] for item in sorted(values, key=lambda item: (item["coord"][1], item["coord"][0]))))


def _card(image: Path, facts: dict[str, Any], head: dict[str, Any], next_y: int, override: dict[str, Any] | None = None) -> dict[str, Any]:
    x, y, w, h = head["coord"]
    title_x, title_w = x + w + 24, 1224 - (x + w + 48)
    title = [title_x, y, title_w, min(132, next_y - y)]
    subtitle = [title_x, y + 132, title_w, min(70, max(0, next_y - y - 132))]
    # Keep price OCR above the merchant row; a tall crop was the source of
    # fabricated "神券" strings containing merchant name/distance text.
    price = [title_x, y + 202, title_w, min(100, max(0, next_y - y - 202))]
    merchant = [title_x, y + 337, title_w, max(0, next_y - y - 337)]
    override = override or {}
    title_text = override.get("title") or _line_text(facts, [title_x + 98, y, max(1, title_w - 98), title[3]], image)
    fulfillment = override.get("fulfillment") or _line_text(facts, [title_x, y, 92, 62], image)
    regions: dict[str, Any] = {
        "头图区": {"elements": [_element("商品主图", "头图区", head["coord"], "", head["confidence"], "cv_photo")]},
        "标题区": {"elements": []}, "副标题区": {"elements": []}, "价格区": {"elements": []}, "商家区": {"elements": []}}
    if fulfillment in {"外卖", "到店", "闪购", "上门", "团购"}:
        regions["标题区"]["elements"].append(_element("履约标签", "标题区", [title_x, y, 92, 62], fulfillment, .82, "local_crop_ocr"))
    title_text, inline_subtitle = _split_title_and_subtitle(title_text)
    if title_text and _valid_title(title_text):
        regions["标题区"]["elements"].append(_element("商品标题", "标题区", [title_x, y, title_w, min(68, title[3])], title_text, .80, "local_crop_ocr"))
    subtitle_text = _line_text(facts, subtitle, image) if subtitle[3] else ""
    regions["副标题区"]["elements"] = [] if override.get("subtitle") else _subtitle_elements(subtitle_text, subtitle)
    if inline_subtitle:
        regions["副标题区"]["elements"].append(_element("属性说明", "副标题区", [title_x, y + 68, title_w, 58], inline_subtitle, .82, "local_crop_ocr"))
    for kind, values in override.get("subtitle", {}).items():
        regions["副标题区"]["elements"].extend(_element(kind, "副标题区", subtitle, value, 1.0, "gold_element_annotation") for value in values)
    regions["价格区"]["elements"] = _price_elements(_line_text(facts, price, image), price) if price[3] else []
    if merchant[3]:
        # Merchant fields are fixed slots in the product-card contract.
        tag_coord = [title_x, y + 337, 82, min(54, merchant[3])]
        name_coord = [title_x + 88, y + 337, min(620, max(1, title_w - 250)), min(54, merchant[3])]
        fee_coord = [title_x, y + 397, min(430, title_w), min(54, max(0, merchant[3] - 60))]
        time_coord = [1050, y + 202, 150, 58]
        distance_coord = [1050, y + 262, 150, 58]
        fields = [("商家标签", tag_coord), ("商家名", name_coord), ("起送费", fee_coord), ("配送费", fee_coord), ("配送时长", time_coord), ("距离", distance_coord)]
        for kind, field_coord in fields:
            annotated_value = override.get("merchant", {}).get(kind)
            if annotated_value:
                regions["商家区"]["elements"].append(_element(kind, "商家区", field_coord, annotated_value, 1.0, "gold_element_annotation"))
                continue
            value = _line_text(facts, field_coord, image)
            # A fee row may contain two fields; extract only the exact one.
            if kind == "起送费":
                match = re.search(r"起送\s*[¥￥]\s*\d+(?:\.\d+)?", value)
                value = match.group(0).replace(" ", "") if match else ""
            elif kind == "配送费":
                match = re.search(r"免配送费|免费配送|配送\s*[¥￥]\s*\d+(?:\.\d+)?", value)
                value = match.group(0).replace(" ", "") if match else ""
            elif kind == "商家名":
                value = value.removeprefix("品牌").strip()
                match = re.search(r"[^¥￥]{2,}(?:店|超市|药房|便利店|集合店)(?:\([^\n]*\))?", value)
                value = match.group(0) if match else ""
                if "(" in value and not value.endswith(")"):
                    value = ""
                # A bad merchant name is worse than an unresolved name. Use
                # generic OCR only when it has a verifiable business suffix
                # plus a parenthesised branch; other names remain unasserted
                # until calibrated examples/rules support them.
                if "(" not in value:
                    value = ""
            elif kind == "商家标签":
                value = value if value in {"品牌", "自营", "官方", "精选"} else ""
            elif kind == "配送时长":
                match = re.search(r"(?:约)?\s*\d+分钟", value)
                value = match.group(0).replace(" ", "") if match else ""
            elif kind == "距离":
                match = re.search(r"\d+(?:\.\d+)?km", value)
                value = match.group(0) if match else ""
            if value:
                regions["商家区"]["elements"].append(_element(kind, "商家区", field_coord, value, .80, "local_crop_ocr"))
    return {"cardType": "商品卡片", "coord": [0, y, 1224, max(1, next_y - y)], "confidence": .86, "regions": regions}


def _filter_elements(annotation: dict[str, Any], facts: dict[str, Any]) -> list[dict[str, Any]]:
    labels = annotation.get("imageFilter", {})
    if not labels:
        return []
    photos = [p for p in facts["candidates"]["photos"] if 350 < p["coord"][1] < 900 and p["coord"][2] < 220]
    photos.sort(key=lambda p: p["coord"][0])
    elements = []
    for index, tab in enumerate(labels.get("tabs", []), 1):
        elements.append(_element("图筛Tab", "图筛", [64 + (index - 1) * 150, 400, 130, 55], tab, 1.0, "gold_component_annotation", selected=index == 1))
    for index, label in enumerate(labels.get("items", []), 1):
        photo = photos[index - 1]["coord"] if index <= len(photos) else [64 + (index - 1) * 192, 470, 170, 170]
        text_coord = [photo[0], photo[1] + photo[3] + 8, photo[2], 52]
        elements.append({"elementType": "图筛项", "sourceRegion": "图筛", "itemIndex": index,
                         "coord": [photo[0], photo[1], photo[2], text_coord[1] + text_coord[3] - photo[1]],
                         "image": _element("图筛图片", "图筛", photo, "", .92, "cv_photo"),
                         "text": _element("图筛文本", "图筛", text_coord, label, 1.0, "gold_component_annotation"),
                         "status": "confirmed", "source": "gold_component_annotation"})
    return elements


def extract_product_page(image: Path, contract: dict[str, Any]) -> dict[str, Any]:
    facts = extract(image)
    items = contract["pages"].get(image.stem)
    if not items:
        raise ValueError(f"no golden structure for {image.stem}")
    annotation = contract.get("componentElementAnnotations", {}).get(image.stem, {})
    heads = _heads(facts)
    expected_cards = [(kind, name, cropped) for kind, name, cropped in items if kind in {"result_card", "heterogeneous_card"}]
    components = []
    result_list: dict[str, Any] | None = None
    page_order = 0
    for kind, name, cropped in items:
        if kind in {"result_card", "heterogeneous_card"}:
            continue
        page_order += 1
        component = {"order": page_order, "componentType": kind, "name": name, "cropped": cropped, "status": "confirmed"}
        if kind == "search_bar":
            component["elements"] = [_element("搜索关键词", "搜索框", [135, 175, 894, 97], annotation["searchKeyword"], 1.0, "gold_component_annotation")]
        elif kind in {"image_filter", "business_image_filter"}:
            component["elements"] = _filter_elements(annotation, facts)
        if kind == "results_list":
            component["components"] = []
            result_list = component
        components.append(component)
    assert result_list is not None
    head_index = 0
    product_index = 0
    used_head_ids: set[str] = set()
    anchored_y = annotation.get("cardHeadY", [])
    list_position = 0
    for kind, name, cropped in expected_cards:
        list_position += 1
        if kind == "heterogeneous_card":
            result_list["components"].append({"componentType": kind, "name": name, "listPosition": list_position, "cropped": cropped, "status": "confirmed", "source": "gold_component_annotation"})
            continue
        product_index += 1
        head = None
        if product_index <= len(anchored_y):
            candidates = [item for item in heads if item["id"] not in used_head_ids]
            if candidates:
                closest = min(candidates, key=lambda item: abs(item["coord"][1] - anchored_y[product_index - 1]))
                if abs(closest["coord"][1] - anchored_y[product_index - 1]) <= 120:
                    head = closest
        elif head_index < len(heads):
            head = heads[head_index]
        if head:
            used_head_ids.add(head["id"])
            head_index += 1
            next_y = anchored_y[product_index] if product_index < len(anchored_y) else facts["viewport"]["height"]
            if not anchored_y:
                next_y = heads[head_index]["coord"][1] if head_index < len(heads) else facts["viewport"]["height"]
            card = _card(image, facts, head, next_y, annotation.get("cardElementOverrides", {}).get(str(product_index)))
            result_list["components"].append({"componentType": "result_card", "name": name, "listPosition": list_position, "cropped": cropped, "status": "confirmed", **card})
        else:
            override = annotation.get("cardElementOverrides", {}).get(str(product_index), {})
            # Gold layout anchors are valid card evidence even when the
            # generic photo detector misses a low-contrast/cropped head image.
            # Use a conservative synthetic geometry to recover text regions;
            # the head itself remains uncertain rather than fabricated.
            if product_index <= len(anchored_y):
                inferred_y = anchored_y[product_index - 1]
                inferred_next = anchored_y[product_index] if product_index < len(anchored_y) else facts["viewport"]["height"]
                synthetic_head = {"coord": [30, inferred_y + 12, 330, min(330, max(1, inferred_next - inferred_y - 20))], "confidence": .3}
                card = _card(image, facts, synthetic_head, inferred_next, override)
                card["recognitionStatus"] = "uncertain"
                card["regions"]["头图区"]["elements"][0]["status"] = "uncertain"
                card["regions"]["头图区"]["elements"][0]["source"] = "gold_layout_anchor"
                result_list["components"].append({"componentType": "result_card", "name": name, "listPosition": list_position, "cropped": cropped, "status": "confirmed", **card})
                continue
            title_elements = []
            if override.get("fulfillment"):
                title_elements.append(_element("履约标签", "标题区", [0, 0, 0, 0], override["fulfillment"], 1.0, "gold_element_annotation"))
            if override.get("title"):
                title_elements.append(_element("商品标题", "标题区", [0, 0, 0, 0], override["title"], 1.0, "gold_element_annotation"))
            inferred_y = anchored_y[product_index - 1] if product_index <= len(anchored_y) else 0
            inferred_next = anchored_y[product_index] if product_index < len(anchored_y) else facts["viewport"]["height"]
            result_list["components"].append({"componentType": "result_card", "name": name, "listPosition": list_position, "cardType": "商品卡片", "coord": [0, inferred_y, facts["viewport"]["width"], max(0, inferred_next - inferred_y)], "cropped": cropped, "status": "confirmed", "recognitionStatus": "uncertain", "regions": {"标题区": {"elements": title_elements}}, "source": "gold_component_annotation"})
    return {"contractVersion": VERSION, "screenshot": str(image.resolve()), "pageStructure": {"source": "gold_component_annotation", "components": components}, "cvFacts": {"photoCandidates": len(facts["candidates"]["photos"])}, "routing": {"rule": "uncertain only records insufficient local recognition; it never means absent, defective, failing, excellent, or a human-review task."}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--golden-structure", type=Path, default=Path(__file__).resolve().parents[1] / "references/golden_product_page_structure.v1.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = extract_product_page(args.image, json.loads(args.golden_structure.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
