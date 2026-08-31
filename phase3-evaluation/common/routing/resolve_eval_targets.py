#!/usr/bin/env python3
"""Resolve a user-selected Phase3 evaluation scope into canonical eval targets.

This is deliberately a small deterministic boundary: user-facing selection is
validated here, while leaf Skills retain their own judging criteria.  The
resolver never reads screenshots and never produces an experience judgement.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PHASE3_DIR = Path(__file__).resolve().parents[2]
SHARED_SCRIPTS_DIR = PHASE3_DIR.parent / "scripts"
CATALOG_PATH = PHASE3_DIR / "catalog.json"
if str(SHARED_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_SCRIPTS_DIR))

from skill_frontmatter import FRONTMATTER_PATTERN, load_weight


SELECTION_MODES = {"full_19", "dimensions", "custom_skills"}
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def fail(message: str) -> ValueError:
    return ValueError(message)


def string_field(frontmatter: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
    if not match:
        raise fail(f"frontmatter_missing:{key}")
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def load_skill(path: Path, dimension: dict[str, Any], project_dir: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise fail(f"skill_unreadable:{path}") from exc
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        raise fail(f"frontmatter_missing:{path}")
    frontmatter = match.group(1)
    weight = load_weight(path)
    if not weight or "优秀" not in weight or "不达标" not in weight:
        raise fail(f"frontmatter_weight_invalid:{path}")
    return {
        "dimension": dimension["id"],
        "skill": path.parent.name,
        "title": string_field(frontmatter, "title"),
        "weight": {
            "优秀": weight["优秀"],
            "达标": weight.get("达标", 0),
            "不达标": weight["不达标"],
        },
        "aggregate": string_field(frontmatter, "aggregate"),
        "extra": string_field(frontmatter, "extra") if re.search(r"^extra:", frontmatter, re.MULTILINE) else "",
        "skillPath": str(path.relative_to(project_dir)),
        "skillsDir": str((PHASE3_DIR / dimension["skillsDir"]).relative_to(project_dir)),
        "contractPath": str((PHASE3_DIR / dimension["contract"]).relative_to(project_dir)),
    }


def load_catalog(project_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if project_dir != PHASE3_DIR.parent:
        catalog_path = project_dir / "phase3-evaluation" / "catalog.json"
    else:
        catalog_path = CATALOG_PATH
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise fail(f"catalog_unreadable:{catalog_path}") from exc
    dimensions = payload.get("dimensions")
    if payload.get("schemaVersion") != "phase3.catalog.v1" or not isinstance(dimensions, list):
        raise fail("catalog_schema_invalid")

    targets: list[dict[str, Any]] = []
    seen_dimensions: set[str] = set()
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            raise fail("catalog_dimension_invalid")
        dimension_id = validate_identifier(dimension.get("id"), "catalog_dimension")
        if dimension_id in seen_dimensions:
            raise fail(f"catalog_dimension_duplicate:{dimension_id}")
        seen_dimensions.add(dimension_id)
        skills = dimension.get("skills")
        if not isinstance(skills, list) or not skills:
            raise fail(f"catalog_skills_invalid:{dimension_id}")
        base = project_dir / "phase3-evaluation" / str(dimension.get("skillsDir", ""))
        contract = project_dir / "phase3-evaluation" / str(dimension.get("contract", ""))
        if not base.is_dir() or not contract.is_file():
            raise fail(f"dimension_missing:{dimension_id}")
        discovered = {path.parent.name for path in base.glob("eval-*/SKILL.md")}
        declared = [validate_identifier(skill, "catalog_skill") for skill in skills]
        if len(set(declared)) != len(declared):
            raise fail(f"catalog_skill_duplicate:{dimension_id}")
        if discovered != set(declared):
            raise fail(f"catalog_skill_drift:{dimension_id}")
        for skill in declared:
            targets.append(load_skill(base / skill / "SKILL.md", dimension, project_dir))
    if len(targets) != 19:
        raise fail(f"canonical_skill_count_expected_19_actual_{len(targets)}")
    return dimensions, targets


def validate_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise fail(f"{label}_invalid")
    return value


def normalize_selection(raw: Any, legacy_dimensions: list[str] | None) -> tuple[dict[str, Any], bool]:
    if raw is None:
        dimensions = legacy_dimensions or ["phase3-card_or_component-eval"]
        return {"mode": "dimensions", "dimensions": dimensions}, True
    if not isinstance(raw, dict):
        raise fail("evaluationSelection_must_be_object")
    mode = raw.get("mode")
    if mode not in SELECTION_MODES:
        raise fail("evaluationSelection_mode_must_be_full_19_dimensions_or_custom_skills")
    if mode == "full_19":
        return {"mode": mode}, False
    if mode == "dimensions":
        dimensions = raw.get("dimensions")
        if not isinstance(dimensions, list) or not dimensions:
            raise fail("evaluationSelection_dimensions_required")
        values = [validate_identifier(item, "dimension") for item in dimensions]
        if len(set(values)) != len(values):
            raise fail("evaluationSelection_dimensions_duplicate")
        return {"mode": mode, "dimensions": values}, False
    skills = raw.get("skills")
    if not isinstance(skills, list) or not skills:
        raise fail("evaluationSelection_skills_required")
    normalized: list[dict[str, str]] = []
    for item in skills:
        if not isinstance(item, dict):
            raise fail("evaluationSelection_skill_must_be_object")
        normalized.append({
            "dimension": validate_identifier(item.get("dimension"), "skill_dimension"),
            "skill": validate_identifier(item.get("skill"), "skill"),
        })
    keys = [(item["dimension"], item["skill"]) for item in normalized]
    if len(set(keys)) != len(keys):
        raise fail("evaluationSelection_skills_duplicate")
    return {"mode": mode, "skills": normalized}, False


def resolve(project_dir: Path, raw_selection: Any, legacy_dimensions: list[str] | None = None) -> dict[str, Any]:
    selection, legacy = normalize_selection(raw_selection, legacy_dimensions)
    dimension_catalog, all_targets = load_catalog(project_dir)
    canonical_dimensions = tuple(item["id"] for item in dimension_catalog)
    by_key = {(item["dimension"], item["skill"]): item for item in all_targets}

    if selection["mode"] == "full_19":
        chosen = list(all_targets)
    elif selection["mode"] == "dimensions":
        dimensions = selection["dimensions"]
        unknown = [dimension for dimension in dimensions if dimension not in canonical_dimensions]
        if unknown:
            raise fail("evaluationSelection_dimension_unknown:" + ",".join(unknown))
        chosen = [item for item in all_targets if item["dimension"] in dimensions]
    else:
        requested = [(item["dimension"], item["skill"]) for item in selection["skills"]]
        unknown = [f"{dimension}/{skill}" for dimension, skill in requested if (dimension, skill) not in by_key]
        if unknown:
            raise fail("evaluationSelection_skill_unknown:" + ",".join(unknown))
        chosen = [by_key[key] for key in requested]

    dimensions = [dimension for dimension in canonical_dimensions if any(item["dimension"] == dimension for item in chosen)]
    if not chosen:
        raise fail("evaluationSelection_resolved_empty")
    return {
        "ok": True,
        "schemaVersion": "phase3.eval-selection.v1",
        "selection": selection,
        "legacyDimensionsFallback": legacy,
        "dimensions": dimensions,
        "evalTargets": chosen,
        "coverage": {
            "selectedCount": len(chosen),
            "fullCount": len(all_targets),
            "isFull": len(chosen) == len(all_targets),
            "label": "完整19项评测" if len(chosen) == len(all_targets) else f"已选{len(chosen)}/{len(all_targets)}项评测",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve user-selected Phase3 eval Skills.")
    parser.add_argument("--project-dir", required=True, type=Path)
    parser.add_argument("--selection-json", default="")
    parser.add_argument("--legacy-dimensions", nargs="*")
    parser.add_argument("--output", type=Path, help="Optional JSON output path for downstream report tooling.")
    parser.add_argument("--eval-targets-output", type=Path, help="Optional canonical evalTargets-list output path.")
    args = parser.parse_args()
    try:
        raw = json.loads(args.selection_json) if args.selection_json else None
        payload = resolve(args.project_dir.resolve(), raw, args.legacy_dimensions)
        rendered = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        if args.eval_targets_output:
            args.eval_targets_output.parent.mkdir(parents=True, exist_ok=True)
            args.eval_targets_output.write_text(
                json.dumps(payload["evalTargets"], ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        print(rendered)
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stdout)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
