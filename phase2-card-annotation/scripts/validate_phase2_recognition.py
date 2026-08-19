#!/usr/bin/env python3
"""Block bad CV recognition before it becomes a Phase3 manifest.

This is a batch gate, not a per-field confidence router: it never asks a
vision model to read rejected OCR.  A failure means re-run the local CV/OCR
pipeline with another bounded configuration, or stop the batch.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from recognition_gate_hooks import run_hooks


def overlap(a: list[int], b: list[int]) -> bool:
    return a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and a[1] < b[1] + b[3] and a[1] + a[3] > b[1]


def malformed_text(value: str) -> bool:
    compact = value.strip()
    meaningful = [char for char in compact if char.isalnum() or "\u4e00" <= char <= "\u9fff"]
    return not meaningful or (len(meaningful) == 1 and not meaningful[0].isdigit()) or any(token in compact for token in ("[[", "]]", "{{", "}}"))


def _role_from_card_region(region_name: str) -> str | None:
    mappings = (
        ("标题", "title"), ("价格", "price"), ("评分", "rating"),
        ("位置", "location"), ("履约", "fulfillment"), ("销量", "sales"),
    )
    return next((role for marker, role in mappings if marker in region_name), None)


def _structured_role_dominates_text(role: str, value: str) -> bool:
    """Allow page hints to override a card region only for field-shaped text.

    OCR often merges a merchant title with a trailing delivery time.  A weak
    substring match must not turn that whole title into a fulfillment field.
    """
    text = value.strip()
    compact = re.sub(r"\s+", "", text)
    rules = {
        "location": r"^\d+(?:\.\d+)?(?:km|公里|m|米)$",
        "rating": r"^(?:\d(?:\.\d)?分|暂无评分)$",
        "sales": r"^(?:月售|已售|年售|回购|加购).{0,10}\d.{0,3}$",
        "fulfillment": r"^(?:(?:约)?\d{1,3}分钟|.{0,4}(?:配送|送达|自取|上门|到店|外卖).{0,6})$",
        "price": r"^(?:[¥￥#Yy]\s*\d|(?:到手价|神价|低价|券后价?|票价|起价)[:：]?\s*[¥￥#Yy]?\d)",
        "tag": r"^.{1,8}$",
    }
    pattern = rules.get(role)
    return bool(pattern and re.search(pattern, compact, re.I))


def gate(facts: dict[str, Any], candidates: dict[str, Any], card_semantics: dict[str, Any], text_semantics: dict[str, Any]) -> dict[str, Any]:
    text = facts.get("candidates", {}).get("text", [])
    accepted = [item for item in text if item.get("route") == "accepted"]
    rejected = [item for item in text if item.get("route") == "rejected"]
    malformed = [item for item in accepted if malformed_text(str(item.get("text", "")))]
    cards = candidates.get("resultCards", [])
    semantics = {item.get("cardId"): item for item in card_semantics.get("cards", [])}
    all_semantic_candidates = {item.get("sourceId"): item for item in text_semantics.get("candidates", [])}
    mapped = {source_id: item for source_id, item in all_semantic_candidates.items() if item.get("status") == "confirmed"}
    # Card-local region mapping is more precise than page-block position for
    # titles/prices on tall cards. Reuse only confirmed region evidence and
    # still send the underlying OCR text through every semantic hook below.
    accepted_by_id = {item.get("id"): item for item in accepted}
    text_ids = set(accepted_by_id)
    for semantic_card in card_semantics.get("cards", []):
        for region in semantic_card.get("regions", []):
            if region.get("status") != "confirmed":
                continue
            role = _role_from_card_region(str(region.get("region", "")))
            if not role:
                continue
            for source_id in region.get("evidenceSourceIds", []):
                if source_id in text_ids and source_id not in mapped:
                    source_role = role
                    page_hint = all_semantic_candidates.get(source_id, {})
                    hinted_role = page_hint.get("semanticRoleCandidate")
                    source_text = str(accepted_by_id.get(source_id, {}).get("text", ""))
                    if (hinted_role in {"price", "rating", "sales", "location", "fulfillment", "tag"}
                            and float(page_hint.get("confidence", 0)) >= 0.72
                            and _structured_role_dominates_text(str(hinted_role), source_text)):
                        source_role = str(hinted_role)
                    mapped[source_id] = {
                        "sourceId": source_id, "semanticRoleCandidate": source_role, "status": "confirmed",
                        "evidence": ["confirmed_card_region_evidence"],
                    }
    errors: list[str] = []
    reprocess: list[str] = []
    if not accepted:
        errors.append("no_usable_ocr_text")
        reprocess.append("使用本地 PaddleOCR 对已定位的卡片文字列分区识别；不得将整页送入模型。")
    if text and len(rejected) / len(text) > 0.25:
        errors.append(f"ocr_fragment_rejection_ratio_exceeds_25_percent:{len(rejected)}/{len(text)}")
        reprocess.append("OCR 碎片过多：更换本地 OCR 版面模式或做卡片级行合并后重跑。")
    if malformed:
        errors.append(f"malformed_text_published:{','.join(str(item.get('id')) for item in malformed)}")
        reprocess.append("清除异常标点/单字碎片后重跑；不得把碎片直接写入 Phase3 元素。")
    if not cards:
        errors.append("no_result_cards")
        reprocess.append("重跑页面结构与结果卡边界识别。")
    for card in cards:
        card_id, bounds = str(card.get("id", "")), card.get("coord", [])
        local_text = [item for item in accepted if isinstance(bounds, list) and len(bounds) == 4 and overlap(item["coord"], bounds)]
        semantic_card = semantics.get(card_id, {})
        card_type = semantic_card.get("selectedCardType", {})
        partial_allowed = semantic_card.get("partialCardPolicy", {}).get("applied") is True
        if len(local_text) < 2 and not partial_allowed:
            errors.append(f"{card_id}:insufficient_usable_text")
        if card_type.get("status") != "confirmed":
            errors.append(f"{card_id}:card_type_unresolved")
        contract_validation = semantic_card.get("contractValidation")
        if isinstance(contract_validation, dict) and contract_validation.get("minimumSatisfied") is not True and not partial_allowed:
            errors.append(f"{card_id}:known_or_fallback_contract_not_satisfied")
        # A card needs at least one deterministic semantic anchor. It may be a
        # title, price, rating, fulfillment, or tag; exact field requirements
        # are card-type-specific and remain Phase3-neutral here.
        if not any(item.get("id") in mapped for item in local_text) and not partial_allowed:
            errors.append(f"{card_id}:no_confirmed_semantic_anchor")
    facts_by_id = {item.get("id"): item for item in accepted}
    semantic_items = [{"sourceId": source_id, "text": str(facts_by_id.get(source_id, {}).get("text", item.get("text", ""))), "role": str(item.get("semanticRoleCandidate", "other"))} for source_id, item in mapped.items()]
    roles_by_card: dict[str, set[str]] = {}
    for card in cards:
        card_id, bounds = str(card.get("id", "")), card.get("coord", [])
        roles_by_card[card_id] = {item["role"] for item in semantic_items if item["sourceId"] in facts_by_id and isinstance(bounds, list) and len(bounds) == 4 and overlap(facts_by_id[item["sourceId"]]["coord"], bounds)}
    hook_findings = run_hooks({"semanticItems": semantic_items, "factsById": facts_by_id, "acceptedText": accepted,
                               "rolesByCard": roles_by_card, "cards": cards, "cardSemantics": semantics})
    errors.extend(f"semantic_hook:{item['hook']}:{item['sourceId']}:{item['reason']}" for item in hook_findings)
    role_by_source = {item["sourceId"]: item["role"] for item in semantic_items}
    reprocess_targets = [
        {"sourceId": item["sourceId"], "role": role_by_source.get(item["sourceId"], ""), "hook": item["hook"], "reason": item["reason"], "action": "rerun_bounded_local_ocr_or_rebuild_card_boundary"}
        for item in hook_findings
    ]
    if hook_findings:
        reprocess.append("仅对 semanticHookFindings 中的 sourceId 重跑裁剪 OCR/卡边界；语言纠错候选只能作为异常信号，不得改写原文。")
    if any(error.endswith(("insufficient_usable_text", "no_confirmed_photo_candidate", "card_type_unresolved", "no_confirmed_semantic_anchor")) for error in errors):
        reprocess.append("按失败卡逐卡重跑本地 CV/OCR；只复用当前截图的卡片边界，禁止跨图坐标套用。")
    return {
        "contractVersion": "phase2.recognition-gate.v1", "valid": not errors,
        "summary": {"ocrTextCandidates": len(text), "acceptedTextCandidates": len(accepted), "rejectedTextCandidates": len(rejected), "resultCards": len(cards)},
        "errors": errors, "semanticHookFindings": hook_findings, "reprocessTargets": reprocess_targets, "reprocess": reprocess,
        "rule": "No model-reading escalation. Gate failure blocks manifest publication and requires local CV/OCR reprocessing.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate Phase2 CV recognition before manifest publication")
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--result-candidates", type=Path, required=True)
    parser.add_argument("--card-semantics", type=Path, required=True)
    parser.add_argument("--text-semantics", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = gate(*(json.loads(path.read_text(encoding="utf-8")) for path in (args.facts, args.result_candidates, args.card_semantics, args.text_semantics)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
