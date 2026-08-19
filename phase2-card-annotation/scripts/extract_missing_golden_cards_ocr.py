#!/usr/bin/env python3
"""Extract bounded Paddle evidence for cards absent from legacy golden JSON.

Expected card boundaries come from pixel-reviewed golden_page_truth.v2.  Only
missing list positions are OCRed.  The artifact is offline calibration evidence
and is never a production Phase2 input.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from extract_cv_facts import ocr_region


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "phase2-card-annotation" / "golden-sample-results"
TRUTH = ROOT / "phase2-card-annotation" / "references" / "golden_page_truth.v2.json"


def actual_positions(payload: dict[str, Any]) -> set[int]:
    return {
        int(card["listPosition"])
        for component in payload.get("pageStructure", {}).get("components", [])
        if component.get("componentType") == "results_list"
        for card in component.get("components", [])
        if card.get("componentType") in {"result_card", "heterogeneous_card"}
    }


def has_elements(value: Any) -> bool:
    if isinstance(value, dict):
        return "elementType" in value or any(has_elements(child) for child in value.values())
    if isinstance(value, list):
        return any(has_elements(child) for child in value)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    truth = json.loads(TRUTH.read_text(encoding="utf-8"))["pages"]
    pages = []
    for path in sorted(RESULTS.rglob("*.elements.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        screenshot_key = payload["verification"]["rawScreenshot"]
        screenshot = ROOT / screenshot_key
        present_cards = {
            int(card["listPosition"]): card
            for component in payload.get("pageStructure", {}).get("components", [])
            if component.get("componentType") == "results_list"
            for card in component.get("components", [])
            if card.get("componentType") in {"result_card", "heterogeneous_card"}
        }
        missing = []
        for position, expected in enumerate(truth[screenshot_key]["resultCards"], 1):
            if position in present_cards and has_elements(present_cards[position].get("regions", {})):
                continue
            observations, backend, error = ocr_region(screenshot, expected["coord"])
            missing.append({
                "listPosition": position,
                **expected,
                "backend": backend,
                "error": error or "",
                "observations": observations,
            })
        if missing:
            pages.append({
                "golden": str(path.relative_to(ROOT)),
                "screenshot": screenshot_key,
                "missingCards": missing,
            })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"pages": pages}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pages": len(pages), "cards": sum(len(page["missingCards"]) for page in pages), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
