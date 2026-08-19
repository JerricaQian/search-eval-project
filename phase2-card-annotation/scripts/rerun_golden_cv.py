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


def box_iou(left: list[int], right: list[int]) -> float:
    x0, y0 = max(left[0], right[0]), max(left[1], right[1])
    x1 = min(left[0] + left[2], right[0] + right[2])
    y1 = min(left[1] + left[3], right[1] + right[3])
    intersection = max(0, x1 - x0) * max(0, y1 - y0)
    union_area = left[2] * left[3] + right[2] * right[3] - intersection
    return intersection / union_area if union_area else 0.0


def calibrated_page(legacy: dict, truth: dict) -> tuple[str, dict] | tuple[None, None]:
    screenshot = Path(legacy["screenshot"]).resolve()
    try:
        key = str(screenshot.relative_to(ROOT))
    except ValueError:
        key = str(screenshot)
    page = truth.get("pages", {}).get(key)
    return (key, page) if isinstance(page, dict) else (None, None)


def prediction_comparison(legacy: dict, cards_path: Path, truth: dict) -> dict:
    truth_key, page = calibrated_page(legacy, truth)
    if page:
        expected_cards = page.get("resultCards", [])
        expected = [normalize_card_type(str(item.get("cardType", ""))) for item in expected_cards]
        expected_coords = [item.get("coord", []) for item in expected_cards]
        expected_count, excluded_count = len(expected_cards), 0
        truth_source = truth.get("contractVersion", "phase2.golden-page-truth.v2")
    else:
        expected, expected_count, excluded_count = expected_card_types(legacy)
        expected_coords = []
        truth_source = "legacy_elements_post_inference_only"
    predicted: list[dict[str, object]] = []
    if cards_path.is_file():
        card_data = json.loads(cards_path.read_text(encoding="utf-8"))
        for card in card_data.get("cards", []):
            selected = card.get("selectedCardType", {})
            predicted.append({
                "cardId": card.get("cardId", ""),
                "cardType": normalize_card_type(str(selected.get("cardType", ""))),
                "status": selected.get("status", "uncertain"),
                "coord": card.get("coord", []),
            })
    predicted_confirmed = [str(item["cardType"]) for item in predicted if item["status"] == "confirmed"]
    predicted_top = [str(item["cardType"]) for item in predicted]
    comparable = expected_count > 0 and len(expected) == expected_count
    boundary_match = comparable and expected_count == len(predicted)
    geometry_ious = []
    if boundary_match and expected_coords and all(isinstance(coord, list) and len(coord) == 4 for coord in expected_coords):
        geometry_ious = [round(box_iou(expected_coords[index], predicted[index]["coord"]), 4) for index in range(expected_count)]
    geometry_match = bool(geometry_ious) and all(value >= 0.72 for value in geometry_ious)
    expected_modules = page.get("pageModules", []) if page else []
    predicted_modules: list[dict[str, object]] = []
    candidates_path = cards_path.with_name("result-candidates.json")
    if expected_modules and candidates_path.is_file():
        candidates_data = json.loads(candidates_path.read_text(encoding="utf-8"))
        for module in candidates_data.get("pageModules", []):
            predicted_modules.append({"moduleType": module.get("module", ""), "coord": module.get("coord", []), "status": module.get("status", "uncertain")})
    expected_module_types = [str(item.get("moduleType", "")) for item in expected_modules]
    predicted_module_types = [str(item["moduleType"]) for item in predicted_modules]
    module_type_match = expected_module_types == predicted_module_types if expected_modules else None
    module_geometry_ious = []
    if module_type_match:
        module_geometry_ious = [round(box_iou(expected_modules[index]["coord"], predicted_modules[index]["coord"]), 4) for index in range(len(expected_modules))]
    return {
        "goldenTruthSource": truth_source,
        "goldenTruthKey": truth_key or "",
        "expectedResultCardCount": expected_count,
        "excludedUnstableGoldenResultCards": excluded_count,
        "expectedCardTypes": expected,
        "predictedCards": predicted,
        "cardTypeComparable": comparable,
        "cardBoundaryCountMatch": boundary_match,
        "cardBoundaryGeometryIous": geometry_ious,
        "cardBoundaryGeometryMatch": geometry_match if expected_coords else None,
        "topCardTypeMatch": boundary_match and expected == predicted_top,
        "cardTypeMatch": boundary_match and expected == predicted_confirmed,
        "expectedPageModules": expected_modules,
        "predictedPageModules": predicted_modules,
        "pageModuleTypeMatch": module_type_match,
        "pageModuleGeometryIous": module_geometry_ious,
        "pageModuleGeometryMatch": (bool(module_geometry_ious) and all(value >= 0.65 for value in module_geometry_ious)) if expected_modules else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-run current CV against legacy golden screenshots")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0, help="For bounded smoke tests; 0 means all samples")
    parser.add_argument("--match", default="", help="Optional regex matched against the golden JSON relative path")
    parser.add_argument("--resume", action="store_true", help="Reuse samples that already have a gate report")
    parser.add_argument("--reuse-cv-artifacts", action="store_true", help="Reuse existing facts/structure/result candidates and rerun only semantics plus gate")
    parser.add_argument("--golden-truth", type=Path, default=ROOT / "phase2-card-annotation" / "references" / "golden_page_truth.v2.json", help="Optional model-assisted truth used only after inference for regression comparison")
    args = parser.parse_args()
    args.output_dir = args.output_dir.resolve()
    truth = json.loads(args.golden_truth.read_text(encoding="utf-8")) if args.golden_truth.is_file() else {"pages": {}}
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
        facts, structure = target / "cv-facts.json", target / "page-structure.json"
        candidates, cards = target / "result-candidates.json", target / "card-semantics.json"
        semantics, gate = target / "text-semantics.json", target / "recognition-gate.json"
        manifest, manifest_audit = target / "elements.json", target / "elements.audit.json"
        query = str(legacy.get("query") or source.name.removesuffix(".elements.json"))
        if args.resume and gate.is_file() and manifest.is_file():
            gate_data = json.loads(gate.read_text(encoding="utf-8"))
            results.append({"legacy": str(source.relative_to(ROOT)), "screenshot": str(screenshot), "artifactDir": str(target.relative_to(ROOT)), "canonicalManifest": str(manifest.relative_to(ROOT)), "valid": gate_data.get("valid", False), "errors": gate_data.get("errors", []), "summary": gate_data.get("summary", {}), **prediction_comparison(legacy, cards, truth), "commands": [{"command": "resume", "exitCode": 0, "output": "existing per-screenshot elements.json and recognition-gate.json"}]})
            continue
        semantic_commands = [
            [sys.executable, str(SCRIPT_DIR / "map_result_card_semantics.py"), str(facts), str(candidates), "--output", str(cards)],
            [sys.executable, str(SCRIPT_DIR / "map_search_page_semantics.py"), str(facts), str(structure), "--output", str(semantics)],
            [sys.executable, str(SCRIPT_DIR / "validate_phase2_recognition.py"), "--facts", str(facts), "--result-candidates", str(candidates), "--card-semantics", str(cards), "--text-semantics", str(semantics), "--output", str(gate)],
            [sys.executable, str(SCRIPT_DIR / "build_phase2_manifest.py"), "--query", query, "--facts", str(facts), "--result-candidates", str(candidates), "--card-semantics", str(cards), "--text-semantics", str(semantics), "--recognition-gate", str(gate), "--output", str(manifest)],
            [sys.executable, str(ROOT / "scripts" / "validate_element_manifest.py"), str(manifest), "--audit", str(manifest_audit)],
        ]
        reusable = all(path.is_file() for path in (facts, structure, candidates))
        commands = semantic_commands if args.reuse_cv_artifacts and reusable else [[
            sys.executable, str(SCRIPT_DIR / "run_phase2_recognition.py"),
            "--query", query, "--screenshot", str(screenshot), "--output", str(manifest),
            "--artifacts-dir", str(target),
        ]]
        completed = []
        for command in commands:
            item = run(command)
            completed.append({"command": command[1] if len(command) > 1 else command[0], "exitCode": item.returncode, "output": item.stdout[-1000:]})
            if item.returncode and args.reuse_cv_artifacts and command[-1] != str(gate):
                break
        gate_data = json.loads(gate.read_text(encoding="utf-8")) if gate.is_file() else {"valid": False, "errors": ["pipeline_stage_failed"]}
        results.append({"legacy": str(source.relative_to(ROOT)), "screenshot": str(screenshot), "artifactDir": str(target.relative_to(ROOT)), "canonicalManifest": str(manifest.relative_to(ROOT)), "valid": gate_data.get("valid", False), "errors": gate_data.get("errors", []), "summary": gate_data.get("summary", {}), **prediction_comparison(legacy, cards, truth), "commands": completed})
    comparable = [item for item in results if item["cardTypeComparable"]]
    index = {
        "contractVersion": "phase2.golden-cv-rerun.v2",
        "evaluationPolicy": "Each screenshot owns one canonicalManifest elements.json. This index is regression summary only and is never a Phase3 fact source. Golden card types are read only after inference and are never classifier inputs.",
        "cardTypeMetrics": {
            "comparableSamples": len(comparable),
            "boundaryCountMatchSamples": sum(bool(item["cardBoundaryCountMatch"]) for item in comparable),
            "boundaryGeometryMatchSamples": sum(item["cardBoundaryGeometryMatch"] is True for item in comparable),
            "topTypeExactMatchSamples": sum(bool(item["topCardTypeMatch"]) for item in comparable),
            "confirmedExactMatchSamples": sum(bool(item["cardTypeMatch"]) for item in comparable),
        },
        "pageModuleMetrics": {
            "comparableSamples": sum(item["pageModuleTypeMatch"] is not None for item in results),
            "typeExactMatchSamples": sum(item["pageModuleTypeMatch"] is True for item in results),
            "geometryMatchSamples": sum(item["pageModuleGeometryMatch"] is True for item in results),
        },
        "samples": results,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"samples": len(results), "passed": sum(item["valid"] for item in results), "failed": sum(not item["valid"] for item in results), "index": str(args.output_dir / "index.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
