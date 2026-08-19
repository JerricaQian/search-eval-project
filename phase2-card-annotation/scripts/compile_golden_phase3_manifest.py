#!/usr/bin/env python3
"""Normalize a curated golden and compile the Phase3 manifest projection.

The normalized document stores every visual element once in ``elementsById``.
Regions and appended items only own stable element-ID references. Calibration
provenance is emitted to an optional evidence sidecar and never copied into the
Phase3 runtime manifest.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterator

from golden_visual_identity import DOWNHANG_REGIONS, duplicate_visual_atoms, iter_owned_elements


ROOT = Path(__file__).resolve().parents[2]
REGION_NAMES = {
    "推荐词区": "AI推荐理由",
}
CARD_TYPES = {
    "商家卡片_文字下挂": ("商家卡片-文字下挂", "service_retail", "到店综合服务"),
    "商家卡片_图文下挂": ("商家卡片-图文下挂", "service_retail", "到店综合服务"),
    "商品卡片": ("商品卡片", "flash_delivery", "闪购零售"),
    "酒店卡片": ("酒店卡片", "hotel_travel", "酒店旅行"),
    "演出电影卡片": ("演出/电影卡片", "maoyan", "猫眼演出电影"),
    "主点卡片": ("主点卡片", "service_retail", "到店综合服务"),
    "异构卡": ("异构卡", "unknown", "未知业务"),
    "广告卡": ("特殊广告卡", "unknown", "未知业务"),
}
PRIMARY_ROLES = {"fulfillment", "rating", "sales", "price", "location", "subtitle"}
EVIDENCE_KEYS = {
    "source", "boundedEvidence", "elementContract", "verification", "routing",
    "legacyContractVersion", "ocrConfidence", "colorEvidence",
}


def union(coords: list[list[int]]) -> list[int]:
    x0 = min(coord[0] for coord in coords)
    y0 = min(coord[1] for coord in coords)
    x1 = max(coord[0] + coord[2] for coord in coords)
    y1 = max(coord[1] + coord[3] for coord in coords)
    return [x0, y0, x1 - x0, y1 - y0]


def query_from(payload: dict[str, Any], golden: Path) -> str:
    screenshot = Path(str(payload.get("verification", {}).get("rawScreenshot", ""))).stem
    for prefix in ("搜索词为", "商家卡片-文下挂-搜索词为"):
        if prefix in screenshot:
            return screenshot.split(prefix, 1)[1].split("_")[0]
    return re.sub(r"\.elements$", "", golden.stem)


def all_nested_elements(value: Any) -> Iterator[dict[str, Any]]:
    """Yield wrapper and leaf elements so normalization is source-lossless."""
    if isinstance(value, dict):
        if "elementType" in value:
            yield value
        for child in value.values():
            yield from all_nested_elements(child)
    elif isinstance(value, list):
        for child in value:
            yield from all_nested_elements(child)


def result_cards(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for component in payload["pageStructure"]["components"]:
        if component.get("componentType") != "results_list":
            continue
        for card in component.get("components", []):
            if card.get("componentType") in {"result_card", "heterogeneous_card"}:
                yield card


def style_key(visual: dict[str, Any]) -> str:
    current = visual.get("styleKey")
    if isinstance(current, str) and len(current.split("|")) == 5:
        return current
    return "|".join(str(value) for value in (
        visual.get("entityKind", "text"), visual.get("colorRole", "unknown"),
        visual.get("semanticRole", "other"), visual.get("containerShape", "unknown"),
        visual.get("graphicAssistRole", visual.get("graphicType", "无")),
    ))


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def normalize_element(source: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    render = copy.deepcopy(source.get("render", {}))
    render.pop("sourceRegion", None)
    visual = copy.deepcopy(source.get("visual", {}))
    evidence: dict[str, Any] = {}
    for key in list(visual):
        if key in EVIDENCE_KEYS:
            evidence[f"visual.{key}"] = visual.pop(key)
    # Legacy prose repeated a deterministic interpretation of the structured
    # fields below. It belongs in neither canonical truth nor its sidecar.
    visual.pop("countDecision", None)
    visual.pop("dedupDecision", None)
    visual.pop("sourceRegion", None)
    visual.pop("styleKey", None)
    text_facts = copy.deepcopy(source.get("textFacts"))
    if isinstance(text_facts, dict):
        text_facts.pop("rawText", None)
        if text_facts.get("fontWeightBucket") == "unknown":
            text_facts.pop("fontWeightBucket", None)
    normalized = {
        "elementType": source.get("elementType", ""),
        "visibleText": source.get("visibleText", ""),
        "coord": source.get("coord", []),
        "status": source.get("status", "uncertain"),
        "render": render,
        "visual": visual,
    }
    attributes = {key: copy.deepcopy(source[key]) for key in ("selected", "itemIndex") if key in source}
    if attributes:
        normalized["attributes"] = attributes
    if isinstance(text_facts, dict):
        normalized["textFacts"] = text_facts
    for key in EVIDENCE_KEYS:
        if key in source:
            evidence[key] = copy.deepcopy(source[key])
    return normalized, evidence


def normalize_golden(payload: dict[str, Any], golden: Path, query: str | None = None, evidence_name: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    duplicate_errors = []
    for card in result_cards(payload):
        duplicate_errors.extend(duplicate_visual_atoms(card.get("regions", {})))
    if duplicate_errors:
        raise ValueError(f"golden contains {len(duplicate_errors)} cross-region duplicate visual atoms")

    elements_by_id: dict[str, dict[str, Any]] = {}
    page_elements_by_id: dict[str, dict[str, Any]] = {}
    evidence_by_id: dict[str, dict[str, Any]] = {}
    page_evidence_by_id: dict[str, dict[str, Any]] = {}
    cards: list[dict[str, Any]] = []
    for card_number, source_card in enumerate(result_cards(payload), 1):
        card_id = f"C{card_number}"
        regions: list[dict[str, Any]] = []
        sequence = 0
        for raw_region_name, source_region in source_card.get("regions", {}).items():
            region_name = REGION_NAMES.get(raw_region_name, raw_region_name)
            element_ids: list[str] = []
            source_ids: dict[int, str] = {}
            for _, source in iter_owned_elements(source_region):
                sequence += 1
                element_id = f"{card_id}-E{sequence:03d}"
                source_ids[id(source)] = element_id
                normalized, evidence = normalize_element(source)
                normalized["ownerRegion"] = region_name
                elements_by_id[element_id] = normalized
                if evidence:
                    evidence_by_id[element_id] = evidence
                element_ids.append(element_id)
            if not element_ids:
                continue
            normalized_region: dict[str, Any] = {
                "name": region_name,
                "coord": union([elements_by_id[element_id]["coord"] for element_id in element_ids]),
                "elementIds": element_ids,
            }
            if raw_region_name in DOWNHANG_REGIONS:
                item_groups = []
                for item in source_region.get("items", []):
                    owned = [source_ids[id(element)] for _, element in iter_owned_elements(item) if id(element) in source_ids]
                    images = [source_ids[id(element)] for element in item.get("imageElements", []) if id(element) in source_ids]
                    prices = [source_ids[id(element)] for element in item.get("priceElements", []) if id(element) in source_ids]
                    texts = [element_id for element_id in owned if element_id not in images and element_id not in prices]
                    item_groups.append({
                        "itemIndex": item.get("itemIndex"),
                        "coord": item.get("coord"),
                        "elementIds": owned,
                        "imageElementIds": images,
                        "textElementIds": texts,
                        "priceElementIds": prices,
                        # Preserve viewport cropping as an observed state.  It is
                        # not recognition uncertainty; Phase3 decides per skill
                        # whether a partial value is comparable.
                        "visibleStatus": item.get("visibleStatus", "confirmed"),
                    })
                normalized_region["itemGroups"] = item_groups
            regions.append(normalized_region)
        cards.append({
            "cardId": card_id,
            "sourceCardType": source_card.get("cardType", "异构卡"),
            "variant": source_card.get("variant", ""),
            "coord": source_card.get("coord"),
            "visibleStatus": source_card.get("visibleStatus", "complete"),
            "listPosition": source_card.get("listPosition", card_number),
            "regions": regions,
        })

    page_modules: list[dict[str, Any]] = []
    for module_index, component in enumerate(payload["pageStructure"]["components"], 1):
        module_type = str(component.get("componentType", "unknown"))
        element_ids: list[str] = []
        if module_type != "results_list":
            for element_index, source in enumerate(all_nested_elements(component), 1):
                element_id = f"M{module_index}-E{element_index:03d}"
                normalized_element, evidence = normalize_element(source)
                normalized_element["ownerModule"] = module_type
                page_elements_by_id[element_id] = normalized_element
                if evidence:
                    page_evidence_by_id[element_id] = evidence
                element_ids.append(element_id)
        coords = [page_elements_by_id[element_id]["coord"] for element_id in element_ids if page_elements_by_id[element_id].get("coord")]
        if module_type == "results_list":
            coords = [card["coord"] for card in cards]
        page_modules.append({
            "order": component.get("order", module_index),
            "moduleType": module_type,
            "name": component.get("name", module_type),
            "status": component.get("status", "uncertain"),
            "visibleStatus": component.get("visibleStatus", "confirmed" if component.get("status") == "confirmed" else "uncertain"),
            "coord": copy.deepcopy(component.get("coord")) if component.get("coord") else (union(coords) if coords else None),
            "elementIds": element_ids,
        })

    screenshot_rel = str(payload["verification"]["rawScreenshot"])
    screenshot = str((ROOT / screenshot_rel).resolve())
    verification = payload.get("verification", {})
    evidence = {
        "contractVersion": "phase2.golden-evidence.v2",
        "sourceGolden": project_relative(golden),
        "verification": copy.deepcopy(verification),
        "elementsById": evidence_by_id,
    }
    if page_evidence_by_id:
        evidence["pageElementsById"] = page_evidence_by_id
    normalized = {
        "contractVersion": "phase2.golden-normalized.v2",
        "query": query or query_from(payload, golden),
        "screenshot": screenshot,
        "provenance": {
            "goldenPath": project_relative(golden),
            "goldenSha256": hashlib.sha256(golden.read_bytes()).hexdigest(),
            "screenshotPath": screenshot_rel,
            "screenshotSha256": verification.get("rawSha256", ""),
            "annotationPath": verification.get("componentAnnotation", ""),
            "annotationSha256": verification.get("componentAnnotationSha256", ""),
            "verificationStatus": verification.get("status", ""),
            "claimScope": verification.get("claimScope", []),
            "excludedClaims": verification.get("excludedClaims", []),
            "evidenceSidecar": evidence_name or f"{golden.stem}.evidence.json",
            "evidenceCanonicalSha256": canonical_json_sha256(evidence),
        },
        "pageModules": page_modules,
        "cards": cards,
        "elementsById": elements_by_id,
    }
    if page_elements_by_id:
        normalized["pageElementsById"] = page_elements_by_id
    return normalized, evidence


def validate_normalized_bundle(normalized: dict[str, Any], evidence: dict[str, Any], evidence_path: Path | None = None) -> list[str]:
    """Validate the compact truth/evidence join before Phase3 expansion."""
    errors: list[str] = []
    if normalized.get("contractVersion") != "phase2.golden-normalized.v2":
        errors.append("normalized_contract_version_invalid")
    if evidence.get("contractVersion") != "phase2.golden-evidence.v2":
        errors.append("evidence_contract_version_invalid")
    provenance = normalized.get("provenance")
    if not isinstance(provenance, dict):
        errors.append("normalized_provenance_missing")
        provenance = {}
    expected_hash = provenance.get("evidenceCanonicalSha256")
    actual_hash = canonical_json_sha256(evidence)
    if expected_hash != actual_hash:
        errors.append("evidence_canonical_sha256_mismatch")
    if evidence_path is not None and provenance.get("evidenceSidecar") != evidence_path.name:
        errors.append("evidence_sidecar_filename_mismatch")

    normalized_ids = set(normalized.get("elementsById", {}))
    evidence_ids = set(evidence.get("elementsById", {}))
    if normalized_ids != evidence_ids:
        errors.append("card_element_id_index_mismatch")
    normalized_page_ids = set(normalized.get("pageElementsById", {}))
    evidence_page_ids = set(evidence.get("pageElementsById", {}))
    if normalized_page_ids != evidence_page_ids:
        errors.append("page_element_id_index_mismatch")

    screenshot = Path(str(normalized.get("screenshot", "")))
    expected_screenshot_hash = provenance.get("screenshotSha256")
    if not screenshot.is_file():
        errors.append("screenshot_missing")
    elif expected_screenshot_hash and hashlib.sha256(screenshot.read_bytes()).hexdigest() != expected_screenshot_hash:
        errors.append("screenshot_sha256_mismatch")
    verification = evidence.get("verification", {})
    if isinstance(verification, dict):
        if verification.get("rawSha256", "") != provenance.get("screenshotSha256", ""):
            errors.append("verification_screenshot_sha256_mismatch")
        if verification.get("componentAnnotationSha256", "") != provenance.get("annotationSha256", ""):
            errors.append("verification_annotation_sha256_mismatch")
    else:
        errors.append("evidence_verification_missing")
    return errors


def phase3_element(element_id: str, source: dict[str, Any], card_id: str, region_name: str) -> dict[str, Any]:
    visible_text = str(source.get("visibleText", ""))
    visual = copy.deepcopy(source.get("visual", {}))
    visual["sourceRegion"] = region_name
    visual["styleKey"] = style_key(visual)
    render = copy.deepcopy(source.get("render", {}))
    render["sourceRegion"] = region_name
    if source.get("status") == "naturally_cropped":
        # A viewport-edge crop is a confirmed visible state, not recognition
        # uncertainty. Phase3 evaluates only the pixels that are present.
        render["visibleStatus"] = "confirmed"
        render["renderState"] = "naturally_cropped"
        visual["visualStatus"] = "confirmed"
    kind = visual.get("entityKind")
    element_type = "图片" if kind == "image" else ("标签" if kind in {"tag", "icon"} else "文本")
    output = {
        "id": element_id,
        "所属组件": card_id,
        "元素类型": element_type,
        "内容简述": f"原文:{visible_text}" if visible_text else f"原文:[{source.get('elementType', '图片')}]",
        "坐标": source["coord"],
        "isExcluded": False,
        "excludeReason": "",
        "render": render,
        "visual": visual,
    }
    if element_type != "图片":
        facts = copy.deepcopy(source.get("textFacts", {}))
        facts["rawText"] = visible_text
        if source.get("status") == "naturally_cropped":
            facts["textStatus"] = "naturally_ellipsized"
        if facts.get("fontWeightBucket") in {None, "", "unknown"}:
            # Golden projection fallback: role/emphasis is already pixel-reviewed;
            # this derived bucket is kept out of canonical truth.
            facts["fontWeightBucket"] = "bold" if facts.get("emphasisLevel") == "primary" else "regular"
        output["textFacts"] = facts
    return output


def compile_phase3(normalized: dict[str, Any]) -> dict[str, Any]:
    elements_by_id = normalized["elementsById"]
    cards: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    alignment_candidates: dict[str, list[dict[str, Any]]] = {}
    for source_card in normalized["cards"]:
        card_id = source_card["cardId"]
        regions = []
        title_ids: list[str] = []
        image_ids: list[str] = []
        append_ids: list[str] = []
        inventory_regions: dict[str, list[dict[str, Any]]] = {}
        anchor_elements: dict[str, list[dict[str, Any]]] = {"image": [], "title": [], "primaryInfo": []}
        all_tag_ids: list[str] = []
        uncertain_ids: list[str] = []
        for source_region in source_card["regions"]:
            name = source_region["name"]
            converted = [phase3_element(element_id, elements_by_id[element_id], card_id, name) for element_id in source_region["elementIds"]]
            region = {"name": name, "coord": source_region["coord"], "elements": converted}
            if "itemGroups" in source_region:
                region["itemGroups"] = copy.deepcopy(source_region["itemGroups"])
            regions.append(region)
            inventory_regions[name] = []
            for element in converted:
                visual = element["visual"]
                if element["render"].get("visibleStatus") != "confirmed" or visual.get("visualStatus") == "uncertain":
                    uncertain_ids.append(element["id"])
                if visual.get("entityKind") in {"tag", "icon"}:
                    all_tag_ids.append(element["id"])
                    inventory_regions[name].append({
                        "elementId": element["id"],
                        "styleKey": visual["styleKey"],
                        "countedInComplexity": bool(visual.get("countedInComplexity", False)),
                    })
                role = element.get("textFacts", {}).get("semanticRole")
                if role == "title":
                    title_ids.append(element["id"])
                    anchor_elements["title"].append(element)
                if element["render"].get("isPhoto"):
                    image_ids.append(element["id"])
                    anchor_elements["image"].append(element)
                if role in PRIMARY_ROLES:
                    anchor_elements["primaryInfo"].append(element)
                if name in DOWNHANG_REGIONS:
                    append_ids.append(element["id"])

        source_type = source_card["sourceCardType"]
        card_type, business_code, business_name = CARD_TYPES.get(source_type, CARD_TYPES["异构卡"])
        region_signature = ">".join(region["name"] for region in regions)
        layout_mode = "image_left" if regions and regions[0]["name"] in {"头图区", "头图区（演出）"} else "stacked"
        # Completeness here means the visible facts are internally complete.
        # A viewport-edge crop limits evaluation scope but is not a Phase2 fact
        # failure and must not force an unrelated re-recognition pass.
        complete = source_card["visibleStatus"] in {"complete", "naturally_cropped"} and not uncertain_ids
        structure = {
            "visibleStatus": source_card["visibleStatus"],
            "cardTypeCode": source_type,
            "layoutMode": layout_mode,
            "layoutSignature": region_signature,
            "comparisonGroupKey": f"{source_type}|{source_card.get('variant', '')}|{layout_mode}|{region_signature}",
            "isResultListItem": True,
            "isHeterogeneous": card_type == "异构卡",
            "listPosition": source_card["listPosition"],
            "regions": [region["name"] for region in regions],
        }
        card = {
            "cardId": card_id,
            "卡片类型": card_type,
            "coord": source_card["coord"],
            "regions": regions,
            "ownershipScope": "unknown" if business_code == "unknown" else "business",
            "businessCode": business_code,
            "businessName": business_name,
            "businessConfidence": "high" if business_code != "unknown" else "unknown",
            "cardTypeCode": source_type,
            "cardTypeName": card_type,
            "classificationEvidence": ["离线黄金像素复核卡型"],
            "structure": structure,
            "factInventory": {
                "complete": complete,
                "scanned": ["card_boundary", "regions", "images", "text", "render_state", "visual_spec", "layout", "relations"],
                "uncertainElementIds": sorted(set(uncertain_ids)),
            },
            "visualInventory": {
                "complete": complete,
                "regions": inventory_regions,
                "tagScanChecklist": [{
                    "candidate": "全卡独立标签与icon",
                    "status": "uncertain" if uncertain_ids else ("found" if all_tag_ids else "not_found"),
                    "checkedRegions": [region["name"] for region in regions],
                    "elementIds": all_tag_ids if not uncertain_ids else [],
                }],
            },
        }
        cards.append(card)
        alignment_key = structure["comparisonGroupKey"]
        alignment_candidates.setdefault(alignment_key, []).append({"card": card, "anchors": anchor_elements})
        for title_id in title_ids:
            for image_id in image_ids:
                relations.append({"relationType": "title_to_image", "from": title_id, "to": image_id, "status": "confirmed"})
            for append_id in append_ids:
                relations.append({"relationType": "title_to_append", "from": title_id, "to": append_id, "status": "confirmed"})

    for key, members in alignment_candidates.items():
        comparable = len(members) >= 2 and all(all(member["anchors"][name] for name in ("image", "title", "primaryInfo")) for member in members)
        for member in members:
            structure = member["card"]["structure"]
            if comparable:
                structure["layoutAnchors"] = {name: member["anchors"][name][0]["坐标"] for name in ("image", "title", "primaryInfo")}
                structure["layoutAnchorRelation"] = "同卡主图、标题、主信息锚点按当前像素坐标记录"
            elif len(members) >= 2:
                structure["comparisonGroupKey"] = f"{key}|{member['card']['cardId']}|not_comparable"

    result_coord = union([card["coord"] for card in cards])
    page_modules = []
    for index, module in enumerate(normalized.get("pageModules", []), 1):
        if not module.get("coord"):
            continue
        projected_module_type = "result_list" if module["moduleType"] == "results_list" else module["moduleType"]
        page_modules.append({
            "id": f"M{index}",
            "moduleType": projected_module_type,
            "coord": module["coord"],
            "visibleStatus": module["visibleStatus"],
            "contentRole": module["name"],
            "isListPrefix": module["moduleType"] != "results_list" and module["order"] < next((item["order"] for item in normalized.get("pageModules", []) if item["moduleType"] == "results_list"), 10**9),
            "isListItem": False,
        })
    if not any(module["moduleType"] == "result_list" for module in page_modules):
        page_modules.append({"id": "results-list", "moduleType": "result_list", "coord": result_coord, "visibleStatus": "confirmed", "contentRole": "search_results", "isListPrefix": False, "isListItem": False})
    return {
        "query": normalized["query"],
        "screenshot": normalized["screenshot"],
        "annotatedImage": "",
        "cards": cards,
        "recognition": {
            "contractVersion": "phase2.golden-phase3-projection.v1",
            "status": "confirmed",
            "phase3Ready": True,
            "wholePageGate": True,
            "blockingCardIds": [],
            "backends": {"source": "pixel_verified_golden_normalized"},
            "errors": [],
            "semanticHookFindings": [],
            "reprocessTargets": [],
            "reprocess": [],
        },
        "pageFacts": {
            "screen": 1,
            "isContinuation": False,
            "viewport": {},
            "modules": page_modules,
        },
        "pageFactInventory": {"complete": True, "scanned": ["result_list", "cards", "elements"], "uncertainElementIds": []},
        "relations": relations,
    }


def write_json(path: Path, payload: dict[str, Any], pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"ensure_ascii": False, "sort_keys": False}
    text = json.dumps(payload, indent=2, **kwargs) if pretty else json.dumps(payload, separators=(",", ":"), **kwargs)
    path.write_text(text + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize one curated golden and compile a Phase3 manifest")
    parser.add_argument("golden", type=Path, nargs="?", help="Legacy golden input used only during migration")
    parser.add_argument("--normalized-input", type=Path, help="Compact normalized v2 truth used after migration")
    parser.add_argument("--evidence-input", type=Path, help="Evidence v2 sidecar paired with --normalized-input")
    parser.add_argument("--output", type=Path, help="Optional legacy expanded Phase3 manifest path")
    parser.add_argument("--normalized-output", type=Path)
    parser.add_argument("--evidence-output", type=Path)
    parser.add_argument("--query")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    if args.normalized_input:
        if args.golden is not None:
            parser.error("legacy golden positional input cannot be combined with --normalized-input")
        if not args.evidence_input:
            parser.error("--evidence-input is required with --normalized-input")
        if args.normalized_output or args.evidence_output:
            parser.error("direct compile mode does not rewrite normalized/evidence inputs")
        normalized_path = args.normalized_input.resolve()
        evidence_path = args.evidence_input.resolve()
        normalized = json.loads(normalized_path.read_text(encoding="utf-8"))
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        errors = validate_normalized_bundle(normalized, evidence, evidence_path)
        if errors:
            raise ValueError("invalid normalized/evidence bundle: " + ",".join(errors))
        golden_label = normalized["provenance"]["goldenPath"]
        mode = "direct_normalized"
    else:
        if args.golden is None:
            parser.error("provide legacy golden or --normalized-input with --evidence-input")
        if args.evidence_input:
            parser.error("--evidence-input requires --normalized-input")
        golden = args.golden.resolve()
        payload = json.loads(golden.read_text(encoding="utf-8"))
        normalized, evidence = normalize_golden(
            payload,
            golden,
            args.query,
            args.evidence_output.name if args.evidence_output else None,
        )
        errors = validate_normalized_bundle(normalized, evidence)
        if errors:
            raise ValueError("invalid migrated normalized/evidence bundle: " + ",".join(errors))
        golden_label = str(golden)
        mode = "legacy_migration"
    manifest = compile_phase3(normalized)
    if args.output:
        write_json(args.output, manifest, args.pretty)
    if args.normalized_output:
        write_json(args.normalized_output, normalized, args.pretty)
    if args.evidence_output:
        write_json(args.evidence_output, evidence, args.pretty)
    print(json.dumps({
        "mode": mode,
        "golden": golden_label,
        "cards": len(normalized["cards"]),
        "elements": len(normalized["elementsById"]),
        "phase3": str(args.output) if args.output else "in_memory_only",
        "normalized": str(args.normalized_output) if args.normalized_output else "",
        "evidence": str(args.evidence_output) if args.evidence_output else "",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
