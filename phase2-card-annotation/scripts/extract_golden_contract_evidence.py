#!/usr/bin/env python3
"""Extract bounded OCR evidence for golden element-contract calibration.

This is an offline golden-only tool.  It reads already reviewed result-card
boundaries and OCRs only the card title strip plus any legacy element that is
likely to contain several independent tags/basic-info fields.  It never edits
the golden JSON and must never be called by the Phase2 production entrypoint.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterator

from extract_cv_facts import ocr_region


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "phase2-card-annotation" / "golden-sample-results"


def cards(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for component in payload.get("pageStructure", {}).get("components", []):
        if component.get("componentType") != "results_list":
            continue
        for card in component.get("components", []):
            if card.get("componentType") == "result_card":
                yield card


def elements(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if "elementType" in value:
            yield value
        for child in value.values():
            yield from elements(child)
    elif isinstance(value, list):
        for child in value:
            yield from elements(child)


def has_title(card: dict[str, Any]) -> bool:
    region = card.get("regions", {}).get("标题区", {})
    return any(
        "标题" in str(item.get("elementType", ""))
        and len(re.sub(r"\s+", "", str(item.get("visibleText", "")))) >= 2
        for item in elements(region)
    )


def title_strip(card: dict[str, Any]) -> list[int] | None:
    coord = card.get("coord")
    if not isinstance(coord, list) or len(coord) != 4:
        return None
    x, y, width, height = coord
    card_type = card.get("cardType")
    if card_type == "商品卡片":
        left, strip_height = x + min(360, int(width * 0.30)), min(150, height)
    elif str(card_type).startswith("商家卡片_"):
        left, strip_height = x + min(180, int(width * 0.15)), min(125, height)
    else:
        left, strip_height = x, min(150, height)
    return [left, y, max(1, x + width - left), max(1, strip_height)]


def likely_merged(item: dict[str, Any]) -> bool:
    text = str(item.get("visibleText", "")).strip()
    region = str(item.get("sourceRegion", ""))
    if region not in {"标签区", "基础信息区", "商家信息区"}:
        return False
    if any(mark in text for mark in ("｜", "|", "；")):
        return True
    anchors = re.findall(r"神券|立减|最高|榜第|回头客|公益商家|好评率|全程保|近期|人均|月售|评分|km|公里", text)
    return len(anchors) >= 2 or len(text) >= 18


def extract(path: Path) -> dict[str, Any]:
    path = path.resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    screenshot = ROOT / payload["verification"]["rawScreenshot"]
    requests: list[dict[str, Any]] = []
    for card in cards(payload):
        if card.get("visibleStatus") == "complete" and card.get("cardType") not in {"异构卡", "广告卡"} and not has_title(card):
            coord = title_strip(card)
            if coord:
                requests.append({"kind": "missing_title", "listPosition": card.get("listPosition"), "coord": coord})
        for item in elements(card.get("regions", {})):
            if likely_merged(item) and isinstance(item.get("coord"), list):
                requests.append({
                    "kind": "merged_semantic_region",
                    "listPosition": card.get("listPosition"),
                    "legacyText": item.get("visibleText", ""),
                    "sourceRegion": item.get("sourceRegion", ""),
                    "coord": item["coord"],
                })
        if str(card.get("cardType", "")) == "商家卡片_图文下挂" and isinstance(card.get("coord"), list):
            card_bottom = card["coord"][1] + card["coord"][3]
            region = card.get("regions", {}).get("下挂商品区", {})
            for item in region.get("items", region.get("products", [])):
                image_values = item.get("imageElements", [])
                if not image_values and isinstance(item.get("image"), dict):
                    image_values = [item["image"]]
                text_values = item.get("textElements", [])
                if not text_values and isinstance(item.get("name"), dict):
                    text_values = [item["name"]]
                price_values = item.get("priceElements", [])
                if not price_values and isinstance(item.get("price"), dict):
                    price_values = [item["price"]]
                meaningful = lambda values: any(len(re.sub(r"\s+", "", str(value.get("visibleText", "")))) > 1 for value in values)
                if image_values and (not meaningful(text_values) or not meaningful(price_values)):
                    ix, iy, iw, ih = image_values[0]["coord"]
                    requests.append({
                        "kind": "incomplete_downhang_item",
                        "listPosition": card.get("listPosition"),
                        "itemIndex": item.get("itemIndex", item.get("productIndex")),
                        "imageBottom": iy + ih,
                        "coord": [ix, iy, iw, max(1, min(card_bottom - iy, max(ih + 170, 390)))],
                    })
    for request in requests:
        observations, backend, error = ocr_region(screenshot, request["coord"])
        request.update({"backend": backend, "error": error or "", "observations": observations})
    return {"golden": str(path.relative_to(ROOT)), "screenshot": str(screenshot.relative_to(ROOT)), "requests": requests}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("golden", type=Path, nargs="*")
    args = parser.parse_args()
    paths = args.golden or sorted(RESULTS.rglob("*.elements.json"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for path in paths:
        payload = extract(path)
        output = args.output_dir / f"{path.parent.name}--{path.stem}.contract-evidence.json"
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary.append({"output": str(output), "requests": len(payload["requests"])})
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
