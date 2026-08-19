#!/usr/bin/env python3
"""Fail closed when any curated golden violates the element-level contract."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from semantic_atomicity import merged_tag_reason
from golden_visual_identity import duplicate_visual_atoms


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "phase2-card-annotation" / "golden-sample-results"
TRUTH = ROOT / "phase2-card-annotation" / "references" / "golden_page_truth.v2.json"


def elements(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if "elementType" in value:
            yield value
        for child in value.values():
            yield from elements(child)
    elif isinstance(value, list):
        for child in value:
            yield from elements(child)


def audit() -> dict[str, Any]:
    truth = json.loads(TRUTH.read_text(encoding="utf-8"))["pages"]
    errors: list[str] = []
    card_count = element_count = 0
    for path in sorted(RESULTS.rglob("*.elements.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        def reject_published_ocr_debug(value: Any) -> None:
            if isinstance(value, dict):
                if "ocrConfidence" in value:
                    errors.append(f"{path.name}:published_ocr_confidence")
                if isinstance(value.get("boundedEvidence"), list) and any(isinstance(item, dict) and "text" in item for item in value["boundedEvidence"]):
                    errors.append(f"{path.name}:duplicated_bounded_evidence_text")
                for child in value.values():
                    reject_published_ocr_debug(child)
            elif isinstance(value, list):
                for child in value:
                    reject_published_ocr_debug(child)
        reject_published_ocr_debug(payload)
        payload_elements = list(elements(payload))
        element_count += len(payload_elements)
        for item in payload_elements:
            for key in ("coord", "sourceRegion", "status", "visibleText"):
                if key not in item:
                    errors.append(f"{path.name}:{item.get('elementType')}:{key}_missing")
            for key in ("render", "visual"):
                if not isinstance(item.get(key), dict):
                    errors.append(f"{path.name}:{item.get('elementType')}:{key}_missing")
            is_image = item.get("visual", {}).get("entityKind") == "image"
            image_semantic = any(token in str(item.get("elementType", "")) for token in ("图片", "头图", "主图", "海报", "视频", "横幅/轮播"))
            if image_semantic != is_image:
                errors.append(f"{path.name}:{item.get('elementType')}:semantic_visual_kind_mismatch")
            if is_image and (item.get("render", {}).get("isPhoto") is not True or item.get("render", {}).get("isSystemUi") is not False):
                errors.append(f"{path.name}:{item.get('elementType')}:image_render_policy_invalid")
            if not is_image and not isinstance(item.get("textFacts"), dict):
                errors.append(f"{path.name}:{item.get('elementType')}:textFacts_missing")
            visual = item.get("visual", {})
            for key in ("entityKind", "visualStatus", "colorRole", "backgroundColor", "textColor", "borderColor", "styleKey", "sourceRegion", "colorEvidence"):
                if key not in visual:
                    errors.append(f"{path.name}:{item.get('elementType')}:visual.{key}_missing")
            if not is_image and item.get("status") == "confirmed" and visual.get("colorRole") == "unknown":
                errors.append(f"{path.name}:{item.get('elementType')}:confirmed_visual_color_unknown")
            text = re.sub(r"\s+", "", str(item.get("visibleText", "")))
            if len(text) == 1:
                errors.append(f"{path.name}:{item.get('elementType')}:one_character:{text}")
        screenshot = payload["verification"]["rawScreenshot"]
        cards = [
            card for component in payload["pageStructure"]["components"]
            if component.get("componentType") == "results_list"
            for card in component.get("components", [])
            if card.get("componentType") in {"result_card", "heterogeneous_card"}
        ]
        expected = truth[screenshot]["resultCards"]
        if len(cards) != len(expected):
            errors.append(f"{path.name}:result_card_count:{len(cards)}!={len(expected)}")
        for index, card in enumerate(cards, 1):
            card_count += 1
            prefix = f"{path.name}:card{index}"
            if index <= len(expected) and card.get("coord") != expected[index - 1]["coord"]:
                errors.append(f"{prefix}:coord_mismatch")
            if index <= len(expected) and card.get("visibleStatus") != expected[index - 1]["visibleStatus"]:
                errors.append(f"{prefix}:visible_status_mismatch")
            regions = card.get("regions", {})
            card_elements = list(elements(regions))
            for duplicate in duplicate_visual_atoms(regions):
                owners = ",".join(owner["region"] for owner in duplicate["owners"])
                errors.append(
                    f"{prefix}:visual_atom_has_multiple_owners:"
                    f"{duplicate['normalizedText']}:{duplicate['coord']}:{owners}"
                )
            if not card_elements:
                errors.append(f"{prefix}:visible_card_requires_element_facts")
            complete_known = card.get("componentType") == "result_card" and card.get("visibleStatus") == "complete" and card.get("cardType") not in {"异构卡", "广告卡"}
            if complete_known and not any("标题" in str(item.get("elementType", "")) and len(re.sub(r"\s+", "", str(item.get("visibleText", "")))) >= 2 for item in regions.get("标题区", {}).get("elements", [])):
                errors.append(f"{prefix}:missing_title")
            graphic_items = regions.get("下挂商品区", {}).get("items", []) if isinstance(regions.get("下挂商品区"), dict) else []
            image_tops = [image["coord"][1] for grouped in graphic_items for image in grouped.get("imageElements", []) if isinstance(image.get("coord"), list)]
            if image_tops:
                downhang_top = min(image_tops)
                for tag in regions.get("标签区", {}).get("elements", []):
                    if tag.get("coord", [0, 0])[1] >= downhang_top:
                        errors.append(f"{prefix}:merchant_tag_inside_downhang_image:{tag.get('visibleText', '')}")
            for item in card_elements:
                text = re.sub(r"\s+", "", str(item.get("visibleText", "")))
                if len(text) == 1:
                    errors.append(f"{prefix}:one_character:{text}")
                semantic_type = str(item.get("elementType", ""))
                if ("标题" in semantic_type or semantic_type.startswith("下挂")) and item.get("source") == "local_crop_ocr":
                    errors.append(f"{prefix}:unreviewed_fixed_crop_text:{semantic_type}:{text}")
                if path.parent.name in {"merchant-text-hang", "merchant-graphic-hang", "product-card"} and ("标题" in semantic_type or semantic_type.startswith("下挂")) and item.get("source") == "bounded_paddleocr_model_calibrated" and not item.get("boundedEvidence"):
                    errors.append(f"{prefix}:bounded_text_missing_pixel_evidence:{semantic_type}:{text}")
                if item.get("sourceRegion") in {"基础信息区", "商家信息区", "标签区"} and re.search(r"[｜|；]", text):
                    errors.append(f"{prefix}:merged_semantic_fields:{text}")
                if item.get("sourceRegion") == "标签区":
                    segments = item.get("visual", {}).get("horizontalForegroundSegments", [])
                    reason = merged_tag_reason(text, segments if isinstance(segments, list) else [])
                    if reason:
                        errors.append(f"{prefix}:multiple_independent_tags_merged:{reason}:{text}")
            for region_name in ("下挂商品区", "文字下挂区", "下挂区", "服务下挂"):
                region = regions.get(region_name)
                if not isinstance(region, dict):
                    continue
                if set(region) != {"items"}:
                    errors.append(f"{prefix}:{region_name}:must_use_items_only")
                    continue
                for item_index, item in enumerate(region["items"], 1):
                    required = {"itemIndex", "coord", "imageElements", "textElements", "priceElements", "auxiliaryElements", "visibleStatus"}
                    if not required.issubset(item) or item.get("itemIndex") != item_index:
                        errors.append(f"{prefix}:{region_name}:item{item_index}:schema")
                    has_text = lambda key: bool(item.get(key)) and all(len(re.sub(r"\s+", "", str(value.get("visibleText", "")))) >= 2 for value in item[key])
                    complete_item = complete_known and item.get("visibleStatus") != "naturally_cropped"
                    if complete_item and region_name == "下挂商品区" and (not item.get("imageElements") or not has_text("textElements") or not has_text("priceElements")):
                        errors.append(f"{prefix}:{region_name}:item{item_index}:requires_image_text_price")
                    if complete_item and path.parent.name == "merchant-graphic-hang" and card.get("cardType") == "商家卡片_图文下挂" and region_name == "下挂商品区" and item.get("imageElements") and item.get("textElements"):
                        image_coord = item["imageElements"][0]["coord"]
                        text_coord = item["textElements"][0]["coord"]
                        text_center = text_coord[0] + text_coord[2] / 2
                        if image_coord[2] < text_coord[2] * 0.60 or not image_coord[0] <= text_center <= image_coord[0] + image_coord[2]:
                            errors.append(f"{prefix}:{region_name}:item{item_index}:image_text_column_mismatch")
                    if complete_item and region_name != "下挂商品区" and (not has_text("textElements") or not has_text("priceElements")):
                        errors.append(f"{prefix}:{region_name}:item{item_index}:requires_text_price")
    return {"valid": not errors, "goldenFiles": 34, "cards": card_count, "elements": element_count, "errors": errors}


def main() -> int:
    result = audit()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
