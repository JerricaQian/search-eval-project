#!/usr/bin/env python3
"""Create a review template covering every active Phase2 manifest element."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def visible_text(element: dict[str, Any]) -> str:
    render = element.get("render")
    if element.get("元素类型") == "图片" or (isinstance(render, dict) and render.get("isPhoto") is True):
        return ""
    content = element.get("内容简述", "")
    return content.removeprefix("原文:") if isinstance(content, str) else ""


def build(manifest_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    screenshot = str(manifest.get("screenshot", ""))
    fields: list[dict[str, Any]] = []
    for card in manifest.get("cards", []):
        if not isinstance(card, dict):
            continue
        card_id = str(card.get("cardId", ""))
        for region in card.get("regions", []):
            if not isinstance(region, dict):
                continue
            for element in region.get("elements", []):
                if not isinstance(element, dict) or element.get("isExcluded"):
                    continue
                is_photo = element.get("元素类型") == "图片" or (
                    isinstance(element.get("render"), dict) and element["render"].get("isPhoto") is True
                )
                fields.append({
                    "cardId": card_id,
                    "elementId": str(element.get("id", "")),
                    "field": "photo" if is_photo else "visible_text",
                    "visibleText": visible_text(element),
                    "coord": element.get("坐标"),
                    "status": "uncertain",
                    "source": "full_image",
                    "evidencePath": screenshot,
                    "reason": "pending_current_pixel_review",
                })
    return {
        "contractVersion": "phase2.current-image-calibration.v1",
        "strategy": "golden_structure_current_pixels",
        "query": str(manifest.get("query", "")),
        "screenshot": screenshot,
        "manifest": str(manifest_path),
        "reviewedAgainstCurrentPixels": False,
        "goldenValueInjection": False,
        "fullImageReadCount": 1,
        "localReviewReadCount": 0,
        "totalImageReadCount": 1,
        "localReviewPaths": [],
        "fields": fields,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a current-image calibration audit template")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    payload = build(args.manifest, manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "fields": len(payload["fields"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
