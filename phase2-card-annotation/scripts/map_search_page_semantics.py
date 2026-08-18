#!/usr/bin/env python3
"""Map OCR candidates to conservative search-page semantic-role candidates."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


VERSION = "phase2.semantic-candidates.v1"


def _block_for(coord: list[int], blocks: list[dict[str, Any]]) -> dict[str, Any] | None:
    y0, y1 = coord[1], coord[1] + coord[3]
    matches = [block for block in blocks if block["coord"][1] < y1 and block["coord"][1] + block["coord"][3] > y0]
    return max(matches, key=lambda block: min(y1, block["coord"][1] + block["coord"][3]) - max(y0, block["coord"][1]), default=None)


def _candidates_for_text(item: dict[str, Any], block: dict[str, Any] | None, rules: dict[str, Any]) -> list[dict[str, Any]]:
    text = str(item.get("text", "")).strip()
    candidates: list[dict[str, Any]] = []
    for rule in rules["textRules"]:
        if not re.search(rule["pattern"], text):
            continue
        # Semantic mapping is deterministic rule matching. OCR engine scores
        # are intentionally not exported or used as a model-escalation signal.
        score = float(rule["score"])
        color = item.get("visualHint", {}).get("colorRole", "unknown")
        score += float(rules.get("visualBonuses", {}).get(rule["role"], {}).get(color, 0))
        requirements = list(rule.get("requires", []))
        evidence = [f"rule:{rule['id']}", f"color:{color}"]
        if "price_color_or_position" in requirements and color not in {"red", "orange"}:
            if not block or block.get("layoutCandidate") not in {"left_image_right_text", "top_image_bottom_text"}:
                evidence.append("missing:price_color_or_position")
                score -= 0.18
        candidates.append({"role": rule["role"], "score": round(max(0, min(score, 1)), 4), "evidence": evidence})
    return candidates


def map_semantics(facts: dict[str, Any], structure: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    if facts.get("contractVersion") != "phase2.cv-facts.v1":
        raise ValueError("cv facts version is not supported")
    if structure.get("contractVersion") != "phase2.search-page-structure.v1":
        raise ValueError("structure version is not supported")
    confirmed_threshold = float(rules["initialThresholds"]["confirmed"])
    uncertain_threshold = float(rules["initialThresholds"]["uncertain"])
    outputs: list[dict[str, Any]] = []
    for item in facts.get("candidates", {}).get("text", []):
        if item.get("route") == "rejected":
            continue
        block = _block_for(item["coord"], structure.get("blocks", []))
        candidates = _candidates_for_text(item, block, rules)
        # A top-most text in a known image/text layout is only a title
        # candidate when no stronger structured field rule matched.
        if not candidates and block and block.get("layoutCandidate") in {"left_image_right_text", "top_image_bottom_text"}:
            if item["coord"][1] <= block["coord"][1] + max(64, block["coord"][3] // 3):
                candidates.append({"role": "title", "score": 0.82, "evidence": ["rule:top_text_in_image_text_layout"]})
        candidates.sort(key=lambda candidate: candidate["score"], reverse=True)
        best = candidates[0] if candidates else {"role": "other", "score": 0.0, "evidence": ["no_domain_rule_matched"]}
        status = "confirmed" if best["score"] >= confirmed_threshold else "uncertain"
        # A near-tie means the evidence cannot safely choose one region.
        if len(candidates) > 1 and candidates[0]["score"] - candidates[1]["score"] < 0.08:
            status = "uncertain"
            best["evidence"].append("role_scores_too_close")
        outputs.append({
            "sourceId": item["id"], "text": item["text"], "coord": item["coord"],
            "blockId": block.get("id") if block else "", "semanticRoleCandidate": best["role"],
            "regionCandidate": rules["roleToRegion"].get(best["role"], "基础信息区"),
            "confidence": best["score"], "status": status, "evidence": best["evidence"],
        })
    return {
        "contractVersion": VERSION, "sourceCvFacts": facts.get("screenshot", ""),
        "rulesVersion": rules["contractVersion"], "candidates": outputs,
        "routing": {
            "rule": "Only confirmed candidates may seed a Phase2 region. Uncertain candidates cannot imply absence, defects, or excellence.",
            "uncertainSourceIds": [item["sourceId"] for item in outputs if item["status"] != "confirmed"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Map search-page OCR candidates to semantic candidates")
    parser.add_argument("cv_facts", type=Path)
    parser.add_argument("structure", type=Path)
    parser.add_argument("--rules", type=Path, default=Path(__file__).resolve().parents[1] / "references/search_page_semantic_rules.v1.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = map_semantics(
        json.loads(args.cv_facts.read_text(encoding="utf-8")),
        json.loads(args.structure.read_text(encoding="utf-8")),
        json.loads(args.rules.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "confirmed": sum(item["status"] == "confirmed" for item in result["candidates"]), "uncertain": len(result["routing"]["uncertainSourceIds"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
