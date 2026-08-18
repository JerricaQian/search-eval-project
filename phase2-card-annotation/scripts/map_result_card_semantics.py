#!/usr/bin/env python3
"""Map assembled result cards to card-type and region candidates.

No region is emitted as present merely because its card type defines it. A
region needs local geometry/text evidence; unknown card type leaves every
region unresolved rather than filling a generic template.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from classify_search_card_types import classify_card_types


VERSION = "phase2.result-card-semantics.v1"


def _overlap(box: list[int], container: list[int]) -> bool:
    return box[0] < container[0] + container[2] and box[0] + box[2] > container[0] and box[1] < container[1] + container[3] and box[1] + box[3] > container[1]


def _region_evidence(card: dict[str, Any], facts: dict[str, Any], definition: dict[str, Any]) -> list[dict[str, Any]]:
    x, y, w, h = card["coord"]
    texts = [item for item in facts.get("candidates", {}).get("text", []) if _overlap(item["coord"], card["coord"])]
    photos = [item for item in facts.get("candidates", {}).get("photos", []) if _overlap(item["coord"], card["coord"])]
    regions: list[dict[str, Any]] = []
    for index, region in enumerate(definition["regions"]):
        name = region["name"]
        evidence_ids: list[str] = []
        # Images support a head-image candidate only when they occupy card left
        # or upper area. Text evidence is intentionally spatial, not lexical.
        if "头图" in name:
            evidence_ids = [item["id"] for item in photos if item["coord"][0] < x + w * 0.45 and item["coord"][1] < y + h * 0.6]
        elif "标题" in name:
            evidence_ids = [item["id"] for item in texts if item["coord"][1] < y + max(72, h * 0.25) and item["coord"][0] > x + w * 0.18]
        elif "价格" in name:
            evidence_ids = [item["id"] for item in texts if "¥" in str(item.get("text", "")) or "￥" in str(item.get("text", ""))]
        else:
            vertical_start = y + int(h * (0.22 + min(index, 5) * 0.10))
            evidence_ids = [item["id"] for item in texts if item["coord"][1] >= vertical_start]
        confidence = 0.82 if evidence_ids else 0.0
        regions.append({"regionId": region["id"], "region": name, "status": "confirmed" if evidence_ids else "uncertain", "confidence": confidence, "evidenceSourceIds": evidence_ids})
    return regions


def _topology_type_candidate(card: dict[str, Any], facts: dict[str, Any], structure_blocks: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """Recognize the two merchant down-hang frameworks from local topology."""
    member_ids = card.get("memberBlockIds", [])
    if len(member_ids) < 2:
        return None
    seed = structure_blocks.get(card.get("seedBlockId", ""))
    if not seed:
        return None
    seed_bottom = seed["coord"][1] + seed["coord"][3]
    attached = [structure_blocks[item_id] for item_id in member_ids if item_id in structure_blocks and structure_blocks[item_id]["coord"][1] >= seed_bottom]
    attached_text_blocks = [block for block in attached if block.get("layoutCandidate") == "text_only"]
    card_text = [item for item in facts.get("candidates", {}).get("text", []) if _overlap(item["coord"], card["coord"])]
    attached_photos = [item for item in facts.get("candidates", {}).get("photos", []) if item["coord"][1] >= seed_bottom and _overlap(item["coord"], card["coord"])]
    if len(attached_photos) >= 2 and len(card_text) >= 2:
        return {"cardType": "商家卡片_图文下挂", "confidence": 0.82, "evidence": ["topology:merchant_body_plus_multiple_attached_product_images", "local_text_present"]}
    if len(attached_text_blocks) >= 1 and len(card_text) >= 2:
        return {"cardType": "商家卡片_文字下挂", "confidence": 0.80, "evidence": ["topology:merchant_body_plus_text_attachment", "local_text_present"]}
    return None


def map_cards(facts: dict[str, Any], candidates: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    definitions = {item["id"]: item for item in taxonomy["cardTypes"] if item.get("scope") == "results_list_card"}
    structure_blocks = {block["id"]: block for block in candidates.get("structureBlocks", [])}
    output: list[dict[str, Any]] = []
    for card in candidates.get("resultCards", []):
        type_result = classify_card_types(facts, taxonomy, card["coord"])
        selected = type_result["selected"]
        hint = card.get("classificationHint")
        if hint:
            type_result["candidates"].append({"cardType": hint["cardType"], "confidence": hint["confidence"], "evidence": list(card.get("evidence", []))})
            type_result["candidates"].sort(key=lambda item: item["confidence"], reverse=True)
            selected = {"cardType": hint["cardType"], "confidence": hint["confidence"], "status": "confirmed"}
            type_result["selected"] = selected
        topology = _topology_type_candidate(card, facts, structure_blocks)
        if selected["status"] != "confirmed" and topology:
            type_result["candidates"].append(topology)
            type_result["candidates"].sort(key=lambda item: item["confidence"], reverse=True)
            selected = {"cardType": topology["cardType"], "confidence": topology["confidence"], "status": "confirmed"}
            type_result["selected"] = selected
        definition = definitions.get(selected["cardType"]) if selected["status"] == "confirmed" else None
        output.append({
            "cardId": card["id"], "coord": card["coord"], "cardTypeCandidates": type_result["candidates"], "selectedCardType": selected,
            "topologyCandidate": topology,
            "regions": _region_evidence(card, facts, definition) if definition else [],
            "routing": "confirmed_card_type_required_for_region_mapping" if not definition else "region_evidence_required",
        })
    return {"contractVersion": VERSION, "sourceCvFacts": facts.get("screenshot", ""), "cards": output,
            "routing": {"rule": "Uncertain card type or region is not an absent element, defect, failing result, excellence, or human-review task."}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Map result-card candidates to semantic candidates")
    parser.add_argument("cv_facts", type=Path)
    parser.add_argument("result_candidates", type=Path)
    parser.add_argument("--taxonomy", type=Path, default=Path(__file__).resolve().parents[1] / "references/search_card_taxonomy.v1.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = map_cards(json.loads(args.cv_facts.read_text(encoding="utf-8")), json.loads(args.result_candidates.read_text(encoding="utf-8")), json.loads(args.taxonomy.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "cards": len(result["cards"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
