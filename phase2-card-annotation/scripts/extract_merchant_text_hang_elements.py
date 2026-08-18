#!/usr/bin/env python3
"""Build conservative nested Phase2 candidates for merchant text-hang cards."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from extract_cv_facts import extract
from extract_merchant_graphic_hang_elements import _crop_ocr, _element, _field_elements, _tag_elements

VERSION = "phase2.merchant-text-hang-elements.v1"


def _safe_text(value: str) -> str:
    """Do not publish OCR noise as a UI fact."""
    value = re.sub(r"\s+", " ", value).strip().replace("#", "¥")
    if len(value) < 2 or re.search(r"\.\.|[A-Za-z]{4,}", value):
        return ""
    return value


def _text_element(kind: str, region: str, coord: list[int], value: str, confidence: float = .76) -> dict[str, Any]:
    value = _safe_text(value)
    return _element(kind, region, coord, value, confidence, "local_crop_ocr", "confirmed" if value else "uncertain")


def _text_item(product: dict[str, Any], index: int) -> dict[str, Any]:
    """Convert a detected lower attachment into one textual service item.

    The source reader keeps price/name separate; this adapter adds distinct
    optional discount and sales slots, never concatenating a service row.
    """
    image = product.get("image", {})
    name = product.get("name", {})
    price = product.get("price", {})
    x, y, w, h = name.get("coord", image.get("coord", [0, 0, 0, 0]))
    price_x, price_y, price_w, price_h = price.get("coord", [x, y, max(1, w // 4), h])
    return {
        "itemIndex": index,
        "coord": [min(x, price_x), min(y, price_y), max(w, price_w), max(h, price_h)],
        "price": {**price, "elementType": "下挂商品价格"},
        "discount": {"elementType": "下挂价格折扣标签", "sourceRegion": "文字下挂区", "coord": [price_x + price_w, price_y, 1, price_h], "visibleText": "", "status": "uncertain", "source": "not_observed"},
        "name": {**name, "elementType": "下挂商品名"},
        "sales": {"elementType": "下挂商品销量", "sourceRegion": "文字下挂区", "coord": [x + w, y, 1, h], "visibleText": "", "status": "uncertain", "source": "not_observed"},
        "status": "uncertain" if product.get("cropped") else "confirmed",
    }


def extract_elements(image: Path, taxonomy: dict[str, Any]) -> dict[str, Any]:
    facts = extract(image)
    width, height = facts["viewport"]["width"], facts["viewport"]["height"]
    # Text-hang cards have a stable large left head image.  This direct
    # detector intentionally does not depend on graphic-hang classification.
    heads = sorted([p for p in facts["candidates"]["photos"] if p["coord"][0] < width * .25 and p["coord"][1] > 650 and p["coord"][2] >= 100 and p["coord"][3] >= 100], key=lambda p: p["coord"][1])
    cards = []
    for index, head in enumerate(heads, 1):
        x, y, w, h = head["coord"]
        next_y = heads[index]["coord"][1] if index < len(heads) else height
        card_h = max(1, next_y - y)
        left = x + w + 20
        fulfillment_coord, title_coord = [left, y - 6, 92, 62], [left + 96, y - 6, width - left - 120, 62]
        info_coord = [left, y + 58, width - left - 24, 64]
        tag_coord, ai_coord = [left, y + 122, width - left - 24, 62], [left, y + 184, width - left - 24, 58]
        hang_y = y + 242
        regions: dict[str, Any] = {"头图区": {"elements": [_element("商家头图", "头图区", head["coord"], "", head["confidence"], "cv_photo")]}, "标题区": {"elements": []}, "商家信息区": {"elements": []}, "标签区": {"elements": []}, "AI推荐理由区": {"elements": []}, "文字下挂区": {"items": []}}
        fulfillment = _safe_text(_crop_ocr(image, fulfillment_coord))
        title_text = _safe_text(_crop_ocr(image, title_coord))
        if fulfillment in {"到店", "外卖", "上门", "景点"}:
            regions["标题区"]["elements"].append(_text_element("履约标签", "标题区", fulfillment_coord, fulfillment, .84))
        if title_text:
            regions["标题区"]["elements"].append(_text_element("商家标题", "标题区", title_coord, title_text, .8))
        regions["商家信息区"]["elements"].extend([item for item in _field_elements(_safe_text(_crop_ocr(image, info_coord, 6)), info_coord) if _safe_text(item["visibleText"])])
        regions["标签区"]["elements"].extend([item for item in _tag_elements(_safe_text(_crop_ocr(image, tag_coord, 6)), tag_coord) if _safe_text(item["visibleText"])])
        ai_text = _crop_ocr(image, ai_coord, 6)
        if ai_text:
            regions["AI推荐理由区"]["elements"].append(_text_element("AI推荐理由", "AI推荐理由区", ai_coord, ai_text))
        # Each visual text row is a service item: price/discount/name/sales are
        # deliberately separate crops, so no cross-row text can be merged.
        for item_index in range(2):
            row_y = hang_y + item_index * 70
            if row_y >= y + card_h - 4:
                break
            price_coord = [left, row_y, 100, 54]
            discount_coord = [left + 102, row_y, 110, 54]
            name_coord = [left + 214, row_y, max(80, width - left - 400), 54]
            sales_coord = [width - 180, row_y, 156, 54]
            regions["文字下挂区"]["items"].append({"itemIndex": item_index + 1, "coord": [left, row_y, width - left - 24, 54], "price": _text_element("下挂商品价格", "文字下挂区", price_coord, _crop_ocr(image, price_coord)), "discount": _text_element("下挂价格折扣标签", "文字下挂区", discount_coord, _crop_ocr(image, discount_coord), .72), "name": _text_element("下挂商品名", "文字下挂区", name_coord, _crop_ocr(image, name_coord, 6)), "sales": _text_element("下挂商品销量", "文字下挂区", sales_coord, _crop_ocr(image, sales_coord), .72)})
        cards.append({"componentType": "result_card", "name": f"商卡{index}-文字下挂", "listPosition": index, "cardType": "商家卡片-文字下挂", "coord": [0, y, width, card_h], "confidence": .8, "status": "confirmed", "cropped": next_y == height, "regions": regions})
    page_components = [{"order": 1, "componentType": "search_bar", "name": "搜索框", "status": "confirmed"}, {"order": 2, "componentType": "tab", "name": "Tab", "status": "confirmed"}, {"order": 3, "componentType": "results_list", "name": "结果列表", "status": "confirmed" if cards else "uncertain", "components": cards}]
    return {"contractVersion": VERSION, "screenshot": str(image.resolve()), "pageStructure": {"source": "cv_local_crop", "components": page_components}, "routing": {"rule": "文字下挂按服务行分组；uncertain 不表示缺失、问题、不达标、优秀或人工复核。"}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--taxonomy", type=Path, default=Path(__file__).resolve().parents[1] / "references/search_card_taxonomy.v1.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = extract_elements(args.image, json.loads(args.taxonomy.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
