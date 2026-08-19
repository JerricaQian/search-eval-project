#!/usr/bin/env python3
"""Validate the draft Phase2 atomic manifest v3 and its no-redundancy rules."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TAXONOMY = ROOT / "phase2-card-annotation" / "references" / "search_card_taxonomy.v1.json"

MODULE_TYPES = {
    "search_bar", "page_tab", "location_filter", "sort_filter", "price_filter",
    "coupon_filter", "instant_filter", "promotion_filter", "image_filter",
    "primary_point", "primary_point_disambiguation", "heterogeneous_module", "live_card",
    "hotel_search_panel", "hotel_notice", "movie_primary_info", "date_filter",
    "business_operation_card", "floating_service", "result_list",
}
CARD_TAXONOMY_IDS = {
    "product": "商品卡片", "merchant_product_card": "商品卡片",
    "merchant_graphic_append": "商家卡片_图文下挂",
    "merchant_text_append": "商家卡片_文字下挂", "hotel": "酒店卡片",
    "performance_movie": "演出电影卡片", "primary_point": "主点卡片",
    "advertisement": "广告卡", "heterogeneous": "异构卡",
}
TITLE_AFFIX_SLOTS = {
    "fulfillment_tag", "merchant_tag", "product_attribute_tag", "gift_tag",
    "scenic_rating_tag", "hotel_class", "city", "delivery_time",
}
FORBIDDEN_KEYS = {
    "isPhoto", "isSystemUi", "role", "semanticRole", "sourceRegion", "ownerRegion",
    "ownerModule", "visibleText", "rawText", "content", "coord", "elementIdsByRole",
    "visualInventory", "factInventory", "styleKey", "countedInComplexity",
    "countDecision", "dedupDecision", "comparisonGroupKey", "layoutAnchors", "relations",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_taxonomy(path: Path = DEFAULT_TAXONOMY) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cards = {card["id"]: card for card in payload.get("cardTypes", [])}

    def region(card_id: str, region_id: str) -> dict[str, Any]:
        return next(item for item in cards[card_id]["regions"] if item["id"] == region_id)

    product = cards["商品卡片"]
    product_head = region("商品卡片", "head_image")["elementDefinitions"]
    product_merchant = region("商品卡片", "merchant")["elementDefinitions"]
    graphic_goods = region("商家卡片_图文下挂", "attached_goods")["elementDefinitions"]
    scenic_title = region("商家卡片_文字下挂", "title")["elementDefinitions"]
    hotel_title = region("酒店卡片", "title")["elementDefinitions"]
    attributes = set(product_head["rightTopDiamondAttribute"]["values"])
    attributes.update(graphic_goods["productLabel"]["diamondAttribute"])
    return {
        "path": path,
        "sha256": sha256(path),
        "contractVersion": payload["contractVersion"],
        "cardIds": set(cards),
        "fulfillment": set(payload["commonElementVocabulary"]["fulfillment"]),
        "merchant": set(product_merchant["merchantTag"]["values"]),
        "productAttribute": attributes,
        "scenicRating": set(scenic_title["scenicRating"]),
        "hotelClass": set(hotel_title["hotelRating"]),
    }


DEFAULT_ENUMS = load_taxonomy()
FULFILLMENT_TAG_VALUES = DEFAULT_ENUMS["fulfillment"]
MERCHANT_TAG_VALUES = DEFAULT_ENUMS["merchant"]


def walk(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield path, key
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}[{index}]")


def is_bounds(value: Any, viewport: list[int]) -> bool:
    if not isinstance(value, list) or len(value) != 4 or not all(isinstance(item, int) for item in value):
        return False
    x, y, width, height = value
    return x >= 0 and y >= 0 and width > 0 and height > 0 and x + width <= viewport[0] and y + height <= viewport[1]


def add_refs(counter: Counter[str], values: Any, errors: list[str], prefix: str) -> None:
    if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
        errors.append(f"{prefix}:id_array_invalid")
        return
    if len(values) != len(set(values)):
        errors.append(f"{prefix}:duplicate_ids")
    counter.update(values)


def validate(payload: dict[str, Any], taxonomy_path: Path = DEFAULT_TAXONOMY) -> dict[str, Any]:
    errors: list[str] = []
    try:
        taxonomy = load_taxonomy(taxonomy_path)
    except (OSError, KeyError, StopIteration, json.JSONDecodeError) as exc:
        taxonomy = DEFAULT_ENUMS
        errors.append(f"taxonomy_file_invalid:{exc}")
    if payload.get("schemaVersion") != "phase2.atomic-manifest.v3":
        errors.append("schema_version_invalid")
    taxonomy_ref = payload.get("taxonomy") if isinstance(payload.get("taxonomy"), dict) else {}
    if taxonomy_ref.get("contractVersion") != taxonomy["contractVersion"]:
        errors.append("taxonomy.contract_version_mismatch")
    if taxonomy_ref.get("sha256") != taxonomy["sha256"]:
        errors.append("taxonomy.sha256_mismatch")
    if not isinstance(taxonomy_ref.get("file"), str) or not taxonomy_ref.get("file"):
        errors.append("taxonomy.file_missing")
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    viewport = source.get("viewport")
    if not isinstance(viewport, list) or len(viewport) != 2 or not all(isinstance(item, int) and item > 0 for item in viewport):
        errors.append("source.viewport_invalid")
        viewport = [1, 1]

    for path, key in walk(payload):
        if key in FORBIDDEN_KEYS:
            errors.append(f"{path}.{key}:forbidden_redundant_or_phase3_field")

    page = payload.get("page") if isinstance(payload.get("page"), dict) else {}
    modules = payload.get("modulesById") if isinstance(payload.get("modulesById"), dict) else {}
    cards = payload.get("cardsById") if isinstance(payload.get("cardsById"), dict) else {}
    regions = payload.get("regionsById") if isinstance(payload.get("regionsById"), dict) else {}
    filter_items = payload.get("filterItemsById") if isinstance(payload.get("filterItemsById"), dict) else {}
    elements = payload.get("elementsById") if isinstance(payload.get("elementsById"), dict) else {}

    module_order = page.get("moduleIds")
    module_refs: Counter[str] = Counter()
    add_refs(module_refs, module_order, errors, "page.moduleIds")
    if set(module_refs) != set(modules):
        errors.append("page.moduleIds_must_reference_every_module_once")

    card_refs: Counter[str] = Counter()
    filter_item_refs: Counter[str] = Counter()
    element_refs: Counter[str] = Counter()
    for module_id, module in modules.items():
        prefix = f"modulesById.{module_id}"
        if not isinstance(module, dict):
            errors.append(f"{prefix}:module_invalid")
            continue
        module_type = module.get("type")
        if module_type not in MODULE_TYPES:
            errors.append(f"{prefix}:module_type_invalid")
        if "bounds" in module and not is_bounds(module["bounds"], viewport):
            errors.append(f"{prefix}.bounds:invalid")
        if isinstance(module.get("slots"), dict):
            for role, ids in module["slots"].items():
                add_refs(element_refs, ids, errors, f"{prefix}.slots.{role}")
        if "cardIds" in module:
            add_refs(card_refs, module.get("cardIds"), errors, f"{prefix}.cardIds")
        if module_type == "image_filter":
            variant = module.get("variant")
            if variant == "with_tabs":
                if "itemIds" in module:
                    errors.append(f"{prefix}:with_tabs_must_reference_items_through_panels")
                panels = module.get("panels")
                tabs = module.get("tabs")
                if not isinstance(panels, list) or not isinstance(tabs, list) or not panels or not tabs:
                    errors.append(f"{prefix}:with_tabs_requires_tabs_and_panels")
                    continue
                panel_ids = {panel.get("id") for panel in panels if isinstance(panel, dict)}
                if len(panel_ids) != len(panels) or None in panel_ids:
                    errors.append(f"{prefix}:panel_ids_invalid")
                selected = 0
                for tab in tabs:
                    if not isinstance(tab, dict) or tab.get("panelId") not in panel_ids:
                        errors.append(f"{prefix}:tab_panel_reference_invalid")
                    elif tab.get("selected") is True:
                        selected += 1
                    if isinstance(tab, dict) and not is_bounds(tab.get("bounds"), viewport):
                        errors.append(f"{prefix}:tab_bounds_invalid")
                if selected != 1:
                    errors.append(f"{prefix}:exactly_one_tab_must_be_selected")
                for panel in panels:
                    if isinstance(panel, dict):
                        add_refs(filter_item_refs, panel.get("itemIds"), errors, f"{prefix}.panels.{panel.get('id')}")
            elif variant in {"without_tabs", "business"}:
                if "tabs" in module or "panels" in module:
                    errors.append(f"{prefix}:{variant}_must_not_define_tabs_or_panels")
                add_refs(filter_item_refs, module.get("itemIds"), errors, f"{prefix}.itemIds")
            else:
                errors.append(f"{prefix}:image_filter_variant_invalid")
        elif module_type == "result_list" and "cardIds" not in module:
            errors.append(f"{prefix}:result_list_requires_cardIds")

    if set(filter_item_refs) != set(filter_items) or any(count != 1 for count in filter_item_refs.values()):
        errors.append("filter_items_must_be_owned_exactly_once")
    if set(card_refs) != set(cards) or any(count != 1 for count in card_refs.values()):
        errors.append("cards_must_be_owned_exactly_once")

    for item_id, item in filter_items.items():
        prefix = f"filterItemsById.{item_id}"
        if not isinstance(item, dict) or not is_bounds(item.get("bounds"), viewport):
            errors.append(f"{prefix}:invalid")
            continue
        slots = item.get("slots")
        if not isinstance(slots, dict) or not slots:
            errors.append(f"{prefix}.slots:invalid")
            continue
        for role, ids in slots.items():
            add_refs(element_refs, ids, errors, f"{prefix}.slots.{role}")

    region_refs: Counter[str] = Counter()
    for card_id, card in cards.items():
        prefix = f"cardsById.{card_id}"
        if not isinstance(card, dict) or not is_bounds(card.get("bounds"), viewport):
            errors.append(f"{prefix}:invalid")
            continue
        taxonomy_card_id = CARD_TAXONOMY_IDS.get(card.get("cardType"))
        if taxonomy_card_id not in taxonomy["cardIds"]:
            errors.append(f"{prefix}:card_type_not_in_taxonomy")
        add_refs(region_refs, card.get("regionIds"), errors, f"{prefix}.regionIds")
    if set(region_refs) != set(regions) or any(count != 1 for count in region_refs.values()):
        errors.append("regions_must_be_owned_exactly_once")

    for region_id, region in regions.items():
        prefix = f"regionsById.{region_id}"
        if not isinstance(region, dict) or not is_bounds(region.get("bounds"), viewport):
            errors.append(f"{prefix}:invalid")
            continue
        has_slots = "slots" in region
        has_items = "items" in region
        if has_slots == has_items:
            errors.append(f"{prefix}:use_exactly_one_of_slots_or_items")
            continue
        if has_slots:
            slots = region.get("slots")
            if not isinstance(slots, dict) or not slots:
                errors.append(f"{prefix}.slots:invalid")
                continue
            for role, ids in slots.items():
                add_refs(element_refs, ids, errors, f"{prefix}.slots.{role}")
                if region.get("name") == "title":
                    for element_id in ids if isinstance(ids, list) else []:
                        element = elements.get(element_id, {})
                        if element.get("kind") == "tag" and role not in TITLE_AFFIX_SLOTS:
                            errors.append(f"{prefix}.slots.{role}:{element_id}:title_tag_slot_invalid")
        else:
            items = region.get("items")
            if not isinstance(items, list) or not items:
                errors.append(f"{prefix}.items:invalid")
                continue
            for index, item in enumerate(items):
                item_prefix = f"{prefix}.items[{index}]"
                if not isinstance(item, dict) or item.get("index") != index or not is_bounds(item.get("bounds"), viewport):
                    errors.append(f"{item_prefix}:invalid")
                    continue
                slots = item.get("slots")
                if not isinstance(slots, dict) or not slots:
                    errors.append(f"{item_prefix}.slots:invalid")
                    continue
                for role, ids in slots.items():
                    add_refs(element_refs, ids, errors, f"{item_prefix}.slots.{role}")

    if set(element_refs) != set(elements) or any(count != 1 for count in element_refs.values()):
        errors.append("elements_must_be_owned_exactly_once")
    for element_id, element in elements.items():
        prefix = f"elementsById.{element_id}"
        if not isinstance(element, dict) or not is_bounds(element.get("bounds"), viewport):
            errors.append(f"{prefix}:invalid")
            continue
        kind = element.get("kind")
        if kind == "media":
            if element.get("mediaType") not in {"photo", "illustration", "logo", "poster", "video_frame", "product_render", "unknown"}:
                errors.append(f"{prefix}:mediaType_required")
            if "text" in element:
                errors.append(f"{prefix}:media_must_not_repeat_text")
        else:
            if "mediaType" in element:
                errors.append(f"{prefix}:non_media_must_not_have_mediaType")
            if kind in {"text", "tag"} and not isinstance(element.get("text"), str):
                errors.append(f"{prefix}:text_required")

    enum_slots = {
        "fulfillment_tag": taxonomy["fulfillment"],
        "merchant_tag": taxonomy["merchant"],
        "product_attribute_tag": taxonomy["productAttribute"],
        "scenic_rating_tag": taxonomy["scenicRating"],
        "hotel_class_tag": taxonomy["hotelClass"],
    }

    def validate_slots(owner: dict[str, Any], prefix: str) -> None:
        for role, ids in owner.get("slots", {}).items():
            for element_id in ids if isinstance(ids, list) else []:
                element = elements.get(element_id, {})
                kind = element.get("kind")
                if kind == "tag" and not role.endswith("_tag"):
                    errors.append(f"{prefix}.slots.{role}:{element_id}:tag_slot_suffix_required")
                if role.endswith("_tag") and kind != "tag":
                    errors.append(f"{prefix}.slots.{role}:{element_id}:tag_slot_requires_tag_kind")
                if role in enum_slots and element.get("text") not in enum_slots[role]:
                    errors.append(f"{prefix}.slots.{role}:{element_id}:{role}_enum_invalid")

    for module_id, module in modules.items():
        if isinstance(module, dict):
            validate_slots(module, f"modulesById.{module_id}")
    for item_id, item in filter_items.items():
        if isinstance(item, dict):
            validate_slots(item, f"filterItemsById.{item_id}")
    for region_id, region in regions.items():
        if not isinstance(region, dict):
            continue
        if "slots" in region:
            validate_slots(region, f"regionsById.{region_id}")
        for index, item in enumerate(region.get("items", [])):
            if isinstance(item, dict):
                validate_slots(item, f"regionsById.{region_id}.items[{index}]")

    publication = payload.get("publication") if isinstance(payload.get("publication"), dict) else {}
    blockers = publication.get("blockers")
    if publication.get("status") == "ready" and blockers != []:
        errors.append("ready_publication_must_have_no_blockers")
    if publication.get("status") == "blocked" and (not isinstance(blockers, list) or not blockers):
        errors.append("blocked_publication_requires_blockers")

    return {
        "valid": not errors,
        "schemaVersion": payload.get("schemaVersion"),
        "moduleCount": len(module_order) if isinstance(module_order, list) else 0,
        "moduleTypeCounts": dict(sorted(Counter(module.get("type") for module in modules.values() if isinstance(module, dict)).items())),
        "cardCount": len(cards),
        "elementCount": len(elements),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate phase2.atomic-manifest.v3")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    args = parser.parse_args()
    payload = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = validate(payload, args.taxonomy.resolve())
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.audit:
        args.audit.parent.mkdir(parents=True, exist_ok=True)
        args.audit.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
