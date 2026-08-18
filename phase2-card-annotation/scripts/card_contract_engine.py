#!/usr/bin/env python3
"""Evaluate result-card facts against explicit recognition contracts.

The engine is deterministic and screenshot-local. It never consumes golden
answers or search-word-specific expected types. A known type must satisfy its
minimum structural contract; otherwise explicit advertising wins, then the
heterogeneous fallback preserves the stable rendered unit.
"""
from __future__ import annotations

import re
from typing import Any


KNOWN_RESULT_TYPES = {
    "商品卡片", "商家卡片_图文下挂", "商家卡片_文字下挂", "酒店卡片",
    "演出电影卡片", "度假酒店套餐卡片",
}


def _overlap(box: list[int], container: list[int]) -> bool:
    return box[0] < container[0] + container[2] and box[0] + box[2] > container[0] and box[1] < container[1] + container[3] and box[1] + box[3] > container[1]


def _usable(item: dict[str, Any]) -> bool:
    return item.get("route") != "rejected"


def _meaningful(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff¥￥]+", "", value)


def price_evidence(item: dict[str, Any], card_coord: list[int]) -> dict[str, bool]:
    """Recognize price evidence without correcting or replacing OCR text."""
    text = str(item.get("text", ""))
    exact = bool(re.search(r"[¥￥]\s*\d|\d+(?:\.\d+)?\s*元", text))
    contextual = bool(re.search(
        r"(?:到手价|到手从|神价|低价|特价|券后|票价|价格|前\d+件).{0,10}[#¥￥Yy半*]?[A-Z]?(?:\d|[OoQ])"
        r"|\d+(?:\.\d+)?\s*起(?:\D|$)"
        r"|[Yy][A-Z]?(?:\d+(?:\.\d+)?)\s*(?:起|/人)",
        text, re.I,
    ))
    x, y, width, height = card_coord
    tx, ty, _, th = item.get("coord", [0, 0, 0, 0])
    color = item.get("visualHint", {}).get("colorRole", "unknown")
    numeric_range = color in {"red", "orange"} and not re.search(r"20\d{2}[-/.年]\d{1,2}", text) and bool(re.search(r"\d{2,4}\s*[-–]\s*\d{2,4}", text))
    contextual = contextual or numeric_range
    digits = sum(char.isdigit() for char in text)
    horizontally_plausible = x + width * 0.20 <= tx <= x + width * 0.84
    vertically_plausible = ty + th >= y + height * 0.20
    obvious_non_price = bool(re.search(r"分钟|公里|\bkm\b|评分|\d(?:\.\d+)?\s*分|\d+(?:\.\d+)?万?条|起送|配送费|月售|已售|20\d{2}[-/.年]|\d+(?:\.\d+)?\s*(?:ml|kg|g|片|包|袋|听|瓶|盒)|酒精|浓度|保质期", text, re.I)) and not contextual
    coupon_threshold_only = bool(re.search(r"神券.{0,8}(?:减|至)\s*\d+", text)) and not contextual
    visual = color in {"red", "orange"} and digits >= 2 and horizontally_plausible and vertically_plausible and not obvious_non_price and not coupon_threshold_only
    return {"exact": exact, "contextual": contextual, "visual": visual}


def price_evidence_items(items: list[dict[str, Any]], card_coord: list[int]) -> list[dict[str, Any]]:
    return [item for item in items if any(price_evidence(item, card_coord).values())]


def _geometry_validation(card: dict[str, Any], facts: dict[str, Any], profile: dict[str, Any] | None) -> dict[str, Any]:
    """Return a soft type-specific geometry signal learned from clean goldens.

    Geometry can separate otherwise-passing types, but it can never satisfy a
    missing semantic/structural minimum group or reject a novel layout alone.
    """
    if not profile or profile.get("status") != "learned":
        return {"available": False, "withinLearnedRange": None, "matchedRatio": 0.0, "checks": {}}
    viewport = facts.get("viewport", {})
    viewport_width = float(viewport.get("width", 0))
    viewport_height = float(viewport.get("height", 0))
    coord = card.get("coord", [])
    if viewport_width <= 0 or viewport_height <= 0 or not isinstance(coord, list) or len(coord) != 4 or coord[3] <= 0:
        return {"available": False, "withinLearnedRange": None, "matchedRatio": 0.0, "checks": {}}
    values = {
        "widthRatio": coord[2] / viewport_width,
        "heightRatio": coord[3] / viewport_height,
        "aspectRatio": coord[2] / coord[3],
    }
    checks: dict[str, Any] = {}
    for field, value in values.items():
        distribution = profile.get("distributions", {}).get(field)
        if not distribution:
            continue
        observed_min = float(distribution["minimum"])
        observed_max = float(distribution["maximum"])
        span = max(observed_max - observed_min, abs(observed_max) * 0.10, 0.02 if field != "aspectRatio" else 0.20)
        lower = max(0.0, observed_min - span * 0.35)
        upper = observed_max + span * 0.35
        checks[field] = {
            "value": round(value, 4), "learnedRangeWithMargin": [round(lower, 4), round(upper, 4)],
            "matched": lower <= value <= upper,
        }
    matched_count = sum(bool(item["matched"]) for item in checks.values())
    matched_ratio = matched_count / len(checks) if checks else 0.0
    return {
        "available": bool(checks), "withinLearnedRange": bool(checks) and matched_count == len(checks),
        "matchedRatio": round(matched_ratio, 4), "checks": checks,
        "source": "approved_golden_aggregate_geometry",
    }


def extract_features(card: dict[str, Any], facts: dict[str, Any], structure_blocks: dict[str, dict[str, Any]]) -> dict[str, bool]:
    coord = card.get("coord", [0, 0, 0, 0])
    x, y, width, height = coord
    texts = [item for item in facts.get("candidates", {}).get("text", []) if _usable(item) and _overlap(item.get("coord", [0, 0, 0, 0]), coord)]
    photos = [item for item in facts.get("candidates", {}).get("photos", []) if _usable(item) and _overlap(item.get("coord", [0, 0, 0, 0]), coord)]
    joined = "\n".join(str(item.get("text", "")) for item in texts)
    title_like = []
    structured_only = re.compile(r"^(?:[¥￥]?\d[\d.]*|\d+(?:\.\d+)?(?:km|公里|分钟|条|分)|月售\d+|已售\d+)$", re.I)
    for item in texts:
        value = str(item.get("text", "")).strip()
        if item.get("coord", [0, 0, 0, 0])[1] <= y + max(100, height * 0.45) and len(_meaningful(value)) >= 2 and not structured_only.fullmatch(value):
            title_like.append(item)
    left_heads = [item for item in photos if item["coord"][0] < x + width * 0.42 and item["coord"][1] < y + height * 0.68]
    seed = structure_blocks.get(str(card.get("seedBlockId", "")))
    seed_bottom = seed["coord"][1] + seed["coord"][3] if seed else y + height * 0.45
    member_ids = card.get("memberBlockIds", [])
    attached_blocks = [structure_blocks[item_id] for item_id in member_ids if item_id in structure_blocks and structure_blocks[item_id]["coord"][1] >= seed_bottom]
    attached_text_blocks = [block for block in attached_blocks if block.get("layoutCandidate") == "text_only"]
    attached_texts = [item for item in texts if any(_overlap(item.get("coord", [0, 0, 0, 0]), block["coord"]) for block in attached_text_blocks)]
    attached_joined = "\n".join(str(item.get("text", "")) for item in attached_texts)
    service_pattern = r"预约|可约|取号|排队|服务|体验|门票|团购|套餐|美发|理发|剪发|洗护|清洗|保洁|家电|维修|按摩|体检|露营|漂流|游乐|剧本|医疗|问诊"
    attached_photos = [item for item in photos if item["coord"][1] >= seed_bottom and item["coord"][0] >= x + width * 0.18]
    graphic_hint = card.get("classificationHint", {}).get("cardType") == "商家卡片_图文下挂" or bool(card.get("attachedProductPhotoIds"))
    poster_media = any(item["coord"][3] >= item["coord"][2] * 1.18 and item["coord"][2] <= width * 0.45 for item in photos)
    price_signals = [price_evidence(item, coord) for item in texts]
    boundary_evidence = set(card.get("evidence", []))
    repeated_list_boundary = bool({"repeated_left_image_right_text_seed", "learned_repeat_interval_backfill"} & boundary_evidence)
    merchant_graphic_boundary = "left_square_merchant_head" in boundary_evidence and "right_side_attached_product_image_group" in boundary_evidence
    viewport_width = float(facts.get("viewport", {}).get("width", 0))
    features = {
        "stable_boundary": card.get("status", "confirmed") == "confirmed" and isinstance(coord, list) and len(coord) == 4 and width > 0 and height > 0,
        "has_visible_text": bool(texts),
        "has_media": bool(photos),
        "left_head_media": bool(left_heads),
        "title_like_text": bool(title_like),
        "price_exact_text": any(item["exact"] for item in price_signals),
        "price_context_text": any(item["contextual"] for item in price_signals),
        "price_visual_text": any(item["visual"] for item in price_signals),
        "price_text": any(any(item.values()) for item in price_signals),
        "product_spec_text": bool(re.search(r"\d+(?:\.\d+)?\s*(?:g|kg|ml|L|片|粒|瓶|盒|包|袋|支|个|罐|听)(?:\s*[xX*×]\s*\d+)?", joined, re.I)),
        "merchant_metrics": bool(re.search(r"(?:\d(?:\.\d)?\s*分|暂无评分|新店(?:入驻)?|\d+\s*条|人均)", joined, re.I)),
        "merchant_fulfillment": bool(re.search(r"到店|外卖|闪购|上门|配送|自取", joined)),
        "graphic_downhang": graphic_hint or bool(attached_photos),
        "text_downhang": bool(attached_text_blocks) and bool(re.search(service_pattern, attached_joined)),
        "service_language": bool(re.search(service_pattern, joined)),
        "hotel_identity": bool(re.search(r"酒店|民宿|住宿|经济型|舒适型|高档型|豪华型", joined)),
        "hotel_status_or_location": bool(re.search(r"满房|预订|房型|早餐|近地铁|距您|影音房|电竞房", joined)),
        "performance_identity": bool(re.search(r"演出|电影|影院|影城|剧场|场馆|票务", joined)),
        "performance_schedule": bool(re.search(r"近期场次|开售|抢票|\d{1,2}:\d{2}|\d{4}[-/.年]\d{1,2}", joined)),
        "poster_media": poster_media,
        "package_identity": bool(re.search(r"旅游|自由行|跟团游|酒店套餐|度假套餐", joined)),
        "package_summary": bool(re.search(r"\d+天|出发|住[:：]|景[:：]|享[:：]|吃[:：]|行[:：]|无购物|无自费|先囤后兑|过期自动退", joined)),
        "poi_identity": bool(re.search(r"地铁站|大学|商场|医院|景点|度假区|公立三甲", joined)),
        "poi_domain_detail": bool(re.search(r"路线|挂号|科室|医生|游客量|门票|行政区|地址|拍照点|游玩", joined)),
        "explicit_ad_marker": bool(re.search(r"(?:^|[^不])广告|推广", joined)),
        "result_list_position": True,
        "pre_results_position": False,
    }
    # A semantic identity is not itself a boundary.  These compound features
    # require the card candidate to carry the geometry/topology evidence for
    # that type's documented cutting strategy.
    features.update({
        "product_repeat_boundary": repeated_list_boundary and not graphic_hint,
        "merchant_graphic_boundary": merchant_graphic_boundary,
        "merchant_text_boundary": repeated_list_boundary and features["text_downhang"],
        "hotel_list_boundary": repeated_list_boundary and features["hotel_identity"],
        "hotel_grid_boundary": bool(viewport_width and width <= viewport_width * 0.68) and features["hotel_identity"],
        "performance_poster_boundary": poster_media and features["performance_identity"] and (repeated_list_boundary or bool(left_heads)),
        "movie_schedule_boundary": features["performance_schedule"] and features["performance_identity"] and repeated_list_boundary,
        "package_bundle_boundary": repeated_list_boundary and features["package_identity"] and features["package_summary"],
    })
    return features


def evaluate_contract(contract: dict[str, Any], features: dict[str, bool], candidate_score: float = 0.0,
                      geometry_validation: dict[str, Any] | None = None) -> dict[str, Any]:
    groups = contract.get("minimumEvidenceGroups", [])
    missing = [group for group in groups if not any(features.get(feature, False) for feature in group)]
    forbidden = [feature for feature in contract.get("forbiddenFeatures", []) if features.get(feature, False)]
    supporting = [feature for feature in contract.get("supportingFeatures", []) if features.get(feature, False)]
    hard_ratio = (len(groups) - len(missing)) / len(groups) if groups else 0.0
    support_total = len(contract.get("supportingFeatures", []))
    support_ratio = len(supporting) / support_total if support_total else 0.0
    # Learned geometry is deliberately a small tie-breaker. It cannot make a
    # failed minimum contract pass and never imposes a hard rejection.
    geometry_bonus = 0.02 * float((geometry_validation or {}).get("matchedRatio", 0.0))
    score = max(0.0, min(1.0, 0.70 * hard_ratio + 0.18 * support_ratio + 0.10 * candidate_score + geometry_bonus - 0.20 * len(forbidden)))
    return {
        "cardType": contract["cardType"],
        "minimumSatisfied": not missing and not forbidden,
        "score": round(score, 4),
        "matchedFeatures": sorted(feature for feature, matched in features.items() if matched),
        "supportingFeatures": supporting,
        "missingEvidenceGroups": missing,
        "forbiddenFeaturesHit": forbidden,
        "geometryValidation": geometry_validation or {"available": False, "withinLearnedRange": None, "matchedRatio": 0.0, "checks": {}},
    }


def resolve_card_type(card: dict[str, Any], facts: dict[str, Any], structure_blocks: dict[str, dict[str, Any]],
                      contracts_payload: dict[str, Any], classifier_candidates: list[dict[str, Any]],
                      geometry_profiles_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    features = extract_features(card, facts, structure_blocks)
    scores = {item.get("cardType"): float(item.get("confidence", 0)) for item in classifier_candidates}
    contracts = {item["cardType"]: item for item in contracts_payload["contracts"]}
    geometry_profiles = {item["cardType"]: item for item in (geometry_profiles_payload or {}).get("profiles", [])}
    evaluations = [
        evaluate_contract(
            contract, features, scores.get(card_type, 0.0),
            _geometry_validation(card, facts, geometry_profiles.get(card_type)),
        )
        for card_type, contract in contracts.items() if card_type in KNOWN_RESULT_TYPES
    ]
    passing = sorted((item for item in evaluations if item["minimumSatisfied"]), key=lambda item: item["score"], reverse=True)
    if passing:
        best = passing[0]
        runner = passing[1] if len(passing) > 1 else None
        separated = not runner or best["score"] - runner["score"] >= 0.08
        status = "confirmed" if separated else "uncertain"
        selected = {"cardType": best["cardType"], "confidence": best["score"], "status": status,
                    "classificationMode": "known_minimum_contract", "evidence": best["matchedFeatures"]}
        return {"selected": selected, "features": features, "contractValidation": best, "contractEvaluations": evaluations,
                "nearestKnownCardType": best["cardType"]}
    ad = evaluate_contract(contracts["广告卡"], features, scores.get("广告卡", 0.0))
    if ad["minimumSatisfied"]:
        selected = {"cardType": "广告卡", "confidence": ad["score"], "status": "confirmed", "classificationMode": "explicit_ad_contract", "evidence": ad["matchedFeatures"]}
        return {"selected": selected, "features": features, "contractValidation": ad, "contractEvaluations": evaluations + [ad], "nearestKnownCardType": ""}
    nearest = max(evaluations, key=lambda item: item["score"], default={"cardType": "", "score": 0.0})
    hetero = evaluate_contract(contracts["异构卡"], features, scores.get("异构卡", 0.0))
    status = "confirmed" if hetero["minimumSatisfied"] else "uncertain"
    selected = {"cardType": "异构卡", "confidence": hetero["score"], "status": status,
                "classificationMode": "heterogeneous_fallback", "evidence": hetero["matchedFeatures"]}
    return {"selected": selected, "features": features, "contractValidation": hetero, "contractEvaluations": evaluations + [ad, hetero],
            "nearestKnownCardType": nearest.get("cardType", "")}
