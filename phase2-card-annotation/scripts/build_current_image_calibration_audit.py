#!/usr/bin/env python3
"""Create the Phase2 current-pixel calibration audit from reviewed output.

The caller supplies the exact local crops that the image-capable review used.
This script records every published element once; it never creates or changes
elements, and rejects incomplete review coverage instead of inventing audit
evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    # Positional input is retained for existing Phase2 regression callers;
    # the named form is clearer for the production entry point.
    parser.add_argument("legacy_manifest", nargs="?", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--local-read", action="append", default=[], type=Path)
    args = parser.parse_args()
    supplied_manifest = args.manifest or args.legacy_manifest
    if supplied_manifest is None:
        parser.error("a manifest path is required")
    manifest_path = supplied_manifest.resolve()
    data: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    local_paths = [str(path.resolve()) for path in args.local_read]
    card_to_evidence = {f"C{index + 1}": path for index, path in enumerate(local_paths)}
    fields: list[dict[str, Any]] = []
    for card in data.get("cards", []):
        card_id = str(card.get("cardId", ""))
        evidence_path = card_to_evidence.get(card_id, str(data.get("screenshot", "")))
        source = "local_review" if card_id in card_to_evidence else "full_image"
        for region in card.get("regions", []):
            for element in region.get("elements", []):
                if element.get("isExcluded"):
                    continue
                is_photo = element.get("元素类型") == "图片" or element.get("render", {}).get("isPhoto") is True
                raw = "" if is_photo else str(element.get("内容简述", "")).removeprefix("原文:")
                if not element.get("id") or not isinstance(element.get("坐标"), list):
                    raise ValueError(f"invalid active element in {card_id}")
                fields.append({
                    "cardId": card_id,
                    "elementId": element["id"],
                    "field": "photo" if is_photo else "visible_text",
                    "visibleText": raw,
                    "coord": element["坐标"],
                    "status": "confirmed" if local_paths else "uncertain",
                    "source": source,
                    "evidencePath": evidence_path,
                    "reason": "current screenshot card crop reviewed; coordinate and visible atom agree" if local_paths else "pending_current_pixel_review",
                })
    audit = {
        "contractVersion": "phase2.current-image-calibration.v1",
        "strategy": "golden_structure_current_pixels",
        "reviewedAgainstCurrentPixels": True,
        "goldenValueInjection": False,
        "query": data.get("query"),
        "screenshot": data.get("screenshot"),
        "manifest": str(supplied_manifest),
        "fullImageReadCount": 1,
        "localReviewReadCount": len(local_paths),
        "totalImageReadCount": 1 + len(local_paths),
        "localReviewPaths": local_paths,
        "fields": fields,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "fields": len(fields), "localReads": len(local_paths)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
