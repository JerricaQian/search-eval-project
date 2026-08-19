#!/usr/bin/env python3
"""Build 34 Phase2 atomic-manifest.v3 files from pixel-verified goldens.

The legacy/corrected JSON is used only for structural vocabulary. Coordinates
come exclusively from the curated golden element/card boxes and their bounded
CV/OCR evidence. Missing module-only boxes stay absent; this builder never
estimates coordinates from a scale factor or an evenly divided layout.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from PIL import Image

from compile_golden_phase3_manifest import normalize_element, normalize_golden, union
from validate_atomic_manifest_v3 import DEFAULT_TAXONOMY, load_taxonomy, validate


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "phase2-card-annotation" / "golden-sample-results"
DEFAULT_OUTPUT = ROOT / "phase2-card-annotation" / "golden-atomic-v3"
TITLE_AFFIX_REVIEWS = ROOT / "phase2-card-annotation" / "references" / "golden_title_affix_reviews.v1.json"
TAXONOMY_ENUMS = load_taxonomy(DEFAULT_TAXONOMY)

MODULE_TYPES = {
    "tab": "page_tab",
    "results_list": "result_list",
    "business_image_filter": "image_filter",
    "heterogeneous_live_card": "heterogeneous_module",
    "primary_point_card": "primary_point",
}
CARD_TYPES = {
    "商家卡片_文字下挂": "merchant_text_append",
    "商家卡片_图文下挂": "merchant_graphic_append",
    "商品卡片": "merchant_product_card",
    "酒店卡片": "hotel",
    "演出电影卡片": "performance_movie",
    "主点卡片": "primary_point",
    "异构卡": "heterogeneous",
    "广告卡": "advertisement",
}
REGION_NAMES = {
    "头图区": "head_media",
    "头图区（演出）": "head_media",
    "标题区": "title",
    "副标题区": "subtitle",
    "基础信息区": "base_info",
    "商家信息区": "merchant_info",
    "标签区": "tags",
    "价格区": "price",
    "文字下挂区": "text_append",
    "下挂商品区": "append_items",
    "下挂区": "append_items",
    "服务下挂": "service_append",
    "位置信息": "location",
    "评分与推荐理由": "rating_and_reason",
    "演出信息区": "performance_info",
    "推荐词区": "recommendation",
    "AI推荐理由": "recommendation",
}
ELEMENT_SLOTS = {
    "商品主图": "media", "商家头图": "media", "酒店头图": "media", "演出海报": "media",
    "异构下挂图片": "media", "下挂商品图片": "media",
    "商品标题": "title", "商家标题": "title", "酒店标题": "title", "酒店名称": "title",
    "演出标题": "title", "电影标题": "title", "下挂商品名": "title",
    "履约标签": "fulfillment_tag", "履约标识": "fulfillment_tag", "酒店/民宿履约标识": "fulfillment_tag",
    "商品价格": "price", "下挂商品价格": "price", "下挂商品原价": "original_price",
    "起价": "price", "价格区间": "price", "价格与交易信息": "price_and_trade",
    "下挂商品销量": "sales", "商品销量": "sales", "评价条数": "review_count",
    "评分": "rating", "距离": "distance", "配送时长": "delivery_time", "地址": "address",
    "城市": "city", "位置信息": "location", "推荐理由": "recommendation", "推荐词": "recommendation",
    "神券": "coupon_type_tag", "满减券": "coupon_value_tag", "立减券": "coupon_value_tag", "保障标签": "guarantee_tag",
    "下挂价格折扣标签": "promotion_tag", "酒店标签": "generic_tag", "商家标签": "merchant_feature_tag",
    "近期场次": "schedule", "演出日期": "date", "演出场馆": "venue",
    "入住人数": "guest_count", "酒店等级": "hotel_class", "景点等级": "scenic_rating_tag", "房间面积": "room_area",
    "床型": "bed_type", "窗型": "window_type", "户型": "room_type", "人均消费": "average_spend",
    "商家品类": "category", "商品属性": "attribute", "优惠信息": "promotion_tag",
    "下挂文字横幅": "banner",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def atomic_leaves(value: Any) -> Iterable[dict[str, Any]]:
    """Yield leaf visual entities, excluding legacy composite wrappers."""
    if isinstance(value, dict):
        descendants: list[dict[str, Any]] = []
        for key, child in value.items():
            if key in {"render", "visual", "textFacts", "boundedEvidence", "elementContract"}:
                continue
            descendants.extend(atomic_leaves(child))
        if "elementType" in value and not descendants:
            yield value
        else:
            yield from descendants
    elif isinstance(value, list):
        for child in value:
            yield from atomic_leaves(child)


def clean_color(value: Any) -> str | None:
    value = str(value or "").strip()
    return value if value else None


def atomic_element(source: dict[str, Any]) -> dict[str, Any]:
    visual = source.get("visual", {})
    render = source.get("render", {})
    entity = visual.get("entityKind", "text")
    kind = "media" if entity == "image" else (entity if entity in {"text", "tag", "icon"} else "text")
    output: dict[str, Any] = {"kind": kind, "bounds": list(source["coord"])}
    text = str(source.get("visibleText", ""))
    if kind in {"text", "tag"}:
        output["text"] = text
    if kind == "media":
        output["mediaType"] = "photo" if render.get("isPhoto") else "illustration"
    status = source.get("status")
    render_state = render.get("renderState")
    if status == "naturally_cropped" or render_state == "naturally_cropped":
        output["visibility"] = "naturally_cropped"
    elif render_state in {"load_failed", "garbled", "abnormal_clipped"}:
        output["visibility"] = render_state
    if "原价" in str(source.get("elementType", "")):
        output["textDecoration"] = "line_through"

    style: dict[str, Any] = {}
    shaped = bool(visual.get("isShaped"))
    background = clean_color(visual.get("backgroundColor"))
    border = clean_color(visual.get("borderColor"))
    if shaped:
        style["container"] = "outlined" if border and background in {None, "#FFFFFF", "#ffffff"} else "filled"
    elif kind == "tag":
        style["container"] = "none"
    for source_key, target_key in (("backgroundColor", "backgroundColor"), ("textColor", "textColor"), ("borderColor", "borderColor")):
        color = clean_color(visual.get(source_key))
        if color:
            style[target_key] = color
    graphic = str(visual.get("graphicAssistRole") or visual.get("graphicType") or "").strip()
    if graphic and graphic != "无":
        style["graphicAssist"] = graphic
    if style:
        output["visual"] = style
    return output


def normalized_atomic_element(source: dict[str, Any]) -> dict[str, Any]:
    legacy = {
        "elementType": source.get("elementType", ""), "visibleText": source.get("visibleText", ""),
        "coord": source.get("coord", []), "status": source.get("status", "confirmed"),
        "render": source.get("render", {}), "visual": source.get("visual", {}),
    }
    return atomic_element(legacy)


def slot_for(source: dict[str, Any]) -> str:
    element_type = str(source.get("elementType", ""))
    text = str(source.get("visibleText", ""))
    entity = source.get("visual", {}).get("entityKind")
    is_independent_tag = entity == "tag" or "标签" in element_type or "标识" in element_type
    if is_independent_tag and text in TAXONOMY_ENUMS["productAttribute"]:
        return "product_attribute_tag"
    if is_independent_tag and text in TAXONOMY_ENUMS["fulfillment"]:
        return "fulfillment_tag"
    if is_independent_tag and text in TAXONOMY_ENUMS["merchant"]:
        return "merchant_tag"
    if element_type in ELEMENT_SLOTS:
        return ELEMENT_SLOTS[element_type]
    role = str(source.get("textFacts", {}).get("semanticRole") or "")
    if role and role != "other":
        return role
    compact = re.sub(r"\s+", "", text)
    if re.search(r"神券|减\d|坏必赔|优惠券|立减|满减", compact):
        return "promotion_tag" if entity == "tag" else "promotion"
    if re.search(r"品牌|店[）)]?$", compact):
        return "merchant"
    if re.search(r"分钟|km|KM|公里|起送|配送|到店|免配送", compact):
        return "fulfillment"
    if re.search(r"月售|已售|人想买", compact) and re.search(r"[¥￥]|价格|价", compact):
        return "price_and_sales"
    if re.search(r"月售|已售|人想买", compact):
        return "sales"
    if re.search(r"[¥￥]|价格|到手价|会员价|神价|冰爽价", compact):
        return "price"
    return re.sub(r"[^a-z0-9]+", "_", element_type.lower()).strip("_") or "other"


TAG_SLOT_RENAMES = {
    "other": "other_tag", "tag": "generic_tag", "promotion": "promotion_tag",
    "guarantee": "guarantee_tag", "coupon_type": "coupon_type_tag",
    "coupon_value": "coupon_value_tag", "price_explanation": "price_explanation_tag",
    "gift": "gift_tag", "ad_label": "ad_tag", "label": "label_tag",
}


def atomic_slot_and_element(source: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    slot = slot_for(source)
    element = normalized_atomic_element(source)
    if slot.endswith("_tag") and element["kind"] == "text":
        element["kind"] = "tag"
        element.setdefault("visual", {}).setdefault("container", "none")
    if element["kind"] == "tag" and not slot.endswith("_tag"):
        slot = TAG_SLOT_RENAMES.get(slot, f"{slot}_tag")
    return slot, element


def add_slot(slots: dict[str, list[str]], name: str, element_id: str) -> None:
    slots.setdefault(name, []).append(element_id)


def product_region_group(slot: str) -> str:
    if slot in {"price", "sales", "price_and_sales", "original_price", "price_and_trade", "price_explanation_tag"}:
        return "price"
    if slot in {"promotion", "promotion_tag", "coupon_type", "coupon_type_tag", "coupon_value", "coupon_value_tag", "guarantee", "guarantee_tag"}:
        return "promotion_and_guarantee"
    if slot in {"merchant", "merchant_tag", "merchant_feature_tag"}:
        return "merchant"
    if slot in {"fulfillment", "delivery_time", "distance", "location"}:
        return "fulfillment"
    return "base_info"


def build_card_regions(card: dict[str, Any], normalized_elements: dict[str, Any], output_elements: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    card_id = card["cardId"]
    groups: list[tuple[str, list[str], list[dict[str, Any]] | None]] = []
    product_attribute_ids = {
        element_id
        for source_region in card["regions"] if source_region["name"] == "标题区"
        for element_id in source_region["elementIds"]
        if card["sourceCardType"] == "商品卡片" and slot_for(normalized_elements[element_id]) == "product_attribute_tag"
    }
    for source_region in card["regions"]:
        name = REGION_NAMES.get(source_region["name"], source_region["name"])
        source_element_ids = [element_id for element_id in source_region["elementIds"] if element_id not in product_attribute_ids]
        if name == "head_media":
            source_element_ids.extend(sorted(product_attribute_ids))
        if "itemGroups" in source_region:
            groups.append((name, source_element_ids, source_region["itemGroups"]))
            continue
        if card["sourceCardType"] == "商品卡片" and name == "base_info":
            split: dict[str, list[str]] = defaultdict(list)
            for element_id in source_element_ids:
                slot, _ = atomic_slot_and_element(normalized_elements[element_id])
                split[product_region_group(slot)].append(element_id)
            for group_name in ("price", "promotion_and_guarantee", "merchant", "fulfillment", "base_info"):
                if split[group_name]:
                    groups.append((group_name, split[group_name], None))
        else:
            if source_element_ids:
                groups.append((name, source_element_ids, None))

    region_ids: list[str] = []
    regions: dict[str, Any] = {}
    for index, (name, element_ids, item_groups) in enumerate(groups, 1):
        region_id = f"{card_id}-R{index:02d}"
        region_ids.append(region_id)
        for element_id in element_ids:
            _, output_elements[element_id] = atomic_slot_and_element(normalized_elements[element_id])
        bounds = union([normalized_elements[element_id]["coord"] for element_id in element_ids])
        if item_groups is None:
            slots: dict[str, list[str]] = {}
            for element_id in element_ids:
                slot, _ = atomic_slot_and_element(normalized_elements[element_id])
                add_slot(slots, slot, element_id)
            regions[region_id] = {"name": name, "bounds": bounds, "slots": slots}
        else:
            items = []
            for item_index, group in enumerate(item_groups):
                item_slots: dict[str, list[str]] = {}
                for element_id in group["elementIds"]:
                    slot, _ = atomic_slot_and_element(normalized_elements[element_id])
                    add_slot(item_slots, slot, element_id)
                visible = group.get("visibleStatus")
                items.append({
                    "index": item_index,
                    "bounds": group["coord"],
                    "visibility": "naturally_cropped" if visible == "naturally_cropped" else "complete",
                    "slots": item_slots,
                })
            regions[region_id] = {"name": name, "bounds": bounds, "items": items}
    return region_ids, regions


def source_module_bounds(component: dict[str, Any], leaves: list[dict[str, Any]], fallback: Any) -> list[int] | None:
    if isinstance(component.get("coord"), list) and len(component["coord"]) == 4:
        return list(component["coord"])
    if leaves:
        return union([leaf["coord"] for leaf in leaves])
    return list(fallback) if isinstance(fallback, list) and len(fallback) == 4 else None


def build_image_filter(module_id: str, component: dict[str, Any], module: dict[str, Any], elements: dict[str, Any], filter_items: dict[str, Any]) -> None:
    tabs = [item for item in component.get("elements", []) if item.get("elementType") == "图筛Tab"]
    wrappers = [item for item in component.get("elements", []) if item.get("elementType") == "图筛项"]
    variant = "with_tabs" if tabs else ("business" if component.get("componentType") == "business_image_filter" else "without_tabs")
    module["variant"] = variant
    item_ids: list[str] = []
    for item_index, wrapper in enumerate(wrappers, 1):
        item_id = f"{module_id}-I{item_index}"
        item_ids.append(item_id)
        slots: dict[str, list[str]] = {}
        leaves = list(atomic_leaves(wrapper))
        for leaf_index, leaf in enumerate(leaves, 1):
            element_id = f"{item_id}-E{leaf_index}"
            elements[element_id] = atomic_element(leaf)
            role = "media" if elements[element_id]["kind"] == "media" else ("label_tag" if elements[element_id]["kind"] == "tag" else "label")
            add_slot(slots, role, element_id)
        filter_items[item_id] = {"bounds": list(wrapper["coord"]), "slots": slots}
    if variant == "with_tabs":
        panel_ids = [f"{module_id}-P{index}" for index in range(1, len(tabs) + 1)]
        selected_index = next((index for index, tab in enumerate(tabs) if tab.get("selected")), 0)
        module["tabs"] = [{
            "id": f"{module_id}-T{index + 1}", "text": str(tab.get("visibleText", "")),
            "selected": index == selected_index, "panelId": panel_ids[index], "bounds": list(tab["coord"]),
        } for index, tab in enumerate(tabs)]
        module["panels"] = [{"id": panel_id, "itemIds": item_ids if index == selected_index else []} for index, panel_id in enumerate(panel_ids)]
    else:
        module["itemIds"] = item_ids


def title_affix_audit(manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    elements = manifest["elementsById"]
    regions = manifest["regionsById"]
    allowed_slots = {"fulfillment_tag", "merchant_tag", "product_attribute_tag", "scenic_rating_tag", "gift_tag", "hotel_class", "city", "delivery_time"}
    for card_id, card in manifest["cardsById"].items():
        for region_id in card["regionIds"]:
            region = regions[region_id]
            if region["name"] != "title" or "slots" not in region:
                continue
            title_boxes = [elements[element_id]["bounds"] for element_id in region["slots"].get("title", [])]
            title_left = min((box[0] for box in title_boxes), default=None)
            title_right = max((box[0] + box[2] for box in title_boxes), default=None)
            for slot, element_ids in region["slots"].items():
                for element_id in element_ids:
                    element = elements[element_id]
                    if element["kind"] == "tag" and slot not in allowed_slots:
                        errors.append(f"{card_id}:{element_id}:unclassified_title_tag:{slot}")
                    if slot == "fulfillment_tag" and element.get("text") not in TAXONOMY_ENUMS["fulfillment"]:
                        errors.append(f"{card_id}:{element_id}:unknown_fulfillment_tag:{element.get('text')}")
                    if slot == "merchant_tag" and element.get("text") not in TAXONOMY_ENUMS["merchant"]:
                        errors.append(f"{card_id}:{element_id}:unknown_merchant_tag:{element.get('text')}")
                    if slot not in allowed_slots:
                        continue
                    x, _, width, _ = element["bounds"]
                    if title_left is None:
                        position = "title_not_visible"
                    elif x + width <= title_left:
                        position = "before_title"
                    elif x >= title_right:
                        position = "after_title"
                    else:
                        position = "inline_or_overlapping_title_box"
                    records.append({"cardId": card_id, "regionId": region_id, "elementId": element_id, "slot": slot, "text": element.get("text", ""), "position": position})
    return records, errors


def build_one(source: Path, source_root: Path = DEFAULT_SOURCE) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    normalized, _ = normalize_golden(payload, source.resolve())
    review_payload = json.loads(TITLE_AFFIX_REVIEWS.read_text(encoding="utf-8"))
    relative_golden = str(source.relative_to(source_root))
    for review in review_payload["reviews"]:
        if review["golden"] != relative_golden:
            continue
        card = next(card for card in normalized["cards"] if card["cardId"] == review["cardId"])
        title_region = next(region for region in card["regions"] if region["name"] == "标题区")
        element_id = next(
            element_id for element_id in title_region["elementIds"]
            if normalized["elementsById"][element_id].get("visibleText") == review["legacyText"]
        )
        title = normalized["elementsById"][element_id]
        title["visibleText"] = review["title"]["text"]
        title["coord"] = review["title"]["bounds"]
        suffix_id = f"{element_id}-A1"
        suffix = copy.deepcopy(title)
        suffix["elementType"] = "景点等级"
        suffix["visibleText"] = review["suffix"]["text"]
        suffix["coord"] = review["suffix"]["bounds"]
        suffix.setdefault("textFacts", {})["semanticRole"] = "other"
        normalized["elementsById"][suffix_id] = suffix
        title_region["elementIds"].insert(title_region["elementIds"].index(element_id) + 1, suffix_id)
    screenshot = Path(normalized["screenshot"])
    with Image.open(screenshot) as image:
        width, height = image.size
    modules: dict[str, Any] = {}
    cards: dict[str, Any] = {}
    regions: dict[str, Any] = {}
    filter_items: dict[str, Any] = {}
    elements: dict[str, Any] = {}

    for card in normalized["cards"]:
        region_ids, card_regions = build_card_regions(card, normalized["elementsById"], elements)
        regions.update(card_regions)
        card_type = CARD_TYPES.get(card["sourceCardType"], "heterogeneous")
        variant = card.get("variant") or ("delivery" if card_type == "merchant_product_card" else "standard")
        cards[card["cardId"]] = {
            "cardType": card_type, "variant": variant, "bounds": card["coord"],
            "visibility": "naturally_cropped" if card["visibleStatus"] == "naturally_cropped" else "complete",
            "regionIds": region_ids,
        }

    normalized_modules = normalized["pageModules"]
    for index, component in enumerate(payload["pageStructure"]["components"], 1):
        module_id = f"M{index}"
        source_type = str(component.get("componentType", ""))
        module_type = MODULE_TYPES.get(source_type, source_type)
        if module_type not in {
            "search_bar", "page_tab", "sort_filter", "promotion_filter", "image_filter", "primary_point",
            "primary_point_disambiguation", "heterogeneous_module", "live_card", "hotel_search_panel", "hotel_notice",
            "movie_primary_info", "date_filter", "business_operation_card", "floating_service", "result_list",
        }:
            module_type = "heterogeneous_module"
        leaves = list(atomic_leaves(component.get("elements", [])))
        fallback = normalized_modules[index - 1].get("coord") if index - 1 < len(normalized_modules) else None
        module: dict[str, Any] = {"type": module_type, "visibility": "confirmed" if component.get("status") == "confirmed" else "uncertain"}
        bounds = source_module_bounds(component, leaves, fallback)
        if bounds:
            module["bounds"] = bounds
        if module_type == "result_list":
            module["cardIds"] = [card["cardId"] for card in normalized["cards"]]
        elif module_type == "image_filter":
            build_image_filter(module_id, component, module, elements, filter_items)
        elif leaves:
            slots: dict[str, list[str]] = {}
            for leaf_index, leaf in enumerate(leaves, 1):
                element_id = f"{module_id}-E{leaf_index:03d}"
                normalized_leaf, _ = normalize_element(leaf)
                slot, elements[element_id] = atomic_slot_and_element(normalized_leaf)
                add_slot(slots, slot, element_id)
            module["slots"] = slots
        modules[module_id] = module

    verification = payload.get("verification", {})
    blockers: list[str] = []
    if not screenshot.is_file():
        blockers.append("source_screenshot_missing")
    manifest = {
        "schemaVersion": "phase2.atomic-manifest.v3",
        "taxonomy": {
            "contractVersion": TAXONOMY_ENUMS["contractVersion"],
            "file": relative(TAXONOMY_ENUMS["path"]),
            "sha256": TAXONOMY_ENUMS["sha256"],
        },
        "source": {"query": normalized["query"], "screenshot": relative(screenshot), "sha256": sha256(screenshot), "viewport": [width, height]},
        "publication": {"status": "blocked" if blockers else "ready", "blockers": blockers},
        "page": {"moduleIds": list(modules)},
        "modulesById": modules,
        "cardsById": cards,
        "regionsById": regions,
        "filterItemsById": filter_items,
        "elementsById": elements,
    }
    title_affixes, title_affix_errors = title_affix_audit(manifest)
    if title_affix_errors:
        manifest["publication"] = {"status": "blocked", "blockers": ["title_affix_enum_violation"]}
    audit = {
        "taxonomy": manifest["taxonomy"],
        "taxonomyValidation": "passed",
        "sourceGolden": relative(source),
        "sourceGoldenSha256": sha256(source),
        "coordinatePolicy": "card/element/filter coordinates copied from pixel-verified golden CV/OCR facts; no manual scale estimation",
        "verificationStatus": verification.get("status", ""),
        "missingModuleBounds": [module_id for module_id, module in modules.items() if "bounds" not in module],
        "titleAffixes": title_affixes,
        "titleAffixErrors": title_affix_errors,
        "cards": len(cards), "regions": len(regions), "elements": len(elements),
    }
    return manifest, audit


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rebuild_from_atomic(source_root: Path, output_root: Path, taxonomy_path: Path = DEFAULT_TAXONOMY) -> dict[str, Any]:
    """Rebuild the retained golden set from atomic v3 as the canonical source."""
    global TAXONOMY_ENUMS
    TAXONOMY_ENUMS = load_taxonomy(taxonomy_path)
    sources = sorted(source_root.rglob("*.atomic.v3.json"))
    if len(sources) != 34:
        raise ValueError(f"expected 34 atomic v3 golden inputs, found {len(sources)}")
    loaded = [(source, json.loads(source.read_text(encoding="utf-8"))) for source in sources]
    records: list[dict[str, Any]] = []
    totals = Counter()
    for source, manifest in loaded:
        result = validate(manifest, taxonomy_path)
        if not result["valid"]:
            raise ValueError(f"{source}: " + ";".join(result["errors"]))
        screenshot = Path(str(manifest["source"]["screenshot"]))
        if not screenshot.is_absolute():
            screenshot = ROOT / screenshot
        if not screenshot.is_file():
            raise ValueError(f"{source}: source_screenshot_missing")
        if sha256(screenshot) != manifest["source"]["sha256"]:
            raise ValueError(f"{source}: source_screenshot_sha256_mismatch")
        title_affixes, title_affix_errors = title_affix_audit(manifest)
        if title_affix_errors:
            raise ValueError(f"{source}: " + ";".join(title_affix_errors))
        missing_bounds = [module_id for module_id, module in manifest["modulesById"].items() if "bounds" not in module]
        relative_source = source.relative_to(source_root)
        output = output_root / relative_source
        write_json(output, manifest)
        card_count = len(manifest["cardsById"])
        region_count = len(manifest["regionsById"])
        element_count = len(manifest["elementsById"])
        totals.update({
            "images": 1, "cards": card_count, "regions": region_count, "elements": element_count,
            "missingModuleBounds": len(missing_bounds), "titleAffixes": len(title_affixes), "titleAffixErrors": 0,
        })
        records.append({
            "manifest": relative(output), "valid": True,
            "taxonomy": manifest["taxonomy"], "taxonomyValidation": "passed",
            "coordinatePolicy": "coordinates retained from the canonical atomic v3 golden; no estimation or legacy JSON lookup",
            "missingModuleBounds": missing_bounds, "titleAffixes": title_affixes, "titleAffixErrors": [],
            "cards": card_count, "regions": region_count, "elements": element_count,
        })
    index = {
        "schemaVersion": "phase2.atomic-manifest.v3.batch-index",
        "taxonomy": {
            "contractVersion": TAXONOMY_ENUMS["contractVersion"],
            "file": relative(TAXONOMY_ENUMS["path"]),
            "sha256": TAXONOMY_ENUMS["sha256"],
        },
        "taxonomyValidation": "passed",
        "coordinatePolicy": "canonical atomic v3 coordinates retained unchanged; screenshots and hashes revalidated",
        "retentionPolicy": "latest atomic manifests are the canonical golden inputs; legacy element JSON is optional migration evidence only",
        "totals": dict(totals), "samples": records,
    }
    write_json(output_root / "index.json", index)
    return index


def build_all(source_root: Path, output_root: Path, taxonomy_path: Path = DEFAULT_TAXONOMY) -> dict[str, Any]:
    """One-time migration from a restored legacy elements.json archive."""
    global TAXONOMY_ENUMS
    TAXONOMY_ENUMS = load_taxonomy(taxonomy_path)
    sources = sorted(source_root.rglob("*.elements.json"))
    if len(sources) != 34:
        raise ValueError(f"expected 34 golden inputs, found {len(sources)}")
    records = []
    totals = Counter()
    for source in sources:
        manifest, audit = build_one(source, source_root)
        result = validate(manifest, taxonomy_path)
        if not result["valid"]:
            raise ValueError(f"{source}: " + ";".join(result["errors"]))
        relative_source = source.relative_to(source_root)
        output = output_root / relative_source.parent / relative_source.name.replace(".elements.json", ".atomic.v3.json")
        write_json(output, manifest)
        totals.update({"images": 1, "cards": audit["cards"], "regions": audit["regions"], "elements": audit["elements"], "missingModuleBounds": len(audit["missingModuleBounds"]), "titleAffixes": len(audit["titleAffixes"]), "titleAffixErrors": len(audit["titleAffixErrors"])})
        retained_audit = {key: value for key, value in audit.items() if key not in {"sourceGolden", "sourceGoldenSha256"}}
        records.append({"manifest": relative(output), "valid": True, **retained_audit})
    index = {
        "schemaVersion": "phase2.atomic-manifest.v3.batch-index",
        "taxonomy": {
            "contractVersion": TAXONOMY_ENUMS["contractVersion"],
            "file": relative(TAXONOMY_ENUMS["path"]),
            "sha256": TAXONOMY_ENUMS["sha256"],
        },
        "taxonomyValidation": "passed",
        "coordinatePolicy": "pixel-verified golden CV/OCR coordinates only; corrected reference JSON coordinates ignored",
        "retentionPolicy": "latest atomic manifests and consolidated index only; legacy element JSON and per-manifest audit sidecars are not retained",
        "totals": dict(totals), "samples": records,
    }
    write_json(output_root / "index.json", index)
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild and validate the 34 retained atomic-manifest.v3 goldens")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_OUTPUT, help="canonical atomic v3 golden root")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--legacy-source-root", type=Path, help="optional restored legacy elements.json root for one-time migration")
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    args = parser.parse_args()
    if args.legacy_source_root:
        result = build_all(args.legacy_source_root.resolve(), args.output_root.resolve(), args.taxonomy.resolve())
    else:
        result = rebuild_from_atomic(args.source_root.resolve(), args.output_root.resolve(), args.taxonomy.resolve())
    print(json.dumps({"valid": True, **result["totals"], "output": relative(args.output_root)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
