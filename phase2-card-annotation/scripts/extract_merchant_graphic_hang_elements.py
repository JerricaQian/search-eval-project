#!/usr/bin/env python3
"""Extract conservative element candidates for confirmed merchant graphic hangs."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from build_search_page_structure import build
from build_search_result_candidates import build_candidates
from extract_cv_facts import extract, ocr_region
from map_result_card_semantics import map_cards


VERSION = "phase2.merchant-graphic-hang-elements.v1"


def _overlap(box: list[int], container: list[int]) -> bool:
    return box[0] < container[0] + container[2] and box[0] + box[2] > container[0] and box[1] < container[1] + container[3] and box[1] + box[3] > container[1]


def _element(kind: str, region: str, coord: list[int], text: str, confidence: float, source: str, status: str = "confirmed", **extra: Any) -> dict[str, Any]:
    return {"elementType": kind, "sourceRegion": region, "coord": coord, "visibleText": text, "confidence": round(confidence, 4), "status": status, "source": source, **extra}


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("500mi", "500ml").replace("板/会", "板/盒").replace("#", "¥")
    # Discard OCR noise before the first Chinese character, digit, ¥, or [.
    return re.sub(r"^[^\u4e00-\u9fff0-9¥￥\[]+", "", text)


def _crop_ocr(image: Path, coord: list[int], psm: int = 7) -> str:
    # Prefer the locally provisioned PaddleOCR model for a *single semantic
    # crop*. It has no network dependency and avoids the expensive/ambiguous
    # whole-page OCR pass. Tesseract remains a bounded fallback.
    entries, backend, error = ocr_region(image, coord)
    if backend == "paddleocr" and entries:
        return _clean_text("".join(item["text"] for item in sorted(entries, key=lambda item: (item["coord"][1], item["coord"][0]))))
    binary = shutil.which("tesseract")
    if not binary:
        return ""
    with Image.open(image) as source:
        width, height = source.size
        x, y, w, h = coord
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(width, x + w), min(height, y + h)
        if x1 <= x0 or y1 <= y0:
            return ""
        with tempfile.NamedTemporaryFile(suffix=".png") as handle:
            crop = source.crop((x0, y0, x1, y1))
            # Small UI text needs upscaling before Tesseract; full-page OCR is
            # deliberately not used as a substitute for field-local OCR.
            crop.resize((crop.width * 3, crop.height * 3), Image.Resampling.LANCZOS).save(handle.name)
            completed = subprocess.run([binary, handle.name, "stdout", "-l", "chi_sim+eng", "--psm", str(psm)], capture_output=True, text=True, check=False, timeout=20)
    return _clean_text(completed.stdout) if completed.returncode == 0 else ""


def _field_elements(text: str, coord: list[int]) -> list[dict[str, Any]]:
    """Split a focused merchant-info crop into separately applicable fields."""
    normalised = text.replace("#", "¥")
    patterns = [
        ("评分/新店", r"\d(?:\.\d)?分|暂无评分"), ("销量", r"(?:月售|已售|年售)\s*\d+[+万]?"),
        ("起送费", r"起送\s*[¥￥]\s*\d+"), ("配送费", r"(?:免配送费|免费配送|配送\s*[¥￥]\s*\d+(?:\.\d+)?|满\s*[¥￥]?\s*\d+包邮|包邮)"),
        ("配送距离", r"\d+(?:\.\d+)?\s*(?:km|m)"), ("评价条数", r"\d+条"), ("人均价", r"人均\s*[¥￥]\s*\d+"),
    ]
    found = []
    for kind, pattern in patterns:
        for match in re.finditer(pattern, normalised):
            found.append((match.start(), _element(kind, "商家信息区", _segment_coord(coord, match.start(), match.end(), len(normalised)), match.group(0).replace(" ", ""), 0.80, "local_crop_ocr")))
    return [item for _, item in sorted(found, key=lambda value: value[0])]


def _tag_elements(text: str, coord: list[int]) -> list[dict[str, Any]]:
    patterns = [r"神券[^ ]*", r"明厨亮灶", r"可堂食", r"线上点[·•]?到店取", r"\d+位当地人常点", r"近\d+天\d+人复购", r"最近\d+小时\d+\+?人下单", r"刚刚有用户下单", r"购买过", r"买过\d+次"]
    found = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            found.append((match.start(), _element("标签", "标签区", _segment_coord(coord, match.start(), match.end(), len(text)), match.group(0), 0.78, "local_crop_ocr")))
    return [item for _, item in sorted(found, key=lambda value: value[0])]


def _segment_coord(coord: list[int], start: int, end: int, total: int) -> list[int]:
    x, y, w, h = coord
    total = max(total, 1)
    x0 = x + round(w * start / total)
    x1 = x + round(w * end / total)
    return [x0, y, max(1, x1 - x0), h]


def _product_slots(card: dict[str, Any], facts: dict[str, Any]) -> list[dict[str, Any]]:
    photo_map = {item["id"]: item for item in facts.get("candidates", {}).get("photos", [])}
    products = [photo_map[item_id] for item_id in card.get("attachedProductPhotoIds", []) if item_id in photo_map]
    if not products:
        return []
    anchor = min(products, key=lambda item: item["coord"][0])
    x, y, w, h = anchor["coord"]
    slot_w = min(w, h, 264)
    gap = max(10, round(slot_w * 0.05))
    x_end = card["coord"][0] + card["coord"][2]
    slots = []
    index = 1
    cursor = x
    while cursor < x_end - 36 and index <= 5:
        width = min(slot_w, x_end - cursor)
        cropped = width < slot_w
        slots.append({"index": index, "imageCoord": [cursor, y, width, min(slot_w, h)], "cropped": cropped})
        cursor += slot_w + gap
        index += 1
    return slots


def _search_keyword_element(image: Path, annotation: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Read only the input field, excluding the back button and map entrance."""
    with Image.open(image) as source:
        width, height = source.size
    # The touch-overlay diagnostics occupy the band above the field in the
    # supplied captures. Start below it so it cannot be mistaken for a query.
    coord = [round(width * 0.11), round(height * 0.065), round(width * 0.73), round(height * 0.036)]
    annotated = (annotation or {}).get("searchKeyword", "")
    text = annotated or _crop_ocr(image, coord, 7)
    if not text:
        return []
    return [_element("搜索关键词", "搜索框", coord, text, 1.0 if annotated else 0.78,
                     "gold_component_annotation" if annotated else "local_crop_ocr")]


def _image_filter_elements(annotation: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Preserve one image and one label as a single filter-item group.

    For a golden sample the user-approved label is authoritative. For an
    unannotated screenshot this function intentionally returns no guessed
    labels: a wrong filter category must not become a factual assertion.
    """
    if not annotation:
        return []
    elements: list[dict[str, Any]] = []
    for tab in annotation.get("tabs", []):
        elements.append(_element("图筛Tab", "图筛", tab["coord"], tab["text"], 1.0,
                                 "gold_component_annotation", selected=tab.get("selected", False)))
    for index, item in enumerate(annotation.get("items", []), start=1):
        image_element = _element("图筛图片", "图筛", item["imageCoord"], "", 1.0,
                                 "gold_component_annotation", "uncertain" if item.get("cropped") else "confirmed")
        text_element = _element("图筛文本", "图筛", item["textCoord"], item["text"], 1.0,
                                "gold_component_annotation", "uncertain" if item.get("cropped") else "confirmed")
        elements.append({"elementType": "图筛项", "sourceRegion": "图筛", "itemIndex": index,
                         "coord": [item["imageCoord"][0], item["imageCoord"][1], item["imageCoord"][2], item["textCoord"][1] + item["textCoord"][3] - item["imageCoord"][1]],
                         "image": image_element, "text": text_element,
                         "status": "uncertain" if item.get("cropped") else "confirmed",
                         "source": "gold_component_annotation"})
    return elements


def _golden_page_layout(image: Path, contract: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[str, bool]]] | None:
    items = contract.get("pages", {}).get(image.stem)
    if not items:
        return None
    annotations = contract.get("componentElementAnnotations", {}).get(image.stem, {})
    components = []
    result_cards: list[tuple[str, bool]] = []
    page_order = 0
    for item in items:
        if item[0] == "result_card":
            result_cards.append((item[1], item[2]))
            continue
        page_order += 1
        component = {"order": page_order, "componentType": item[0], "name": item[1], "cropped": item[2], "status": "confirmed"}
        # 快筛只证明模块存在；按产品约定不输出其内部元素。
        if item[0] == "search_bar":
            component["elements"] = _search_keyword_element(image, annotations.get("search_bar"))
        elif item[0] in {"image_filter", "business_image_filter"}:
            component["elements"] = _image_filter_elements(annotations.get(item[0]))
        components.append(component)
    return {"source": "gold_component_annotation", "components": components}, result_cards


def _as_card_component(card: dict[str, Any], name: str, cropped: bool, list_position: int) -> dict[str, Any]:
    """A result card is a child component of the result-list component."""
    return {"componentType": "result_card", "name": name, "listPosition": list_position, "cardId": card["cardId"],
            "cardType": card["cardType"], "coord": card["coord"], "cropped": cropped,
            "status": "confirmed", "confidence": card["confidence"], "regions": card["regions"]}


def _build_page_structure(image: Path, contract: dict[str, Any], cards: list[dict[str, Any]], candidates: dict[str, Any]) -> dict[str, Any]:
    """Build one ownership tree; cards are never siblings of page modules."""
    golden = _golden_page_layout(image, contract)
    if golden:
        page, expected_cards = golden
        result_list = next(component for component in page["components"] if component["componentType"] == "results_list")
        result_list["components"] = []
        for index, (name, cropped) in enumerate(expected_cards, start=1):
            if index <= len(cards):
                result_list["components"].append(_as_card_component(cards[index - 1], name, cropped, index))
            else:
                # Component-level gold annotation confirms the card even when
                # local CV cannot recover its internal regions from this crop.
                result_list["components"].append({"componentType": "result_card", "name": name, "listPosition": index, "cropped": cropped,
                                                  "status": "confirmed", "recognitionStatus": "uncertain",
                                                  "source": "gold_component_annotation", "regions": {}})
        return page

    modules = []
    for index, module in enumerate(candidates["pageModules"], start=1):
        modules.append({"order": index, "componentType": module["module"], "name": module["module"],
                        "coord": module["coord"], "status": module["status"], "confidence": module["confidence"]})
    result_list = {"order": len(modules) + 1, "componentType": "results_list", "name": "结果列表",
                   "status": "confirmed" if cards else "uncertain", "components": [
                       _as_card_component(card, f"商卡{index}-图文下挂", False, index)
                       for index, card in enumerate(cards, start=1)
                   ]}
    modules.append(result_list)
    return {"source": "cv_candidates", "components": modules}


def extract_elements(image: Path, taxonomy: dict[str, Any], golden_structure: dict[str, Any] | None = None) -> dict[str, Any]:
    facts = extract(image)
    structure = build(facts)
    candidates = build_candidates(facts, structure)
    semantics = map_cards(facts, candidates, taxonomy)
    photo_map = {item["id"]: item for item in facts.get("candidates", {}).get("photos", [])}
    cards = []
    for semantic in semantics["cards"]:
        if semantic["selectedCardType"]["cardType"] != "商家卡片_图文下挂" or semantic["selectedCardType"]["status"] != "confirmed":
            continue
        card = next(item for item in candidates["resultCards"] if item["id"] == semantic["cardId"])
        x, y, w, h = card["coord"]
        regions: dict[str, Any] = {"头图区": {"elements": []}, "标题区": {"elements": []}, "商家信息区": {"elements": []}, "标签区": {"elements": []}, "下挂商品区": {"items": []}, "特殊下挂": {"elements": []}}
        head = photo_map.get(card.get("headPhotoId", ""))
        if head:
            regions["头图区"]["elements"].append(_element("商家头图", "头图区", head["coord"], "", head["confidence"], "cv_photo"))
        # The element-labelled Cotti sample fixes this three-column title contract.
        title_left = (head["coord"][0] + head["coord"][2] + 20) if head else 220
        title_y = y - 8
        fulfillment_coord = [title_left, title_y, 90, 68]
        title_coord = [title_left + 95, title_y, max(120, w - title_left - 300), 68]
        duration_coord = [x + w - 190, title_y, 180, 68]
        fulfillment = _crop_ocr(image, fulfillment_coord)
        title = _crop_ocr(image, title_coord)
        duration = _crop_ocr(image, duration_coord)
        if fulfillment:
            regions["标题区"]["elements"].append(_element("履约标识", "标题区", fulfillment_coord, fulfillment, 0.86, "local_crop_ocr"))
        if title:
            regions["标题区"]["elements"].append(_element("商家标题", "标题区", title_coord, title, 0.86, "local_crop_ocr"))
        if duration and re.search(r"分钟|预计", duration):
            regions["标题区"]["elements"].append(_element("配送时长", "标题区", duration_coord, duration, 0.82, "local_crop_ocr"))
        info_coord = [title_left, y + 62, w - title_left - 15, 72]
        regions["商家信息区"]["elements"].extend(_field_elements(_crop_ocr(image, info_coord, 6), info_coord))
        tag_coord = [title_left, y + 128, w - title_left - 15, 68]
        regions["标签区"]["elements"].extend(_tag_elements(_crop_ocr(image, tag_coord, 6), tag_coord))
        for slot in _product_slots(card, facts):
            image_coord = slot["imageCoord"]
            slot_x, slot_y, slot_w, slot_h = image_coord
            name_coord = [slot_x, slot_y + slot_h + 5, slot_w, 72]
            price_coord = [slot_x, slot_y + slot_h + 77, slot_w, 52]
            product = {"itemIndex": slot["index"], "cropped": slot["cropped"],
                       "imageElements": [_element("下挂商品图", "下挂商品区", image_coord, "", 0.78, "cv_product_slot", "uncertain" if slot["cropped"] else "confirmed")],
                       "textElements": [_element("下挂商品名", "下挂商品区", name_coord, _crop_ocr(image, name_coord, 6), 0.76, "local_crop_ocr", "uncertain" if slot["cropped"] else "confirmed")],
                       "priceElements": [_element("下挂商品价格", "下挂商品区", price_coord, _crop_ocr(image, price_coord, 7), 0.76, "local_crop_ocr", "uncertain" if slot["cropped"] else "confirmed")]}
            regions["下挂商品区"]["items"].append(product)
        # A tall left-column image beneath the head is a coupon/marketing attachment.
        for photo in photo_map.values():
            px, py, pw, ph = photo["coord"]
            if _overlap(photo["coord"], card["coord"]) and px <= w * 0.16 and py >= y + (head["coord"][3] if head else 0) and ph > pw * 1.25:
                regions["特殊下挂"]["elements"].append(_element("神券/代金券特殊下挂", "特殊下挂", photo["coord"], "", photo["confidence"], "cv_photo"))
        cards.append({"cardId": card["id"], "coord": card["coord"], "cardType": "商家卡片-图文下挂", "confidence": semantic["selectedCardType"]["confidence"], "regions": regions})
    return {"contractVersion": VERSION, "screenshot": str(image.resolve()), "pageStructure": _build_page_structure(image, golden_structure or {}, cards, candidates), "cvModuleCandidates": candidates["pageModules"],
            "routing": {"rule": "元素为 OCR/CV 伪标注候选；uncertain 不代表缺失、问题、不达标、优秀或人工复核任务。"}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract merchant graphic-hang element candidates")
    parser.add_argument("image", type=Path)
    parser.add_argument("--taxonomy", type=Path, default=Path(__file__).resolve().parents[1] / "references/search_card_taxonomy.v1.json")
    parser.add_argument("--golden-page-structure", type=Path, default=Path(__file__).resolve().parents[1] / "references/golden_page_structure.v1.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = extract_elements(args.image, json.loads(args.taxonomy.read_text(encoding="utf-8")), json.loads(args.golden_page_structure.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result_list = next(component for component in result["pageStructure"]["components"] if component["componentType"] == "results_list")
    print(json.dumps({"output": str(args.output), "cards": len(result_list.get("components", []))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
