#!/usr/bin/env python3
"""Separate page modules from repeatable result-card candidates.

The input structure is deliberately non-semantic. This script adds only
conservative candidates: a repeated image-left/text-right block seeds a result
card, and intervening text-only blocks are attached until the next seed. It
does not decide that omitted optional modules are absent or defective.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


VERSION = "phase2.search-result-candidates.v1"


def _overlap_y(a: list[int], b: list[int]) -> bool:
    return a[1] < b[1] + b[3] and a[1] + a[3] > b[1]


def _texts_in(box: list[int], texts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in texts if _overlap_y(box, item["coord"])]


def _union(boxes: list[list[int]]) -> list[int]:
    x0, y0 = min(box[0] for box in boxes), min(box[1] for box in boxes)
    x1 = max(box[0] + box[2] for box in boxes)
    y1 = max(box[1] + box[3] for box in boxes)
    return [x0, y0, x1 - x0, y1 - y0]


def _module_candidates(facts: dict[str, Any], structure: dict[str, Any]) -> list[dict[str, Any]]:
    texts = facts.get("candidates", {}).get("text", [])
    joined = "\n".join(str(item.get("text", "")) for item in texts)
    viewport = facts["viewport"]
    module_rules = [
        ("search_bar", r".{1,}", 0.55, "top_text_candidate"),
        ("tab", r"全部|外卖|团购|地点|攻略", 0.80, "tab_terms"),
        ("tip_strip", r"提示|温馨|为你|推荐", 0.62, "tip_terms"),
        ("image_filter", r"男士剪发|女士剪发|儿童理发|烫染|洗头", 0.70, "image_filter_terms"),
        ("text_filter", r"附近|热门|推荐|价格", 0.58, "text_filter_terms"),
        ("business_image_filter", r"品类|服务|套餐", 0.52, "business_image_filter_terms"),
        ("main_poi_card", r"地铁站|大学|医院|商场|景点", 0.68, "poi_terms"),
        ("business_operation_card", r"广告|推广|领券|限时", 0.66, "operation_terms"),
        ("sort_filter", r"综合排序|排序|筛选", 0.88, "sort_filter_terms"),
        ("promotion_filter", r"神券|优惠|满减", 0.80, "promotion_terms"),
    ]
    modules: list[dict[str, Any]] = []
    for module_id, pattern, score, reason in module_rules:
        matched = [item for item in texts if re.search(pattern, str(item.get("text", "")))]
        if module_id == "search_bar":
            matched = [item for item in texts if item["coord"][1] < viewport["height"] * 0.15]
        if not matched:
            continue
        box = _union([item["coord"] for item in matched])
        modules.append({"module": module_id, "coord": box, "confidence": score, "status": "confirmed" if score >= 0.78 else "uncertain", "evidence": [reason]})
    confirmed_tabs = [module for module in modules if module["module"] == "tab" and module["status"] == "confirmed"]
    if confirmed_tabs:
        tab_bottom = max(module["coord"][1] + module["coord"][3] for module in confirmed_tabs)
        # A multi-image row immediately after Tab is a business image filter,
        # not the beginning of the result-card list (e.g. medicine categories).
        for block in structure.get("blocks", []):
            bx, by, bw, bh = block["coord"]
            images = [item for item in facts.get("candidates", {}).get("photos", []) if _overlap_y(item["coord"], block["coord"])]
            x_span = max((item["coord"][0] + item["coord"][2] for item in images), default=0) - min((item["coord"][0] for item in images), default=0)
            preceding_merchant_head = any(item["coord"][1] < by and item["coord"][0] <= viewport["width"] * 0.16 and item["coord"][2] >= 88 and item["coord"][3] >= 88 for item in facts.get("candidates", {}).get("photos", []))
            if by >= tab_bottom and not preceding_merchant_head and bh >= 80 and len(images) >= 3 and x_span >= viewport["width"] * 0.55:
                modules.append({"module": "business_image_filter", "coord": block["coord"], "confidence": 0.78, "status": "confirmed", "evidence": ["multiple_business_images_spanning_row"]})
                break
        watcher_text = [item for item in texts if re.search(r"直播|观看", str(item.get("text", "")))]
        for block in structure.get("blocks", []):
            bx, by, bw, bh = block["coord"]
            if block.get("layoutCandidate") != "other" or bh < 360 or by + bh <= tab_bottom:
                continue
            has_watcher = any(_overlap_y(item["coord"], block["coord"]) for item in watcher_text)
            if has_watcher:
                modules.append({"module": "live_card", "cardType": "异构卡-直播卡", "coord": [0, tab_bottom, int(viewport["width"]), by + bh - tab_bottom], "confidence": 0.82, "status": "confirmed", "evidence": ["large_media_block_after_tab", "live_or_viewer_text"]})
                break
    return modules


def _merchant_graphic_hang_cards(facts: dict[str, Any], results_start_y: int) -> list[dict[str, Any]]:
    """Find the merchant-image/text-downhang topology from local photo geometry.

    A merchant head image is a near-square photo in the left image column. A
    graphic downhang needs a separate, sufficiently large photo group to its
    right below that head. Tall left-column coupon artwork is deliberately not
    counted as a product group.
    """
    viewport_width = int(facts["viewport"]["width"])
    photos = sorted(facts.get("candidates", {}).get("photos", []), key=lambda item: item["coord"][1])
    heads = []
    for item in photos:
        x, y, w, h = item["coord"]
        ratio = w / h if h else 0
        # Merchant heads use the narrow left column; product strips begin
        # around x=227 on a 1224px reference canvas, so 16% keeps them apart.
        if y < results_start_y or x > viewport_width * 0.16 or w < 88 or h < 88 or not 0.65 <= ratio <= 1.35:
            continue
        heads.append(item)
    cards: list[dict[str, Any]] = []
    for index, head in enumerate(heads):
        x, y, w, h = head["coord"]
        next_y = heads[index + 1]["coord"][1] if index + 1 < len(heads) else int(facts["viewport"]["height"])
        product_groups = []
        for photo in photos:
            px, py, pw, ph = photo["coord"]
            if py < y + h * 0.70 or py >= next_y or px < viewport_width * 0.18 or pw < 96 or ph < 96:
                continue
            product_groups.append(photo)
        if not product_groups:
            continue
        bottom = min(next_y, max(photo["coord"][1] + photo["coord"][3] for photo in product_groups) + 150)
        cards.append({
            "id": f"G{len(cards) + 1}", "coord": [0, y, viewport_width, bottom - y],
            "seedBlockId": "", "memberBlockIds": [], "confidence": 0.90, "status": "confirmed",
            "classificationHint": {"cardType": "商家卡片_图文下挂", "confidence": 0.90},
            "evidence": ["left_square_merchant_head", "right_side_attached_product_image_group", "left_coupon_art_excluded"],
            "headPhotoId": head["id"], "attachedProductPhotoIds": [photo["id"] for photo in product_groups],
        })
    return cards


def build_candidates(facts: dict[str, Any], structure: dict[str, Any]) -> dict[str, Any]:
    if facts.get("contractVersion") != "phase2.cv-facts.v1":
        raise ValueError("cv facts version is not supported")
    if structure.get("contractVersion") != "phase2.search-page-structure.v1":
        raise ValueError("structure version is not supported")
    blocks = sorted(structure.get("blocks", []), key=lambda block: block["coord"][1])
    modules = _module_candidates(facts, structure)
    sort_modules = [module for module in modules if module["module"] == "sort_filter" and module["status"] == "confirmed"]
    results_start_y = max((module["coord"][1] + module["coord"][3] for module in sort_modules), default=0)
    seeds = {index for index, block in enumerate(blocks) if block.get("layoutCandidate") == "left_image_right_text" and block.get("confidence", 0) >= 0.75}
    # Photo detection is a useful second seed source: OCR can occasionally
    # cause a valid image-left/text-right block to be labelled "other".
    for photo in facts.get("candidates", {}).get("photos", []):
        px, py, pw, ph = photo["coord"]
        if px > facts["viewport"]["width"] * 0.40 or pw < 96 or ph < 96:
            continue
        for index, block in enumerate(blocks):
            if _overlap_y(block["coord"], photo["coord"]) and block["coord"][3] >= 160:
                seeds.add(index)
                break
    seeds = sorted(seeds)
    seeds = [index for index in seeds if blocks[index]["coord"][1] >= results_start_y]
    cards: list[dict[str, Any]] = []
    for card_index, start_index in enumerate(seeds):
        end_index = seeds[card_index + 1] if card_index + 1 < len(seeds) else len(blocks)
        members = blocks[start_index:end_index]
        # Do not absorb a very distant next page/module. The next card seed
        # already provides the normal stopping boundary.
        while len(members) > 1 and members[-1]["coord"][1] - members[0]["coord"][1] > max(720, members[0]["coord"][3] * 3):
            members.pop()
        coord = _union([member["coord"] for member in members])
        cards.append({
            "id": f"C{card_index + 1}", "coord": coord,
            "seedBlockId": blocks[start_index]["id"], "memberBlockIds": [member["id"] for member in members],
            "confidence": round(min(0.95, blocks[start_index]["confidence"]), 4),
            "status": "confirmed", "evidence": ["repeated_left_image_right_text_seed", "attached_until_next_card_seed"],
        })
    graphic_cards = _merchant_graphic_hang_cards(facts, results_start_y)
    if graphic_cards:
        # The specialised detector owns intervals it can explain. Keep generic
        # cards only for non-overlapping list sections, avoiding duplicates.
        def overlaps_special(card: dict[str, Any]) -> bool:
            cy0, cy1 = card["coord"][1], card["coord"][1] + card["coord"][3]
            return any(cy0 < special["coord"][1] + special["coord"][3] and cy1 > special["coord"][1] for special in graphic_cards)
        cards = graphic_cards + [card for card in cards if not overlaps_special(card)]
        cards.sort(key=lambda card: card["coord"][1])
        for index, card in enumerate(cards, start=1):
            card["id"] = f"C{index}"
    return {
        "contractVersion": VERSION, "sourceCvFacts": facts.get("screenshot", ""),
        "pageModules": modules, "resultCards": cards, "structureBlocks": blocks,
        "routing": {"rule": "Only repeated list-layout seeds become result-card candidates. Missing optional modules, ungrouped blocks, or uncertain candidates cannot establish absence, defects, failing results, excellence, or a human-review task."}
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build search-page module and result-card candidates")
    parser.add_argument("cv_facts", type=Path)
    parser.add_argument("structure", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_candidates(json.loads(args.cv_facts.read_text(encoding="utf-8")), json.loads(args.structure.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "modules": len(result["pageModules"]), "resultCards": len(result["resultCards"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
