#!/usr/bin/env python3
"""Build non-semantic search-page structure candidates from CV/OCR facts.

The output intentionally stops at layout: block boundaries, image/text groups,
and their confidence.  Domain labels such as 商品卡片、标题区 and 价格区 remain
the responsibility of the search-page rule layer, so a weak geometric signal
cannot turn into a false missing-field or evaluation conclusion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VERSION = "phase2.search-page-structure.v1"


def _box_of(item: dict[str, Any]) -> list[int]:
    return [int(value) for value in item["coord"]]


def _union(boxes: list[list[int]]) -> list[int] | None:
    if not boxes:
        return None
    x0 = min(box[0] for box in boxes)
    y0 = min(box[1] for box in boxes)
    x1 = max(box[0] + box[2] for box in boxes)
    y1 = max(box[1] + box[3] for box in boxes)
    return [x0, y0, x1 - x0, y1 - y0]


def _overlaps_y(box: list[int], y0: int, y1: int) -> bool:
    return box[1] < y1 and box[1] + box[3] > y0


def _build_blocks(facts: dict[str, Any], min_gap: int, min_height: int) -> list[dict[str, Any]]:
    viewport = facts["viewport"]
    height = int(viewport["height"])
    strong_gaps = [band for band in facts.get("whitespaceBands", []) if int(band.get("height", 0)) >= min_gap]
    boundaries = [0] + [int(band["y1"]) for band in strong_gaps] + [height]
    blocks: list[dict[str, Any]] = []
    for start, end in zip(boundaries, boundaries[1:]):
        if end - start < min_height:
            continue
        blocks.append({"coord": [0, start, int(viewport["width"]), end - start], "boundaryEvidence": "strong_whitespace"})
    # Entirely non-white screens can have no strong gaps.  Retain content rows
    # as weaker blocks rather than silently claiming a page has no structure.
    if not blocks:
        for row in facts.get("contentRows", []):
            if int(row.get("height", 0)) >= min_height:
                blocks.append({"coord": [0, int(row["y0"]), int(viewport["width"]), int(row["height"])], "boundaryEvidence": "content_row_fallback"})
    return blocks


def _layout_for_block(block: dict[str, Any], text: list[dict[str, Any]], photos: list[dict[str, Any]], width: int) -> tuple[str, list[dict[str, Any]], float, list[str]]:
    x, y, w, h = _box_of(block)
    texts = [item for item in text if _overlaps_y(_box_of(item), y, y + h)]
    images = [item for item in photos if _overlaps_y(_box_of(item), y, y + h)]
    text_box = _union([_box_of(item) for item in texts])
    image_box = _union([_box_of(item) for item in images])
    candidates: list[dict[str, Any]] = []
    if image_box:
        candidates.append({"kind": "image_group", "coord": image_box, "memberIds": [item["id"] for item in images]})
    if text_box:
        candidates.append({"kind": "text_group", "coord": text_box, "memberIds": [item["id"] for item in texts]})

    reasons: list[str] = []
    confidence = 0.42 if block["boundaryEvidence"] == "strong_whitespace" else 0.28
    if text_box:
        confidence += 0.24
    else:
        reasons.append("no_local_ocr_text_group")
    if image_box:
        confidence += 0.16
    if text_box and image_box:
        image_is_left = image_box[0] + image_box[2] <= text_box[0] + max(24, width // 30)
        image_is_above = image_box[1] + image_box[3] <= text_box[1] + max(18, h // 12)
        if image_is_left:
            return "left_image_right_text", candidates, min(confidence + 0.15, 0.95), reasons
        if image_is_above:
            return "top_image_bottom_text", candidates, min(confidence + 0.12, 0.95), reasons
        reasons.append("image_text_geometry_not_a_known_list_pattern")
    elif text_box:
        return "text_only", candidates, min(confidence, 0.9), reasons
    else:
        reasons.append("no_element_candidates_in_block")
    return "other", candidates, min(confidence, 0.9), reasons


def build(facts: dict[str, Any], min_gap: int = 16, min_height: int = 48) -> dict[str, Any]:
    if facts.get("contractVersion") != "phase2.cv-facts.v1":
        raise ValueError("input must be phase2.cv-facts.v1")
    viewport = facts["viewport"]
    text = list(facts.get("candidates", {}).get("text", []))
    photos = list(facts.get("candidates", {}).get("photos", []))
    structures: list[dict[str, Any]] = []
    for index, block in enumerate(_build_blocks(facts, min_gap, min_height), start=1):
        layout, regions, confidence, reasons = _layout_for_block(block, text, photos, int(viewport["width"]))
        if facts.get("routing", {}).get("missingCapabilities"):
            reasons.append("required_local_capability_missing")
            confidence = min(confidence, 0.49)
        structures.append({
            "id": f"B{index}", "coord": _box_of(block), "layoutCandidate": layout,
            "regionCandidates": regions, "confidence": round(confidence, 4),
            "boundaryEvidence": block["boundaryEvidence"],
            "route": "local_vision" if confidence < 0.75 else "accepted",
            "routeReasons": reasons,
        })
    return {
        "contractVersion": VERSION,
        "sourceCvFacts": facts.get("screenshot", ""), "viewport": viewport,
        "blocks": structures,
        "routing": {
            "initialStructureThreshold": 0.75,
            "unresolvedBlockIds": [block["id"] for block in structures if block["route"] != "accepted"],
            "rule": "Blocks are layout candidates only. Unresolved blocks must not imply missing modules, cards, or fields.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build search-page structure candidates from CV facts")
    parser.add_argument("cv_facts", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-gap", type=int, default=16)
    parser.add_argument("--min-height", type=int, default=48)
    args = parser.parse_args()
    facts = json.loads(args.cv_facts.read_text(encoding="utf-8"))
    result = build(facts, min_gap=args.min_gap, min_height=args.min_height)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "blocks": len(result["blocks"]), "unresolved": len(result["routing"]["unresolvedBlockIds"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
