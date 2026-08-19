#!/usr/bin/env python3
"""Visual-identity helpers shared by golden repair and validation.

A single rendered atom must have exactly one semantic owner inside a card.
Legacy calibration occasionally copied a price/text row into a generic region
and later added the same pixels to a more specific appended-item/price region.
"""
from __future__ import annotations

import re
from typing import Any, Iterator


DOWNHANG_REGIONS = {"下挂商品区", "文字下挂区", "下挂区", "服务下挂"}
OWNER_PRIORITY = {
    "价格区": 40,
    "下挂商品区": 30,
    "文字下挂区": 30,
    "下挂区": 30,
    "服务下挂": 30,
    "标题区": 20,
    "基础信息区": 20,
    "商家信息区": 20,
    "演出信息区": 10,
    "标签区": 0,
}


def normalized_visible_text(value: Any) -> str:
    return re.sub(r"[\s|｜]+", "", str(value or "")).replace("￥", "¥")


def visual_atom_key(element: dict[str, Any]) -> tuple[tuple[int, ...], str] | None:
    coord = element.get("coord")
    text = normalized_visible_text(element.get("visibleText"))
    if not isinstance(coord, list) or len(coord) != 4 or not text:
        return None
    return tuple(int(value) for value in coord), text


def iter_owned_elements(value: Any, path: tuple[Any, ...] = ()) -> Iterator[tuple[tuple[Any, ...], dict[str, Any]]]:
    if isinstance(value, dict):
        if "elementType" in value:
            yield path, value
            return
        for key, child in value.items():
            yield from iter_owned_elements(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from iter_owned_elements(child, path + (index,))


def duplicate_visual_atoms(regions: dict[str, Any]) -> list[dict[str, Any]]:
    by_text: dict[str, list[dict[str, Any]]] = {}
    for region_name, region in regions.items():
        for path, element in iter_owned_elements(region, (region_name,)):
            key = visual_atom_key(element)
            if key is None:
                continue
            by_text.setdefault(key[1], []).append({
                "region": region_name,
                "path": path,
                "element": element,
            })
    duplicates: list[dict[str, Any]] = []
    for text, candidates in by_text.items():
        pending = list(candidates)
        while pending:
            seed = pending.pop(0)
            owners = [seed]
            changed = True
            while changed:
                changed = False
                for candidate in list(pending):
                    if any(same_rendered_atom(candidate["element"], owner["element"]) for owner in owners):
                        owners.append(candidate)
                        pending.remove(candidate)
                        changed = True
            if len(owners) > 1:
                duplicates.append({
                    "coord": owners[0]["element"]["coord"],
                    "normalizedText": text,
                    "owners": owners,
                })
    return duplicates


def same_rendered_atom(left: dict[str, Any], right: dict[str, Any]) -> bool:
    a = left.get("coord")
    b = right.get("coord")
    if not (isinstance(a, list) and isinstance(b, list) and len(a) == len(b) == 4):
        return False
    if a == b:
        return True
    ax0, ay0, aw, ah = a
    bx0, by0, bw, bh = b
    overlap_w = max(0, min(ax0 + aw, bx0 + bw) - max(ax0, bx0))
    overlap_h = max(0, min(ay0 + ah, by0 + bh) - max(ay0, by0))
    overlap = overlap_w * overlap_h
    smaller = min(aw * ah, bw * bh)
    same_kind = left.get("visual", {}).get("entityKind") == right.get("visual", {}).get("entityKind")
    return bool(same_kind and smaller > 0 and overlap / smaller >= 0.80)


def canonical_owner(owners: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the sole highest-priority owner; ties require manual review."""
    ranked = sorted(owners, key=lambda owner: OWNER_PRIORITY.get(owner["region"], 15), reverse=True)
    if len(ranked) < 2:
        return ranked[0] if ranked else None
    best = OWNER_PRIORITY.get(ranked[0]["region"], 15)
    second = OWNER_PRIORITY.get(ranked[1]["region"], 15)
    if best > second:
        return ranked[0]
    regions = {owner["region"] for owner in ranked}
    kinds = {owner["element"].get("visual", {}).get("entityKind") for owner in ranked}
    if len(regions) == 1 and len(kinds) == 1:
        # For one tag represented by both its full container and an inner OCR
        # text box, the complete visual entity owns the larger box.
        return max(ranked, key=lambda owner: owner["element"]["coord"][2] * owner["element"]["coord"][3])
    return None
