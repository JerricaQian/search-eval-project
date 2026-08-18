#!/usr/bin/env python3
"""Repair legacy golden JSON against its actual screenshot boundary.

These historical files predate the Phase3 contract.  This conservative repair
does not invent new text: it keeps human-approved annotations, clips visible
geometry to the source image, and downgrades screen-edge / invalid OCR facts.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "phase2-card-annotation" / "golden-samples"


def screenshot_for(payload: dict[str, Any], result_path: Path) -> Path | None:
    raw = str(payload.get("screenshot", ""))
    candidate = Path(raw)
    if raw and candidate.is_file():
        return candidate.resolve()
    group = result_path.parent.name
    stem = result_path.stem.removesuffix(".elements")
    aliases = {
        "演出卡": "演出电影卡-演出卡", "电影卡": "演出电影卡-电影卡",
        "万达广场": "主点卡-万达广场", "迪士尼": "主点卡-迪士尼",
    }
    preferred = aliases.get(stem, stem)
    matches = sorted(SAMPLES.rglob(f"{preferred}.png"))
    if not matches and raw:
        matches = sorted(SAMPLES.rglob(Path(raw).name))
    return matches[0].resolve() if matches else None


def valid_local_text(text: str, element_type: str) -> bool:
    text = text.strip()
    if not text:
        return False
    if "价格" in element_type:
        return bool(re.search(r"[¥￥]\s*\d|\d+(?:\.\d+)?\s*元", text))
    chinese = sum("\u4e00" <= char <= "\u9fff" for char in text)
    digits = sum(char.isdigit() for char in text)
    latin = sum(char.isascii() and char.isalpha() for char in text)
    return chinese >= 2 or digits >= 2 or (chinese >= 1 and latin <= 3)


def repair_node(value: Any, width: int, height: int, changes: list[str], path: str = "$") -> Any:
    if isinstance(value, list):
        return [repair_node(item, width, height, changes, f"{path}[{index}]") for index, item in enumerate(value)]
    if not isinstance(value, dict):
        return value
    value = {key: repair_node(item, width, height, changes, f"{path}.{key}") for key, item in value.items() if key != "confidence"}
    coord = value.get("coord")
    clipped = False
    if isinstance(coord, list) and len(coord) == 4 and all(isinstance(item, (int, float)) for item in coord):
        x, y, w, h = coord
        x0, y0, x1, y1 = max(0, x), max(0, y), min(width, x + w), min(height, y + h)
        if x1 <= x0 or y1 <= y0:
            # The item is wholly outside the captured screenshot. Do not leave
            # a fake in-bounds pixel box: an uncertain legacy item without a
            # coordinate is safer than a coordinate for invisible content.
            value.pop("coord", None)
            value["cropped"] = True
            value["status"] = "uncertain"
            if "visibleText" in value:
                value["visibleText"] = ""
            changes.append(f"outside:{path}")
        elif [x0, y0, x1 - x0, y1 - y0] != coord:
            value["coord"] = [x0, y0, x1 - x0, y1 - y0]
            value["cropped"] = True
            value["status"] = "uncertain"
            if "visibleText" in value:
                value["visibleText"] = ""
            changes.append(f"clipped:{path}")
            clipped = True
    if value.get("source") == "local_crop_ocr" and value.get("status") == "confirmed":
        text = str(value.get("visibleText", ""))
        if not valid_local_text(text, str(value.get("elementType", ""))):
            value["visibleText"] = ""
            value["status"] = "uncertain"
            value["source"] = "legacy_ocr_rejected_by_text_hygiene"
            changes.append(f"ocr_rejected:{path}")
    if clipped:
        value["source"] = "screenshot_boundary_clamp"
    return value


def repair(path: Path) -> tuple[dict[str, Any], list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    screen = screenshot_for(payload, path)
    if not screen:
        return payload, ["screenshot_not_found"]
    with Image.open(screen) as image:
        width, height = image.size
    changes: list[str] = []
    repaired = repair_node(payload, width, height, changes)
    repaired["screenshot"] = str(screen)
    return repaired, changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair historical golden JSON without inventing screenshot facts")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--in-place", action="store_true")
    args = parser.parse_args()
    results = []
    for path in args.paths:
        repaired, changes = repair(path)
        if args.in_place:
            path.write_text(json.dumps(repaired, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append({"path": str(path), "changes": len(changes), "details": changes[:20]})
    print(json.dumps({"inPlace": args.in_place, "files": results}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
