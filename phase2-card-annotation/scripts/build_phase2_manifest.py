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
    return bool(raw) and (status(candidate) == "confirmed" or semantic.get("status") == "confirmed")


def visual_hint(candidate: dict[str, Any], kind: str, region: str, role: str = "") -> dict[str, Any]:
    hint = candidate.get("visualHint", {})
    color = hint.get("colorRole", "unknown") if isinstance(hint, dict) else "unknown"
    median = hint.get("medianRgb") if isinstance(hint, dict) else None
    exact_text_color = ""
    if isinstance(median, list) and len(median) == 3 and all(isinstance(channel, int) and 0 <= channel <= 255 for channel in median):
        exact_text_color = "#" + "".join(f"{channel:02X}" for channel in median)
    confirmed = status(candidate) == "confirmed" and color != "unknown"
    value: dict[str, Any] = {
        "entityKind": kind, "visualStatus": "confirmed" if confirmed else "uncertain",
        "isColored": color not in {"neutral", "unknown"}, "isShaped": False,
        "colorRole": color, "backgroundColor": "", "textColor": exact_text_color, "borderColor": "",
        "hasGraphicAssist": False, "graphicType": "无", "styleKey": f"{kind}|{color}|{role or 'other'}|无容器|无",
        "sourceRegion": region, "colorEvidence": hint.get("evidence", "not_measured") if isinstance(hint, dict) else "not_measured",
    }
    if kind in {"tag", "icon"} and confirmed:
        value.update({"semanticRole": role or "其他标签", "containerShape": "无容器",
                      "graphicAssistRole": "无", "countedInComplexity": value["isColored"],
                      "countDecision": "本地 OCR 与颜色候选确认的独立标签文本",
                      "dedupDecision": "未与其他实体去重", "dedupWithElementIds": []})
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
    visual.update({"entityKind": "image", "sourceRegion": region})
    return {"id": f"{card_id}-P{index}", "所属组件": card_id, "元素类型": "图片",
        "内容简述": "原文:图片", "坐标": item["coord"], "isExcluded": False, "excludeReason": "",
        "render": render, "visual": visual}


def build_card(candidate: dict[str, Any], semantic: dict[str, Any], facts: dict[str, Any], text_semantics: dict[str, Any]) -> dict[str, Any]:
    card_id, coord = candidate["id"], candidate["coord"]
    selected = semantic.get("selectedCardType", {})
    selected_type = selected.get("cardType", "")
    confirmed_type = selected.get("status") == "confirmed"
    card_type = TYPE_NAMES.get(selected_type, "异构卡")
    semantic_by_source = {item.get("sourceId"): item for item in text_semantics.get("candidates", [])}
    regions: dict[str, list[dict[str, Any]]] = {}
    text_candidates = [x for x in facts["candidates"]["text"] if overlap(x["coord"], coord)]
    photo_candidates = [x for x in facts["candidates"]["photos"] if overlap(x["coord"], coord)]
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
    for index, item in enumerate(photo_candidates, 1):
        if status(item) != "confirmed":
            continue
        item = {**item, "coord": clip(item["coord"], coord)}
        if item["coord"] is None:
            continue
        regions.setdefault("头图区", []).append(image_element(card_id, item, index))
    if not regions:
        regions["基础信息区"] = []
    region_rows = [{"name": name, "coord": union([e["坐标"] for e in elements], coord), "elements": elements} for name, elements in regions.items()]
    elements = [element for row in region_rows for element in row["elements"]]
    uncertain = unresolved_ids + [element["id"] for element in elements if element["render"]["visibleStatus"] != "confirmed"]
    titles = [e for e in elements if e.get("textFacts", {}).get("semanticRole") == "title"]
    images = [e for e in elements if e["元素类型"] == "图片"]
    inventory_regions = {row["name"]: [{"elementId": e["id"], "styleKey": e.get("visual", {}).get("styleKey", ""), "countedInComplexity": bool(e.get("visual", {}).get("countedInComplexity", False))} for e in row["elements"] if e.get("visual", {}).get("entityKind") in {"tag", "icon"}] for row in region_rows}
    tags = [e for e in elements if e.get("visual", {}).get("entityKind") in {"tag", "icon"}]
    complete = confirmed_type and not uncertain and bool(elements)
    partial = semantic.get("partialCardPolicy", {}).get("applied") is True
    classification_evidence = selected.get("evidence", [])
    if not isinstance(classification_evidence, list):
        classification_evidence = []
    classification_evidence = [str(item) for item in classification_evidence if str(item).strip()] or ["phase2_local_cv_card_candidate"]
    return {"cardId": card_id, "卡片类型": card_type, "coord": coord, "regions": region_rows,
        "ownershipScope": "unknown", "businessCode": "unknown", "businessName": "", "businessConfidence": "unknown",
        "cardTypeCode": selected_type or "unknown", "cardTypeName": card_type, "resultType": "result_card",
        "classificationEvidence": classification_evidence,
        "structure": {"visibleStatus": "naturally_cropped" if partial else "complete" if complete else "uncertain", "cardTypeCode": selected_type or "unknown",
            "layoutMode": next((r.get("layoutCandidate") for r in semantic.get("regions", []) if r.get("region") == "头图区"), "other"),
            "layoutSignature": "cv_candidate", "comparisonGroupKey": f"{selected_type or 'unknown'}|cv_candidate",
            "isResultListItem": True, "isHeterogeneous": card_type == "异构卡", "listPosition": int(card_id.removeprefix("C")) if card_id.removeprefix("C").isdigit() else 0,
            "regions": [{"region": row["name"], "coord": row["coord"], "visibleStatus": "confirmed" if row["elements"] else "uncertain", "hasPhysicalBoundary": False, "hasBackgroundSeparation": False} for row in region_rows]},
        "factInventory": {"complete": complete, "scanned": ["card_boundary", "regions", "images", "text", "render_state", "visual_spec", "layout", "relations"], "uncertainElementIds": uncertain, "notes": ["assembled_from_local_cv_candidates"] + (["bottom_partial_card_type_inherited_from_previous_confirmed_merchant_card"] if partial else [])},
        "visualInventory": {"complete": complete and all(e.get("visual", {}).get("visualStatus") == "confirmed" for e in tags), "regions": inventory_regions,
            "tagScanChecklist": [{"candidate": "local_cv_tag_icon_candidates", "status": "found" if tags else "not_found", "checkedRegions": list(regions), "elementIds": [e["id"] for e in tags], "visualBasis": "local CV/OCR candidate scan"}]},
        "_relations": [{"relationType": "title_to_image", "from": title["id"], "to": image["id"], "status": "uncertain", "evidence": "same card only; local CV cannot confirm semantic correspondence"} for title in titles for image in images]}


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
