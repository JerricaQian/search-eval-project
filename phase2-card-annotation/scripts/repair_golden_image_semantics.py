#!/usr/bin/env python3
"""Repair image-like golden elements misclassified as UI text."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "phase2-card-annotation" / "golden-sample-results"
IMAGE_TOKENS = ("图片", "头图", "主图", "海报", "视频", "横幅/轮播")


def is_image_element(element: dict[str, Any]) -> bool:
    return any(token in str(element.get("elementType", "")) for token in IMAGE_TOKENS)


def repair_element(element: dict[str, Any]) -> bool:
    if not is_image_element(element) or element.get("visual", {}).get("entityKind") == "image":
        return False
    region = str(element.get("sourceRegion", ""))
    confirmed = element.get("status") == "confirmed"
    element["render"] = {
        "visibleStatus": "confirmed" if confirmed else "uncertain",
        "renderState": "normal" if confirmed else "uncertain",
        "sourceRegion": region,
        "isPhoto": True,
        "isSystemUi": False,
    }
    element["visual"] = {
        "entityKind": "image",
        "visualStatus": "confirmed" if confirmed else "uncertain",
        "isColored": False,
        "isShaped": False,
        "colorRole": "unknown",
        "backgroundColor": "",
        "textColor": "",
        "borderColor": "",
        "hasGraphicAssist": False,
        "graphicType": "无",
        "styleKey": f"image|unknown|photo|{region}|无",
        "sourceRegion": region,
        "colorEvidence": "photo_excluded_phase3_pixel_measurement_required",
    }
    element.pop("textFacts", None)
    return True


def main() -> int:
    files = sorted(RESULTS.rglob("*.elements.json"))
    changed_files = changed_elements = 0
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        changed = 0

        def visit(value: Any) -> None:
            nonlocal changed
            if isinstance(value, dict):
                if "elementType" in value:
                    changed += int(repair_element(value))
                    return
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(payload.get("pageStructure", {}))
        if changed:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed_files += 1
            changed_elements += changed
    print(json.dumps({"files": len(files), "changedFiles": changed_files, "changedElements": changed_elements}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
