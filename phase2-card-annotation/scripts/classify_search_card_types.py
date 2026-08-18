#!/usr/bin/env python3
"""Produce conservative card-type candidates before region/element mapping.

This is intentionally a candidate generator: screenshots normally need geometry,
OCR and card-local visual evidence together. It never converts a non-match into
an advertising/heterogeneous conclusion.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


VERSION = "phase2.card-type-candidates.v1"

SIGNALS: dict[str, dict[str, list[str]]] = {
    "商品卡片": {
        "core": [r"[¥￥]\s*\d", r"商品", r"到手价|券后|划线价"],
        "supporting": [r"配送费|起送|月售|已售", r"推荐理由|商品属性|平台保障"],
    },
    "商家卡片_图文下挂": {
        "core": [r"到店|外卖|闪购", r"配送时长|配送费|起送费"],
        "supporting": [r"评价.*条|人均|商圈|推荐菜|代金券", r"已售|月售"],
    },
    "商家卡片_文字下挂": {
        "core": [r"到店|外卖|闪购|上门", r"服务|预约|取号|排队"],
        "supporting": [r"推荐理由|今日可约|保洁|洗护|问诊", r"评价.*条|人均|商圈"],
    },
    "酒店卡片": {
        "core": [r"酒店|民宿", r"[¥￥]\s*\d+\s*起"],
        "supporting": [r"满房|低价房|预订|房型|早餐|近地铁", r"经济型|舒适型|高档型|豪华型"],
    },
    "主点卡片": {
        "core": [r"地铁站|大学|商场|医院|景点|度假区"],
        "supporting": [r"途径路线|拍照点|游玩路线|门诊|挂号|科室|医生|游客量"],
    },
    "演出电影卡片": {
        "core": [r"演出|影院|电影", r"近期场次|抢票|开售|场馆"],
        "supporting": [r"\d{4}-\d{2}-\d{2}|十[分份]制|[¥￥]\s*\d+[-–]\d+"],
    },
    "度假酒店套餐卡片": {
        "core": [r"旅游|跟团游|自由行|酒店套餐", r"\d+天|出发|套餐"],
        "supporting": [r"住\s|景\s|享\s|吃\s|行\s|无购物|无自费|先囤后兑"],
    },
}


def _matches(patterns: list[str], text: str) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE)]


def _overlaps(box: list[int], container: list[int]) -> bool:
    return box[0] < container[0] + container[2] and box[0] + box[2] > container[0] and box[1] < container[1] + container[3] and box[1] + box[3] > container[1]


def classify_card_types(facts: dict[str, Any], taxonomy: dict[str, Any], card_coord: list[int] | None = None) -> dict[str, Any]:
    if facts.get("contractVersion") != "phase2.cv-facts.v1":
        raise ValueError("cv facts version is not supported")
    allowed = {
        item["id"] for item in taxonomy["cardTypes"]
        if item.get("scope", "results_list_card") == "results_list_card"
    }
    text_items = facts.get("candidates", {}).get("text", [])
    if card_coord:
        text_items = [item for item in text_items if _overlaps(item["coord"], card_coord)]
    text = "\n".join(str(item.get("text", "")) for item in text_items)
    candidates = []
    for card_type, signal_set in SIGNALS.items():
        if card_type not in allowed:
            continue
        core = _matches(signal_set["core"], text)
        supporting = _matches(signal_set["supporting"], text)
        # A core hit alone often comes from a neighboring card; require two core
        # signals, or one core plus supporting evidence, to be considered.
        score = min(1.0, 0.36 * len(core) + 0.14 * len(supporting))
        candidates.append({
            "cardType": card_type,
            "confidence": round(score, 4),
            "evidence": [f"ocr-pattern:{pattern}" for pattern in core + supporting],
        })
    candidates.sort(key=lambda item: item["confidence"], reverse=True)
    best = candidates[0] if candidates else None
    runner_up = candidates[1] if len(candidates) > 1 else None
    is_separated = not runner_up or best["confidence"] - runner_up["confidence"] >= 0.14
    status = "confirmed" if best and best["confidence"] >= 0.78 and is_separated else "uncertain"
    return {
        "contractVersion": VERSION,
        "sourceCvFacts": facts.get("screenshot", ""),
        "cardCoord": card_coord,
        "taxonomyVersion": taxonomy["contractVersion"],
        "candidates": candidates,
        "selected": {"cardType": best["cardType"] if best else "", "confidence": best["confidence"] if best else 0, "status": status},
        "routing": {"rule": "Only a confirmed card type may select its region contract. An uncertain card type is neither advertising nor heterogeneous and cannot imply a missing element, defect, failing result, excellence, or human-review task."}
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify search card type candidates")
    parser.add_argument("cv_facts", type=Path)
    parser.add_argument("--taxonomy", type=Path, default=Path(__file__).resolve().parents[1] / "references/search_card_taxonomy.v1.json")
    parser.add_argument("--coord", help="Optional x,y,width,height of one result card; only its OCR is classified")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    coord = [int(value) for value in args.coord.split(",")] if args.coord else None
    if coord and len(coord) != 4:
        parser.error("--coord must be x,y,width,height")
    result = classify_card_types(json.loads(args.cv_facts.read_text(encoding="utf-8")), json.loads(args.taxonomy.read_text(encoding="utf-8")), coord)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "selected": result["selected"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
