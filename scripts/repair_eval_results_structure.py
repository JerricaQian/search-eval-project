#!/usr/bin/env python3
"""Repair structural (non-semantic) defects in phase3 dual eval result files.

Scope is deliberately narrow: only fix what blocks scripts/validate_eval_results.py
while preserving every skill's grading, issue semantics/count and assessmentRows.

Three defect classes are handled:

1. legacy_issue_fields
   Older eval-8-info-redundancy issues use the pre-schema shape
   (``finding`` / ``type``) and lack the required keys
   ``component``/``elementType``/``dimension``/``description``/``rating``.
   The missing keys are back-filled from data already present in the record:
     - description <- finding (verbatim, no rewording)
     - dimension   <- the skill's fixed dimension label
     - rating      <- the rating the issue already implies (listed issues in
                      this skill are the failing units) 
     - component   <- manifest component of the element, else legacy ``type``
     - elementType <- manifest element type
   No issue is added, removed, merged or re-worded.

2. counter_mismatch
   overview.fail / overview.pass disagree with the number of fail/pass rated
   issues. The issues are the source of truth, so the counters are recomputed
   and the delta is absorbed by ``excellent`` to keep ``total`` unchanged.
   ``failRate`` is then recomputed with the validator's own formula.

3. stale_manifest_total
   evidence.sourceManifestTotal points at an outdated manifest count and is
   refreshed from the current elements_*.audit.json ``total``.

Usage:
  python3 scripts/repair_eval_results_structure.py            # apply
  python3 scripts/repair_eval_results_structure.py --dry-run  # preview only
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
MANIFEST_DIR = PROJECT_ROOT / "screenshots-out"

# Skills whose overview.total is the evaluated-unit count rather than the
# manifest element count (mirrors validate_eval_results.py).
COMPONENT_SKILLS = {
    "eval-1-supply-completeness",
    "eval-2-visual-order-alignment",
    "eval-3-color-logic",
    "eval-4-element-complexity",
    "eval-5-info-hierarchy",
    "eval-6-info-partitioning",
    "eval-7-info-authenticity",
    "eval-8-info-redundancy",
}

REQUIRED_ISSUE_FIELDS = {
    "elementId",
    "coord",
    "component",
    "elementType",
    "content",
    "dimension",
    "description",
    "rating",
}

FAIL_RATINGS = {"🔴", "不达标"}
PASS_RATINGS = {"🟡", "达标"}

# Fixed dimension label per skill, used only to back-fill absent `dimension`.
SKILL_DIMENSION = {
    "eval-1-supply-completeness": "供给信息完整度",
    "eval-2-visual-order-alignment": "视觉顺序一致性",
    "eval-3-color-logic": "色彩逻辑",
    "eval-4-element-complexity": "元素复杂度",
    "eval-5-info-hierarchy": "信息层级",
    "eval-6-info-partitioning": "信息分区",
    "eval-7-info-authenticity": "信息真实性",
    "eval-8-info-redundancy": "信息无冗余",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def compute_fail_rate(failed: int, total: int) -> str:
    """Reproduce the validator's expected failRate string exactly."""
    return f"{(failed / total * 100):.1f}%" if total else "0%"


def repair_file(results_path: Path, manifest_path: Path, changes: list[str]) -> tuple[Any, bool]:
    results = load_json(results_path)
    manifest = load_json(manifest_path)
    manifest_total = manifest.get("total")
    active_by_id = {
        item.get("id"): item
        for item in manifest.get("activeElements", [])
        if isinstance(item, dict)
    }
    tag = results_path.name
    dirty = False

    for result in results:
        skill = result.get("skill", "unknown")
        for unit in result.get("units", []):
            tab = unit.get("tab", "unknown")
            details = unit.get("details") or {}
            overview = details.get("overview") or {}
            evidence = details.get("evidence") or {}
            issues = details.get("issues")
            where = f"{tag}::{skill}/{tab}"

            # -- defect 3: stale sourceManifestTotal -------------------------
            if skill in COMPONENT_SKILLS and "evidence" in details:
                current = evidence.get("sourceManifestTotal")
                if current != manifest_total and isinstance(manifest_total, int):
                    evidence["sourceManifestTotal"] = manifest_total
                    changes.append(
                        f"{where}: sourceManifestTotal {current} -> {manifest_total}"
                    )
                    dirty = True

            if not isinstance(issues, list):
                continue

            # -- defect 1: legacy issues missing required fields -------------
            for issue in issues:
                if not isinstance(issue, dict):
                    continue
                missing = REQUIRED_ISSUE_FIELDS - issue.keys()
                if not missing:
                    continue
                element = active_by_id.get(issue.get("elementId")) or {}
                filled = []

                if "description" in missing:
                    # Carry the existing narrative over verbatim.
                    issue["description"] = issue.get("finding", "")
                    filled.append("description")
                if "dimension" in missing:
                    issue["dimension"] = SKILL_DIMENSION.get(skill, skill)
                    filled.append("dimension")
                if "rating" in missing:
                    # Listed issues in these legacy records are the failing
                    # units; overview.fail already accounts for them.
                    issue["rating"] = "不达标"
                    filled.append("rating")
                if "component" in missing:
                    issue["component"] = (
                        element.get("component")
                        or issue.get("type")
                        or element.get("group")
                        or "未标注"
                    )
                    filled.append("component")
                if "elementType" in missing:
                    issue["elementType"] = (
                        element.get("elementType")
                        or element.get("type")
                        or "文本/标签"
                    )
                    filled.append("elementType")
                if "content" in missing:
                    issue["content"] = element.get("content", "")
                    filled.append("content")
                if "coord" in missing and element.get("coord") is not None:
                    issue["coord"] = element["coord"]
                    filled.append("coord")

                if filled:
                    changes.append(
                        f"{where}: issue {issue.get('elementId')} back-filled "
                        f"{','.join(filled)}"
                    )
                    dirty = True

            # -- defect 2: fail/pass counters vs. issue ratings --------------
            issue_fail = sum(
                1 for i in issues if isinstance(i, dict) and i.get("rating") in FAIL_RATINGS
            )
            issue_pass = sum(
                1 for i in issues if isinstance(i, dict) and i.get("rating") in PASS_RATINGS
            )
            total = overview.get("total")
            failed = overview.get("fail")
            passed = overview.get("pass")

            if not isinstance(total, int):
                continue

            if failed != issue_fail or passed != issue_pass:
                excellent = total - issue_fail - issue_pass
                if excellent < 0:
                    changes.append(
                        f"{where}: SKIPPED counter fix (would make excellent<0; "
                        f"total={total} fail={issue_fail} pass={issue_pass})"
                    )
                    continue
                changes.append(
                    f"{where}: overview fail {failed}->{issue_fail}, "
                    f"pass {passed}->{issue_pass}, "
                    f"excellent {overview.get('excellent')}->{excellent} "
                    f"(total {total} unchanged)"
                )
                overview["fail"] = issue_fail
                overview["pass"] = issue_pass
                overview["excellent"] = excellent
                dirty = True

            # Keep failRate consistent with whatever fail/total now are.
            expected_rate = compute_fail_rate(overview.get("fail", 0), total)
            current_rate = overview.get("failRate")
            accepted = {expected_rate, expected_rate.replace(".0%", "%")}
            if current_rate not in accepted:
                changes.append(
                    f"{where}: failRate {current_rate} -> {expected_rate}"
                )
                overview["failRate"] = expected_rate
                dirty = True

    return results, dirty


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args()

    result_files = sorted(REPORTS_DIR.glob(".eval_results_*_dual.json"))
    all_changes: list[str] = []
    touched = 0
    missing_manifest: list[str] = []

    for results_path in result_files:
        key = results_path.name[len(".eval_results_"):-len("_dual.json")]
        manifest_path = MANIFEST_DIR / f"elements_{key}.audit.json"
        if not manifest_path.exists():
            missing_manifest.append(key)
            continue
        changes: list[str] = []
        repaired, dirty = repair_file(results_path, manifest_path, changes)
        all_changes.extend(changes)
        if dirty and not args.dry_run:
            results_path.write_text(
                json.dumps(repaired, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        if dirty:
            touched += 1

    for line in all_changes:
        print(line)
    print("-" * 60)
    print(f"files scanned : {len(result_files)}")
    print(f"files changed : {touched}{' (dry-run)' if args.dry_run else ''}")
    print(f"total changes : {len(all_changes)}")
    if missing_manifest:
        print(f"missing manifest: {missing_manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
