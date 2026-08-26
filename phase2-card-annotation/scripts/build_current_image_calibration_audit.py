#!/usr/bin/env python3
"""Create the Phase2 current-pixel calibration audit from reviewed output.

The manifest remains the only Phase2 fact source.  A recorded visual review
can attest that the current full screenshot was reconciled against it; this
script then records each published element exactly once.  Without that
attestation it writes a deliberately non-publishable template.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from apply_visual_review import load_review


def main() -> int:
    parser = argparse.ArgumentParser()
    # Positional input is retained for existing Phase2 regression callers;
    # the named form is clearer for the production entry point.
    parser.add_argument("legacy_manifest", nargs="?", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--local-read", action="append", default=[], type=Path)
    parser.add_argument("--visual-review", type=Path,
                        help="Recorded current-screenshot review used to reconcile this manifest")
    args = parser.parse_args()
    supplied_manifest = args.manifest or args.legacy_manifest
    if supplied_manifest is None:
        parser.error("a manifest path is required")
    manifest_path = supplied_manifest.resolve()
    data: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    review: dict[str, Any] = {}
    if args.visual_review:
        review = load_review(args.visual_review)
        if Path(str(review.get("screenshot", ""))).resolve() != Path(str(data.get("screenshot", ""))).resolve():
            raise ValueError("visual review screenshot does not match manifest")
    review_paths = review.get("localReviewPaths", [])
    if not isinstance(review_paths, list) or any(not isinstance(path, str) or not path for path in review_paths):
        raise ValueError("visual review localReviewPaths must be a list of non-empty paths")
    local_paths = [str(path.resolve()) for path in args.local_read]
    local_paths.extend(review_paths)
    if len(local_paths) != len(set(local_paths)):
        raise ValueError("local review paths must be unique")
    complete_review = review.get("completeCurrentPixelReview") is True
    fields: list[dict[str, Any]] = []
    for card in data.get("cards", []):
        card_id = str(card.get("cardId", ""))
        evidence_path = str(data.get("screenshot", ""))
        source = "full_image"
        for region in card.get("regions", []):
            for element in region.get("elements", []):
                if element.get("isExcluded"):
                    continue
                is_photo = element.get("元素类型") == "图片" or element.get("render", {}).get("isPhoto") is True
                facts = element.get("textFacts") if isinstance(element.get("textFacts"), dict) else {}
                raw = "" if is_photo else str(facts.get("rawText") or element.get("内容简述", "")).removeprefix("原文:")
                if not element.get("id") or not isinstance(element.get("坐标"), list):
                    raise ValueError(f"invalid active element in {card_id}")
                fields.append({
                    "cardId": card_id,
                    "elementId": element["id"],
                    "field": "photo" if is_photo else "visible_text",
                    "visibleText": raw,
                    "coord": element["坐标"],
                    "status": "confirmed" if complete_review else "uncertain",
                    "source": source,
                    "evidencePath": evidence_path,
                    "reason": "confirmed_from_current_screenshot_pixels_via_recorded_visual_review" if complete_review else "pending_current_pixel_review",
                })
    audit = {
        "contractVersion": "phase2.current-image-calibration.v1",
        "strategy": "golden_structure_current_pixels",
        "reviewedAgainstCurrentPixels": complete_review,
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
    print(json.dumps({"output": str(args.output), "fields": len(fields), "localReads": len(local_paths), "reviewed": complete_review}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
