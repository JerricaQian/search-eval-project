#!/usr/bin/env python3
"""Apply explicit pixel-reviewed tag atom boundaries to golden JSON files."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "phase2-card-annotation" / "golden-sample-results"
DEFAULT_REVIEWS = ROOT / "phase2-card-annotation" / "references" / "golden_tag_split_reviews.v1.json"


def result_cards(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for component in payload.get("pageStructure", {}).get("components", []):
        for card in component.get("components", []):
            if card.get("componentType") == "result_card":
                yield card


def load_reviews(path: Path) -> dict[tuple[str, int, str], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        (item["golden"], int(item["listPosition"]), item["legacyText"]): item["atoms"]
        for item in payload["reviews"]
    }


def apply_to_card(relative: str, card: dict[str, Any], reviews: dict[tuple[str, int, str], list[dict[str, Any]]]) -> int:
    values = card.get("regions", {}).get("标签区", {}).get("elements", [])
    if not isinstance(values, list):
        return 0
    before = list(values)
    output: list[dict[str, Any]] = []
    changed = 0
    for element in values:
        key = (relative, int(card.get("listPosition", 0)), str(element.get("visibleText", "")))
        atoms = reviews.get(key)
        if atoms is None:
            output.append(element)
            continue
        for atom in atoms:
            value = {
                "elementType": element.get("elementType", "商家标签"),
                "sourceRegion": "标签区",
                "coord": atom["coord"],
                "visibleText": atom["visibleText"],
                "status": "confirmed",
                "source": "model_pixel_calibrated_independent_visual_entities",
                "boundedEvidence": [{"coord": atom["coord"]}],
            }
            if "itemIndex" in element:
                value["itemIndex"] = copy.deepcopy(element["itemIndex"])
            output.append(value)
        changed += 1
    # OCR boxes on one visual row commonly differ by 1–3 vertical pixels.
    # Bucket that jitter before x-ordering so publication preserves reading
    # order instead of placing a right-hand tag before its left sibling.
    values[:] = sorted(output, key=lambda item: (round(item.get("coord", [0, 0])[1] / 10), item.get("coord", [0, 0])[0], item.get("coord", [0, 0])[1]))
    return changed + int(values != before and changed == 0)


def apply_to_path(path: Path, reviews: dict[tuple[str, int, str], list[dict[str, Any]]]) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    relative = str(path.relative_to(RESULTS))
    changed = sum(apply_to_card(relative, card, reviews) for card in result_cards(payload))
    if changed:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("golden", type=Path, nargs="*")
    args = parser.parse_args()
    reviews = load_reviews(args.reviews)
    paths = [path.resolve() for path in args.golden] if args.golden else sorted(RESULTS.rglob("*.elements.json"))
    output = {str(path.relative_to(ROOT)): apply_to_path(path, reviews) for path in paths}
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
