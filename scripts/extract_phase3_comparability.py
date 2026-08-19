#!/usr/bin/env python3
"""Derive cross-card comparability evidence from Phase2 atomic facts.

Phase2 owns element identity, ownership, coordinates, render state and basic
semantic/visual facts.  This Phase3 helper owns grouping comparable cards,
matching fields and extracting observable format/position/style differences.
It deliberately does not rate those differences; the eval skill decides
whether they materially hinder comparison.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from phase2_bundle_loader import load_phase2_facts


NON_COMPARABLE_ROLES = {"", "other", "marketing_copy", "recommendation"}


def element_text(element: dict[str, Any]) -> str:
    facts = element.get("textFacts") if isinstance(element.get("textFacts"), dict) else {}
    raw = facts.get("rawText")
    if isinstance(raw, str):
        return raw.strip()
    summary = str(element.get("内容简述", ""))
    return summary.removeprefix("原文:").strip()


def format_signature(text: str) -> str:
    """Keep units/punctuation while replacing values with stable tokens."""
    value = re.sub(r"\d+(?:\.\d+)?", "#", text)
    value = re.sub(r"\s+", "", value)
    return value.lower()


def relative_position(coord: list[int], card_coord: list[int]) -> dict[str, float]:
    x, y, width, height = coord
    card_x, card_y, card_width, card_height = card_coord
    return {
        "x": round((x - card_x) / max(card_width, 1), 4),
        "y": round((y - card_y) / max(card_height, 1), 4),
        "width": round(width / max(card_width, 1), 4),
        "height": round(height / max(card_height, 1), 4),
    }


def style_signature(element: dict[str, Any]) -> dict[str, Any]:
    facts = element.get("textFacts") if isinstance(element.get("textFacts"), dict) else {}
    visual = element.get("visual") if isinstance(element.get("visual"), dict) else {}
    return {
        "entityKind": visual.get("entityKind"),
        "colorRole": visual.get("colorRole"),
        "containerShape": visual.get("containerShape"),
        "graphicAssistRole": visual.get("graphicAssistRole", visual.get("graphicType")),
        "emphasisLevel": facts.get("emphasisLevel"),
        "fontSizeBucket": facts.get("fontSizeBucket"),
        "fontWeightBucket": facts.get("fontWeightBucket"),
        "textColorRole": facts.get("textColorRole"),
    }


def iter_card_elements(card: dict[str, Any]):
    for region in card.get("regions", []):
        region_name = str(region.get("name", ""))
        for element in region.get("elements", []):
            if isinstance(element, dict):
                yield region_name, element


def eligible_element(region_name: str, element: dict[str, Any]) -> bool:
    if element.get("isExcluded") is True or element.get("元素类型") == "图片":
        return False
    render = element.get("render") if isinstance(element.get("render"), dict) else {}
    facts = element.get("textFacts") if isinstance(element.get("textFacts"), dict) else {}
    if render.get("visibleStatus") != "confirmed":
        return False
    # A naturally cropped value is a valid visible atom but not a complete
    # cross-card value; Phase3 may still evaluate it in non-comparison skills.
    if render.get("renderState") == "naturally_cropped" or facts.get("textStatus") == "naturally_ellipsized":
        return False
    role = str(facts.get("semanticRole", ""))
    return role not in NON_COMPARABLE_ROLES and bool(element_text(element)) and bool(region_name)


def derive_comparability(manifest: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    excluded: list[dict[str, Any]] = []
    for card in manifest.get("cards", []):
        structure = card.get("structure") if isinstance(card.get("structure"), dict) else {}
        if not structure.get("isResultListItem"):
            continue
        key = str(structure.get("comparisonGroupKey") or "").strip()
        if not key:
            # Atomic v3 deliberately does not pre-group cards for an eval.
            # Phase3 derives a structural candidate group from neutral facts.
            card_type = str(card.get("cardTypeCode") or card.get("卡片类型") or "unknown")
            variant = str(card.get("variant") or "")
            key = f"{card_type}|{variant}"
        if not key:
            excluded.append({"cardId": card.get("cardId"), "reason": "missing_comparison_group_key"})
            continue
        groups[key].append(card)

    card_groups: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    for key, cards in sorted(groups.items()):
        card_groups.append({"comparisonGroupKey": key, "cardIds": [card.get("cardId") for card in cards]})
        if len(cards) < 2:
            continue
        fields: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for card in cards:
            card_coord = card.get("coord")
            if not isinstance(card_coord, list) or len(card_coord) != 4:
                excluded.append({"cardId": card.get("cardId"), "reason": "invalid_card_coord"})
                continue
            seen_roles: set[str] = set()
            for region_name, element in iter_card_elements(card):
                if not eligible_element(region_name, element):
                    continue
                role = str(element["textFacts"]["semanticRole"])
                # Multiple elements with one role in a card need semantic
                # disambiguation by the evaluator; do not invent an ordering.
                if role in seen_roles:
                    excluded.append({"cardId": card.get("cardId"), "elementId": element.get("id"), "reason": "ambiguous_repeated_role", "semanticRole": role})
                    continue
                seen_roles.add(role)
                text = element_text(element)
                fields[role].append({
                    "cardId": card.get("cardId"),
                    "elementId": element.get("id"),
                    "semanticRole": role,
                    "text": text,
                    "formatSignature": format_signature(text),
                    "region": region_name,
                    "relativePosition": relative_position(element.get("坐标"), card_coord),
                    "styleSignature": style_signature(element),
                })
        for role, observations in sorted(fields.items()):
            if len({item["cardId"] for item in observations}) < 2:
                continue
            formats = {item["formatSignature"] for item in observations}
            regions = {item["region"] for item in observations}
            styles = {json.dumps(item["styleSignature"], ensure_ascii=False, sort_keys=True) for item in observations}
            comparisons.append({
                "comparisonGroupKey": key,
                "semanticRole": role,
                "observations": observations,
                "detectedDifferences": {
                    "format": len(formats) > 1,
                    "region": len(regions) > 1,
                    "style": len(styles) > 1,
                },
                "phase3JudgementRequired": True,
            })
    return {
        "contractVersion": "phase3.comparability-extraction.v1",
        "query": manifest.get("query", ""),
        "cardGroups": card_groups,
        "comparisons": comparisons,
        "excludedCandidates": excluded,
        "notes": ["差异是 Phase3 候选证据，不直接等于可比性问题或评级"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract Phase3 cross-card comparability candidates")
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument("--normalized-input", type=Path)
    parser.add_argument("--evidence-input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.normalized_input:
        if args.manifest or not args.evidence_input:
            parser.error("--normalized-input requires --evidence-input and cannot be combined with manifest")
        manifest = load_phase2_facts(normalized_path=args.normalized_input, evidence_path=args.evidence_input)
    else:
        if not args.manifest or args.evidence_input:
            parser.error("provide manifest, or --normalized-input with --evidence-input")
        manifest = load_phase2_facts(manifest_path=args.manifest)
    result = derive_comparability(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "groups": len(result["cardGroups"]), "comparisons": len(result["comparisons"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
