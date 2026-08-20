#!/usr/bin/env python3
"""Local Phase2 candidate pass: screenshot -> manifest, artifacts and local audit.

The individual CV/OCR artifacts are retained for current-image calibration.
Production callers must still perform the visual review and exhaustive audit
defined by references/current_image_calibration.v1.md before Phase3 consumes it.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent


def invoke(arguments: list[str], check: bool = True, env: dict[str, str] | None = None) -> int:
    return subprocess.run(arguments, cwd=ROOT, check=check, env=env).returncode


def write_structure_gate(candidates: Path, semantics: Path, output: Path) -> bool:
    """Stage A: publish only bounded, known page components to Paddle."""
    cards = json.loads(candidates.read_text(encoding="utf-8")).get("resultCards", [])
    mapped = {item.get("cardId"): item for item in json.loads(semantics.read_text(encoding="utf-8")).get("cards", [])}
    errors = []
    if not cards:
        errors.append("no_result_cards")
    for card in cards:
        coord = card.get("coord", [])
        selected = mapped.get(card.get("id"), {}).get("selectedCardType", {})
        if not isinstance(coord, list) or len(coord) != 4 or coord[2] <= 0 or coord[3] <= 0:
            errors.append(f"{card.get('id')}:invalid_component_boundary")
        if selected.get("status") != "confirmed" or selected.get("cardType") == "异构卡":
            errors.append(f"{card.get('id')}:page_or_component_type_unresolved")
    output.write_text(json.dumps({"contractVersion": "phase2.structure-gate.v1", "valid": not errors, "errors": errors}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return not errors


def add_publication_error(gate_path: Path, error: str) -> None:
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    gate["valid"] = False
    gate.setdefault("errors", []).append(error)
    gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def mark_manifest_blocked(output: Path, error: str) -> None:
    payload = json.loads(output.read_text(encoding="utf-8"))
    recognition = payload.setdefault("recognition", {})
    recognition.update({"status": "blocked", "phase3Ready": False, "wholePageGate": False})
    recognition.setdefault("errors", []).append(error)
    payload.setdefault("pageFactInventory", {})["complete"] = False
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(query: str, screenshot: Path, output: Path, audit: Path | None, artifacts: Path, require_bounded_paddleocr: bool = False, visual_review: Path | None = None) -> int:
    artifacts.mkdir(parents=True, exist_ok=True)
    facts_initial = artifacts / "cv-facts.initial.json"
    structure_initial = artifacts / "page-structure.initial.json"
    candidates_initial = artifacts / "result-candidates.initial.json"
    card_semantics_initial = artifacts / "card-semantics.initial.json"
    text_semantics_initial = artifacts / "text-semantics.initial.json"
    gate_initial = artifacts / "recognition-gate.initial.json"
    facts = artifacts / "cv-facts.json"
    structure = artifacts / "page-structure.json"
    candidates = artifacts / "result-candidates.json"
    card_semantics = artifacts / "card-semantics.json"
    text_semantics = artifacts / "text-semantics.json"
    gate_report = artifacts / "recognition-gate.json"
    structure_gate = artifacts / "structure-gate.json"
    paddle_report = artifacts / "component-paddle-read.json"

    invoke(["bash", str(SCRIPT_DIR / "run_cv_facts.sh"), str(screenshot), "--output", str(facts_initial)])
    invoke([sys.executable, str(SCRIPT_DIR / "build_search_page_structure.py"), str(facts_initial), "--output", str(structure_initial)])
    invoke([sys.executable, str(SCRIPT_DIR / "build_search_result_candidates.py"), str(facts_initial), str(structure_initial), "--output", str(candidates_initial)])
    invoke([sys.executable, str(SCRIPT_DIR / "map_result_card_semantics.py"), str(facts_initial), str(candidates_initial), "--output", str(card_semantics_initial)])
    invoke([sys.executable, str(SCRIPT_DIR / "map_search_page_semantics.py"), str(facts_initial), str(structure_initial), "--output", str(text_semantics_initial)])
    structure_ok = write_structure_gate(candidates_initial, card_semantics_initial, structure_gate)
    initial_gate_code = invoke([sys.executable, str(SCRIPT_DIR / "validate_phase2_recognition.py"), "--facts", str(facts_initial), "--result-candidates", str(candidates_initial), "--card-semantics", str(card_semantics_initial), "--text-semantics", str(text_semantics_initial), "--output", str(gate_initial)], check=False)

    initial_to_final = (
        (facts_initial, facts), (structure_initial, structure), (candidates_initial, candidates),
        (card_semantics_initial, card_semantics), (text_semantics_initial, text_semantics), (gate_initial, gate_report),
    )
    gate_code = initial_gate_code
    component_paddle_ok = False
    if structure_ok:
        retry_env = os.environ.copy()
        # Component OCR is sequential by contract. One CPU thread avoids
        # Paddle/OpenBLAS saturating the machine while it scans six crops.
        retry_threads = retry_env.get("PHASE2_OCR_THREADS", "1")
        for variable in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "PADDLE_NUM_THREADS"):
            retry_env[variable] = retry_threads
        # Paddle is confined to this one bounded-card retry process. The
        # initial whole-page pass remains Tesseract/CV only, and the model is
        # loaded at most once for all sequential card crops.
        if retry_env.get("PHASE2_DISABLE_BOUNDED_PADDLEOCR") != "1":
            retry_env.setdefault("PHASE2_ENABLE_PADDLEOCR", "1")
        retry_arguments = [
            sys.executable, str(SCRIPT_DIR / "reprocess_bounded_cards.py"),
            "--screenshot", str(screenshot), "--facts", str(facts_initial),
            "--result-candidates", str(candidates_initial), "--card-semantics", str(card_semantics_initial),
            "--recognition-gate", str(gate_initial), "--output", str(facts), "--report", str(paddle_report), "--all-components", "--require-backend", "paddleocr",
        ]
        retry_code = invoke(retry_arguments, check=False, env=retry_env)
        if retry_code == 0:
            component_paddle_ok = True
            invoke([sys.executable, str(SCRIPT_DIR / "build_search_page_structure.py"), str(facts), "--output", str(structure)])
            invoke([sys.executable, str(SCRIPT_DIR / "build_search_result_candidates.py"), str(facts), str(structure), "--output", str(candidates)])
            invoke([sys.executable, str(SCRIPT_DIR / "map_result_card_semantics.py"), str(facts), str(candidates), "--output", str(card_semantics)])
            invoke([sys.executable, str(SCRIPT_DIR / "map_search_page_semantics.py"), str(facts), str(structure), "--output", str(text_semantics)])
            gate_code = invoke([sys.executable, str(SCRIPT_DIR / "validate_phase2_recognition.py"), "--facts", str(facts), "--result-candidates", str(candidates), "--card-semantics", str(card_semantics), "--text-semantics", str(text_semantics), "--output", str(gate_report)], check=False)
        else:
            for source, destination in initial_to_final:
                shutil.copyfile(source, destination)
    else:
        for source, destination in initial_to_final:
            shutil.copyfile(source, destination)
        add_publication_error(gate_report, "structure_gate_failed_before_component_paddle")
        gate_code = 1
    # Stage D is mandatory: the image-capable session supplies a recorded
    # current-screen review after Paddle has located each component line.
    if visual_review and facts.is_file():
        reviewed = artifacts / "cv-facts.visual-reviewed.json"
        invoke([sys.executable, str(SCRIPT_DIR / "apply_visual_review.py"), "--facts", str(facts), "--review", str(visual_review), "--output", str(reviewed)])
        shutil.copyfile(reviewed, facts)
        invoke([sys.executable, str(SCRIPT_DIR / "build_search_page_structure.py"), str(facts), "--output", str(structure)])
        invoke([sys.executable, str(SCRIPT_DIR / "build_search_result_candidates.py"), str(facts), str(structure), "--output", str(candidates)])
        invoke([sys.executable, str(SCRIPT_DIR / "map_result_card_semantics.py"), str(facts), str(candidates), "--output", str(card_semantics)])
        invoke([sys.executable, str(SCRIPT_DIR / "map_search_page_semantics.py"), str(facts), str(structure), "--output", str(text_semantics)])
        gate_code = invoke([sys.executable, str(SCRIPT_DIR / "validate_phase2_recognition.py"), "--facts", str(facts), "--result-candidates", str(candidates), "--card-semantics", str(card_semantics), "--text-semantics", str(text_semantics), "--output", str(gate_report)], check=False)
    elif facts.is_file():
        add_publication_error(gate_report, "main_session_local_visual_review_required")
        gate_code = 1
    if not component_paddle_ok:
        add_publication_error(gate_report, "component_paddle_read_required")
        gate_code = 1
    build_args = [sys.executable, str(SCRIPT_DIR / "build_phase2_manifest.py"), "--query", query, "--facts", str(facts), "--result-candidates", str(candidates), "--card-semantics", str(card_semantics), "--text-semantics", str(text_semantics), "--recognition-gate", str(gate_report), "--output", str(output)]
    if audit:
        build_args.extend(["--recognition-audit", str(audit)])
    invoke(build_args)
    validation_args = [sys.executable, str(ROOT / "scripts" / "validate_element_manifest.py"), str(output), "--audit", str(output.with_suffix(".audit.json"))]
    if audit:
        # A syntactically valid manifest is not enough for publication.  The
        # supplied audit is the only place that can prove every non-excluded
        # atom was checked against this screenshot's pixels.
        validation_args.extend(["--recognition-audit", str(audit), "--require-current-image-calibration"])
    validation_code = invoke(validation_args, check=False)
    if validation_code != 0:
        mark_manifest_blocked(output, "element_manifest_or_item_groups_validation_failed")
    elif gate_code != 0:
        mark_manifest_blocked(output, "phase2_gate_failed")
    return 0 if gate_code == 0 and validation_code == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Recognize a screenshot directly into the Phase3 manifest contract")
    parser.add_argument("--query", required=True)
    parser.add_argument("--screenshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recognition-audit", type=Path, help="Optional separate debug audit; the canonical gate is embedded in --output")
    parser.add_argument("--artifacts-dir", type=Path, help="Optional retained CV/OCR process artifacts directory")
    parser.add_argument("--require-bounded-paddleocr", action="store_true", help="Fail the bounded retry if PaddleOCR is unavailable instead of falling back")
    parser.add_argument("--visual-review", type=Path, help="Current-screenshot main-session local visual-review JSON")
    args = parser.parse_args()
    if args.artifacts_dir:
        return run(args.query, args.screenshot, args.output, args.recognition_audit, args.artifacts_dir, args.require_bounded_paddleocr, args.visual_review)
    else:
        with tempfile.TemporaryDirectory(prefix="phase2-recognition-") as temp:
            return run(args.query, args.screenshot, args.output, args.recognition_audit, Path(temp), args.require_bounded_paddleocr, args.visual_review)


if __name__ == "__main__":
    raise SystemExit(main())
