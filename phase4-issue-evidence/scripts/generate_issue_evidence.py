#!/usr/bin/env python3
"""Generate consolidated full-page evidence images for Phase3 findings.

Each source screenshot produces one original-size evidence image. Single-element
findings retain their exact element identity and coordinate for assessment
traceability, but display the containing Phase2 card/component boundary as context.
Card/component findings use that same Phase2 aggregate boundary directly.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


PROBLEM_RATINGS = {"达标", "不达标", "🟡", "🔴"}
SINGLE_ELEMENT_DIMENSION = "phase3-single_element-eval"
COMPONENT_DIMENSION = "phase3-card_or_component-eval"
PAGE_DIMENSION = "phase3-page_framework-eval"


def safe_name(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z._-]+", "_", value).strip("_")
    return value[:80] or "issue"


def rect_ok(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(isinstance(item, (int, float)) for item in value)
        and value[2] > 0
        and value[3] > 0
    )


def build_manifest_index(
    manifest: dict[str, Any],
) -> tuple[dict[str, list[float]], dict[str, tuple[list[float], str]]]:
    """Return Phase2 minimal-element and component/module coordinate indexes."""
    elements: dict[str, list[float]] = {}
    components: dict[str, tuple[list[float], str]] = {}

    # Atomic v3 is the canonical Phase2 output.  Resolve its indexed facts
    # directly instead of requiring a legacy, expanded ``cards[]`` projection.
    for element_id, element in (manifest.get("elementsById") or {}).items():
        if not isinstance(element_id, str) or not isinstance(element, dict):
            continue
        bounds = element.get("bounds")
        if rect_ok(bounds):
            elements[element_id] = bounds
    for card_id, card in (manifest.get("cardsById") or {}).items():
        if not isinstance(card_id, str) or not isinstance(card, dict):
            continue
        bounds = card.get("bounds")
        if rect_ok(bounds):
            components[card_id] = (bounds, "card")
    for module_id, module in (manifest.get("modulesById") or {}).items():
        if not isinstance(module_id, str) or not isinstance(module, dict):
            continue
        bounds = module.get("bounds")
        if rect_ok(bounds):
            components[module_id] = (bounds, "component")

    for card in manifest.get("cards") or []:
        if not isinstance(card, dict):
            continue
        component_id = card.get("cardId") or card.get("id")
        coord = card.get("coord")
        if isinstance(component_id, str) and rect_ok(coord):
            scope = "component" if card.get("卡片类型") == "宏观组件" else "card"
            components[component_id] = (coord, scope)
        for region in card.get("regions") or []:
            if not isinstance(region, dict):
                continue
            for element in region.get("elements") or []:
                if not isinstance(element, dict):
                    continue
                element_id = element.get("id")
                element_coord = element.get("坐标", element.get("coord"))
                if isinstance(element_id, str) and rect_ok(element_coord):
                    elements[element_id] = element_coord

    page_facts = manifest.get("pageFacts") or {}
    for module in page_facts.get("modules") or []:
        if not isinstance(module, dict):
            continue
        module_id = module.get("id")
        coord = module.get("coord")
        if isinstance(module_id, str) and rect_ok(coord):
            components[module_id] = (coord, "component")
    return elements, components


def resolve_issue_box(
    result: dict[str, Any],
    issue: dict[str, Any],
    elements: dict[str, list[float]],
    components: dict[str, tuple[list[float], str]],
) -> tuple[list[float] | None, str | None, str | None]:
    """Resolve a Phase2-confirmed display boundary for an evaluation issue."""
    dimension = result.get("dimension")
    if dimension == SINGLE_ELEMENT_DIMENSION:
        element_id = issue.get("elementId")
        if not isinstance(element_id, str) or not rect_ok(elements.get(element_id)):
            return None, None, "single_element_target_missing"
        component_id = issue.get("component") or issue.get("cardId")
        component = components.get(component_id) if isinstance(component_id, str) else None
        if component:
            coord, scope = component
            return coord, scope, None
        return None, None, f"single_element_context_boundary_missing:{component_id or 'unknown'}"

    if dimension == COMPONENT_DIMENSION:
        component_id = issue.get("component") or issue.get("cardId")
        component = components.get(component_id) if isinstance(component_id, str) else None
        if component:
            coord, scope = component
            return coord, scope, None
        return None, None, f"component_boundary_missing:{component_id or 'unknown'}"

    if dimension == PAGE_DIMENSION:
        coord = issue.get("evidenceCoord")
        if rect_ok(coord):
            return coord, "component", None
        return None, None, "page_region_boundary_missing"

    return None, None, f"unsupported_dimension:{dimension}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate full-page issue evidence images")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, help="Phase2 manifest used to resolve element and component boundaries")
    args = parser.parse_args()

    results = json.loads(args.results.read_text(encoding="utf-8"))
    if not isinstance(results, list):
        raise ValueError("results must be a JSON array")

    manifest_screenshot = ""
    elements: dict[str, list[float]] = {}
    components: dict[str, tuple[list[float], str]] = {}
    if args.manifest and args.manifest.is_file():
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if isinstance(manifest, dict):
            source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
            manifest_screenshot = str(manifest.get("screenshot") or source.get("screenshot") or "")
            elements, components = build_manifest_index(manifest)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    skipped: list[dict[str, str]] = []
    issues_by_screenshot: dict[str, list[tuple[dict[str, Any], list[float], str]]] = {}

    for result in results:
        if not isinstance(result, dict):
            continue
        skill = str(result.get("skill", "skill"))
        for unit in result.get("units", []):
            if not isinstance(unit, dict):
                continue
            details = unit.get("details") or {}
            screenshot = str(details.get("screenshot") or manifest_screenshot)
            for issue in details.get("issues") or []:
                if not isinstance(issue, dict) or str(issue.get("rating", "")) not in PROBLEM_RATINGS:
                    continue
                issue_key = f"{skill}/{unit.get('tab', '')}/{issue.get('elementId', issue.get('component', 'page'))}"
                coord, scope, reason = resolve_issue_box(result, issue, elements, components)
                if not screenshot or not rect_ok(coord) or not scope:
                    skipped.append({"issue": issue_key, "reason": reason or "screenshot_missing"})
                    continue
                issues_by_screenshot.setdefault(screenshot, []).append((issue, coord, scope))

    for screenshot, grouped_issues in issues_by_screenshot.items():
        evidence = Image.open(screenshot).convert("RGB")
        draw = ImageDraw.Draw(evidence)
        line_width = max(2, min(8, round(min(evidence.width, evidence.height) / 240)))
        drawn_boxes: set[tuple[int, int, int, int]] = set()
        for _, coord, _ in grouped_issues:
            x, y, w, h = (int(round(item)) for item in coord)
            box = (x, y, w, h)
            if box in drawn_boxes:
                continue
            drawn_boxes.add(box)
            draw.rectangle((x, y, x + w, y + h), outline="#E53935", width=line_width)

        path = args.output_dir / f"{safe_name(Path(screenshot).stem)}_all_issues.png"
        evidence.save(path)
        resolved_path = str(path.resolve())
        for issue, _, scope in grouped_issues:
            issue["evidenceImage"] = resolved_path
            issue["evidenceScope"] = scope
            if issue.get("elementId") in elements:
                issue["evidenceTargetElementId"] = issue["elementId"]
                issue["evidenceTargetCoord"] = elements[issue["elementId"]]
            issue.pop("evidenceCrop", None)
        created.append(resolved_path)

    args.results.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"created": created, "skipped": skipped, "count": len(created), "mode": "one-image-per-screenshot"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
