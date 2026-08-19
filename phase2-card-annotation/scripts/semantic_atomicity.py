#!/usr/bin/env python3
"""Shared element-atomicity rules for Phase2 and golden validation."""
from __future__ import annotations

import re
from typing import Any


TAG_GROUP_PATTERNS: dict[str, str] = {
    "coupon": r"神券|立减|最高膨",
    "guarantee": r"全程保|全程无推销",
    "public_service": r"公益商家",
    "social_proof": r"好评率|回头客|浏览|复购|赞过",
    "ranking": r"榜第\d+名",
    "amenity_or_service": r"免费停车|免费水果|休闲区|泰式手法|精油SPA",
}


def semantic_tag_groups(text: str) -> set[str]:
    """Return independent tag families represented by one text candidate."""
    compact = re.sub(r"\s+", "", str(text))
    groups = {name for name, pattern in TAG_GROUP_PATTERNS.items() if re.search(pattern, compact)}
    # “回头客榜/好评榜” is one ranking label; the category word is not a
    # second social-proof chip unless a separate visual entity proves it.
    if "ranking" in groups and re.search(r"(?:回头客|好评)榜第\d+名", compact):
        groups.discard("social_proof")
    return groups


def merged_tag_reason(text: str, horizontal_segments: list[dict[str, Any]] | None = None) -> str | None:
    """Explain why one 标签区 candidate must be reviewed/split.

    OCR line boxes are evidence containers, not semantic UI elements. Two tag
    families are sufficient proof of a merge. Multiple visually independent
    horizontal foreground groups plus one known tag anchor also require a
    split, covering sibling tags whose wording is not in a fixed vocabulary.
    """
    compact = re.sub(r"\s+", "", str(text))
    parts = [part for part in re.split(r"[｜|；]", compact) if part]
    if len(parts) > 1:
        return "delimited_fields"
    groups = semantic_tag_groups(compact)
    if len(groups) > 1:
        return "multiple_semantic_tag_families:" + ",".join(sorted(groups))
    segments = horizontal_segments if isinstance(horizontal_segments, list) else []
    roles = {str(item.get("colorRole", "unknown")) for item in segments} - {"", "unknown", "multicolor"}
    if len(segments) > 1 and len(roles) > 1 and groups:
        return f"multiple_visual_color_entities:{len(segments)}"
    return None
