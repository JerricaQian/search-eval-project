#!/usr/bin/env python3
"""Extract local OCR evidence inside already reviewed golden card boundaries.

This helper does not write golden files.  It emits bounded, page-relative OCR
observations so a separate human-reviewed rebuild can transcribe card elements
without sending an entire long screenshot to PaddleOCR.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from extract_cv_facts import ocr_region


def extract(golden_path: Path) -> dict[str, Any]:
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    screenshot = Path(golden["screenshot"])
    cards: list[dict[str, Any]] = []
    for component in golden["pageStructure"]["components"]:
        if component.get("componentType") != "results_list":
            continue
        for card in component.get("components", []):
            coord = card.get("coord")
            if not coord:
                continue
            observations, backend, error = ocr_region(screenshot, coord)
            cards.append({
                "listPosition": card.get("listPosition"),
                "cardType": card.get("cardType"),
                "coord": coord,
                "backend": backend,
                "error": error or "",
                "observations": observations,
            })
    return {
        "golden": str(golden_path.resolve()),
        "screenshot": str(screenshot),
        "cards": cards,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("golden", type=Path, nargs="+")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--require-backend", choices=("paddleocr", "tesseract"), help="Fail instead of silently accepting an OCR backend downgrade")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for golden_path in args.golden:
        payload = extract(golden_path)
        if args.require_backend:
            wrong = [card for card in payload["cards"] if card.get("backend") != args.require_backend]
            if wrong:
                positions = [card.get("listPosition") for card in wrong]
                raise RuntimeError(f"{golden_path}: required {args.require_backend}, got downgrade on cards {positions}")
        output = args.output_dir / f"{golden_path.stem}.bounded-ocr.json"
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summaries.append({
            "output": str(output),
            "cards": len(payload["cards"]),
            "observations": sum(len(card["observations"]) for card in payload["cards"]),
            "backends": sorted({card["backend"] for card in payload["cards"]}),
        })
    print(json.dumps(summaries, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
