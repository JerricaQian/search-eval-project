#!/usr/bin/env python3
"""Apply an explicitly recorded main-session local visual review to CV facts.

This is deliberately an input-driven evidence step, not a language-correction
model. A review must identify the current screenshot, local crop and each
observed string. Superseded OCR inside that reviewed card is retained as
rejected audit evidence and can never leak into the manifest.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

from extract_cv_facts import Box, _direct_text_phase3_facts

def overlap(a: list[int], b: list[int]) -> bool:
    return a[0] < b[0]+b[2] and a[0]+a[2] > b[0] and a[1] < b[1]+b[3] and a[1]+a[3] > b[1]

def apply(facts: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    if Path(str(review.get("screenshot", ""))).resolve() != Path(str(facts["screenshot"])).resolve():
        raise ValueError("visual review screenshot does not match CV facts")
    observed = review.get("cards", [])
    # A local review normally confirms only selected fields (for example the
    # merchant header).  It is not evidence that every other line in the card
    # is wrong.  Replacing the whole card silently discarded valid Paddle
    # reads of promotions and attached products, leaving a schema-valid but
    # materially incomplete manifest.  Only an explicit full-card replacement
    # may invalidate the rest of that card's OCR observations.
    replacement_boxes = [
        field["coord"]
        for card in observed
        for field in card.get("fields", [])
        if isinstance(field, dict) and isinstance(field.get("coord"), list) and len(field["coord"]) == 4
    ]
    full_card_replacements = [card["coord"] for card in observed if card.get("replaceAllCardText") is True]
    for item in facts.get("candidates", {}).get("text", []):
        if any(overlap(item["coord"], box) for box in replacement_boxes + full_card_replacements):
            item["route"] = "rejected"
            item.setdefault("rejectionReasons", []).append("superseded_by_main_session_local_visual_review")
    replacement_photo_boxes = [
        box for card in observed for box in card.get("replacePhotoBoxes", [])
        if isinstance(box, list) and len(box) == 4
    ]
    for item in facts.get("candidates", {}).get("photos", []):
        if any(overlap(item["coord"], box) for box in replacement_photo_boxes):
            item["route"] = "rejected"
            item.setdefault("rejectionReasons", []).append("superseded_by_main_session_local_visual_review")
    next_id = 1
    text = facts.setdefault("candidates", {}).setdefault("text", [])
    for card in observed:
        for field in card.get("fields", []):
            coord = [int(v) for v in field["coord"]]
            label = str(field["text"]).strip()
            if not label:
                continue
            box = Box(*coord)
            visible_status = field.get("visibleStatus", "confirmed")
            if visible_status not in {"confirmed", "naturally_cropped", "uncertain"}:
                raise ValueError(f"invalid visual review visibleStatus: {visible_status}")
            phase3_facts = _direct_text_phase3_facts(label, box, {"colorRole": field.get("colorRole", "unknown"), "evidence": "main_session_local_visual_read"}, True)
            if visible_status != "confirmed":
                phase3_facts["render"].update({"visibleStatus": visible_status, "renderState": "partial" if visible_status == "naturally_cropped" else "uncertain"})
                phase3_facts["textFacts"]["textStatus"] = visible_status
                # Visual facts use the existing binary confidence enum;
                # render/text preserve the more precise natural-crop state.
                phase3_facts["visual"]["visualStatus"] = "uncertain"
            text.append({"id": f"VR{next_id}", "kind": "text", "text": label, "coord": coord,
                "ocrConsensus": {"status": "confirmed", "primaryText": label, "secondaryText": "",
                                 "method": "main_session_local_visual_read"},
                "geometry": {"rowAlignment": "main_session_local_review"},
                "visualHint": {"colorRole": field.get("colorRole", "unknown"), "evidence": "main_session_local_visual_read"},
                "phase3Facts": phase3_facts,
                "route": "accepted", "rejectionReasons": [],
                "visualReview": {"cardId": card.get("cardId", ""), "crop": card["coord"], "readId": field.get("readId", "main_session_local_read"), "role": field.get("role", "other"), "visibleStatus": visible_status}})
            next_id += 1
    next_photo_id = 1
    photos = facts.setdefault("candidates", {}).setdefault("photos", [])
    for card in observed:
        for photo in card.get("photos", []):
            coord = [int(v) for v in photo["coord"]]
            visible_status = photo.get("visibleStatus", "confirmed")
            if visible_status not in {"confirmed", "naturally_cropped", "uncertain"}:
                raise ValueError(f"invalid visual review photo visibleStatus: {visible_status}")
            visual_status = "confirmed" if visible_status == "confirmed" else "uncertain"
            photos.append({
                "id": f"VP{next_photo_id}", "kind": "photo_candidate", "coord": coord,
                "detectorRule": "main_session_local_visual_read", "confidence": 1.0,
                "confidenceParts": {"detector": 1.0, "rowGeometry": 1.0},
                "phase3Facts": {
                    "render": {"visibleStatus": visible_status, "renderState": "normal" if visible_status == "confirmed" else "partial" if visible_status == "naturally_cropped" else "uncertain", "isPhoto": True, "isSystemUi": False},
                    "visual": {"entityKind": "image", "visualStatus": visual_status, "isColored": False, "isShaped": False, "colorRole": "unknown", "backgroundColor": "", "textColor": "", "borderColor": "", "hasGraphicAssist": False, "graphicType": "无", "styleKey": "image|unknown|photo|无容器|无", "colorEvidence": "main_session_local_visual_read"},
                },
                "route": "accepted", "rejectionReasons": [],
                "visualReview": {"cardId": card.get("cardId", ""), "crop": card["coord"], "readId": photo.get("readId", "main_session_local_read"), "visibleStatus": visible_status},
            })
            next_photo_id += 1
    facts.setdefault("routing", {})["visualReview"] = {"source": "main_session_local_read", "cards": observed,
        "localReviewReadCount": len(observed)}
    facts["routing"]["unresolvedCandidateIds"] = [item["id"] for kind in ("text", "photos") for item in facts["candidates"].get(kind, []) if item.get("route") != "accepted"]
    return facts

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--facts", type=Path, required=True); parser.add_argument("--review", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = apply(json.loads(args.facts.read_text(encoding="utf-8")), json.loads(args.review.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return 0
if __name__ == "__main__": raise SystemExit(main())
