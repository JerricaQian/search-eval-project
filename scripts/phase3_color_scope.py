"""Shared Phase3 colour-measurement scope derived from Phase2 page facts."""
from __future__ import annotations

from pathlib import Path
from typing import Any


# These regions are navigation or query-refinement controls.  They do not
# participate in either component/card or page colour-complexity conclusions.
EXCLUDED_PAGE_MODULE_TYPES = frozenset({
    "tab",
    "image_filter", "graphical_filter",
    "business_image_filter",
    "text_filter",
    "sort_filter", "promotion_filter", "quick_filter", "filter",
})


def _coord(module: dict[str, Any]) -> list[int] | None:
    value = module.get("coord") or module.get("bounds")
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        x, y, width, height = (int(round(float(item))) for item in value)
    except (TypeError, ValueError):
        return None
    return [x, y, width, height] if width > 0 and height > 0 else None


def excluded_page_modules(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Return audited exclusion records for Tab and all filter modules."""
    modules = ((manifest.get("pageFacts") or {}).get("modules") or [])
    viewport_width = int((((manifest.get("pageFacts") or {}).get("viewport") or {}).get("width") or 0))
    records: list[dict[str, Any]] = []
    for module in modules:
        if not isinstance(module, dict):
            continue
        module_type = str(module.get("moduleType") or module.get("type") or "")
        coord = _coord(module)
        if module_type not in EXCLUDED_PAGE_MODULE_TYPES or coord is None:
            continue
        original_coord = list(coord)
        # CV may localise only the selectable text portion of a Tab row and
        # omit its left utility entry.  Colour scope excludes the complete
        # Tab strip, so extend that one-row module to the page edges.
        if module_type == "tab" and viewport_width > 0:
            coord = [0, coord[1], viewport_width, coord[3]]
        records.append({
            "moduleId": str(module.get("id") or ""),
            "moduleType": module_type,
            "coord": coord,
            "sourceCoord": original_coord,
            "excludeRegion": [coord[1], coord[1] + coord[3], coord[0], coord[0] + coord[2]],
            "reason": "navigation_or_query_refinement_not_in_color_scope",
        })
    return records


def merged_exclude_regions(manifest: dict[str, Any], manual_regions: list[list[int]] | None = None) -> tuple[list[list[int]], list[dict[str, Any]]]:
    """Merge caller-supplied content exclusions with mandatory page controls."""
    merged: list[list[int]] = []
    for region in manual_regions or []:
        if isinstance(region, list) and len(region) == 4:
            merged.append([int(value) for value in region])
    records = excluded_page_modules(manifest)
    for record in records:
        region = record["excludeRegion"]
        if region not in merged:
            merged.append(region)
    return merged, records
