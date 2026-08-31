"""Shared Phase3 colour-measurement scope derived from Phase2 page facts."""
from __future__ import annotations

from pathlib import Path
from typing import Any


# These regions are navigation or query-refinement controls.  They do not
# participate in either component/card or page colour-complexity conclusions.
EXCLUDED_PAGE_MODULE_TYPES = frozenset({
    "tab", "page_tab",
    "image_filter", "graphical_filter",
    "business_image_filter",
    "text_filter",
    "sort_filter", "promotion_filter", "quick_filter", "date_filter", "filter",
})

EXCLUDED_CONTENT_MODULE_TYPES = frozenset({
    "live_card", "heterogeneous_live_card",
    "business_operation_card", "marketing_banner", "marketing_card", "banner",
})


def _coord(module: dict[str, Any]) -> list[int] | None:
    value = module.get("coord") or module.get("bounds") or module.get("坐标")
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        x, y, width, height = (int(round(float(item))) for item in value)
    except (TypeError, ValueError):
        return None
    return [x, y, width, height] if width > 0 and height > 0 else None


def excluded_page_modules(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Return audited exclusion records for navigation and content modules."""
    modules = ((manifest.get("pageFacts") or {}).get("modules") or [])
    viewport = ((manifest.get("pageFacts") or {}).get("viewport") or {})
    viewport_size = viewport.get("size") if isinstance(viewport.get("size"), list) else []
    viewport_width = int(viewport.get("width") or (viewport_size[0] if viewport_size else 0) or 0)
    records: list[dict[str, Any]] = []
    for module in modules:
        if not isinstance(module, dict):
            continue
        module_type = str(module.get("moduleType") or module.get("type") or "")
        coord = _coord(module)
        if module_type not in EXCLUDED_PAGE_MODULE_TYPES | EXCLUDED_CONTENT_MODULE_TYPES or coord is None:
            continue
        original_coord = list(coord)
        # CV may localise only the selectable text portion of a Tab row and
        # omit its left utility entry.  Colour scope excludes the complete
        # Tab strip, so extend that one-row module to the page edges.
        if module_type in {"tab", "page_tab"} and viewport_width > 0:
            coord = [0, coord[1], viewport_width, coord[3]]
        records.append({
            "moduleId": str(module.get("id") or ""),
            "moduleType": module_type,
            "coord": coord,
            "sourceCoord": original_coord,
            "excludeRegion": [coord[1], coord[1] + coord[3], coord[0], coord[0] + coord[2]],
            "reason": (
                "content_media_not_ui_design_color"
                if module_type in EXCLUDED_CONTENT_MODULE_TYPES
                else "navigation_or_query_refinement_not_in_color_scope"
            ),
        })
    return records


def _iter_elements(manifest: dict[str, Any]):
    seen: set[str] = set()
    for card in manifest.get("cards", []):
        for region in card.get("regions", []):
            for element in region.get("elements", []):
                element_id = str(element.get("id") or "") if isinstance(element, dict) else ""
                if isinstance(element, dict) and element_id not in seen:
                    seen.add(element_id)
                    yield element
    for module in ((manifest.get("pageFacts") or {}).get("modules") or []):
        for element in module.get("elements", []):
            element_id = str(element.get("id") or "") if isinstance(element, dict) else ""
            if isinstance(element, dict) and element_id not in seen:
                seen.add(element_id)
                yield element
        for item in module.get("filterItems", []):
            for element in item.get("elements", []):
                element_id = str(element.get("id") or "") if isinstance(element, dict) else ""
                if isinstance(element, dict) and element_id not in seen:
                    seen.add(element_id)
                    yield element


def excluded_photo_elements(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Return Phase2-confirmed photo/image rectangles excluded from page colour."""
    records: list[dict[str, Any]] = []
    for element in _iter_elements(manifest):
        render = element.get("render") if isinstance(element.get("render"), dict) else {}
        visual = element.get("visual") if isinstance(element.get("visual"), dict) else {}
        coord = _coord(element)
        if coord is None or render.get("visibleStatus") != "confirmed":
            continue
        if render.get("isPhoto") is not True:
            continue
        records.append({
            "elementId": str(element.get("id") or ""),
            "coord": coord,
            "excludeRegion": [coord[1], coord[1] + coord[3], coord[0], coord[0] + coord[2]],
            "entityKind": visual.get("entityKind"),
            "reason": "phase2_confirmed_photo_not_ui_design_color",
        })
    return records


def retained_system_ui_overlays(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Return confirmed UI atoms that must be restored inside excluded photos."""
    records: list[dict[str, Any]] = []
    for element in _iter_elements(manifest):
        render = element.get("render") if isinstance(element.get("render"), dict) else {}
        coord = _coord(element)
        if coord is None or render.get("visibleStatus") != "confirmed" or render.get("isSystemUi") is not True:
            continue
        records.append({
            "elementId": str(element.get("id") or ""),
            "coord": coord,
            "restoreRegion": [coord[1], coord[1] + coord[3], coord[0], coord[0] + coord[2]],
            "reason": "confirmed_system_ui_overlay_retained_in_color_scope",
        })
    return records


def color_scope_from_manifest(
    manifest: dict[str, Any],
    manual_regions: list[list[int]] | None = None,
) -> tuple[list[list[int]], list[dict[str, Any]], list[list[int]], list[dict[str, Any]]]:
    """Build complete exclusion and UI-restore scopes from validated JSON facts."""
    exclusions: list[list[int]] = []
    for region in manual_regions or []:
        if isinstance(region, list) and len(region) == 4:
            exclusions.append([int(value) for value in region])
    exclusion_records = excluded_page_modules(manifest) + excluded_photo_elements(manifest)
    for record in exclusion_records:
        region = record["excludeRegion"]
        if region not in exclusions:
            exclusions.append(region)
    overlay_records = [
        record
        for record in retained_system_ui_overlays(manifest)
        if any(
            max(record["restoreRegion"][0], excluded[0]) < min(record["restoreRegion"][1], excluded[1])
            and max(record["restoreRegion"][2], excluded[2]) < min(record["restoreRegion"][3], excluded[3])
            for excluded in exclusions
        )
    ]
    restore_regions = [record["restoreRegion"] for record in overlay_records]
    return exclusions, exclusion_records, restore_regions, overlay_records


def merged_exclude_regions(manifest: dict[str, Any], manual_regions: list[list[int]] | None = None) -> tuple[list[list[int]], list[dict[str, Any]]]:
    """Backward-compatible exclusion-only view of the complete colour scope."""
    merged, records, _, _ = color_scope_from_manifest(manifest, manual_regions)
    return merged, records
