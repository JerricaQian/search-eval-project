#!/usr/bin/env python3
"""Run one bounded, card-aware OCR retry after the Phase2 recognition gate.

The retry is deterministic and screenshot-local.  It consumes only card
boundaries and gate findings from the first pass, OCRs at most three compact
regions per failing card, and merges corroborated/new observations back into
CV facts.  It never calls a vision model and never uses golden answers.
"""
from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from extract_cv_facts import Box, _clamp_box, _direct_text_phase3_facts, _text_color_hint, ocr_region


VERSION = "phase2.bounded-card-reprocess.v1"


def overlap(a: list[int], b: list[int]) -> bool:
    return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[1] + a[3] > b[1]


def intersection_ratio(a: list[int], b: list[int]) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    area = (x1 - x0) * (y1 - y0)
    return area / max(1, min(a[2] * a[3], b[2] * b[3]))


def meaningful(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff¥￥.+%折减分钟公里]", "", value)


def numeric_signature(value: str) -> str:
    return "".join(re.findall(r"\d", value))


def text_quality(value: str) -> int:
    compact = meaningful(value)
    chinese = sum("\u4e00" <= char <= "\u9fff" for char in compact)
    latin = sum(char.isascii() and char.isalpha() for char in compact)
    punctuation = sum(not (char.isalnum() or "\u4e00" <= char <= "\u9fff" or char in "¥￥.,+-%折减/×* ()[]") for char in value)
    unexplained_latin = latin if chinese >= 2 and latin >= 3 and not re.search(r"(?:ml|kg|cm|mm|km|NaCl|SPA|KTV|Plus|Pro|SOHO|SKU)", value, re.I) else 0
    return len(compact) + chinese - punctuation * 2 - unexplained_latin


def mixed_script_gibberish(value: str) -> bool:
    compact = meaningful(value)
    chinese = sum("\u4e00" <= char <= "\u9fff" for char in compact)
    latin = sum(char.isascii() and char.isalpha() for char in compact)
    allowed = re.search(r"(?:ml|kg|cm|mm|km|Na\s*c?Cl|SOHO|S\W*K\W*U|SPA|KTV|Plus|Pro)", value, re.I)
    return chinese >= 2 and latin >= 5 and latin / max(1, chinese + latin) > 0.45 and not allowed


def punctuation_gibberish(value: str) -> bool:
    if not value:
        return True
    punctuation = sum(not (char.isalnum() or "\u4e00" <= char <= "\u9fff" or char in "¥￥.,+-%折减/×* ()[]") for char in value)
    return punctuation / len(value) > 0.35


def compatible_text(left: str, right: str) -> bool:
    a, b = meaningful(left), meaningful(right)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) >= 2 and shorter in longer and len(shorter) / len(longer) >= 0.45:
        return True
    left_digits, right_digits = numeric_signature(left), numeric_signature(right)
    if left_digits and right_digits and left_digits == right_digits and SequenceMatcher(None, a, b).ratio() >= 0.45:
        return True
    matcher = SequenceMatcher(None, a, b)
    longest = matcher.find_longest_match(0, len(a), 0, len(b)).size
    if longest >= 6 and longest / min(len(a), len(b)) >= 0.25:
        return True
    return matcher.ratio() >= 0.78


def corroborated_title_span(primary: str, bounded: str) -> str:
    """Remove merged non-title edges without correcting any Chinese glyph.

    The returned title is a literal substring of the original OCR. A bounded
    crop may only corroborate where that substring starts/ends; its differing
    glyphs are never copied into the published value.
    """
    matches = re.findall(r"[\u4e00-\u9fff][\u4e00-\u9fffA-Za-z0-9（）()·&.+-]*[\u4e00-\u9fff）)]", primary)
    span = max(matches, key=len, default="")
    left = "".join(re.findall(r"[\u4e00-\u9fff]", span))
    right = "".join(re.findall(r"[\u4e00-\u9fff]", bounded))
    if len(left) < 4 or len(right) < 4 or span == primary.strip():
        return ""
    return span if SequenceMatcher(None, left, right).ratio() >= 0.70 else ""


def group_bounded_title_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Join a wrapped title while excluding short badge/city observations."""
    if len(entries) <= 1:
        return entries
    long_entries = [item for item in entries if sum("\u4e00" <= char <= "\u9fff" for char in str(item.get("text", ""))) >= 4]
    if not long_entries:
        return entries
    main = max(long_entries, key=lambda item: (sum("\u4e00" <= char <= "\u9fff" for char in str(item.get("text", ""))), item.get("coord", [0, 0, 0, 0])[2]))
    mx, my, mw, mh = main["coord"]
    continuation = [
        item for item in entries if item is not main
        and item["coord"][1] >= my + mh * 0.65
        and sum("\u4e00" <= char <= "\u9fff" for char in str(item.get("text", ""))) >= 2
        and (re.search(r"[）)]", str(item.get("text", ""))) or item["coord"][0] >= mx - mw * 0.45)
    ]
    selected = [main] + sorted(continuation, key=lambda item: (item["coord"][1], item["coord"][0]))
    extras = []
    for item in entries:
        text = str(item.get("text", "")).strip()
        if item in selected:
            continue
        if re.fullmatch(r"演出|外卖|景点|推荐|神券|直播中?|自营|品牌", text):
            extras.append({**item, "_boundedRegion": "tag", "_semanticRegion": "tag"})
        elif re.fullmatch(r"北京|上海|广州|深圳|杭州|南京|成都|重庆|天津|苏州|武汉|西安", text):
            extras.append({**item, "_boundedRegion": "location", "_semanticRegion": "location"})
    if len(selected) == 1:
        return [{**main, "_boundedRegion": "source_line", "_semanticRegion": "title"}] + extras
    x0 = min(item["coord"][0] for item in selected)
    y0 = min(item["coord"][1] for item in selected)
    x1 = max(item["coord"][0] + item["coord"][2] for item in selected)
    y1 = max(item["coord"][1] + item["coord"][3] for item in selected)
    grouped_text = "".join(str(item.get("text", "")).strip() for item in selected)
    return [{"text": grouped_text, "coord": [x0, y0, x1 - x0, y1 - y0], "ocrConsensus": {"status": "bounded_single_observation", "primaryText": grouped_text, "secondaryText": "", "method": "bounded_title_line_group"}, "_boundedRegion": "source_line", "_semanticRegion": "title"}] + extras


def group_bounded_price_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rejoin Paddle fragments belonging to the same visible price row."""
    rows: list[list[dict[str, Any]]] = []
    for item in sorted(entries, key=lambda value: (value["coord"][1], value["coord"][0])):
        row = next((candidate for candidate in rows if abs(candidate[0]["coord"][1] - item["coord"][1]) <= 14), None)
        if row is None:
            rows.append([item])
        else:
            row.append(item)
    grouped = []
    for row in rows:
        ordered = sorted(row, key=lambda item: item["coord"][0])
        text = "".join(str(item.get("text", "")).strip() for item in ordered)
        x0 = min(item["coord"][0] for item in ordered)
        y0 = min(item["coord"][1] for item in ordered)
        x1 = max(item["coord"][0] + item["coord"][2] for item in ordered)
        y1 = max(item["coord"][1] + item["coord"][3] for item in ordered)
        grouped.append({"text": text, "coord": [x0, y0, x1 - x0, y1 - y0], "ocrConsensus": {"status": "bounded_single_observation", "primaryText": text, "secondaryText": "", "method": "bounded_price_line_group"}, "_boundedRegion": "price", "_semanticRegion": "price"})
    return grouped


def _card_for_source(source: dict[str, Any], cards: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [card for card in cards if overlap(source.get("coord", [0, 0, 0, 0]), card.get("coord", [0, 0, 0, 0]))]
    if not matches:
        source_center = source.get("coord", [0, 0, 0, 0])[1] + source.get("coord", [0, 0, 0, 0])[3] / 2
        nearby = []
        for card in cards:
            top, bottom = card["coord"][1], card["coord"][1] + card["coord"][3]
            distance = top - source_center if source_center < top else source_center - bottom if source_center > bottom else 0
            if distance <= max(24, card["coord"][3] * 0.12):
                nearby.append((distance, 0 if source_center >= bottom else 1, card))
        return min(nearby, key=lambda item: (item[0], item[1]), default=(0, 0, None))[2]
    source_box = source.get("coord", [0, 0, 0, 0])
    center_y = source_box[1] + source_box[3] / 2
    centered = [card for card in matches if card["coord"][1] <= center_y < card["coord"][1] + card["coord"][3]]
    return min(centered or matches, key=lambda card: card["coord"][3])


def _text_column(card: dict[str, Any], facts: dict[str, Any]) -> int:
    x, y, width, height = card["coord"]
    photos = [item for item in facts.get("candidates", {}).get("photos", []) if item.get("route") != "rejected" and overlap(item.get("coord", [0, 0, 0, 0]), card["coord"])]
    explicit_head = str(card.get("headPhotoId", ""))
    left_heads = [item for item in photos if item["id"] == explicit_head] if explicit_head else [item for item in photos if item["coord"][0] < x + width * 0.45 and item["coord"][1] < y + height * 0.35]
    if left_heads:
        right = max(item["coord"][0] + item["coord"][2] for item in left_heads)
        # Leave room for a compact badge immediately after the head image
        # (e.g. 外卖/景点). Starting on the badge makes line OCR merge its
        # coloured glyphs into the title.
        return min(x + round(width * 0.46), max(x + round(width * 0.26), right + 16))
    return x + round(width * 0.22)


def _crop(card: dict[str, Any], facts: dict[str, Any], region: str) -> list[int]:
    x, y, width, height = card["coord"]
    text_x = _text_column(card, facts)
    right = x + width
    if region == "title":
        top, bottom = y, y + max(96, round(height * 0.34))
    elif region == "price":
        top, bottom = y + round(height * 0.30), y + round(height * 0.88)
    elif region == "info":
        top, bottom = y + round(height * 0.14), y + round(height * 0.64)
    else:
        top, bottom = y, y + height
    return [text_x, top, max(1, right - text_x), max(1, bottom - top)]


def plan_targets(facts: dict[str, Any], candidates: dict[str, Any], semantics: dict[str, Any], gate: dict[str, Any]) -> list[dict[str, Any]]:
    cards = candidates.get("resultCards", [])
    by_card = {item.get("cardId"): item for item in semantics.get("cards", [])}
    facts_by_id = {item.get("id"): item for item in facts.get("candidates", {}).get("text", [])}
    requested: dict[str, set[str]] = {}
    source_ids: dict[tuple[str, str], set[str]] = {}
    semantic_region_by_source: dict[str, str] = {}
    for semantic_card in semantics.get("cards", []):
        for region in semantic_card.get("regions", []):
            name = str(region.get("region", ""))
            semantic_region = "title" if "标题" in name else "price" if "价格" in name else ""
            if semantic_region:
                for source_id in region.get("evidenceSourceIds", []):
                    semantic_region_by_source[str(source_id)] = semantic_region

    for finding in gate.get("reprocessTargets", []):
        source = facts_by_id.get(finding.get("sourceId"))
        card = _card_for_source(source, cards) if source else None
        if not card:
            continue
        card_id = card["id"]
        requested.setdefault(card_id, set()).add("source_line")
        source_ids.setdefault((card_id, "source_line"), set()).add(str(finding.get("sourceId")))
        role = str(finding.get("role", ""))
        if role in {"title", "price"}:
            semantic_region_by_source[str(finding.get("sourceId"))] = role

    for card in cards:
        card_id = card["id"]
        semantic = by_card.get(card_id, {})
        selected = semantic.get("selectedCardType", {})
        validation = semantic.get("contractValidation", {})
        missing_groups = validation.get("missingEvidenceGroups", []) if isinstance(validation, dict) else []
        missing = {str(field) for group in missing_groups if isinstance(group, list) for field in group}
        if "title_like_text" in missing:
            requested.setdefault(card_id, set()).add("title")
        if "price_text" in missing:
            requested.setdefault(card_id, set()).add("price")
        if missing & {"merchant_metrics", "performance_identity", "performance_schedule", "hotel_identity", "package_identity"}:
            requested.setdefault(card_id, set()).add("info")
        if selected.get("status") != "confirmed" or any(str(error).startswith(f"{card_id}:") for error in gate.get("errors", [])):
            requested.setdefault(card_id, set()).add("full")

    order = {"source_line": 0, "title": 1, "price": 2, "info": 3, "full": 4}
    result: list[dict[str, Any]] = []
    for card in cards:
        card_id = card["id"]
        regions = sorted(requested.get(card_id, set()), key=lambda item: order[item])
        # Source-line OCR is represented by one union crop per card.  Prefer
        # specific missing-field windows, then use full text-column recovery.
        if "source_line" in regions:
            sources = [facts_by_id[source_id] for source_id in source_ids.get((card_id, "source_line"), set()) if source_id in facts_by_id]
            if sources:
                # A full-image OCR box may merge the left logo/photo with the
                # merchant title. The bounded retry must start at the inferred
                # text column or it simply reproduces the same corruption.
                x0 = max(_text_column(card, facts), max(card["coord"][0], min(item["coord"][0] for item in sources) - 24))
                # Full-page OCR boxes may legitimately extend a few pixels
                # above the CV card boundary. Preserve that glyph cap-height
                # instead of clipping the first title row at the card edge.
                y0 = max(0, min(item["coord"][1] for item in sources) - 14)
                x1 = min(card["coord"][0] + card["coord"][2], max(item["coord"][0] + item["coord"][2] for item in sources) + 32)
                semantic_regions = {semantic_region_by_source.get(item["id"], "") for item in sources}
                semantic_region = "title" if "title" in semantic_regions else "price" if "price" in semantic_regions else ""
                card_type = str(by_card.get(card_id, {}).get("selectedCardType", {}).get("cardType", ""))
                if semantic_region == "price":
                    x0 = max(card["coord"][0], min(item["coord"][0] for item in sources) - 24)
                if semantic_region == "title" and card_type == "演出电影卡片":
                    x0 = max(x0, card["coord"][0] + round(card["coord"][2] * 0.26))
                if semantic_region == "title":
                    source_height = max(item["coord"][3] for item in sources)
                    factor = 1.65 if card_type == "演出电影卡片" else 0.78
                    minimum_height = 120 if card_type == "演出电影卡片" else 72
                    y1 = min(int(facts.get("viewport", {}).get("height", card["coord"][1] + card["coord"][3])), y0 + max(minimum_height, round(source_height * factor)))
                else:
                    y1 = min(int(facts.get("viewport", {}).get("height", card["coord"][1] + card["coord"][3])), max(item["coord"][1] + item["coord"][3] for item in sources) + 14)
                result.append({"cardId": card_id, "cardType": card_type, "region": "source_line", "semanticRegion": semantic_region, "coord": [x0, y0, x1 - x0, y1 - y0], "sourceIds": sorted(item["id"] for item in sources)})
        specific = [region for region in regions if region not in {"source_line", "full"}]
        for region in specific[:2]:
            result.append({"cardId": card_id, "region": region, "coord": _crop(card, facts, region), "sourceIds": []})
        if not specific and "full" in regions:
            result.append({"cardId": card_id, "region": "full", "coord": _crop(card, facts, "full"), "sourceIds": []})
        # Hard cap protects CPU even when several hooks hit the same card.
        card_targets = [item for item in result if item["cardId"] == card_id]
        if len(card_targets) > 3:
            keep = set(id(item) for item in card_targets[:3])
            result = [item for item in result if item["cardId"] != card_id or id(item) in keep]
    return result


def _candidate(entry: dict[str, Any], rgb: np.ndarray, width: int, height: int, candidate_id: str, target: dict[str, Any], backend: str) -> dict[str, Any] | None:
    x, y, w, h = (int(value) for value in entry.get("coord", [0, 0, 0, 0]))
    box = _clamp_box(x, y, w, h, width, height)
    text = str(entry.get("text", "")).strip()
    if not box or len(meaningful(text)) < 2 or punctuation_gibberish(text):
        return None
    default_region = "price" if target.get("semanticRegion") == "price" else target["region"]
    effective_region = str(entry.get("_boundedRegion", default_region))
    effective_semantic_region = str(entry.get("_semanticRegion", target.get("semanticRegion", "")))
    if effective_region != "source_line" and mixed_script_gibberish(text):
        return None
    hint = _text_color_hint(rgb, box)
    consensus = entry.get("ocrConsensus") if isinstance(entry.get("ocrConsensus"), dict) else {"status": "bounded_single_observation", "primaryText": text, "secondaryText": ""}
    return {
        "id": candidate_id, "kind": "text", "text": text, "coord": box.as_list(),
        "ocrConsensus": consensus,
        "geometry": {"rowAlignment": "bounded_card_region"}, "visualHint": hint,
        "phase3Facts": _direct_text_phase3_facts(text, box, hint, True),
        "route": "accepted", "rejectionReasons": [],
        "boundedReprocess": {"cardId": target["cardId"], "region": effective_region, "semanticRegion": effective_semantic_region, "crop": target["coord"], "backend": backend, "sourceIds": target.get("sourceIds", [])},
    }


def merge_observations(facts: dict[str, Any], observations: list[dict[str, Any]], target_source_ids: set[str]) -> tuple[int, int]:
    existing = facts.get("candidates", {}).get("text", [])
    next_id = max((int(match.group(1)) for item in existing if (match := re.fullmatch(r"T(\d+)", str(item.get("id", ""))))), default=0) + 1
    added = corroborated = 0
    for observation in observations:
        ranked = sorted(existing, key=lambda item: intersection_ratio(item.get("coord", [0, 0, 0, 0]), observation["coord"]), reverse=True)
        match = ranked[0] if ranked and intersection_ratio(ranked[0].get("coord", [0, 0, 0, 0]), observation["coord"]) >= 0.48 else None
        semantic_region = observation.get("boundedReprocess", {}).get("semanticRegion")
        cleaned_title = corroborated_title_span(str(match.get("text", "")), observation["text"]) if match and semantic_region == "title" else ""
        if match and cleaned_title:
            old_text = str(match.get("text", ""))
            match["text"] = cleaned_title
            match["coord"] = observation["coord"]
            match["visualHint"] = observation["visualHint"]
            match["phase3Facts"] = observation["phase3Facts"]
            match["ocrConsensus"] = {"status": "confirmed", "primaryText": cleaned_title, "secondaryText": observation["text"], "method": "bounded_title_segmentation_corroboration"}
            match["ocrRefinement"] = {"applied": True, "originalText": old_text, "refinedText": cleaned_title, "backend": observation["boundedReprocess"]["backend"], "crop": observation["boundedReprocess"]["crop"], "acceptance": "literal_primary_substring_corroborated_by_bounded_title_crop"}
            match["boundedReprocess"] = observation["boundedReprocess"]
            match.get("phase3Facts", {}).get("textFacts", {})["rawText"] = cleaned_title
            corroborated += 1
            continue
        bounded_backend = observation.get("boundedReprocess", {}).get("backend")
        bounded_chinese = sum("\u4e00" <= char <= "\u9fff" for char in observation["text"])
        if match and semantic_region == "title" and bounded_backend == "paddleocr" and bounded_chinese >= 4 and mixed_script_gibberish(str(match.get("text", ""))):
            old_text = str(match.get("text", ""))
            match.update({"text": observation["text"], "coord": observation["coord"], "visualHint": observation["visualHint"], "phase3Facts": observation["phase3Facts"]})
            match["ocrConsensus"] = {"status": "confirmed", "primaryText": observation["text"], "secondaryText": old_text, "method": "bounded_paddle_title_recovery"}
            match["ocrRefinement"] = {"applied": True, "originalText": old_text, "refinedText": observation["text"], "backend": "paddleocr", "crop": observation["boundedReprocess"]["crop"], "acceptance": "bounded_card_title_recovered_from_mixed_script_full_page_failure"}
            match["boundedReprocess"] = observation["boundedReprocess"]
            match.get("phase3Facts", {}).get("textFacts", {})["rawText"] = observation["text"]
            corroborated += 1
            continue
        if match and semantic_region == "price" and bounded_backend == "paddleocr" and re.search(r"[¥￥]\s*\d", observation["text"]):
            old_digits, new_digits = numeric_signature(str(match.get("text", ""))), numeric_signature(observation["text"])
            if old_digits and new_digits and old_digits == new_digits:
                old_text = str(match.get("text", ""))
                match.update({"text": observation["text"], "coord": observation["coord"], "visualHint": observation["visualHint"], "phase3Facts": observation["phase3Facts"]})
                match["ocrConsensus"] = {"status": "confirmed", "primaryText": observation["text"], "secondaryText": old_text, "method": "bounded_paddle_price_line_recovery"}
                match["ocrRefinement"] = {"applied": True, "originalText": old_text, "refinedText": observation["text"], "backend": "paddleocr", "crop": observation["boundedReprocess"]["crop"], "acceptance": "same_numeric_signature_in_bounded_price_line"}
                match["boundedReprocess"] = observation["boundedReprocess"]
                match.get("phase3Facts", {}).get("textFacts", {})["rawText"] = observation["text"]
                corroborated += 1
                continue
        if match and compatible_text(str(match.get("text", "")), observation["text"]):
            old_text, new_text = str(match.get("text", "")), observation["text"]
            chosen = new_text if text_quality(new_text) > text_quality(old_text) else old_text
            match["text"] = chosen
            match["ocrConsensus"] = {"status": "confirmed", "primaryText": chosen, "secondaryText": old_text if chosen == new_text else new_text, "method": "bounded_card_reread_corroboration"}
            match["ocrRefinement"] = {"applied": chosen != old_text, "originalText": old_text, "refinedText": chosen, "backend": observation["boundedReprocess"]["backend"], "crop": observation["boundedReprocess"]["crop"], "acceptance": "bounded_card_reread_corroborated"}
            match["boundedReprocess"] = observation["boundedReprocess"]
            direct = match.get("phase3Facts", {}).get("textFacts", {})
            direct["rawText"] = chosen
            corroborated += 1
            continue
        if match and observation.get("boundedReprocess", {}).get("region") == "source_line":
            # A source-line retry may be useful only as corroboration. Never
            # publish a divergent OCR string from the same visual row.
            continue
        observation["id"] = f"T{next_id}"
        next_id += 1
        existing.append(observation)
        added += 1

    # A targeted source is superseded only when a new/corroborated observation
    # overlaps its visual line.  Otherwise the original finding remains and the
    # second gate will continue to block the page.
    for item in existing:
        if item.get("id") not in target_source_ids:
            continue
        supporting = [other for other in existing if other is not item and other.get("route") == "accepted" and intersection_ratio(item.get("coord", [0, 0, 0, 0]), other.get("coord", [0, 0, 0, 0])) >= 0.48]
        if supporting and any(compatible_text(str(item.get("text", "")), str(other.get("text", ""))) or text_quality(str(other.get("text", ""))) > text_quality(str(item.get("text", ""))) for other in supporting):
            item["route"] = "rejected"
            item.setdefault("rejectionReasons", []).append("superseded_by_bounded_card_reread")
    facts["candidates"]["text"] = existing
    facts.setdefault("routing", {})["unresolvedCandidateIds"] = [item["id"] for kind in ("text", "photos") for item in facts.get("candidates", {}).get(kind, []) if item.get("route") == "rejected"]
    return added, corroborated


def reprocess(screenshot: Path, facts: dict[str, Any], candidates: dict[str, Any], semantics: dict[str, Any], gate: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    targets = plan_targets(facts, candidates, semantics, gate)
    with Image.open(screenshot) as image:
        rgb = np.asarray(image.convert("RGB"))
    height, width, _ = rgb.shape
    observations: list[dict[str, Any]] = []
    backend_counts: dict[str, int] = {}
    crop_reports: list[dict[str, Any]] = []
    for target in targets:
        psm = 6 if target.get("semanticRegion") == "title" and target.get("cardType") == "演出电影卡片" else 7 if target["region"] in {"source_line", "title", "price"} else 6
        entries, backend, error = ocr_region(screenshot, target["coord"], tesseract_psm=psm)
        if target.get("semanticRegion") == "title":
            entries = group_bounded_title_entries(entries)
        elif target.get("semanticRegion") == "price":
            entries = group_bounded_price_entries(entries)
        backend_counts[backend] = backend_counts.get(backend, 0) + 1
        before = len(observations)
        for entry in entries:
            candidate = _candidate(entry, rgb, width, height, "", target, backend)
            if candidate:
                observations.append(candidate)
        crop_reports.append({**target, "backend": backend, "tesseractPsm": psm, "error": error or "", "observations": len(observations) - before})
    target_source_ids = {source_id for target in targets for source_id in target.get("sourceIds", [])}
    added, corroborated = merge_observations(facts, observations, target_source_ids)
    backends = facts.setdefault("backends", {})
    backends["boundedCardReprocessAttempts"] = 1 if targets else 0
    backends["boundedCardReprocessCrops"] = len(targets)
    backends["boundedCardReprocessAdded"] = added
    backends["boundedCardReprocessCorroborated"] = corroborated
    backends["boundedCardReprocessBackends"] = backend_counts
    facts.setdefault("routing", {})["boundedCardReprocess"] = {"contractVersion": VERSION, "targets": targets, "added": added, "corroborated": corroborated}
    report = {"contractVersion": VERSION, "targets": targets, "crops": crop_reports, "observations": len(observations), "added": added, "corroborated": corroborated, "backendCounts": backend_counts}
    return facts, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one bounded card-aware OCR retry from Phase2 gate findings")
    parser.add_argument("--screenshot", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--result-candidates", type=Path, required=True)
    parser.add_argument("--card-semantics", type=Path, required=True)
    parser.add_argument("--recognition-gate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result, report = reprocess(
        args.screenshot,
        json.loads(args.facts.read_text(encoding="utf-8")),
        json.loads(args.result_candidates.read_text(encoding="utf-8")),
        json.loads(args.card_semantics.read_text(encoding="utf-8")),
        json.loads(args.recognition_gate.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "targets": len(report["targets"]), "added": report["added"], "corroborated": report["corroborated"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
