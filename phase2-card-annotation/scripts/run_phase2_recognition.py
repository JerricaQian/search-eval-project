#!/usr/bin/env python3
"""One-command Phase2 recognition: screenshot -> Phase3 manifest + audit.

The individual CV/OCR artifacts are retained for diagnosis, but callers only
need this entry point and never have to manually assemble JSON contracts.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent


def invoke(arguments: list[str], check: bool = True) -> int:
    return subprocess.run(arguments, cwd=ROOT, check=check).returncode


def run(query: str, screenshot: Path, output: Path, audit: Path | None, artifacts: Path) -> int:
    artifacts.mkdir(parents=True, exist_ok=True)
    facts = artifacts / "cv-facts.json"
    structure = artifacts / "page-structure.json"
    candidates = artifacts / "result-candidates.json"
    card_semantics = artifacts / "card-semantics.json"
    text_semantics = artifacts / "text-semantics.json"
    gate_report = artifacts / "recognition-gate.json"
    invoke(["bash", str(SCRIPT_DIR / "run_cv_facts.sh"), str(screenshot), "--output", str(facts)])
    invoke([sys.executable, str(SCRIPT_DIR / "build_search_page_structure.py"), str(facts), "--output", str(structure)])
    invoke([sys.executable, str(SCRIPT_DIR / "build_search_result_candidates.py"), str(facts), str(structure), "--output", str(candidates)])
    invoke([sys.executable, str(SCRIPT_DIR / "map_result_card_semantics.py"), str(facts), str(candidates), "--output", str(card_semantics)])
    invoke([sys.executable, str(SCRIPT_DIR / "map_search_page_semantics.py"), str(facts), str(structure), "--output", str(text_semantics)])
    gate_code = invoke([sys.executable, str(SCRIPT_DIR / "validate_phase2_recognition.py"), "--facts", str(facts), "--result-candidates", str(candidates), "--card-semantics", str(card_semantics), "--text-semantics", str(text_semantics), "--output", str(gate_report)], check=False)
    build_args = [sys.executable, str(SCRIPT_DIR / "build_phase2_manifest.py"), "--query", query, "--facts", str(facts), "--result-candidates", str(candidates), "--card-semantics", str(card_semantics), "--text-semantics", str(text_semantics), "--recognition-gate", str(gate_report), "--output", str(output)]
    if audit:
        build_args.extend(["--recognition-audit", str(audit)])
    invoke(build_args)
    validation_args = [sys.executable, str(ROOT / "scripts" / "validate_element_manifest.py"), str(output), "--audit", str(output.with_suffix(".audit.json"))]
    if audit:
        validation_args.extend(["--recognition-audit", str(audit)])
    validation_code = invoke(validation_args, check=False)
    return 0 if gate_code == 0 and validation_code == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Recognize a screenshot directly into the Phase3 manifest contract")
    parser.add_argument("--query", required=True)
    parser.add_argument("--screenshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recognition-audit", type=Path, help="Optional separate debug audit; the canonical gate is embedded in --output")
    parser.add_argument("--artifacts-dir", type=Path, help="Optional retained CV/OCR process artifacts directory")
    args = parser.parse_args()
    if args.artifacts_dir:
        return run(args.query, args.screenshot, args.output, args.recognition_audit, args.artifacts_dir)
    else:
        with tempfile.TemporaryDirectory(prefix="phase2-recognition-") as temp:
            return run(args.query, args.screenshot, args.output, args.recognition_audit, Path(temp))


if __name__ == "__main__":
    raise SystemExit(main())
