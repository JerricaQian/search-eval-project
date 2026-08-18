#!/usr/bin/env python3
"""Learn aggregate card geometry ranges from approved golden annotations.

Only human-approved/golden card boundaries are inputs. The output contains
normalized distributions, never screenshot-specific coordinates or predicted
labels, so production CV can use it without leaking a sample answer.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
ALIASES = {
    "商家卡片-图文下挂": "商家卡片_图文下挂",
    "商家卡片-文字下挂": "商家卡片_文字下挂",
    "电影影院卡": "演出电影卡片",
    "演出卡": "演出电影卡片",
}

# Geometry profiles describe fully visible mobile result cards.  These broad
# physical limits only reject broken/partial golden annotations; the learned
# p10/p90 ranges below remain the type-specific signal used by recognition.
STABLE_GEOMETRY_LIMITS = {
    "widthRatio": (0.25, 1.05),
    "heightRatio": (0.05, 0.45),
    "aspectRatio": (0.50, 8.00),
}


def quantile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return round(float(ordered[index]), 4)


def summary(values: list[float]) -> dict[str, float]:
    return {
        "p10": quantile(values, 0.10), "median": round(float(statistics.median(values)), 4),
        "p90": quantile(values, 0.90), "minimum": round(min(values), 4), "maximum": round(max(values), 4),
    }


def golden_cards(payload: dict[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []

    def visit(value: object) -> None:
        if isinstance(value, dict):
            if value.get("componentType") == "result_card":
                card_type = value.get("cardType")
                if isinstance(card_type, str) and card_type:
                    coord = value.get("coord")
                    cards.append({
                        "cardType": ALIASES.get(card_type, card_type),
                        "coord": coord if isinstance(coord, list) and len(coord) == 4 else None,
                        "name": value.get("name"),
                    })
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    return cards


def learn(paths: list[Path]) -> dict[str, Any]:
    observations: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    pages: dict[str, set[str]] = defaultdict(set)
    seen_pages: dict[str, set[str]] = defaultdict(set)
    excluded: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        screenshot = Path(payload["screenshot"])
        with Image.open(screenshot) as image:
            width, height = image.size
        source_cards = golden_cards(payload)
        for card in source_cards:
            seen_pages[card["cardType"]].add(str(path.relative_to(ROOT)))
        cards: list[dict[str, Any]] = []
        for card in source_cards:
            coord = card["coord"]
            if coord is None:
                excluded[card["cardType"]]["missingCoord"] += 1
                continue
            x, y, card_width, card_height = coord
            if card_width <= 0 or card_height <= 0:
                excluded[card["cardType"]]["invalidCoord"] += 1
                continue
            geometry = {
                "widthRatio": card_width / width,
                "heightRatio": card_height / height,
                "aspectRatio": card_width / card_height,
            }
            broken_fields = [
                field for field, value in geometry.items()
                if not STABLE_GEOMETRY_LIMITS[field][0] <= value <= STABLE_GEOMETRY_LIMITS[field][1]
            ]
            if broken_fields:
                excluded[card["cardType"]]["unstableOrPartialGeometry"] += 1
                continue
            cards.append(card)
        cards.sort(key=lambda item: item["coord"][1])
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for card in cards:
            by_type[card["cardType"]].append(card)
            x, y, card_width, card_height = card["coord"]
            values = observations[card["cardType"]]
            values["xRatio"].append(x / width)
            values["topRatio"].append(y / height)
            values["widthRatio"].append(card_width / width)
            values["heightRatio"].append(card_height / height)
            values["aspectRatio"].append(card_width / card_height)
            pages[card["cardType"]].add(str(path.relative_to(ROOT)))
        for card_type, typed_cards in by_type.items():
            observations[card_type]["cardsPerPage"].append(float(len(typed_cards)))
            for left, right in zip(typed_cards, typed_cards[1:]):
                observations[card_type]["topGapRatio"].append((right["coord"][1] - left["coord"][1]) / height)
    profiles = []
    for card_type in sorted(seen_pages):
        fields = observations[card_type]
        accepted_count = len(fields["widthRatio"])
        profiles.append({
            "cardType": card_type,
            "status": "learned" if accepted_count else "unavailable",
            "seenPageCount": len(seen_pages[card_type]),
            "pageCount": len(pages[card_type]),
            "cardCount": accepted_count,
            "excludedCardCount": sum(excluded[card_type].values()),
            "excludedReasons": dict(sorted(excluded[card_type].items())),
            "distributions": {name: summary(values) for name, values in sorted(fields.items()) if values},
        })
    return {
        "contractVersion": "phase2.learned-card-geometry-profiles.v1",
        "sourcePolicy": "Only approved golden result-card boundaries. Aggregate normalized ranges only; never reuse screenshot coordinates or predicted labels.",
        "stableGeometryLimits": {name: {"minimum": bounds[0], "maximum": bounds[1]} for name, bounds in STABLE_GEOMETRY_LIMITS.items()},
        "profiles": profiles,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Learn aggregate card geometry profiles from approved golden JSON")
    parser.add_argument("--golden-root", type=Path, default=ROOT / "phase2-card-annotation" / "golden-sample-results")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = sorted(args.golden_root.rglob("*.elements.json"))
    result = learn(paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"goldenFiles": len(paths), "profiles": len(result["profiles"]), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
