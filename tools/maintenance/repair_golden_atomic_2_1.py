#!/usr/bin/env python3
"""Repair the in-place golden-atomic-2.1 corpus for the current Phase3 contract.

This is intentionally version-scoped and idempotent.  It must never be aimed at
golden-atomic-2.0, which remains the rollback/audit baseline.
"""
from __future__ import annotations

import argparse
import colorsys
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLDEN_ROOT = ROOT / "phase2-card-annotation" / "golden-atomic-2.1"


# Bounds are calibrated against the retained source screenshots.  They cover
# the complete visible module surface, not merely the text inside the module.
MODULE_BOUNDS: dict[str, dict[str, list[int]]] = {
    "merchant-graphic-hang/库迪.atomic.v3.json": {"M2": [0, 291, 1224, 109], "M3": [0, 400, 1224, 136]},
    "merchant-graphic-hang/烧烤.atomic.v3.json": {"M2": [0, 291, 1224, 109], "M3": [0, 400, 1224, 136]},
    "merchant-graphic-hang/生日蛋糕.atomic.v3.json": {
        "M2": [0, 291, 1224, 109], "M3": [0, 400, 1224, 551], "M5": [0, 1303, 1224, 192],
    },
    "merchant-graphic-hang/盒马.atomic.v3.json": {
        "M2": [0, 291, 1224, 109], "M3": [0, 400, 1224, 136], "M4": [0, 554, 1224, 138],
    },
    "merchant-graphic-hang/药店.atomic.v3.json": {
        "M2": [0, 291, 1224, 109], "M4": [0, 673, 1224, 190], "M6": [928, 2045, 296, 140],
    },
    "merchant-graphic-hang/蜜雪冰城.atomic.v3.json": {
        "M2": [0, 291, 1224, 109], "M3": [0, 400, 1224, 750], "M4": [0, 1168, 1224, 140],
    },
    "merchant-graphic-hang/隆江猪脚饭.atomic.v3.json": {"M2": [0, 291, 1224, 109], "M3": [0, 400, 1224, 136]},
    "performance-movie-card/演出卡.atomic.v3.json": {"M2": [0, 267, 1224, 109]},
    "performance-movie-card/电影卡.atomic.v3.json": {"M2": [0, 267, 1224, 109]},
    "primary-point-card/万达广场.atomic.v3.json": {
        "M2": [0, 267, 1224, 109], "M5": [0, 921, 1224, 250], "M6": [0, 1183, 1224, 107],
    },
    "primary-point-card/迪士尼.atomic.v3.json": {
        "M2": [0, 267, 1224, 109], "M5": [0, 1595, 1224, 245], "M6": [0, 1843, 1224, 107],
    },
    "product-card/啤酒.atomic.v3.json": {
        "M2": [0, 291, 1224, 109], "M4": [0, 733, 1224, 137], "M5": [0, 886, 1224, 204],
    },
    "product-card/喜力啤酒整箱.atomic.v3.json": {
        "M2": [0, 291, 1224, 109], "M3": [0, 400, 1224, 136], "M4": [0, 554, 1224, 138],
    },
    "product-card/安睡裤.atomic.v3.json": {"M2": [0, 291, 1224, 109], "M4": [0, 726, 1224, 208]},
    "product-card/布洛芬.atomic.v3.json": {
        "M2": [0, 291, 1224, 109], "M4": [0, 663, 1224, 168], "M6": [928, 2045, 296, 140],
    },
    "product-card/榴莲.atomic.v3.json": {
        "M2": [0, 291, 1224, 109], "M4": [0, 718, 1224, 136], "M5": [0, 872, 1224, 187],
    },
    "product-card/生理盐水.atomic.v3.json": {
        "M2": [0, 291, 1224, 109], "M3": [0, 400, 1224, 136], "M5": [928, 2045, 296, 140],
    },
    "product-card/西瓜.atomic.v3.json": {
        "M2": [0, 291, 1224, 109], "M4": [0, 662, 1224, 136], "M5": [0, 816, 1224, 203],
    },
}

TEXT_HANG_FILES = {
    "商家卡片-文下挂-搜索词为体检.atomic.v3.json",
    "商家卡片-文下挂-搜索词为剧本杀.atomic.v3.json",
    "商家卡片-文下挂-搜索词为手机维修.atomic.v3.json",
    "商家卡片-文下挂-搜索词为按摩.atomic.v3.json",
    "商家卡片-文下挂-搜索词为游乐场.atomic.v3.json",
    "商家卡片-文下挂-搜索词为漂流.atomic.v3.json",
    "商家卡片-文下挂-搜索词为理发.atomic.v3.json",
    "商家卡片-文下挂-搜索词为空调清洗.atomic.v3.json",
    "商家卡片-文下挂-搜索词为解压体验馆.atomic.v3.json",
    "商家卡片-文下挂-搜索词为露营.atomic.v3.json",
    "商家卡片-文下挂-搜索词为面部清洁.atomic.v3.json",
}
for filename in TEXT_HANG_FILES:
    MODULE_BOUNDS[f"merchant-text-hang/{filename}"] = {
        "M1": [0, 122, 1224, 165],
        "M2": [0, 291, 1224, 109],
    }


PRICE_LABEL_RE = re.compile(r"(?:特价|特惠|低价|立减|立享|冰爽价|神价|新客价|已优惠|折$)")
TIME_LABEL_RE = re.compile(r"(?:约)?\d+分钟$")
MAIN_PRICE_RE = re.compile(r"[¥￥]\s*\d")
RATING_RE = re.compile(r"\d(?:\.\d+)?分")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def chromatic(color: str) -> bool:
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        return False
    r, g, b = (int(color[index:index + 2], 16) / 255.0 for index in (1, 3, 5))
    return colorsys.rgb_to_hsv(r, g, b)[1] >= 0.12


def target_tag_slot(role: str) -> str | None:
    if role == "recommendation":
        return "recommendation_tag"
    if role == "promotion":
        return "promotion_tag"
    if role in {"fulfillment", "delivery_time"}:
        return "delivery_time_tag"
    if role == "sales":
        return "live_status_tag"
    if role.startswith("price"):
        return "price_promotion_tag"
    return None


def should_be_colored_text_tag(element: dict[str, Any], role: str) -> bool:
    if element.get("kind") != "text":
        return False
    text = str(element.get("text") or "").strip()
    color = (element.get("visual") or {}).get("textColor", "")
    if not text or not chromatic(color):
        return False
    # Explicit user exceptions: the main price and score remain text, not tags.
    if MAIN_PRICE_RE.search(text) or RATING_RE.search(text):
        return False
    if role == "recommendation":
        return True
    if role == "promotion":
        return True
    if role in {"fulfillment", "delivery_time"}:
        return bool(TIME_LABEL_RE.fullmatch(text)) or len(text) <= 12
    if role == "sales":
        return "观看" in text
    if role.startswith("price"):
        return bool(PRICE_LABEL_RE.search(text))
    return False


def iter_slot_owners(payload: dict[str, Any]):
    for owner_type, mapping in (
        ("module", payload["modulesById"]),
        ("filter_item", payload["filterItemsById"]),
        ("region", payload["regionsById"]),
    ):
        for owner_id, owner in mapping.items():
            yield owner_type, owner_id, owner
            for index, item in enumerate(owner.get("items", [])):
                yield "region_item", f"{owner_id}#{index}", item


def reclassify_colored_text_tags(payload: dict[str, Any]) -> int:
    elements = payload["elementsById"]
    changed = 0
    for _, _, owner in iter_slot_owners(payload):
        slots = owner.get("slots")
        if not isinstance(slots, dict):
            continue
        additions: dict[str, list[str]] = {}
        for role in list(slots):
            kept: list[str] = []
            for element_id in slots[role]:
                element = elements[element_id]
                target = target_tag_slot(role)
                if target and should_be_colored_text_tag(element, role):
                    element["kind"] = "tag"
                    additions.setdefault(target, []).append(element_id)
                    changed += 1
                else:
                    kept.append(element_id)
            if kept:
                slots[role] = kept
            else:
                del slots[role]
        for role, ids in additions.items():
            slots.setdefault(role, []).extend(element_id for element_id in ids if element_id not in slots.get(role, []))
    return changed


def tag_graphic_assist(text: str) -> str:
    if "神券" in text or "闪购" in text:
        return "lightning"
    if "15分钟" in text:
        return "lightning"
    if "必玩榜" in text or text.startswith("住就送"):
        return "medal"
    return "none"


def enrich_tag_visuals(payload: dict[str, Any]) -> int:
    changed = 0
    for element in payload["elementsById"].values():
        if element.get("kind") != "tag":
            continue
        visual = element.setdefault("visual", {})
        background = str(visual.get("backgroundColor") or "")
        declared_container = str(visual.get("container") or "").lower()
        if declared_container not in {"filled", "outlined"}:
            visual["container"] = "none" if background.upper() in {"", "#FFFFFF"} else "filled"
        visual.setdefault("backgroundColor", "")
        visual.setdefault("textColor", "")
        visual.setdefault("borderColor", "")
        visual["graphicAssist"] = tag_graphic_assist(str(element.get("text") or ""))
        changed += 1
    return changed


def element_text(payload: dict[str, Any], ids: list[str]) -> str:
    for element_id in ids:
        element = payload["elementsById"].get(element_id, {})
        text = str(element.get("text") or "").strip()
        if text:
            return text
    return ""


def card_title(payload: dict[str, Any], card_id: str) -> str:
    card = payload["cardsById"][card_id]
    for region_id in card["regionIds"]:
        region = payload["regionsById"][region_id]
        if region.get("name") != "title":
            continue
        for role in ("title", "subtitle", "other"):
            text = element_text(payload, region.get("slots", {}).get(role, []))
            if text:
                return text
    return ""


def enrich_media_semantics(payload: dict[str, Any]) -> int:
    contexts: dict[str, str] = {}
    region_to_card = {
        region_id: card_id
        for card_id, card in payload["cardsById"].items()
        for region_id in card["regionIds"]
    }
    for _, owner_id, owner in iter_slot_owners(payload):
        slots = owner.get("slots", {})
        local_text = ""
        for role in ("title", "label", "name", "other", "subtitle"):
            local_text = element_text(payload, slots.get(role, []))
            if local_text:
                break
        base_region_id = owner_id.split("#", 1)[0]
        card_id = region_to_card.get(base_region_id)
        if not local_text and card_id:
            local_text = card_title(payload, card_id)
        for ids in slots.values():
            for element_id in ids:
                if payload["elementsById"][element_id].get("kind") == "media":
                    contexts[element_id] = local_text

    changed = 0
    for element_id, element in payload["elementsById"].items():
        if element.get("kind") != "media":
            continue
        subject = contexts.get(element_id, "").strip()
        media_type = element.get("mediaType")
        noun = "海报" if media_type == "poster" else "图片"
        element["semanticDescription"] = f"{subject}的可见{noun}" if subject else f"页面中的可见{noun}内容"
        element["semanticStatus"] = "confirmed"
        changed += 1
    return changed


def fix_disney_empty_atom(payload: dict[str, Any], relative: str) -> int:
    if relative != "primary-point-card/迪士尼.atomic.v3.json":
        return 0
    element = payload["elementsById"]["M3-E004"]
    element.pop("text", None)
    element["kind"] = "media"
    element["mediaType"] = "video_frame"
    element["semanticDescription"] = "迪士尼直播模块底部的酒店商品推荐横栏"
    element["semanticStatus"] = "confirmed"
    return 1


REVIEWED_LIVE_OVERLAYS: dict[str, list[tuple[str, str, list[int]]]] = {
    "hotel-card/全季酒店-第1次.atomic.v3.json": [
        ("C1-ICON-LIVE", "C1-E001", [30, 576, 57, 42]),
        ("C5-ICON-LIVE", "C5-E001", [30, 2325, 57, 42]),
    ],
    "merchant-graphic-hang/库迪.atomic.v3.json": [
        ("C1-ICON-LIVE", "C1-E001", [32, 554, 61, 45]),
        ("C2-ICON-LIVE", "C2-E001", [32, 1269, 61, 45]),
        ("C3-ICON-LIVE", "C3-E001", [32, 1984, 61, 45]),
    ],
    "merchant-graphic-hang/生日蛋糕.atomic.v3.json": [("C2-ICON-LIVE", "C2-E001", [32, 2176, 61, 45])],
    "merchant-text-hang/商家卡片-文下挂-搜索词为手机维修.atomic.v3.json": [
        ("C1-ICON-LIVE", "C1-E001", [32, 881, 61, 45]),
        ("C2-ICON-LIVE", "C2-E001", [32, 1356, 61, 45]),
        ("C4-ICON-LIVE", "C4-E001", [32, 2306, 61, 45]),
    ],
    "merchant-text-hang/商家卡片-文下挂-搜索词为游乐场.atomic.v3.json": [("C5-ICON-LIVE", "C5-E001", [32, 2405, 61, 45])],
    "merchant-text-hang/商家卡片-文下挂-搜索词为理发.atomic.v3.json": [
        ("C1-ICON-LIVE", "C1-E001", [32, 881, 61, 45]),
        ("C4-ICON-LIVE", "C4-E001", [32, 2306, 61, 45]),
    ],
    "merchant-text-hang/商家卡片-文下挂-搜索词为空调清洗.atomic.v3.json": [
        ("C3-ICON-LIVE", "C3-E001", [32, 1829, 61, 45]),
        ("C4-ICON-LIVE", "C4-E001", [32, 2304, 61, 45]),
    ],
    "primary-point-card/万达广场.atomic.v3.json": [
        ("C1-ICON-LIVE", "C1-E001", [32, 1318, 61, 45]),
        ("C2-ICON-LIVE", "C2-E001", [32, 2034, 61, 45]),
    ],
}

REVIEWED_PLAY_OVERLAYS: dict[str, list[tuple[str, str, list[int], str, str]]] = {
    "hotel-card/全季酒店-第1次.atomic.v3.json": [
        ("C1-ICON-PLAY", "C1-E001", [291, 610, 22, 24], "none", ""),
        ("C2-ICON-PLAY", "C2-E001", [263, 1070, 62, 62], "filled", "#AFAFAF"),
        ("C3-ICON-PLAY", "C3-E001", [264, 1466, 61, 61], "filled", "#C2C2C2"),
        ("C5-ICON-PLAY", "C5-E001", [291, 2319, 22, 24], "none", ""),
    ],
    "hotel-card/全季酒店-第2次.atomic.v3.json": [
        ("C1-ICON-PLAY", "C1-E001", [285, 1501, 54, 54], "filled", "#0069A7"),
        ("C2-ICON-PLAY", "C2-E001", [285, 2010, 54, 55], "filled", "#0066B5"),
        ("C3-ICON-PLAY", "C3-E001", [288, 2520, 53, 53], "filled", "#737D8B"),
    ],
}


def attach_icon_to_media_region(payload: dict[str, Any], icon_id: str, media_id: str) -> None:
    for region in payload["regionsById"].values():
        slots = region.get("slots", {})
        if any(media_id in ids for ids in slots.values()):
            slots.setdefault("media_overlay_icon", [])
            if icon_id not in slots["media_overlay_icon"]:
                slots["media_overlay_icon"].append(icon_id)
            return
    raise ValueError(f"attached media has no region owner: {media_id}")


def add_reviewed_overlays(payload: dict[str, Any], relative: str) -> int:
    additions: dict[str, dict[str, Any]] = {}
    if relative == "hotel-card/酒店.atomic.v3.json":
        additions.update({
        "C2-E018": {
            "kind": "icon", "bounds": [30, 1973, 66, 50],
            "semanticDescription": "头图左上角的直播状态角标", "semanticStatus": "confirmed",
            "attachedTo": "C2-E001",
            "visual": {"container": "filled", "backgroundColor": "#FF2D78", "textColor": "#FFFFFF", "borderColor": "", "graphicAssist": "live_equalizer"},
        },
        "C2-E019": {
            "kind": "icon", "bounds": [300, 1995, 45, 45],
            "semanticDescription": "头图右上区域的播放按钮", "semanticStatus": "confirmed",
            "attachedTo": "C2-E001",
            "visual": {"container": "none", "backgroundColor": "", "textColor": "#FFFFFF", "borderColor": "", "graphicAssist": "play"},
        },
        "C3-E008": {
            "kind": "icon", "bounds": [287, 2508, 55, 55],
            "semanticDescription": "头图右上区域的播放按钮", "semanticStatus": "confirmed",
            "attachedTo": "C3-E001",
            "visual": {"container": "filled", "backgroundColor": "#C9C9C9", "textColor": "#FFFFFF", "borderColor": "", "graphicAssist": "play"},
        },
        })
    for icon_id, media_id, bounds in REVIEWED_LIVE_OVERLAYS.get(relative, []):
        additions[icon_id] = {
            "kind": "icon", "bounds": bounds,
            "semanticDescription": "头图左上角的直播状态角标", "semanticStatus": "confirmed",
            "attachedTo": media_id,
            "visual": {"container": "filled", "backgroundColor": "#FF2D78", "textColor": "#FFFFFF", "borderColor": "", "graphicAssist": "live_equalizer"},
        }
    for icon_id, media_id, bounds, container, background in REVIEWED_PLAY_OVERLAYS.get(relative, []):
        additions[icon_id] = {
            "kind": "icon", "bounds": bounds,
            "semanticDescription": "头图右上区域的播放按钮", "semanticStatus": "confirmed",
            "attachedTo": media_id,
            "visual": {"container": container, "backgroundColor": background, "textColor": "#FFFFFF", "borderColor": "", "graphicAssist": "play"},
        }
    if not additions:
        return 0
    payload["elementsById"].update(additions)
    for icon_id, icon in additions.items():
        attach_icon_to_media_region(payload, icon_id, str(icon["attachedTo"]))
    return len(additions)


def repair_one(path: Path, golden_root: Path) -> Counter[str]:
    relative = path.relative_to(golden_root).as_posix()
    payload = json.loads(path.read_text(encoding="utf-8"))
    stats: Counter[str] = Counter(files=1)
    for module_id, bounds in MODULE_BOUNDS.get(relative, {}).items():
        payload["modulesById"][module_id]["bounds"] = bounds
        stats["moduleBounds"] += 1
    stats["emptyAtomsFixed"] += fix_disney_empty_atom(payload, relative)
    stats["coloredTextTags"] += reclassify_colored_text_tags(payload)
    stats["tagVisuals"] += enrich_tag_visuals(payload)
    stats["mediaSemantics"] += enrich_media_semantics(payload)
    stats["overlayIcons"] += add_reviewed_overlays(payload, relative)
    write_json(path, payload)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden-root", type=Path, default=DEFAULT_GOLDEN_ROOT)
    args = parser.parse_args()
    golden_root = args.golden_root.resolve()
    if golden_root.name != "golden-atomic-2.1":
        raise SystemExit("refusing to modify any directory except golden-atomic-2.1")
    manifests = sorted(golden_root.rglob("*.atomic.v3.json"))
    if len(manifests) != 34:
        raise SystemExit(f"expected 34 manifests, found {len(manifests)}")
    totals: Counter[str] = Counter()
    for path in manifests:
        totals.update(repair_one(path, golden_root))
    missing = []
    for path in manifests:
        payload = json.loads(path.read_text(encoding="utf-8"))
        missing.extend(f"{path.relative_to(golden_root)}:{module_id}" for module_id, module in payload["modulesById"].items() if "bounds" not in module)
    if missing:
        raise SystemExit("module bounds remain missing: " + ",".join(missing))
    print(json.dumps(dict(totals), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
