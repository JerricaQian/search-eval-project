#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase2 元素清单遗漏走查。

本审计以清单事实为输入，输出两类结果：
1. 坐标边界告警：元素未落在所属卡范围内时必须复核；历史清单可能存在分区框偏差，
   因此先作为告警，不把它误判成元素缺失。
2. 履约类型识别：仅以卡内的最小独立标签识别十类标准履约标：到店、外卖、快递、
   酒店、民宿、景点、旅游、演出、上门、在线。外卖卡额外检查配送时效、起送/配送费、
   距离；其他履约类型不套用外卖字段规则。

未声明履约标签的业务卡进入 `manualReview` 队列，必须结合原图复核后才能作为
“无履约信息”的结论使用，避免用清单遗漏反过来证明页面没有该信息。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image

TIME_RE = re.compile(r"(?:\d{1,3}\s*分钟|约\s*\d{1,3}\s*分)")
DELIVERY_RE = re.compile(r"(?:起送|配送费|免配送费)")
DISTANCE_RE = re.compile(r"(?:\d+(?:\.\d+)?\s*(?:km|公里|m|米))", re.IGNORECASE)
# 履约标的唯一标准分类。键为 Phase2/Phase3 使用的标准值；值为历史与业务文案兼容别名。
FULFILMENT_TYPE_ALIASES = {
    "到店": {"到店", "团购"},
    "外卖": {"外卖", "闪购", "美团专送", "专送"},
    "快递": {"快递"},
    "酒店": {"酒店"},
    "民宿": {"民宿"},
    "景点": {"景点"},
    "旅游": {"旅游", "旅游产品"},
    "演出": {"演出", "电影"},
    "上门": {"上门"},
    "在线": {"在线"},
}
DELIVERY_FIELD_FULFILMENT_TYPES = {"外卖"}
TEXT_TYPES = {"文本", "标签"}


def within(inner: list[float], outer: list[float]) -> bool:
    x, y, w, h = inner
    ox, oy, ow, oh = outer
    return ox <= x and oy <= y and x + w <= ox + ow and y + h <= oy + oh


def is_business_card(card: dict[str, Any]) -> bool:
    return card.get("卡片类型") in {
        "商品卡片", "商家卡片-图文下挂", "商家卡片-文字下挂", "商家卡片-无下挂",
        "演出/电影卡片", "主点卡片",
    }


def active_elements(card: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        element
        for region in card.get("regions", [])
        for element in region.get("elements", [])
        if not element.get("isExcluded") and element.get("元素类型") in TEXT_TYPES
    ]


def card_text(elements: list[dict[str, Any]]) -> str:
    return " ".join(str(element.get("内容简述", "")).removeprefix("原文:") for element in elements)


def detect_fulfilment_types(elements: list[dict[str, Any]]) -> list[str]:
    labels = {
        str(element.get("内容简述", "")).removeprefix("原文:").strip()
        for element in elements
    }
    return [
        fulfilment_type
        for fulfilment_type, aliases in FULFILMENT_TYPE_ALIASES.items()
        if labels & aliases
    ]


def infer_fulfilment_types(card: dict[str, Any], elements: list[dict[str, Any]]) -> list[str]:
    """Use explicit labels first; otherwise infer only from current-card transactional evidence."""
    explicit = detect_fulfilment_types(elements)
    if explicit:
        return explicit
    text = f"{card.get('卡片类型', '')} {card_text(elements)}"
    if DELIVERY_RE.search(text) or TIME_RE.search(text):
        return ["外卖"]
    if any(token in text for token in ("随时退", "过期退", "套餐", "团购")):
        return ["到店"]
    return []


def audit_manifest(manifest_path: Path, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    if manifest is None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []
    manual_review: list[dict[str, str]] = []
    checked_cards: list[dict[str, Any]] = []
    screenshot_path = Path(str(manifest.get("screenshot", "")))
    screenshot_height: int | None = None
    if screenshot_path.is_file():
        with Image.open(screenshot_path) as screenshot:
            screenshot_height = screenshot.height
    else:
        warnings.append(f"screenshot_not_found_for_crop_check:{screenshot_path}")

    for card in manifest.get("cards", []):
        card_id = str(card.get("cardId", ""))
        elements = active_elements(card)
        text = card_text(elements)
        geometry_errors = [
            element["id"] for element in elements
            if is_business_card(card) and isinstance(element.get("坐标"), list)
            and isinstance(card.get("coord"), list) and not within(element["坐标"], card["coord"])
        ]
        if geometry_errors:
            warnings.append(f"{card_id}:active_element_outside_card:{','.join(geometry_errors)}")

        fulfilment_types = infer_fulfilment_types(card, elements) if is_business_card(card) else []
        has_fulfilment = bool(fulfilment_types)
        requires_delivery_fields = bool(set(fulfilment_types) & DELIVERY_FIELD_FULFILMENT_TYPES)
        has_time = bool(TIME_RE.search(text))
        has_delivery = bool(DELIVERY_RE.search(text))
        has_distance = bool(DISTANCE_RE.search(text))
        checked_cards.append({
            "cardId": card_id,
            "fulfilmentTypes": fulfilment_types,
            "hasFulfilment": has_fulfilment,
            "hasTime": has_time,
            "hasDeliveryFeeOrMinimum": has_delivery,
            "hasDistance": has_distance,
        })
        card_coord = card.get("coord") or [0, 0, 0, 0]
        is_bottom_cropped = screenshot_height is not None and card_coord[1] + card_coord[3] >= screenshot_height
        if requires_delivery_fields and (screenshot_height is None or is_bottom_cropped):
            reason = "原始截图不可用，不能根据不完整清单把履约字段判定为页面缺失。"
            if is_bottom_cropped:
                reason = "履约卡触及截图底部，起送/配送费/距离可能在截图外；仅可人工确认当前可见区域，不能自动判定缺失。"
            manual_review.append({"cardId": card_id, "reason": reason})
        elif requires_delivery_fields:
            missing = []
            if not has_time:
                missing.append("配送时效")
            if not has_delivery:
                missing.append("起送/配送费")
            if not has_distance:
                missing.append("距离")
            if missing:
                manual_review.append({
                    "cardId": card_id,
                    "reason": f"履约信息闭环缺少{'、'.join(missing)}；必须按原图逐项复核，补标后才允许 Phase3 判定该字段缺失。",
                })
        elif is_business_card(card) and not has_fulfilment:
            manual_review.append({
                "cardId": card_id,
                "reason": "未在清单识别到十类标准履约标；需基于原图确认是否存在未被标注的履约信息。",
            })

    return {
        "valid": not errors,
        "manifest": str(manifest_path),
        "checkedCards": checked_cards,
        "errors": errors,
        "warnings": warnings,
        "manualReview": manual_review,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Phase2 element completeness")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit_manifest(args.manifest)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
