#!/usr/bin/env python3
"""Assemble CV/OCR candidate artifacts into the Phase3 element-manifest contract.

This adapter deliberately preserves uncertainty.  It supplies the complete
field shape Phase3 needs, but never upgrades a weak OCR/CV candidate into an
absence, quality, colour-complexity, or semantic-authenticity conclusion.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


VERSION = "phase2.page-manifest.v2"
TYPE_NAMES = {
    "商品卡片": "商品卡片", "商家卡片_图文下挂": "商家卡片-图文下挂",
    "商家卡片_文字下挂": "商家卡片-文字下挂", "酒店卡片": "酒店卡片",
    "演出电影卡片": "演出/电影卡片", "度假酒店套餐卡片": "度假/酒店套餐卡片",
    "广告卡": "特殊广告卡", "异构卡": "异构卡",
}


def overlap(a: list[int], b: list[int]) -> bool:
    return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[1] + a[3] > b[1]


def clip(box: list[int], container: list[int]) -> list[int] | None:
    """Keep a CV candidate inside its result-card ownership boundary."""
    x0, y0 = max(box[0], container[0]), max(box[1], container[1])
    x1 = min(box[0] + box[2], container[0] + container[2])
    y1 = min(box[1] + box[3], container[1] + container[3])
    if x1 <= x0 or y1 <= y0:
        return None
    return [x0, y0, x1 - x0, y1 - y0]


def union(boxes: list[list[int]], fallback: list[int]) -> list[int]:
    if not boxes:
        return fallback
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[0] + b[2] for b in boxes), max(b[1] + b[3] for b in boxes)
    return [x0, y0, x1 - x0, y1 - y0]


def status(candidate: dict[str, Any]) -> str:
    return "confirmed" if candidate.get("route") == "accepted" else "uncertain"


def usable_text(candidate: dict[str, Any], semantic: dict[str, Any]) -> bool:
    """Only turn accepted/confirmed recognition into Phase3 visual entities.

    Weak OCR remains in the recognition audit.  This prevents one-character
    fragments from becoming false UI atoms while keeping the evidence visible.
    """
    raw = str(candidate.get("text", "")).strip()
    compact = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff¥￥.+%折减]", "", raw)
    chinese = sum("\u4e00" <= char <= "\u9fff" for char in compact)
    latin = sum(char.isascii() and char.isalpha() for char in compact)
    punctuation = sum(not (char.isalnum() or "\u4e00" <= char <= "\u9fff" or char in "¥￥.,+-%折减/×* ()[]") for char in raw)
    coherent = len(compact) >= 2 and punctuation / max(1, len(raw)) <= 0.35
    if chinese == 0 and latin and len(compact) <= 4:
        coherent = False
    if chinese >= 2 and latin >= 5 and latin / max(1, chinese + latin) > 0.45:
        coherent = False
    return bool(raw) and coherent and (status(candidate) == "confirmed" or semantic.get("status") == "confirmed")


def card_local_semantics(candidate: dict[str, Any], selected_type: str, text_candidates: list[dict[str, Any]], semantic_by_source: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Complete page-level rules with card-local geometry.

    Page OCR blocks can span an entire merchant card, so their top-text rule
    cannot reliably name the title. Card ownership is known here: select one
    upper, coherent, non-structured CJK line as title and place remaining
    untyped observations into the type-specific region without changing text.
    """
    x, y, width, height = candidate["coord"]
    output = {source_id: dict(value) for source_id, value in semantic_by_source.items()}
    structured = re.compile(r"月售|已售|评分|到店|外卖|上门|景点|酒店|民宿|\d(?:\.\d)?\s*分|\d+(?:\.\d+)?\s*(?:km|公里|分钟|元)|[¥￥]\s*\d|起送|配送费|\d{4}[-/.年]\d{1,2}")
    possible_titles = []
    for item in text_candidates:
        value = str(item.get("text", "")).strip()
        chinese = sum("\u4e00" <= char <= "\u9fff" for char in value)
        if item["coord"][1] <= y + max(100, height * 0.42) and chinese >= 2 and not structured.search(value):
            possible_titles.append(item)
    if possible_titles and not any(value.get("semanticRoleCandidate") == "title" and value.get("status") == "confirmed" for value in output.values()):
        top = min(item["coord"][1] for item in possible_titles)
        same_title_row = [item for item in possible_titles if item["coord"][1] <= top + max(28, item["coord"][3])]
        title = max(same_title_row, key=lambda item: (sum("\u4e00" <= char <= "\u9fff" for char in str(item.get("text", ""))), item["coord"][2]))
        output[title["id"]] = {**output.get(title["id"], {}), "semanticRoleCandidate": "title", "regionCandidate": "标题区", "status": "confirmed", "evidence": ["card_local_upper_cjk_title"]}
    fallback_region = {
        "商家卡片_图文下挂": "下挂商品区",
        "商家卡片_文字下挂": "文字下挂区",
        "演出电影卡片": "演出信息区",
        "酒店卡片": "基础信息区",
        "度假酒店套餐卡片": "套餐概要",
        "商品卡片": "副标题区",
    }.get(selected_type, "基础信息区")
    for item in text_candidates:
        current = output.get(item["id"], {})
        if current.get("semanticRoleCandidate", "other") != "other":
            continue
        lower_content = item["coord"][1] >= y + height * 0.28
        output[item["id"]] = {**current, "semanticRoleCandidate": "other", "regionCandidate": fallback_region if lower_content else "基础信息区"}
    return output


def visual_hint(candidate: dict[str, Any], kind: str, region: str, role: str = "") -> dict[str, Any]:
    hint = candidate.get("visualHint", {})
    color = hint.get("colorRole", "unknown") if isinstance(hint, dict) else "unknown"
    median = hint.get("medianRgb") if isinstance(hint, dict) else None
    exact_text_color = ""
    if isinstance(median, list) and len(median) == 3 and all(isinstance(channel, int) and 0 <= channel <= 255 for channel in median):
        exact_text_color = "#" + "".join(f"{channel:02X}" for channel in median)
    background_color = ""
    container_shape = "unknown"
    if kind in {"tag", "icon"}:
        surface = hint.get("surfaceMedianRgb") if isinstance(hint, dict) else None
        if isinstance(surface, list) and len(surface) == 3 and all(isinstance(channel, int) and 0 <= channel <= 255 for channel in surface):
            sr, sg, sb = surface
            spread = max(surface) - min(surface)
            if spread >= 45 and sum(surface) / 3 < 235:
                background_color = "#" + "".join(f"{channel:02X}" for channel in surface)
                exact_text_color = "#FFFFFF" if sum(surface) / 3 < 205 else exact_text_color
                if sr > sg * 1.25 and sr > sb * 1.25:
                    color = "orange" if sg >= sr * 0.34 else "red"
                elif sb > sr * 1.18 and sb > sg * 1.05:
                    color = "blue"
                elif sg > sr * 1.15 and sg > sb * 1.08:
                    color = "green"
    confirmed = status(candidate) == "confirmed" and color != "unknown"
    value: dict[str, Any] = {
        "entityKind": kind, "visualStatus": "confirmed" if confirmed else "uncertain",
        "isColored": color not in {"neutral", "unknown"}, "isShaped": False,
        "colorRole": color, "backgroundColor": background_color, "textColor": exact_text_color, "borderColor": "",
        "hasGraphicAssist": False, "graphicType": "无", "styleKey": f"{kind}|{color}|{role or 'other'}|无容器|无",
        "sourceRegion": region, "colorEvidence": hint.get("evidence", "not_measured") if isinstance(hint, dict) else "not_measured",
    }
    if kind in {"tag", "icon"} and confirmed:
        raw = str(candidate.get("text", ""))
        semantic_role = "券标" if re.search(r"神券|券", raw) else "履约标" if re.search(r"外卖|配送|到店|上门", raw) else "业务类型标" if re.search(r"演出|景点", raw) else "推荐标" if re.search(r"推荐|必玩", raw) else role or "其他标签"
        value.update({"semanticRole": semantic_role, "containerShape": container_shape,
                      "graphicAssistRole": "无", "countedInComplexity": value["isColored"],
                      "dedupWithElementIds": []})
        value["styleKey"] = f"{kind}|{color}|{semantic_role}|{container_shape}|无"
    return value


def text_element(card_id: str, item: dict[str, Any], semantic: dict[str, Any], index: int) -> tuple[str, dict[str, Any]]:
    role = semantic.get("semanticRoleCandidate", "other")
    region = semantic.get("regionCandidate", "基础信息区")
    element_type = "标签" if role == "tag" else "文本"
    visible = status(item)
    direct = item.get("phase3Facts", {}) if isinstance(item.get("phase3Facts"), dict) else {}
    render = dict(direct.get("render", {}))
    render.update({"visibleStatus": visible, "renderState": "normal" if visible == "confirmed" else "uncertain", "sourceRegion": region, "isPhoto": False, "isSystemUi": True})
    element: dict[str, Any] = {
        "id": f"{card_id}-T{index}", "所属组件": card_id, "元素类型": element_type,
        "内容简述": f"原文:{item.get('text', '')}", "坐标": item["coord"], "isExcluded": False, "excludeReason": "",
        "render": render,
    }
    if element_type == "文本":
        facts = dict(direct.get("textFacts", {}))
        color = item.get("visualHint", {}).get("colorRole", facts.get("textColorRole", "unknown"))
        facts.update({"rawText": item.get("text", ""), "textStatus": "complete" if visible == "confirmed" else "uncertain",
                      "semanticRole": role, "emphasisLevel": "primary" if role in {"title", "price"} else "secondary", "textColorRole": color})
        facts.setdefault("fontSizeBucket", "unknown"); facts.setdefault("fontWeightBucket", "unknown")
        element["textFacts"] = facts
        visual = dict(direct.get("visual", {}))
        if not visual:
            visual = visual_hint(item, "text", region, role)
        visual.update({"entityKind": "text", "sourceRegion": region, "styleKey": f"text|{color}|{role or 'other'}|无容器|无"})
        element["visual"] = visual
    else:
        element["visual"] = visual_hint(item, "tag", region, "其他标签")
    return region, element


def image_element(card_id: str, item: dict[str, Any], index: int, region: str = "头图区") -> dict[str, Any]:
    visible = status(item)
    direct = item.get("phase3Facts", {}) if isinstance(item.get("phase3Facts"), dict) else {}
    render = dict(direct.get("render", {})); render.update({"visibleStatus": visible, "renderState": "normal" if visible == "confirmed" else "uncertain", "sourceRegion": region, "isPhoto": True, "isSystemUi": False})
    visual = dict(direct.get("visual", {})) or visual_hint(item, "image", region, "photo")
    visual.update({"entityKind": "image", "sourceRegion": region, "styleKey": f"image|unknown|photo|{region}|无"})
    return {"id": f"{card_id}-P{index}", "所属组件": card_id, "元素类型": "图片",
        "内容简述": "原文:图片", "坐标": item["coord"], "isExcluded": False, "excludeReason": "",
        "render": render, "visual": visual}


def append_item_groups(region: str, elements: list[dict[str, Any]], card_type: str) -> list[dict[str, Any]]:
    """Keep image/text/price facts owned by one visible appended item.

    The flat ``elements`` array remains for Phase3 compatibility; itemGroups is
    the lossless ownership layer and every appended element must occur in
    exactly one group.  Text-hang rows are clustered vertically. Graphic-hang
    products use their image columns as anchors.
    """
    if region not in {"下挂商品区", "文字下挂区", "下挂区", "服务下挂"} or not elements:
        return []
    images = [item for item in elements if item.get("元素类型") == "图片"]
    texts = [item for item in elements if item.get("元素类型") != "图片"]
    anchors: list[list[dict[str, Any]]]
    if card_type == "商家卡片_图文下挂" and images:
        anchors = [[item] for item in sorted(images, key=lambda value: value["坐标"][0])]
        for item in texts:
            center = item["坐标"][0] + item["坐标"][2] / 2
            target = min(anchors, key=lambda group: abs(center - (group[0]["坐标"][0] + group[0]["坐标"][2] / 2)))
            target.append(item)
    else:
        anchors = []
        for item in sorted(elements, key=lambda value: (value["坐标"][1], value["坐标"][0])):
            center = item["坐标"][1] + item["坐标"][3] / 2
            target = next((group for group in anchors if abs(center - sum(value["坐标"][1] + value["坐标"][3] / 2 for value in group) / len(group)) <= max(item["坐标"][3], 28)), None)
            if target is None:
                anchors.append([item])
            else:
                target.append(item)
    groups = []
    for index, members in enumerate(anchors, 1):
        # The first element was accidentally duplicated by neither branch: the
        # expression above appends only when an existing row is found.
        members = list(dict.fromkeys(item["id"] for item in members))
        resolved = [next(item for item in elements if item["id"] == member_id) for member_id in members]
        image_ids = [item["id"] for item in resolved if item.get("元素类型") == "图片"]
        price_ids = [item["id"] for item in resolved if item.get("textFacts", {}).get("semanticRole") == "price"]
        text_ids = [item["id"] for item in resolved if item["id"] not in image_ids and item["id"] not in price_ids]
        groups.append({
            "itemIndex": index,
            "coord": union([item["坐标"] for item in resolved], resolved[0]["坐标"]),
            "elementIds": [item["id"] for item in resolved],
            "imageElementIds": image_ids,
            "textElementIds": text_ids,
            "priceElementIds": price_ids,
            "visibleStatus": "confirmed" if all(item.get("render", {}).get("visibleStatus") == "confirmed" for item in resolved) else "uncertain",
        })
    return groups


def build_card(candidate: dict[str, Any], semantic: dict[str, Any], facts: dict[str, Any], text_semantics: dict[str, Any]) -> dict[str, Any]:
    card_id, coord = candidate["id"], candidate["coord"]
    selected = semantic.get("selectedCardType", {})
    selected_type = selected.get("cardType", "")
    confirmed_type = selected.get("status") == "confirmed"
    card_type = TYPE_NAMES.get(selected_type, "异构卡")
    regions: dict[str, list[dict[str, Any]]] = {}
    text_candidates = [x for x in facts["candidates"]["text"] if overlap(x["coord"], coord)]
    photo_candidates = [x for x in facts["candidates"]["photos"] if overlap(x["coord"], coord)]
    semantic_by_source = card_local_semantics(
        candidate, selected_type, text_candidates,
        {item.get("sourceId"): item for item in text_semantics.get("candidates", [])},
    )
    unresolved_ids = [item["id"] for item in text_candidates + photo_candidates if status(item) != "confirmed"]
    for index, item in enumerate(text_candidates, 1):
        source_semantic = semantic_by_source.get(item["id"], {})
        if not usable_text(item, source_semantic):
            continue
        item = {**item, "coord": clip(item["coord"], coord)}
        if item["coord"] is None:
            continue
        region, element = text_element(card_id, item, source_semantic, index)
        regions.setdefault(region, []).append(element)
    head_photo_id = str(candidate.get("headPhotoId", ""))
    attached_photo_ids = {str(value) for value in candidate.get("attachedProductPhotoIds", [])}
    emitted_head_image_ids: list[str] = []
    for index, item in enumerate(photo_candidates, 1):
        if status(item) != "confirmed":
            continue
        if item["id"] in attached_photo_ids:
            image_region = "下挂商品区"
        elif item["id"] == head_photo_id or (not head_photo_id and not emitted_head_image_ids):
            image_region = "头图区"
        else:
            image_region = "特殊下挂"
        item = {**item, "coord": clip(item["coord"], coord)}
        if item["coord"] is None:
            continue
        element = image_element(card_id, item, index, image_region)
        regions.setdefault(image_region, []).append(element)
        if image_region == "头图区":
            emitted_head_image_ids.append(element["id"])
    if not regions:
        regions["基础信息区"] = []
    region_rows = []
    for name, region_elements in regions.items():
        row = {"name": name, "coord": union([e["坐标"] for e in region_elements], coord), "elements": region_elements}
        groups = append_item_groups(name, region_elements, selected_type)
        if groups:
            row["itemGroups"] = groups
        region_rows.append(row)
    elements = [element for row in region_rows for element in row["elements"]]
    uncertain = unresolved_ids + [element["id"] for element in elements if element["render"]["visibleStatus"] != "confirmed"]
    titles = [e for e in elements if e.get("textFacts", {}).get("semanticRole") == "title"]
    head_images = [e for row in region_rows if row["name"] == "头图区" for e in row["elements"] if e["元素类型"] == "图片"]
    inventory_regions = {row["name"]: [{"elementId": e["id"], "styleKey": e.get("visual", {}).get("styleKey", ""), "countedInComplexity": bool(e.get("visual", {}).get("countedInComplexity", False))} for e in row["elements"] if e.get("visual", {}).get("entityKind") in {"tag", "icon"}] for row in region_rows}
    tags = [e for e in elements if e.get("visual", {}).get("entityKind") in {"tag", "icon"}]
    complete = confirmed_type and not uncertain and bool(elements)
    partial = semantic.get("partialCardPolicy", {}).get("applied") is True
    classification_evidence = selected.get("evidence", [])
    if not isinstance(classification_evidence, list):
        classification_evidence = []
    classification_evidence = [str(item) for item in classification_evidence if str(item).strip()] or ["phase2_local_cv_card_candidate"]
    layout_mode = "left_image_right_text" if selected_type in {
        "商品卡片", "商家卡片_图文下挂", "商家卡片_文字下挂", "酒店卡片", "演出电影卡片", "度假酒店套餐卡片"
    } and bool(head_images) else "other"
    return {"cardId": card_id, "卡片类型": card_type, "coord": coord, "regions": region_rows,
        "ownershipScope": "unknown", "businessCode": "unknown", "businessName": "", "businessConfidence": "unknown",
        "cardTypeCode": selected_type or "unknown", "cardTypeName": card_type, "resultType": "result_card",
        "classificationEvidence": classification_evidence,
        "structure": {"visibleStatus": "naturally_cropped" if partial else "complete" if complete else "uncertain", "cardTypeCode": selected_type or "unknown",
            "layoutMode": layout_mode,
            "layoutSignature": "cv_candidate", "comparisonGroupKey": f"{selected_type or 'unknown'}|cv_candidate",
            "isResultListItem": True, "isHeterogeneous": card_type == "异构卡", "listPosition": int(card_id.removeprefix("C")) if card_id.removeprefix("C").isdigit() else 0,
            "regions": [{"region": row["name"], "coord": row["coord"], "visibleStatus": "confirmed" if row["elements"] else "uncertain", "hasPhysicalBoundary": False, "hasBackgroundSeparation": False} for row in region_rows]},
        "factInventory": {"complete": complete, "scanned": ["card_boundary", "regions", "images", "text", "render_state", "visual_spec", "layout", "relations"], "uncertainElementIds": uncertain, "notes": ["assembled_from_local_cv_candidates"] + (["bottom_partial_card_type_inherited_from_previous_confirmed_repeated_type"] if partial else [])},
        "visualInventory": {"complete": complete and all(e.get("visual", {}).get("visualStatus") == "confirmed" for e in tags), "regions": inventory_regions,
            "tagScanChecklist": [{"candidate": "local_cv_tag_icon_candidates", "status": "found" if tags else "not_found", "checkedRegions": list(regions), "elementIds": [e["id"] for e in tags]}]},
        "_relations": (
            [{"relationType": "title_to_image", "from": title["id"], "to": image["id"], "status": "confirmed"} for title in titles for image in head_images]
            + [{"relationType": "title_to_append", "from": title["id"], "to": element_id, "status": "confirmed"}
               for title in titles for row in region_rows for group in row.get("itemGroups", []) for element_id in group["elementIds"]]
        )}


def recognition_state(facts: dict[str, Any], card_semantics: dict[str, Any], gate: dict[str, Any] | None, card_ids: list[str]) -> dict[str, Any]:
    if gate is None:
        selected = [item.get("selectedCardType", {}) for item in card_semantics.get("cards", [])]
        derived_valid = bool(selected) and all(item.get("status") == "confirmed" for item in selected) and not facts.get("routing", {}).get("unresolvedCandidateIds", [])
        gate = {"valid": derived_valid, "errors": [] if derived_valid else ["recognition_gate_not_supplied_or_derived_incomplete"],
                "semanticHookFindings": [], "reprocessTargets": [], "reprocess": []}
    valid = gate.get("valid") is True
    errors = [str(item) for item in gate.get("errors", [])]
    blocking = sorted({match.group(1) for error in errors if (match := re.match(r"^(C\d+):", error))})
    if not valid and not blocking:
        blocking = list(card_ids)
    return {
        "contractVersion": VERSION,
        "status": "confirmed" if valid else "blocked",
        "phase3Ready": valid,
        "wholePageGate": True,
        "blockingCardIds": blocking,
        "backends": facts.get("backends", {}),
        "errors": errors,
        "semanticHookFindings": gate.get("semanticHookFindings", []),
        "reprocessTargets": gate.get("reprocessTargets", []),
        "reprocess": gate.get("reprocess", []),
    }


def build(query: str, facts: dict[str, Any], candidates: dict[str, Any], card_semantics: dict[str, Any], text_semantics: dict[str, Any], gate: dict[str, Any] | None = None) -> dict[str, Any]:
    semantic_by_card = {item["cardId"]: item for item in card_semantics.get("cards", [])}
    cards = [build_card(card, semantic_by_card.get(card["id"], {}), facts, text_semantics) for card in candidates.get("resultCards", [])]
    relations = [relation for card in cards for relation in card.pop("_relations")]
    modules = [{"id": f"M{i}", "moduleType": module.get("module", "other"), "coord": module["coord"], "visibleStatus": module.get("status", "uncertain"), "contentRole": ";".join(module.get("evidence", [])), "isListPrefix": False, "isListItem": False} for i, module in enumerate(candidates.get("pageModules", []), 1)]
    modules.append({"id": f"M{len(modules)+1}", "moduleType": "result_list", "coord": union([card["coord"] for card in cards], [0, 0, facts["viewport"]["width"], facts["viewport"]["height"]]), "visibleStatus": "confirmed" if cards else "uncertain", "contentRole": "结果供给", "isListPrefix": False, "isListItem": False})
    recognition = recognition_state(facts, card_semantics, gate, [card["cardId"] for card in cards])
    return {"query": query, "screenshot": facts["screenshot"], "annotatedImage": "", "cards": cards,
        "recognition": recognition,
        "pageFacts": {"screen": 1, "isContinuation": False, "viewport": facts["viewport"], "modules": modules},
        "pageFactInventory": {"complete": bool(cards) and recognition["phase3Ready"], "scanned": ["modules", "result_cards", "cv_candidates", "whole_page_gate"], "uncertainElementIds": list(facts.get("routing", {}).get("unresolvedCandidateIds", [])), "notes": ["assembled_from_phase2_cv_facts.v1", f"recognition:{recognition['status']}"]},
        "relations": relations}


def recognition_audit(query: str, screenshot: str, manifest: str, facts: dict[str, Any], cards: list[dict[str, Any]]) -> dict[str, Any]:
    """Record both accepted and unresolved recognition without inventing elements."""
    fields: list[dict[str, str]] = []
    for card in cards:
        card_id, bounds = card["cardId"], card["coord"]
        for kind in ("text", "photos"):
            for item in facts["candidates"].get(kind, []):
                if not overlap(item["coord"], bounds):
                    continue
                raw = str(item.get("text", "图片"))
                fields.append({"cardId": card_id, "elementId": item.get("id", ""), "field": "visible_text" if kind == "text" else "photo",
                    "visibleText": raw, "status": status(item), "source": "full_image",
                    "reason": "accepted local candidate" if status(item) == "confirmed" else "kept as unresolved local candidate; not emitted as a confirmed Phase3 element"})
                if kind == "text" and isinstance(item.get("visualHint"), dict):
                    fields.append({"cardId": card_id, "elementId": item.get("id", ""), "field": "color_role",
                        "visibleText": str(item["visualHint"].get("colorRole", "unknown")), "status": status(item), "source": "full_image",
                        "reason": "local foreground-pixel colour estimate; requires local review before any stronger visual conclusion"})
    return {"query": query, "screenshot": screenshot, "manifest": manifest, "fullImageReadCount": 1,
        "localReviewReadCount": 0, "totalImageReadCount": 1, "fields": fields}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a Phase3-ready element manifest from Phase2 candidate JSON")
    parser.add_argument("--query", required=True); parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--result-candidates", type=Path, required=True); parser.add_argument("--card-semantics", type=Path, required=True)
    parser.add_argument("--text-semantics", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recognition-gate", type=Path, help="Embed the whole-page recognition gate in the canonical manifest")
    parser.add_argument("--recognition-audit", type=Path, help="Write the corresponding Phase2 recognition audit")
    args = parser.parse_args()
    gate = json.loads(args.recognition_gate.read_text(encoding="utf-8")) if args.recognition_gate else None
    payload = build(args.query, *(json.loads(path.read_text(encoding="utf-8")) for path in (args.facts, args.result_candidates, args.card_semantics, args.text_semantics)), gate)
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.recognition_audit:
        args.recognition_audit.parent.mkdir(parents=True, exist_ok=True)
        audit = recognition_audit(args.query, payload["screenshot"], str(args.output), json.loads(args.facts.read_text(encoding="utf-8")), payload["cards"])
        args.recognition_audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "cards": len(payload["cards"]), "phase3Ready": payload["recognition"]["phase3Ready"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
