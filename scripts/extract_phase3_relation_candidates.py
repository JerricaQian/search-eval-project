#!/usr/bin/env python3
"""Enumerate Phase3 authenticity and redundancy candidate pairs.

The output is intentionally non-judgemental. Phase2 supplies atomic ownership
and visible facts; Phase3 enumerates pairs and each eval skill performs its own
semantic comparison before producing a verdict.
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
from pathlib import Path
from typing import Any

from phase2_bundle_loader import load_phase2_facts


DOWNHANG_REGIONS = {
    "下挂商品区", "文字下挂区", "下挂区", "服务下挂", "特殊下挂", "领域下挂区",
    "append_items", "text_append", "service_append",
}
CONSISTENCY_ROLES = {"subtitle", "size", "specification", "product_attribute"}


def text_of(element: dict[str, Any]) -> str:
    facts = element.get("textFacts") if isinstance(element.get("textFacts"), dict) else {}
    if isinstance(facts.get("rawText"), str):
        return facts["rawText"].strip()
    return re.sub(r"^原文[:：]\s*", "", str(element.get("内容简述", ""))).strip()


def normalized_text(text: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text.lower())


def atom(card_id: str, region: str, element: dict[str, Any]) -> dict[str, Any]:
    facts = element.get("textFacts") if isinstance(element.get("textFacts"), dict) else {}
    return {
        "cardId": card_id,
        "region": region,
        "elementId": element.get("id"),
        "elementType": element.get("元素类型"),
        "text": text_of(element),
        "semanticRole": facts.get("semanticRole"),
        "coord": element.get("坐标"),
    }


def derive_relation_candidates(manifest: dict[str, Any]) -> dict[str, Any]:
    authenticity: list[dict[str, Any]] = []
    redundancy: list[dict[str, Any]] = []
    for card in manifest.get("cards", []):
        card_id = str(card.get("cardId", ""))
        atoms: list[dict[str, Any]] = []
        titles: list[dict[str, Any]] = []
        targets: list[dict[str, Any]] = []
        for region_payload in card.get("regions", []):
            region = str(region_payload.get("name", ""))
            for element in region_payload.get("elements", []):
                if not isinstance(element, dict) or element.get("isExcluded") is True:
                    continue
                render = element.get("render") if isinstance(element.get("render"), dict) else {}
                visual = element.get("visual") if isinstance(element.get("visual"), dict) else {}
                if render.get("visibleStatus") != "confirmed" or visual.get("visualStatus") == "uncertain":
                    continue
                current = atom(card_id, region, element)
                atoms.append(current)
                if current["semanticRole"] == "title":
                    titles.append(current)
                if (
                    element.get("元素类型") == "图片"
                    or region in DOWNHANG_REGIONS
                    or current["semanticRole"] in CONSISTENCY_ROLES
                ):
                    targets.append(current)
        authenticity.append({
            "cardId": card_id,
            "titleAtoms": titles,
            "targetAtoms": targets,
            "candidatePairs": [
                {
                    "title": title,
                    "target": target,
                    "relationType": (
                        "title_to_image" if target["elementType"] == "图片"
                        else "title_to_size" if target["semanticRole"] in {"size", "specification"}
                        else "title_to_attribute"
                    ),
                    "phase3JudgementRequired": True,
                }
                for title in titles for target in targets if title["elementId"] != target["elementId"]
            ],
        })

        text_atoms = [item for item in atoms if item["text"]]
        pairs: list[dict[str, Any]] = []
        for left, right in itertools.combinations(text_atoms, 2):
            left_norm = normalized_text(left["text"])
            right_norm = normalized_text(right["text"])
            if not left_norm or not right_norm:
                continue
            exact = left_norm == right_norm
            containment = min(len(left_norm), len(right_norm)) >= 2 and (left_norm in right_norm or right_norm in left_norm)
            if exact or containment:
                pairs.append({
                    "left": left,
                    "right": right,
                    "lexicalCue": "exact" if exact else "containment",
                    "phase3JudgementRequired": True,
                })
        redundancy.append({"cardId": card_id, "examinedAtoms": text_atoms, "candidatePairs": pairs})
    return {
        "contractVersion": "phase3.relation-candidates.v1",
        "query": manifest.get("query", ""),
        "authenticityCandidates": authenticity,
        "redundancyCandidates": redundancy,
        "notes": ["候选对不是真实性冲突或信息冗余结论，必须由对应 Phase3 Skill 终判"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract Phase3 semantic relation candidates")
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
    result = derive_relation_candidates(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "cards": len(result["authenticityCandidates"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
