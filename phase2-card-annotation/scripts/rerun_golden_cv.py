#!/usr/bin/env python3
"""Run the current CV pipeline over every historical golden screenshot.

This is a learning/regression batch: it never overwrites golden JSON. Each
sample gets retained local CV artifacts and a gate verdict for later rebuild.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent


def slug(value: str) -> str:
    return re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE).strip("_")


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def normalize_card_type(value: str) -> str:
    aliases = {
        "商家卡片-图文下挂": "商家卡片_图文下挂",
        "商家卡片-文字下挂": "商家卡片_文字下挂",
        "电影影院卡": "演出电影卡片",
        "演出卡": "演出电影卡片",
    }
    return aliases.get(value, value)


def expected_card_types(legacy: dict) -> tuple[list[str], int, int]:
    """Read golden truth only for post-inference evaluation.

    The returned values are never passed to a CV or classification command.
    """
    values: list[str] = []
    result_card_count = 0
    excluded_count = 0
    with Image.open(Path(legacy["screenshot"])) as image:
        viewport_width, viewport_height = image.size

    def visit(value: object) -> None:
        nonlocal result_card_count, excluded_count
        if isinstance(value, dict):
            if value.get("componentType") == "result_card":
                card_type = value.get("cardType")
                coord = value.get("coord")
                stable = False
                if isinstance(coord, list) and len(coord) == 4 and coord[2] > 0 and coord[3] > 0:
                    width_ratio = coord[2] / viewport_width
                    height_ratio = coord[3] / viewport_height
                    aspect_ratio = coord[2] / coord[3]
                    stable = 0.25 <= width_ratio <= 1.05 and 0.05 <= height_ratio <= 0.45 and 0.50 <= aspect_ratio <= 8.0
                if stable and isinstance(card_type, str) and card_type:
                    result_card_count += 1
                    values.append(normalize_card_type(card_type))
                else:
                    excluded_count += 1
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(legacy)
    return values, result_card_count, excluded_count


def prediction_comparison(legacy: dict, cards_path: Path) -> dict:
    expected, expected_count, excluded_count = expected_card_types(legacy)
    predicted: list[dict[str, object]] = []
    if cards_path.is_file():
        card_data = json.loads(cards_path.read_text(encoding="utf-8"))
        for card in card_data.get("cards", []):
            selected = card.get("selectedCardType", {})
            predicted.append({
                "cardId": card.get("cardId", ""),
                "cardType": normalize_card_type(str(selected.get("cardType", ""))),
                "status": selected.get("status", "uncertain"),
            })
    predicted_confirmed = [str(item["cardType"]) for item in predicted if item["status"] == "confirmed"]
    predicted_top = [str(item["cardType"]) for item in predicted]
    comparable = expected_count > 0 and len(expected) == expected_count
    boundary_match = comparable and expected_count == len(predicted)
    return {
        "expectedResultCardCount": expected_count,
        "excludedUnstableGoldenResultCards": excluded_count,
        "expectedCardTypes": expected,
        "predictedCards": predicted,
        "cardTypeComparable": comparable,
        "cardBoundaryCountMatch": boundary_match,
        "topCardTypeMatch": boundary_match and expected == predicted_top,
        "cardTypeMatch": boundary_match and expected == predicted_confirmed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-run current CV against legacy golden screenshots")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0, help="For bounded smoke tests; 0 means all samples")
    parser.add_argument("--match", default="", help="Optional regex matched against the golden JSON relative path")
    parser.add_argument("--resume", action="store_true", help="Reuse samples that already have a gate report")
    parser.add_argument("--reuse-cv-artifacts", action="store_true", help="Reuse existing facts/structure/result candidates and rerun only semantics plus gate")
    args = parser.parse_args()
    args.output_dir = args.output_dir.resolve()
    inputs = sorted((ROOT / "phase2-card-annotation" / "golden-sample-results").rglob("*.elements.json"))
    if args.match:
        inputs = [path for path in inputs if re.search(args.match, str(path.relative_to(ROOT)))]
    if args.limit:
        inputs = inputs[:args.limit]
    results = []
    for source in inputs:
        legacy = json.loads(source.read_text(encoding="utf-8"))
        screenshot = Path(legacy["screenshot"])
        target = args.output_dir / slug(str(source.relative_to(ROOT)).removesuffix(".elements.json"))
        target.mkdir(parents=True, exist_ok=True)
        facts, structure = target / "facts.json", target / "structure.json"
        candidates, cards = target / "result-candidates.json", target / "card-semantics.json"
        semantics, gate = target / "text-semantics.json", target / "recognition-gate.json"
        manifest, manifest_audit = target / "elements.json", target / "elements.audit.json"
        query = str(legacy.get("query") or source.name.removesuffix(".elements.json"))
        if args.resume and gate.is_file() and manifest.is_file():
            gate_data = json.loads(gate.read_text(encoding="utf-8"))
            results.append({"legacy": str(source.relative_to(ROOT)), "screenshot": str(screenshot), "artifactDir": str(target.relative_to(ROOT)), "canonicalManifest": str(manifest.relative_to(ROOT)), "valid": gate_data.get("valid", False), "errors": gate_data.get("errors", []), "summary": gate_data.get("summary", {}), **prediction_comparison(legacy, cards), "commands": [{"command": "resume", "exitCode": 0, "output": "existing per-screenshot elements.json and recognition-gate.json"}]})
            continue
        cv_commands = [
            ["bash", str(SCRIPT_DIR / "run_cv_facts.sh"), str(screenshot), "--output", str(facts)],
            [sys.executable, str(SCRIPT_DIR / "build_search_page_structure.py"), str(facts), "--output", str(structure)],
            [sys.executable, str(SCRIPT_DIR / "build_search_result_candidates.py"), str(facts), str(structure), "--output", str(candidates)],
        ]
        semantic_commands = [
            [sys.executable, str(SCRIPT_DIR / "map_result_card_semantics.py"), str(facts), str(candidates), "--output", str(cards)],
            [sys.executable, str(SCRIPT_DIR / "map_search_page_semantics.py"), str(facts), str(structure), "--output", str(semantics)],
            [sys.executable, str(SCRIPT_DIR / "validate_phase2_recognition.py"), "--facts", str(facts), "--result-candidates", str(candidates), "--card-semantics", str(cards), "--text-semantics", str(semantics), "--output", str(gate)],
            [sys.executable, str(SCRIPT_DIR / "build_phase2_manifest.py"), "--query", query, "--facts", str(facts), "--result-candidates", str(candidates), "--card-semantics", str(cards), "--text-semantics", str(semantics), "--recognition-gate", str(gate), "--output", str(manifest)],
            [sys.executable, str(ROOT / "scripts" / "validate_element_manifest.py"), str(manifest), "--audit", str(manifest_audit)],
        ]
        reusable = all(path.is_file() for path in (facts, structure, candidates))
        commands = semantic_commands if args.reuse_cv_artifacts and reusable else cv_commands + semantic_commands
        completed = []
        for command in commands:
            item = run(command)
            completed.append({"command": command[1] if len(command) > 1 else command[0], "exitCode": item.returncode, "output": item.stdout[-1000:]})
            if item.returncode and command[-1] != str(gate):
                break
        gate_data = json.loads(gate.read_text(encoding="utf-8")) if gate.is_file() else {"valid": False, "errors": ["pipeline_stage_failed"]}
        results.append({"legacy": str(source.relative_to(ROOT)), "screenshot": str(screenshot), "artifactDir": str(target.relative_to(ROOT)), "canonicalManifest": str(manifest.relative_to(ROOT)), "valid": gate_data.get("valid", False), "errors": gate_data.get("errors", []), "summary": gate_data.get("summary", {}), **prediction_comparison(legacy, cards), "commands": completed})
    comparable = [item for item in results if item["cardTypeComparable"]]
    index = {
        "contractVersion": "phase2.golden-cv-rerun.v2",
        "evaluationPolicy": "Each screenshot owns one canonicalManifest elements.json. This index is regression summary only and is never a Phase3 fact source. Golden card types are read only after inference and are never classifier inputs.",
        "cardTypeMetrics": {
            "comparableSamples": len(comparable),
            "boundaryCountMatchSamples": sum(bool(item["cardBoundaryCountMatch"]) for item in comparable),
            "topTypeExactMatchSamples": sum(bool(item["topCardTypeMatch"]) for item in comparable),
            "confirmedExactMatchSamples": sum(bool(item["cardTypeMatch"]) for item in comparable),
        },
        "samples": results,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"samples": len(results), "passed": sum(item["valid"] for item in results), "failed": sum(not item["valid"] for item in results), "index": str(args.output_dir / "index.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
