#!/usr/bin/env python3
"""Extract golden-only OCR evidence for each graphic downhang item column.

The crop is derived from the reviewed image element and card bottom.  It never
uses a fixed global x slot, and therefore cannot merge adjacent product names.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image

from extract_cv_facts import ocr_region


ROOT = Path(__file__).resolve().parents[2]


# Pixel-reviewed column containers for pages where the generic photo detector
# locked onto objects/text *inside* a product image and split one real column
# into several false 96/134 px slots.
MANUAL_ITEM_IMAGES: dict[tuple[str, int], list[list[int]]] = {
    ("盒马.elements.json", 1): [[227, 923, 264, 264], [504, 923, 264, 264], [781, 923, 264, 264], [1058, 923, 166, 264]],
    ("盒马.elements.json", 2): [[227, 1579, 264, 264], [504, 1579, 264, 264], [781, 1579, 264, 264], [1058, 1579, 166, 264]],
    ("盒马.elements.json", 3): [[227, 2217, 264, 264], [504, 2217, 264, 264], [781, 2217, 264, 264], [1058, 2217, 166, 264]],
    ("蜜雪冰城.elements.json", 1): [[227, 1538, 264, 264], [504, 1538, 264, 264], [781, 1538, 264, 264], [1058, 1538, 166, 264]],
    ("药店.elements.json", 2): [[227, 1810, 264, 240], [504, 1810, 264, 240], [781, 1810, 264, 240], [1058, 1810, 166, 240]],
}


def image_values(item: dict[str, Any]) -> list[dict[str, Any]]:
    values = item.get("imageElements", [])
    if not values and isinstance(item.get("image"), dict):
        values = [item["image"]]
    return values


def extract(path: Path, required_backend: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    screenshot = ROOT / payload["verification"]["rawScreenshot"]
    with Image.open(screenshot) as source_image:
        screenshot_height = source_image.height
    cards = []
    for component in payload["pageStructure"]["components"]:
        if component.get("componentType") != "results_list":
            continue
        result_cards = component.get("components", [])
        for card_index, card in enumerate(result_cards):
            region = card.get("regions", {}).get("下挂商品区", {})
            card_bottom = card["coord"][1] + card["coord"][3]
            next_card_top = result_cards[card_index + 1]["coord"][1] if card_index + 1 < len(result_cards) else screenshot_height
            item_results = []
            existing_items = region.get("items", region.get("products", []))
            manual = MANUAL_ITEM_IMAGES.get((path.name, int(card.get("listPosition", 0))))
            source_items = ([{"itemIndex": index, "imageElements": [{"coord": coord}]} for index, coord in enumerate(manual, 1)] if manual else existing_items)
            for item in source_items:
                images = image_values(item)
                if not images:
                    continue
                ix, iy, iw, ih = images[0]["coord"]
                top = min(card_bottom, iy + ih - 4)
                # The reviewed card box may end before its appended price row.
                # The next result card's top is the actual ownership boundary:
                # it preserves this card's price without leaking the following
                # merchant header into the product column.
                crop_bottom = min(screenshot_height, next_card_top)
                coord = [ix, top, iw, max(1, crop_bottom - top)]
                observations, backend, error = ocr_region(screenshot, coord)
                naturally_cropped_empty = (card.get("visibleStatus") == "naturally_cropped" or iw < 180) and backend != required_backend
                if backend != required_backend and not naturally_cropped_empty:
                    raise RuntimeError(f"{path}: card {card.get('listPosition')} item {item.get('itemIndex')}: required {required_backend}, got {backend}: {error}")
                if naturally_cropped_empty:
                    observations = []
                    backend = f"{required_backend}_empty_naturally_cropped"
                item_results.append({
                    "itemIndex": item.get("itemIndex", item.get("productIndex")),
                    "imageCoord": images[0]["coord"],
                    "coord": coord,
                    "backend": backend,
                    "observations": observations,
                })
            cards.append({"listPosition": card.get("listPosition"), "items": item_results})
    return {"golden": str(path.resolve()), "screenshot": str(screenshot.resolve()), "cards": cards}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("golden", type=Path, nargs="+")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--require-backend", default="paddleocr", choices=("paddleocr", "tesseract"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for path in args.golden:
        payload = extract(path, args.require_backend)
        output = args.output_dir / f"{path.stem}.graphic-items-ocr.json"
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary.append({"output": str(output), "items": sum(len(card["items"]) for card in payload["cards"])})
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
