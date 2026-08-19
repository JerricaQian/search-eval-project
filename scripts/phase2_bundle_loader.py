#!/usr/bin/env python3
"""Load Phase2 facts for Phase3 without persisting an expanded projection."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / "phase2-card-annotation" / "scripts" / "compile_golden_phase3_manifest.py"
ATOMIC_VALIDATOR = ROOT / "phase2-card-annotation" / "scripts" / "validate_atomic_manifest_v3.py"

CARD_NAMES = {
    "merchant_text_append": "商家卡片-文字下挂",
    "merchant_graphic_append": "商家卡片-图文下挂",
    "merchant_product_card": "商品卡片",
    "product": "商品卡片",
    "hotel": "酒店卡片",
    "performance_movie": "演出/电影卡片",
    "primary_point": "主点卡片",
    "heterogeneous": "异构卡",
    "advertisement": "特殊广告卡",
}
SLOT_ROLES = {
    "title": "title", "subtitle": "subtitle", "price": "price", "original_price": "price",
    "price_and_sales": "price", "price_and_trade": "price", "sales": "sales", "monthly_sales": "sales",
    "rating": "rating", "location": "location", "distance": "location", "address": "location", "city": "location",
    "fulfillment": "fulfillment", "fulfillment_tag": "fulfillment", "delivery_time": "fulfillment",
    "promotion": "promotion", "promotion_tag": "promotion", "coupon_type_tag": "promotion",
    "coupon_value_tag": "promotion", "guarantee_tag": "guarantee",
    "merchant_tag": "merchant", "merchant_feature_tag": "merchant_feature",
    "product_attribute_tag": "product_attribute", "scenic_rating_tag": "scenic_rating",
    "gift_tag": "gift", "generic_tag": "tag", "other_tag": "tag",
}


@lru_cache(maxsize=1)
def _compiler() -> ModuleType:
    script_dir = str(COMPILER.parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    spec = importlib.util.spec_from_file_location("phase2_golden_bundle_compiler", COMPILER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Phase2 bundle compiler: {COMPILER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def _atomic_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("phase2_atomic_v3_validator", ATOMIC_VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load Phase2 atomic validator: {ATOMIC_VALIDATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _compat_element(element_id: str, source: dict[str, Any], card_id: str, slot: str) -> dict[str, Any]:
    kind = source.get("kind")
    visual_source = source.get("visual") if isinstance(source.get("visual"), dict) else {}
    visibility = source.get("visibility")
    naturally_cropped = visibility == "naturally_cropped"
    entity_kind = "image" if kind == "media" else kind
    visual = {
        "entityKind": entity_kind,
        "visualStatus": "confirmed",
        "backgroundColor": visual_source.get("backgroundColor", ""),
        "textColor": visual_source.get("textColor", ""),
        "borderColor": visual_source.get("borderColor", ""),
        "containerShape": visual_source.get("container", "none"),
        "graphicAssistRole": visual_source.get("graphicAssist", "无"),
    }
    render = {
        "visibleStatus": "confirmed",
        "renderState": "naturally_cropped" if naturally_cropped else (visibility or "normal"),
        "isPhoto": kind == "media" and source.get("mediaType") == "photo",
        "isSystemUi": kind != "media",
    }
    text = str(source.get("text", ""))
    output = {
        "id": element_id,
        "所属组件": card_id,
        "元素类型": "图片" if kind == "media" else ("标签" if kind in {"tag", "icon"} else "文本"),
        "内容简述": f"原文:{text}" if text else "原文:[图片]",
        "坐标": source["bounds"],
        "isExcluded": False,
        "excludeReason": "",
        "render": render,
        "visual": visual,
    }
    if kind != "media":
        semantic_role = SLOT_ROLES.get(slot, slot[:-4] if slot.endswith("_tag") else "other")
        output["textFacts"] = {
            "rawText": text,
            "textStatus": "naturally_ellipsized" if naturally_cropped else "complete",
            "semanticRole": semantic_role,
        }
    return output


def _atomic_to_phase3(payload: dict[str, Any]) -> dict[str, Any]:
    elements = payload["elementsById"]
    regions = payload["regionsById"]
    result_card_ids = {
        card_id
        for module in payload["modulesById"].values()
        if module.get("type") == "result_list"
        for card_id in module.get("cardIds", [])
    }
    cards = []
    for card_id, card in payload["cardsById"].items():
        converted_regions = []
        for region_id in card["regionIds"]:
            region = regions[region_id]
            converted = []
            if "slots" in region:
                for slot, element_ids in region["slots"].items():
                    converted.extend(_compat_element(element_id, elements[element_id], card_id, slot) for element_id in element_ids)
            else:
                for item in region.get("items", []):
                    for slot, element_ids in item["slots"].items():
                        converted.extend(_compat_element(element_id, elements[element_id], card_id, slot) for element_id in element_ids)
            converted_regions.append({"name": region["name"], "coord": region["bounds"], "elements": converted})
        region_signature = ">".join(region["name"] for region in converted_regions)
        card_type = str(card["cardType"])
        cards.append({
            "cardId": card_id,
            "卡片类型": CARD_NAMES.get(card_type, card_type),
            "cardTypeCode": card_type,
            "variant": card.get("variant", ""),
            "coord": card["bounds"],
            "regions": converted_regions,
            "structure": {
                "visibleStatus": card["visibility"],
                "isResultListItem": card_id in result_card_ids,
                "isHeterogeneous": card_type == "heterogeneous",
                "regions": [region["name"] for region in converted_regions],
                "layoutSignature": region_signature,
            },
        })
    page_modules = [
        {
            "id": module_id,
            "moduleType": module["type"],
            "coord": module.get("bounds"),
            "visibleStatus": module["visibility"],
            "contentRole": module["type"],
            "isListItem": False,
        }
        for module_id, module in payload["modulesById"].items()
    ]
    screenshot = Path(str(payload["source"]["screenshot"]))
    if not screenshot.is_absolute():
        screenshot = ROOT / screenshot
    return {
        "query": payload["source"]["query"],
        "screenshot": str(screenshot.resolve()),
        "cards": cards,
        "pageFacts": {"screen": 1, "isContinuation": False, "viewport": {"size": payload["source"]["viewport"]}, "modules": page_modules},
        "recognition": {"contractVersion": "phase2.atomic-manifest.v3.compat-view", "status": "confirmed", "phase3Ready": True},
        "relations": [],
    }


def load_phase2_facts(
    *,
    manifest_path: Path | None = None,
    normalized_path: Path | None = None,
    evidence_path: Path | None = None,
) -> dict[str, Any]:
    """Return the Phase3 fact view from either input format.

    Normalized golden bundles are verified against their evidence sidecar and
    projected only in memory. No ``elements_*.json`` file is created.
    """
    if normalized_path is not None:
        if manifest_path is not None:
            raise ValueError("manifest_path cannot be combined with normalized_path")
        if evidence_path is None:
            raise ValueError("evidence_path is required with normalized_path")
        normalized_path = normalized_path.resolve()
        evidence_path = evidence_path.resolve()
        normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        compiler = _compiler()
        errors = compiler.validate_normalized_bundle(normalized, evidence, evidence_path)
        if errors:
            raise ValueError("invalid normalized/evidence bundle: " + ",".join(errors))
        return compiler.compile_phase3(normalized)
    if evidence_path is not None:
        raise ValueError("evidence_path requires normalized_path")
    if manifest_path is None:
        raise ValueError("provide manifest_path or normalized_path with evidence_path")
    payload = json.loads(manifest_path.resolve().read_text(encoding="utf-8"))
    if payload.get("schemaVersion") == "phase2.atomic-manifest.v3":
        result = _atomic_validator().validate(payload)
        if not result["valid"]:
            raise ValueError("invalid atomic v3 manifest: " + ",".join(result["errors"]))
        if payload.get("publication", {}).get("status") != "ready":
            raise ValueError("atomic v3 manifest is not publication-ready")
        screenshot = Path(str(payload.get("source", {}).get("screenshot", "")))
        if not screenshot.is_absolute():
            screenshot = ROOT / screenshot
        if not screenshot.is_file():
            raise ValueError("atomic v3 source screenshot is missing")
        actual_hash = hashlib.sha256(screenshot.read_bytes()).hexdigest()
        if actual_hash != payload.get("source", {}).get("sha256"):
            raise ValueError("atomic v3 source screenshot sha256 mismatch")
        return _atomic_to_phase3(payload)
    return payload
