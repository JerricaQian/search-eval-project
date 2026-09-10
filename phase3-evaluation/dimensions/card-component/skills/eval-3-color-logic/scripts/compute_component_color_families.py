#!/usr/bin/env python3
"""Derive canonical seven-colour families for every Phase2 result card.

This is the sole deterministic component calculator shared by component and
page colour evaluation.  It derives colour families from Phase2 visual facts
and, when the accepted source screenshot is available, measures each card's
effective UI pixels for the page-level dominant-colour condition.  The page
Skill only aggregates this artifact; it never launches its own pixel script.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from PIL import Image


ROOT = Path(__file__).resolve().parents[6]
SHARED_SCRIPTS = ROOT / "scripts"
PHASE3_SCRIPTS = ROOT / "phase3-evaluation" / "common" / "scripts"
for directory in (SHARED_SCRIPTS, PHASE3_SCRIPTS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from color_taxonomy import HUE7_ZH, hue7_family, is_chromatic_rgb
from phase2_bundle_loader import load_phase2_facts


CONTRACT_VERSION = "component-color-families.v3.1"
FAMILY_ORDER = ("red", "orange", "yellow", "green", "cyan", "blue", "purple")
COLOR_FIELDS = ("textColor", "backgroundColor", "borderColor")
COLOR_ROLE_FAMILIES = frozenset(FAMILY_ORDER)
DOMINANT_COLOR_AREA_RATIO_THRESHOLD = 0.05
FILTER_COMPONENT_TYPES = {
    "image_filter",
    "business_image_filter",
    "graphic_filter",
    "business_graphic_filter",
}
HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
RGB_RE = re.compile(r"^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,[^)]*)?\)$", re.IGNORECASE)


def parse_rgb(value: Any) -> tuple[int, int, int] | None:
    """Parse a published CSS-like colour value without guessing unknown formats."""
    if isinstance(value, (list, tuple)) and len(value) >= 3 and all(isinstance(x, int) for x in value[:3]):
        rgb = tuple(value[:3])
        return rgb if all(0 <= channel <= 255 for channel in rgb) else None
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = HEX_RE.fullmatch(text)
    if match:
        raw = match.group(1)
        if len(raw) in {3, 4}:
            raw = "".join(char * 2 for char in raw[:3])
        else:
            raw = raw[:6]
        return tuple(int(raw[index:index + 2], 16) for index in (0, 2, 4))
    match = RGB_RE.fullmatch(text)
    if match:
        rgb = tuple(int(match.group(index)) for index in (1, 2, 3))
        return rgb if all(0 <= channel <= 255 for channel in rgb) else None
    return None


def rgb_hue(red: int, green: int, blue: int) -> float:
    """Return the HSV hue in degrees for a non-neutral RGB colour."""
    high = max(red, green, blue) / 255.0
    low = min(red, green, blue) / 255.0
    delta = high - low
    if delta == 0:
        return 0.0
    r, g, b = red / 255.0, green / 255.0, blue / 255.0
    if high == r:
        hue = 60.0 * (((g - b) / delta) % 6)
    elif high == g:
        hue = 60.0 * (((b - r) / delta) + 2)
    else:
        hue = 60.0 * (((r - g) / delta) + 4)
    return hue % 360.0


def visual_element_is_excluded(element: dict[str, Any]) -> str | None:
    render = element.get("render") if isinstance(element.get("render"), dict) else {}
    visual = element.get("visual") if isinstance(element.get("visual"), dict) else {}
    if element.get("isExcluded"):
        return str(element.get("excludeReason") or "phase2_excluded")
    if render.get("visibleStatus") != "confirmed" or visual.get("visualStatus") != "confirmed":
        return "visual_not_confirmed"
    if render.get("isPhoto") or visual.get("entityKind") == "image" or element.get("元素类型") == "图片":
        return "photo_or_image"
    if visual.get("entityKind") == "icon" or element.get("元素类型") == "图标":
        return "graphic_or_icon"
    return None


def component_is_filter(card: dict[str, Any]) -> bool:
    """Keep graphic filters out even when a legacy manifest exposes one as a card."""
    values = (
        card.get("cardTypeCode"), card.get("cardType"), card.get("componentType"),
        card.get("moduleType"), card.get("contentRole"), card.get("卡片类型"),
    )
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized in FILTER_COMPONENT_TYPES or "图筛" in value:
            return True
    return False


def component_rating(color_count: int) -> str:
    if color_count <= 4:
        return "优秀"
    if color_count == 5:
        return "达标"
    return "不达标"


def rect_from_value(value: Any) -> tuple[int, int, int, int] | None:
    """Read a Phase2 ``[x, y, width, height]`` rectangle without guessing."""
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    if any(not isinstance(item, (int, float)) for item in value):
        return None
    x, y, width, height = (int(item) for item in value)
    if width <= 0 or height <= 0:
        return None
    return x, y, width, height


def element_rect(element: dict[str, Any]) -> tuple[int, int, int, int] | None:
    return rect_from_value(element.get("coord")) or rect_from_value(element.get("坐标"))


def family_from_color_role(value: Any) -> str | None:
    """Use legacy confirmed seven-colour roles only when CSS values are absent."""
    if not isinstance(value, str):
        return None
    family = value.strip().lower()
    return family if family in COLOR_ROLE_FAMILIES else None


def component_colour_families(
    card: dict[str, Any],
) -> tuple[list[str], list[str], list[str], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Collect a card's verified colour facts and the exclusions used for pixels."""
    scanned_ids: list[str] = []
    excluded_ids: list[str] = []
    neutral_values: list[dict[str, Any]] = []
    source_values: list[dict[str, Any]] = []
    excluded_regions: list[dict[str, Any]] = []
    family_keys: set[str] = set()
    for element in iter_card_elements(card):
        element_id = element.get("id")
        if not isinstance(element_id, str) or not element_id:
            continue
        excluded_reason = visual_element_is_excluded(element)
        if excluded_reason:
            excluded_ids.append(element_id)
            rect = element_rect(element)
            if rect:
                excluded_regions.append({"elementId": element_id, "rect": rect, "reason": excluded_reason})
            continue
        scanned_ids.append(element_id)
        visual = element.get("visual") if isinstance(element.get("visual"), dict) else {}
        element_families: set[str] = set()
        has_css_colour = False
        for field in COLOR_FIELDS:
            value = visual.get(field)
            rgb = parse_rgb(value)
            if rgb is None:
                continue
            has_css_colour = True
            if not is_chromatic_rgb(*rgb):
                neutral_values.append({"elementId": element_id, "field": field, "value": value})
                continue
            family = hue7_family(rgb_hue(*rgb))
            element_families.add(family)
            source_values.append({
                "elementId": element_id,
                "field": field,
                "value": value,
                "colorFamily": HUE7_ZH[family],
            })
        # Legacy accepted manifests published semantic colour roles instead of
        # CSS values.  They remain valid deterministic Phase2 evidence.
        if not has_css_colour:
            family = family_from_color_role(visual.get("colorRole"))
            if family:
                element_families.add(family)
                source_values.append({
                    "elementId": element_id,
                    "field": "visual.colorRole",
                    "value": visual.get("colorRole"),
                    "colorFamily": HUE7_ZH[family],
                })
        family_keys.update(element_families)
    ordered_keys = [family for family in FAMILY_ORDER if family in family_keys]
    return (
        scanned_ids,
        excluded_ids,
        [HUE7_ZH[family] for family in ordered_keys],
        neutral_values,
        source_values,
        excluded_regions,
    )


def measure_component_colour_areas(
    image: Image.Image | None,
    card: dict[str, Any],
    family_names: list[str],
    excluded_regions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Measure known card colour families after excluding photos and image filters.

    The denominator is every pixel in the card's confirmed effective UI bounds
    after Phase2-excluded media is removed.  Only families already established
    by the card's Phase2 colour facts receive a numerator, so photos, filters
    and unconfirmed colours cannot create a dominant colour.
    """
    empty_areas = {HUE7_ZH[family]: 0 for family in FAMILY_ORDER}
    if image is None:
        return {
            "status": "unavailable",
            "reason": "accepted_screenshot_unavailable",
            "effectiveUiPixelCount": 0,
            "colorFamilyPixelAreas": empty_areas,
        }
    rect = rect_from_value(card.get("coord")) or rect_from_value(card.get("坐标"))
    if rect is None:
        return {
            "status": "unavailable",
            "reason": "card_bounds_unavailable",
            "effectiveUiPixelCount": 0,
            "colorFamilyPixelAreas": empty_areas,
        }
    x, y, width, height = rect
    left, top = max(0, x), max(0, y)
    right, bottom = min(image.width, x + width), min(image.height, y + height)
    if right <= left or bottom <= top:
        return {
            "status": "unavailable",
            "reason": "card_bounds_outside_screenshot",
            "effectiveUiPixelCount": 0,
            "colorFamilyPixelAreas": empty_areas,
        }
    excluded_rects = [item["rect"] for item in excluded_regions if isinstance(item.get("rect"), tuple)]
    allowed_families = {key for key, zh_name in HUE7_ZH.items() if zh_name in family_names}
    areas = {HUE7_ZH[family]: 0 for family in FAMILY_ORDER}
    effective_pixels = 0
    rgb_image = image.convert("RGB")
    pixels = rgb_image.load()
    for pixel_y in range(top, bottom):
        for pixel_x in range(left, right):
            if any(
                excluded_x <= pixel_x < excluded_x + excluded_width
                and excluded_y <= pixel_y < excluded_y + excluded_height
                for excluded_x, excluded_y, excluded_width, excluded_height in excluded_rects
            ):
                continue
            effective_pixels += 1
            red, green, blue = pixels[pixel_x, pixel_y]
            if not is_chromatic_rgb(red, green, blue):
                continue
            family = hue7_family(rgb_hue(red, green, blue))
            if family in allowed_families:
                areas[HUE7_ZH[family]] += 1
    return {
        "status": "measured",
        "reason": "",
        "effectiveUiPixelCount": effective_pixels,
        "colorFamilyPixelAreas": areas,
    }


def iter_card_elements(card: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for region in card.get("regions", []):
        if not isinstance(region, dict):
            continue
        for element in region.get("elements", []):
            if isinstance(element, dict):
                yield element


def compute_components(facts: dict[str, Any], screenshot_path: Path | None = None) -> list[dict[str, Any]]:
    image: Image.Image | None = None
    if screenshot_path and screenshot_path.is_file():
        try:
            with Image.open(screenshot_path) as source:
                image = source.convert("RGB")
        except OSError:
            image = None
    components: list[dict[str, Any]] = []
    for card in facts.get("cards", []):
        if not isinstance(card, dict) or not isinstance(card.get("cardId"), str):
            continue
        if component_is_filter(card):
            continue
        scanned_ids, excluded_ids, families, neutral_values, source_values, excluded_regions = component_colour_families(card)
        area_measurement = measure_component_colour_areas(image, card, families, excluded_regions)
        components.append({
            "componentId": card["cardId"],
            "scannedElementIds": scanned_ids,
            "excludedElementIds": excluded_ids,
            "neutralColorValues": neutral_values,
            "sourceColorValues": source_values,
            "colorFamilies": families,
            "colorFamilyCount": len(families),
            "effectiveUiPixelCount": area_measurement["effectiveUiPixelCount"],
            "colorFamilyPixelAreas": area_measurement["colorFamilyPixelAreas"],
            "dominantColorMeasurementStatus": area_measurement["status"],
            "dominantColorMeasurementReason": area_measurement["reason"],
            "rating": component_rating(len(families)),
            "evidenceSource": "phase2_json_visual_colors",
        })
    return components


def main() -> int:
    parser = argparse.ArgumentParser(description="按七色系计算 Phase2 结果卡的组件色彩结果")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    facts = load_phase2_facts(manifest_path=args.manifest)
    screenshot = facts.get("screenshot")
    screenshot_path = Path(screenshot) if isinstance(screenshot, str) and screenshot else None
    result = {
        "contract": "component-color-families",
        "contractVersion": CONTRACT_VERSION,
        "manifest": str(args.manifest.resolve()),
        "dominantColorAreaRatioThreshold": DOMINANT_COLOR_AREA_RATIO_THRESHOLD,
        "components": compute_components(facts, screenshot_path),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
