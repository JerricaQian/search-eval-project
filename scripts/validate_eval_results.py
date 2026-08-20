#!/usr/bin/env python3
"""Validate deterministic overview accounting in phase3 evaluation results."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


COMPONENT_ROW_REQUIREMENTS: dict[str, set[str]] = {
    "eval-1-supply-completeness": {"componentId", "visibleBounds", "applicableFields", "checkResults", "rating"},
    "eval-2-visual-order-alignment": {"comparisonGroupKey", "members", "layoutSignatures", "readingOrderChecks", "rating"},
    "eval-3-color-logic": {"componentId", "validUiPixelCount", "excludedPhotoPixelCount", "colorFamilies", "colorFamilyCount", "debugImage", "rating"},
    "eval-4-element-complexity": {"componentId", "scannedRegions", "includedTagStyles", "includedIconStyles", "excludedEntities", "tagStyleCount", "iconStyleCount", "rating"},
    "eval-5-info-hierarchy": {"componentId", "sourceElements", "weightSequence", "tierTrace", "levelCount", "rating"},
    "eval-6-info-partitioning": {"componentId", "partitions", "adjacentBoundaryChecks", "issueCount", "rating"},
    "eval-7-info-authenticity": {"componentId", "candidatePairs", "pairJudgements", "inapplicableChecks", "conflicts", "conflictCount", "rating"},
    "eval-8-info-redundancy": {"regionId", "regionType", "examinedElements", "candidatePairs", "duplicateCount", "rating"},
}

MEASUREMENT_REQUIRED_SKILLS = {
    "eval-3-color-logic",
    "eval-4-element-complexity",
    "eval-6-info-partitioning",
    "eval-3-page-color-logic",
    "eval-6-info-comparability",
    "eval-7-info-authenticity",
    "eval-8-info-redundancy",
}

FORBIDDEN_COPY_TERMS_PATH = Path(__file__).with_name("forbidden_copy_terms.json")
FORBIDDEN_ID_PATTERN_EXEMPTIONS = {"P0", "P1", "P2"}


def _load_forbidden_copy_terms() -> dict[str, Any]:
    return json.loads(FORBIDDEN_COPY_TERMS_PATH.read_text(encoding="utf-8"))


def require_no_forbidden_terms(errors: list[str], prefix: str, text: str) -> None:
    """Block internal IDs/field names/script filenames/English enums leaking into reader-facing copy."""
    if not isinstance(text, str) or not text:
        return
    terms = _load_forbidden_copy_terms()
    for pattern in terms.get("internal_id_patterns", []):
        for match in re.finditer(pattern, text):
            if match.group(0) in FORBIDDEN_ID_PATTERN_EXEMPTIONS:
                continue
            errors.append(f"{prefix}:copy_contains_internal_id:{match.group(0)}")
    for field_name in terms.get("internal_field_names", []):
        if re.search(rf"\b{re.escape(field_name)}\b", text):
            errors.append(f"{prefix}:copy_contains_internal_field_name:{field_name}")
    script_pattern = terms.get("script_filename_pattern")
    if script_pattern and re.search(script_pattern, text):
        errors.append(f"{prefix}:copy_contains_script_filename")
    enum_pattern = terms.get("english_enum_pattern")
    if enum_pattern and re.search(enum_pattern, text, re.IGNORECASE):
        errors.append(f"{prefix}:copy_contains_english_enum_value")


def require_recommendation_matches_threshold(errors: list[str], prefix: str, issue: dict[str, Any]) -> None:
    """Block optimization suggestions whose stated acceptance threshold drifts from the issue's own rule."""
    finding = issue.get("finding") if isinstance(issue.get("finding"), dict) else {}
    rule = str(finding.get("ruleOrThreshold") or "")
    recommendation = str(issue.get("recommendation") or "")
    rule_numbers = set(re.findall(r"\d+", rule))
    recommendation_numbers = set(re.findall(r"\d+", recommendation))
    if rule_numbers and recommendation_numbers and rule_numbers.isdisjoint(recommendation_numbers):
        errors.append(f"{prefix}:recommendation_threshold_must_match_ruleOrThreshold")


PAGE_EVIDENCE_REQUIREMENTS: dict[str, set[str]] = {
    "eval-1-supply-module-completeness": {"modules", "expectedModules", "layoutChecks", "rating"},
    "eval-2-visual-order-alignment": {"pageRegions", "sameTypeComparisons", "rating"},
    "eval-3-page-color-logic": {"validUiPixelCount", "excludedPhotoPixelCount", "colorFamilies", "colorFamilyCount", "debugImage", "rating"},
    "eval-4-static-component-complexity": {"firstScreenBounds", "functionalModules", "moduleCount", "rating"},
    "eval-5-browsing-flow-smoothness": {"listPositions", "visibleListPositionCount", "coverageStatus", "heterogeneousCount", "rating"},
    "eval-6-info-comparability": {"cardGroups", "comparableFields", "comparisons", "inconsistencyCount", "rating"},
    "eval-7-info-redundancy": {"pageRegions", "candidatePairs", "redundancyCount", "rating"},
}


def require_row_fields(errors: list[str], prefix: str, row: Any, required: set[str]) -> bool:
    if not isinstance(row, dict):
        errors.append(f"{prefix}:assessmentRow_must_be_object")
        return False
    missing = required - row.keys()
    if missing:
        errors.append(f"{prefix}:assessmentRow_missing_fields:{','.join(sorted(missing))}")
        return False
    return True


def require_non_empty_string(errors: list[str], prefix: str, payload: dict[str, Any], field: str) -> None:
    if not isinstance(payload.get(field), str) or not payload[field].strip():
        errors.append(f"{prefix}:{field}_must_be_non_empty_string")


def require_measurement(errors: list[str], prefix: str, row: dict[str, Any]) -> None:
    """Require a reproducible measurement record when a Skill relies on deterministic metrics."""
    measurement = row.get("measurement")
    if not isinstance(measurement, dict):
        errors.append(f"{prefix}:measurement_must_be_object")
        return
    tool = measurement.get("tool")
    artifact_path = measurement.get("artifactPath")
    parameters = measurement.get("parameters")
    if not isinstance(tool, str) or not tool.strip() or not Path(tool).is_file():
        errors.append(f"{prefix}:measurement_tool_missing")
    if not isinstance(artifact_path, str) or not artifact_path or not Path(artifact_path).is_file():
        errors.append(f"{prefix}:measurement_artifact_missing")
    if not isinstance(parameters, dict) or not parameters:
        errors.append(f"{prefix}:measurement_parameters_must_be_non_empty_object")


def require_structured_finding(errors: list[str], prefix: str, issue: dict[str, Any]) -> None:
    """Require the complete issue payload consumed by Phase4/5."""
    finding = issue.get("finding")
    if not isinstance(finding, dict):
        errors.append(f"{prefix}:finding_must_be_object")
    else:
        for field in ("observableFact", "ruleOrThreshold", "verdictReason", "userImpact"):
            require_non_empty_string(errors, f"{prefix}/finding", finding, field)
    require_non_empty_string(errors, prefix, issue, "recommendation")


def require_component_copy_consistency(
    errors: list[str],
    prefix: str,
    skill: str,
    issue: dict[str, Any],
    assessment_rows: Any,
) -> None:
    """Block issue copy that contradicts or degrades deterministic component measurements."""
    if not isinstance(assessment_rows, list):
        return
    component_id = str(issue.get("component") or "")
    row = next((item for item in assessment_rows if isinstance(item, dict) and str(item.get("componentId") or "") == component_id), None)
    if not isinstance(row, dict):
        return
    finding = issue.get("finding") if isinstance(issue.get("finding"), dict) else {}
    observable_fact = str(finding.get("observableFact") or "")
    rule = str(finding.get("ruleOrThreshold") or "")
    verdict = str(finding.get("verdictReason") or "")
    combined = f"{observable_fact} {rule} {verdict}"
    rating = str(issue.get("rating") or "")
    if skill == "eval-3-color-logic":
        count = row.get("colorFamilyCount")
        families = row.get("colorFamilies")
        if not isinstance(count, int) or count < 0:
            return
        if str(count) not in observable_fact:
            errors.append(f"{prefix}:color_copy_must_include_measured_colorFamilyCount")
        if not isinstance(families, list) or not families:
            errors.append(f"{prefix}:color_copy_requires_colorFamilies")
        if re.search(r"\b(?:red|orange|yellow|green|blue|cyan|magenta|purple)\b", combined, re.IGNORECASE):
            errors.append(f"{prefix}:color_copy_must_use_chinese_family_names")
        expected_rating = "优秀" if count <= 3 else "达标" if count <= 5 else "不达标"
        if rating != expected_rating or expected_rating not in verdict:
            errors.append(f"{prefix}:color_copy_rating_must_match_measured_count")
    elif skill == "eval-4-element-complexity":
        tag_count = row.get("tagStyleCount")
        icon_count = row.get("iconStyleCount")
        if not isinstance(tag_count, int) or not isinstance(icon_count, int):
            return
        if str(tag_count) not in observable_fact or str(icon_count) not in observable_fact:
            errors.append(f"{prefix}:complexity_copy_must_include_tag_and_icon_counts")
        expected_rating = "不达标" if tag_count > 4 or icon_count > 3 else "优秀" if tag_count <= 2 and icon_count <= 1 else "达标"
        if rating != expected_rating or expected_rating not in verdict:
            errors.append(f"{prefix}:complexity_copy_rating_must_match_measured_counts")
    elif skill == "eval-5-info-hierarchy":
        level_count = row.get("levelCount")
        tier_trace = row.get("tierTrace")
        if not isinstance(level_count, int) or level_count < 0:
            return
        if str(level_count) not in observable_fact:
            errors.append(f"{prefix}:hierarchy_copy_must_include_measured_levelCount")
        if not isinstance(tier_trace, list) or not tier_trace:
            errors.append(f"{prefix}:hierarchy_copy_requires_tierTrace")
        expected_rating = "优秀" if 3 <= level_count <= 5 else "不达标"
        if rating != expected_rating or expected_rating not in verdict:
            errors.append(f"{prefix}:hierarchy_copy_rating_must_match_measured_levelCount")
    elif skill == "eval-7-info-authenticity":
        statuses = row.get("pairJudgements")
        conflict_count = row.get("conflictCount")
        if not isinstance(conflict_count, int) or conflict_count < 0:
            return
        if str(conflict_count) not in observable_fact:
            errors.append(f"{prefix}:authenticity_copy_must_include_measured_conflictCount")
        if not isinstance(statuses, list) or not statuses:
            errors.append(f"{prefix}:authenticity_copy_requires_pairJudgements")
        expected_rating = "优秀" if conflict_count == 0 else "不达标"
        if rating != expected_rating or expected_rating not in verdict:
            errors.append(f"{prefix}:authenticity_copy_rating_must_match_measured_conflictCount")


def require_complexity_description(errors: list[str], prefix: str, issue: dict[str, Any]) -> None:
    """Block opaque threshold-only wording: readers must see the actual counted objects."""
    description = issue.get("description")
    fact = (issue.get("finding") or {}).get("observableFact") if isinstance(issue.get("finding"), dict) else ""
    combined = f"{description or ''}{fact or ''}"
    prohibited = "图标样式数量为 2 至 3 种且未触发不达标条件时评级为达标"
    if not isinstance(description, str) or not description.strip():
        errors.append(f"{prefix}:complexity_description_missing")
    elif prohibited in combined:
        errors.append(f"{prefix}:complexity_description_must_not_repeat_template_rule")
    if "「" not in combined or "种" not in combined:
        errors.append(f"{prefix}:complexity_description_must_list_visible_objects_and_count")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate evaluation result accounting")
    parser.add_argument("--manifest-audit", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True, help="JSON array of EVAL_SCHEMA results")
    parser.add_argument("--audit", type=Path, help="Write audit JSON")
    parser.add_argument("--phase2-review", type=Path, help="Write pending Phase2 re-recognition requests for unsupported component findings")
    parser.add_argument("--require-evidence", action="store_true", help="Require a local evidence image for every failed element issue")
    args = parser.parse_args()

    manifest = json.loads(args.manifest_audit.read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = json.loads(args.results.read_text(encoding="utf-8"))
    expected_total = manifest.get("total")
    manifest_query = manifest.get("query", "")
    if not isinstance(manifest_query, str) or not manifest_query.strip():
        match = re.match(r"^elements_(.+?)(?:_[^/]+)?\.audit\.json$", args.manifest_audit.name)
        manifest_query = match.group(1) if match else ""
    active_by_id = {item.get("id"): item for item in manifest.get("activeElements", []) if isinstance(item, dict)}
    page_framework_dimension = "phase3-page_framework-eval"
    component_skills = {
        "eval-1-supply-completeness",
        "eval-2-visual-order-alignment",
        "eval-3-color-logic",
        "eval-4-element-complexity",
        "eval-5-info-hierarchy",
        "eval-6-info-partitioning",
        "eval-7-info-authenticity",
        "eval-8-info-redundancy",
    }
    errors: list[str] = []
    phase2_review_items: list[dict[str, Any]] = []
    if not manifest.get("valid") or not isinstance(expected_total, int) or expected_total <= 0:
        errors.append("manifest_audit_invalid")

    for result in results:
        skill = result.get("skill", "unknown")
        for unit in result.get("units", []):
            tab = unit.get("tab", "unknown")
            details = unit.get("details") or {}
            if not isinstance(details, dict):
                errors.append(f"{skill}/{tab}:details_must_be_object")
                continue
            require_non_empty_string(errors, f"{skill}/{tab}", unit, "reason")
            require_non_empty_string(errors, f"{skill}/{tab}", details, "criterion")
            require_non_empty_string(errors, f"{skill}/{tab}", details, "summary")
            require_no_forbidden_terms(errors, f"{skill}/{tab}:reason", str(unit.get("reason") or ""))
            require_no_forbidden_terms(errors, f"{skill}/{tab}:criterion", str(details.get("criterion") or ""))
            require_no_forbidden_terms(errors, f"{skill}/{tab}:summary", str(details.get("summary") or ""))
            screenshot = details.get("screenshot")
            if not isinstance(screenshot, str) or not screenshot or not Path(screenshot).is_file():
                errors.append(f"{skill}/{tab}:screenshot_must_reference_existing_original")
            evidence_mode = details.get("evidenceMode")
            if evidence_mode not in {"annotated-region", "original-page", "hybrid"}:
                errors.append(f"{skill}/{tab}:evidenceMode_invalid:{evidence_mode}")
            overview = details.get("overview") or {}
            values = [overview.get("total"), overview.get("excellent"), overview.get("pass"), overview.get("fail")]
            if not all(isinstance(value, int) and value >= 0 for value in values):
                errors.append(f"{skill}/{tab}:overview_requires_non_negative_integers")
                continue
            total, excellent, passed, failed = values
            evidence = (unit.get("details") or {}).get("evidence") or {}
            if result.get("dimension") == page_framework_dimension:
                if total != 1:
                    errors.append(f"{skill}/{tab}:page_framework_overview_total_must_equal_1")
                assessment_rows = evidence.get("assessmentRows")
                if evidence_mode not in {"original-page", "hybrid", "annotated-region"}:
                    errors.append(f"{skill}/{tab}:page_framework_requires_evidence_mode")
                required_page_fields = PAGE_EVIDENCE_REQUIREMENTS.get(skill)
                measurement_required = skill in MEASUREMENT_REQUIRED_SKILLS
                if unit.get("rating") != "优秀" or measurement_required:
                    if not isinstance(assessment_rows, list) or len(assessment_rows) != 1:
                        errors.append(f"{skill}/{tab}:page_framework_requires_exactly_one_assessmentRow")
                    elif required_page_fields:
                        require_row_fields(errors, f"{skill}/{tab}", assessment_rows[0], required_page_fields)
                        if measurement_required and isinstance(assessment_rows[0], dict):
                            require_measurement(errors, f"{skill}/{tab}/row_1", assessment_rows[0])
                    else:
                        errors.append(f"{skill}/{tab}:unknown_page_framework_skill_without_evidence_contract")
                if skill == "eval-6-info-comparability" and isinstance(assessment_rows, list) and assessment_rows:
                    row = assessment_rows[0]
                    if isinstance(row, dict):
                        for field in ("cardGroups", "comparableFields", "comparisons"):
                            if not isinstance(row.get(field), list):
                                errors.append(f"{skill}/{tab}:{field}_must_be_array")
                        comparisons = row.get("comparisons")
                        if isinstance(comparisons, list):
                            for index, comparison in enumerate(comparisons, start=1):
                                if not isinstance(comparison, dict) or not {
                                    "comparisonGroupKey", "semanticRole", "observations",
                                    "detectedDifferences", "phase3Judgement",
                                }.issubset(comparison):
                                    errors.append(f"{skill}/{tab}:comparison_{index}_missing_phase3_derivation_trace")
                                    continue
                                if not isinstance(comparison.get("observations"), list) or len(comparison["observations"]) < 2:
                                    errors.append(f"{skill}/{tab}:comparison_{index}_requires_two_observations")
                                if not isinstance(comparison.get("detectedDifferences"), dict):
                                    errors.append(f"{skill}/{tab}:comparison_{index}_detectedDifferences_invalid")
                                if comparison.get("phase3Judgement") not in {"consistent", "inconsistent", "not_material", "needs_review"}:
                                    errors.append(f"{skill}/{tab}:comparison_{index}_phase3Judgement_invalid")
                page_issues = (unit.get("details") or {}).get("issues")
                if unit.get("rating") in {"达标", "不达标", "🟡", "🔴"} and (not isinstance(page_issues, list) or not page_issues):
                    errors.append(f"{skill}/{tab}:actionable_page_result_requires_non_empty_issues")
                if page_issues is not None and not isinstance(page_issues, list):
                    errors.append(f"{skill}/{tab}:page_framework_issues_must_be_array")
                    page_issues = []
                page_issue_required = {"pageArea", "dimension", "description", "rating", "priority", "priorityReason", "finding", "recommendation"}
                page_recommendations: set[str] = set()
                for issue in page_issues or []:
                    if not isinstance(issue, dict):
                        errors.append(f"{skill}/{tab}:page_framework_issue_must_be_object")
                        continue
                    missing_page_fields = page_issue_required - issue.keys()
                    if missing_page_fields:
                        errors.append(f"{skill}/{tab}:page_framework_issue_missing_fields:{','.join(sorted(missing_page_fields))}")
                    require_structured_finding(errors, f"{skill}/{tab}:page_framework_issue", issue)
                    issue_finding = issue.get("finding") if isinstance(issue.get("finding"), dict) else {}
                    require_no_forbidden_terms(errors, f"{skill}/{tab}:page_framework_issue:observableFact", str(issue_finding.get("observableFact") or ""))
                    require_no_forbidden_terms(errors, f"{skill}/{tab}:page_framework_issue:description", str(issue.get("description") or ""))
                    require_no_forbidden_terms(errors, f"{skill}/{tab}:page_framework_issue:recommendation", str(issue.get("recommendation") or ""))
                    require_recommendation_matches_threshold(errors, f"{skill}/{tab}:page_framework_issue", issue)
                    recommendation = str(issue.get("recommendation", "")).strip()
                    if recommendation and recommendation in page_recommendations:
                        errors.append(f"{skill}/{tab}:page_framework_issue_recommendation_must_be_issue_specific")
                    page_recommendations.add(recommendation)
                    forbidden_fields = {"elementId", "coord", "component", "elementType", "content"} & issue.keys()
                    if forbidden_fields:
                        errors.append(f"{skill}/{tab}:page_framework_issue_forbidden_fields:{','.join(sorted(forbidden_fields))}")
                    if args.require_evidence and issue.get("rating") in {"达标", "不达标", "🟡", "🔴"}:
                        evidence_path = issue.get("evidenceImage")
                        if not isinstance(evidence_path, str) or not evidence_path or not Path(evidence_path).is_file():
                            errors.append(f"{skill}/{tab}:page_framework_issue_evidence_image_missing")
            elif skill in component_skills:
                evaluated_unit_count = evidence.get("evaluatedUnitCount")
                assessment_rows = evidence.get("assessmentRows")
                measurement_required = skill in MEASUREMENT_REQUIRED_SKILLS
                evidence_required = unit.get("rating") != "优秀" or measurement_required or skill in {"eval-2-visual-order-alignment", "eval-7-info-authenticity"}
                if evidence_required:
                    if not isinstance(evaluated_unit_count, int) or evaluated_unit_count < 0:
                        errors.append(f"{skill}/{tab}:component_evaluatedUnitCount_required")
                    elif total != evaluated_unit_count:
                        errors.append(f"{skill}/{tab}:overview_total_{total}_must_equal_evaluatedUnitCount_{evaluated_unit_count}")
                    if not isinstance(assessment_rows, list) or len(assessment_rows) != evaluated_unit_count:
                        errors.append(f"{skill}/{tab}:component_assessmentRows_must_match_evaluatedUnitCount")
                    if evidence.get("sourceManifestTotal") != expected_total:
                        errors.append(f"{skill}/{tab}:sourceManifestTotal_must_equal_{expected_total}")
                    required_component_fields = COMPONENT_ROW_REQUIREMENTS.get(skill)
                    if isinstance(assessment_rows, list) and required_component_fields:
                        for index, row in enumerate(assessment_rows, start=1):
                            require_row_fields(errors, f"{skill}/{tab}/row_{index}", row, required_component_fields)
                            if measurement_required and isinstance(row, dict):
                                require_measurement(errors, f"{skill}/{tab}/row_{index}", row)
                if skill == "eval-2-visual-order-alignment" and isinstance(assessment_rows, list):
                    for index, row in enumerate(assessment_rows, start=1):
                        if isinstance(row, dict) and (not isinstance(row.get("comparisonGroupKey"), str) or not row["comparisonGroupKey"].strip()):
                            errors.append(f"{skill}/{tab}:alignment_assessmentRow_{index}_comparisonGroupKey_invalid")
                if skill == "eval-7-info-authenticity" and isinstance(assessment_rows, list):
                    for index, row in enumerate(assessment_rows, start=1):
                        if not isinstance(row, dict):
                            continue
                        relations = row.get("candidatePairs")
                        statuses = row.get("pairJudgements")
                        inapplicable = row.get("inapplicableChecks")
                        if not isinstance(relations, list):
                            errors.append(f"{skill}/{tab}:authenticity_assessmentRow_{index}_candidatePairs_invalid")
                        if not isinstance(statuses, list) or len(statuses) != len(relations or []):
                            errors.append(f"{skill}/{tab}:authenticity_assessmentRow_{index}_pairJudgements_must_match_candidates")
                        elif any(status not in {"consistent", "conflict", "not_applicable"} for status in statuses):
                            errors.append(f"{skill}/{tab}:authenticity_assessmentRow_{index}_pairJudgements_invalid")
                        if not isinstance(inapplicable, list):
                            errors.append(f"{skill}/{tab}:authenticity_assessmentRow_{index}_inapplicableChecks_must_be_array")
                if skill == "eval-4-element-complexity" and isinstance(assessment_rows, list):
                    for index, row in enumerate(assessment_rows, start=1):
                        if not isinstance(row, dict):
                            errors.append(f"{skill}/{tab}:complexity_assessmentRow_{index}_must_be_object")
                            continue
                        required_complexity_fields = {
                            "componentId", "scannedRegions", "includedTagStyles", "includedIconStyles",
                            "excludedEntities", "tagStyleCount", "iconStyleCount", "rating",
                        }
                        missing_complexity_fields = required_complexity_fields - row.keys()
                        if missing_complexity_fields:
                            errors.append(
                                f"{skill}/{tab}:complexity_assessmentRow_{index}_missing_fields:"
                                f"{','.join(sorted(missing_complexity_fields))}"
                            )
                            continue
                        if not isinstance(row["scannedRegions"], list) or not row["scannedRegions"]:
                            errors.append(f"{skill}/{tab}:complexity_assessmentRow_{index}_scannedRegions_invalid")
                        for field in ("includedTagStyles", "includedIconStyles", "excludedEntities"):
                            if not isinstance(row[field], list):
                                errors.append(f"{skill}/{tab}:complexity_assessmentRow_{index}_{field}_must_be_array")
                        tag_count = row.get("tagStyleCount")
                        icon_count = row.get("iconStyleCount")
                        if not isinstance(tag_count, int) or tag_count < 0:
                            errors.append(f"{skill}/{tab}:complexity_assessmentRow_{index}_tagStyleCount_invalid")
                        elif isinstance(row.get("includedTagStyles"), list) and tag_count != len(row["includedTagStyles"]):
                            errors.append(f"{skill}/{tab}:complexity_assessmentRow_{index}_tagStyleCount_mismatch")
                        if not isinstance(icon_count, int) or icon_count < 0:
                            errors.append(f"{skill}/{tab}:complexity_assessmentRow_{index}_iconStyleCount_invalid")
                        elif isinstance(row.get("includedIconStyles"), list) and icon_count != len(row["includedIconStyles"]):
                            errors.append(f"{skill}/{tab}:complexity_assessmentRow_{index}_iconStyleCount_mismatch")
                        if isinstance(tag_count, int) and isinstance(icon_count, int):
                            expected_rating = "不达标" if tag_count > 4 or icon_count > 3 else "优秀" if tag_count <= 2 and icon_count <= 1 else "达标"
                            if row.get("rating") != expected_rating:
                                errors.append(f"{skill}/{tab}:complexity_assessmentRow_{index}_rating_must_be_{expected_rating}")
                        for field in ("includedTagStyles", "includedIconStyles"):
                            entries = row.get(field)
                            if isinstance(entries, list):
                                for entry_index, entry in enumerate(entries, start=1):
                                    if not isinstance(entry, dict) or not all(
                                        isinstance(entry.get(key), str) and entry[key].strip()
                                        for key in ("elementId", "content", "styleKey", "countDecision", "dedupDecision")
                                    ):
                                        errors.append(f"{skill}/{tab}:complexity_{field}_{entry_index}_must_include_traceable_chinese_style_facts")
                                    elif len([part for part in entry["styleKey"].split("|") if part.strip()]) != 5:
                                        errors.append(f"{skill}/{tab}:complexity_{field}_{entry_index}_styleKey_must_have_five_segments")
                if skill == "eval-3-color-logic" and isinstance(assessment_rows, list):
                    for index, row in enumerate(assessment_rows, start=1):
                        if not isinstance(row, dict):
                            errors.append(f"{skill}/{tab}:color_assessmentRow_{index}_must_be_object")
                            continue
                        required_color_fields = {
                            "componentId", "validUiPixelCount", "excludedPhotoPixelCount",
                            "colorFamilies", "colorFamilyCount", "debugImage", "rating",
                        }
                        missing_color_fields = required_color_fields - row.keys()
                        if missing_color_fields:
                            errors.append(
                                f"{skill}/{tab}:color_assessmentRow_{index}_missing_fields:"
                                f"{','.join(sorted(missing_color_fields))}"
                            )
                            continue
                        if not isinstance(row["validUiPixelCount"], int) or row["validUiPixelCount"] < 0:
                            errors.append(f"{skill}/{tab}:color_assessmentRow_{index}_validUiPixelCount_invalid")
                        if not isinstance(row["excludedPhotoPixelCount"], int) or row["excludedPhotoPixelCount"] < 0:
                            errors.append(f"{skill}/{tab}:color_assessmentRow_{index}_excludedPhotoPixelCount_invalid")
                        families = row["colorFamilies"]
                        if not isinstance(families, list) or not all(
                            isinstance(item, dict)
                            and isinstance(item.get("family"), str)
                            and isinstance(item.get("pixelCount"), int)
                            and isinstance(item.get("ratio"), (int, float))
                            for item in families
                        ):
                            errors.append(f"{skill}/{tab}:color_assessmentRow_{index}_colorFamilies_invalid")
                        if not isinstance(row["colorFamilyCount"], int) or row["colorFamilyCount"] < 0:
                            errors.append(f"{skill}/{tab}:color_assessmentRow_{index}_colorFamilyCount_invalid")
                        elif isinstance(families, list) and row["colorFamilyCount"] != len(families):
                            errors.append(f"{skill}/{tab}:color_assessmentRow_{index}_colorFamilyCount_mismatch")
                        debug_image = row["debugImage"]
                        if not isinstance(debug_image, str) or not debug_image or not Path(debug_image).is_file():
                            errors.append(f"{skill}/{tab}:color_assessmentRow_{index}_debugImage_missing")
                        family_count = row.get("colorFamilyCount")
                        if isinstance(family_count, int):
                            expected_rating = "优秀" if family_count <= 3 else "达标" if family_count <= 5 else "不达标"
                            if row.get("rating") != expected_rating:
                                errors.append(f"{skill}/{tab}:color_assessmentRow_{index}_rating_must_be_{expected_rating}")
            elif total != expected_total:
                errors.append(f"{skill}/{tab}:overview_total_{total}_must_equal_{expected_total}")
            if excellent + passed + failed != total:
                errors.append(f"{skill}/{tab}:overview_distribution_does_not_sum_to_total")
            fail_rate = overview.get("failRate")
            expected_rate = f"{(failed / total * 100):.1f}%" if total else "0%"
            if fail_rate not in (expected_rate, expected_rate.replace('.0%', '%')):
                errors.append(f"{skill}/{tab}:failRate_{fail_rate}_must_equal_{expected_rate}")
            issues = details.get("issues")
            if result.get("dimension") == page_framework_dimension:
                continue
            if unit.get("rating") in {"达标", "不达标", "🟡", "🔴"} and (not isinstance(issues, list) or not issues):
                errors.append(f"{skill}/{tab}:actionable_result_requires_non_empty_issues")
            if not isinstance(issues, list):
                errors.append(f"{skill}/{tab}:issues_must_be_array")
                continue
            issue_ids: set[str] = set()
            issue_recommendations: set[str] = set()
            issue_pass = 0
            issue_fail = 0
            required_issue_fields = {"elementId", "coord", "component", "elementType", "content", "dimension", "description", "rating", "priority", "priorityReason", "finding", "recommendation"}
            for issue in issues:
                if not isinstance(issue, dict):
                    errors.append(f"{skill}/{tab}:issue_must_be_object")
                    continue
                missing = required_issue_fields - issue.keys()
                if missing:
                    errors.append(f"{skill}/{tab}:issue_missing_fields:{','.join(sorted(missing))}")
                    continue
                require_structured_finding(errors, f"{skill}/{tab}:issue", issue)
                issue_finding = issue.get("finding") if isinstance(issue.get("finding"), dict) else {}
                require_no_forbidden_terms(errors, f"{skill}/{tab}:issue:observableFact", str(issue_finding.get("observableFact") or ""))
                require_no_forbidden_terms(errors, f"{skill}/{tab}:issue:description", str(issue.get("description") or ""))
                require_no_forbidden_terms(errors, f"{skill}/{tab}:issue:recommendation", str(issue.get("recommendation") or ""))
                require_recommendation_matches_threshold(errors, f"{skill}/{tab}:issue", issue)
                if skill in {"eval-3-color-logic", "eval-4-element-complexity", "eval-5-info-hierarchy", "eval-7-info-authenticity"}:
                    require_component_copy_consistency(
                        errors, f"{skill}/{tab}:issue", skill, issue, assessment_rows
                    )
                if skill == "eval-4-element-complexity":
                    require_complexity_description(errors, f"{skill}/{tab}:issue", issue)
                recommendation = str(issue.get("recommendation", "")).strip()
                if recommendation and recommendation in issue_recommendations:
                    errors.append(f"{skill}/{tab}:issue_recommendation_must_be_issue_specific")
                issue_recommendations.add(recommendation)
                element_id = issue.get("elementId")
                if not isinstance(element_id, str) or element_id in issue_ids:
                    errors.append(f"{skill}/{tab}:issue_elementId_missing_or_duplicate:{element_id}")
                    continue
                issue_ids.add(element_id)
                element_in_manifest = element_id in active_by_id
                if not element_in_manifest:
                    errors.append(f"{skill}/{tab}:issue_elementId_not_in_manifest:{element_id}")
                elif issue.get("coord") != active_by_id[element_id].get("coord"):
                    errors.append(f"{skill}/{tab}:issue_coord_must_equal_manifest:{element_id}")
                if issue.get("rating") in {"🔴", "不达标"} and skill in {"eval-1-supply-completeness", "eval-8-info-redundancy"}:
                    if skill == "eval-1-supply-completeness":
                        required_evidence = ("applicabilityEvidence", "visibleAbsenceEvidence")
                    else:
                        required_evidence = ("redundancyEvidence",)
                    missing_evidence = [
                        key for key in required_evidence
                        if not isinstance(issue.get(key), str) or not issue.get(key).strip()
                    ]
                    if missing_evidence:
                        phase2_review_items.append({
                            "status": "pending",
                            "query": manifest_query,
                            "skill": skill,
                            "tab": tab,
                            "elementId": element_id,
                            "component": issue.get("component", ""),
                            "coord": issue.get("coord"),
                            "content": issue.get("content", ""),
                            "missingEvidence": missing_evidence,
                            "phase3Description": issue.get("description", ""),
                            "instruction": "回退 Phase2：重新读取整图并按需局部复核此坐标及所属卡片，确认字段/实体是否真实可见、缺失或被重复标注；更新统一清单与 recognition-audit 后，重新执行 Phase3。",
                        })
                        errors.append(f"{skill}/{tab}:failed_issue_requires_phase2_review:{element_id}:{','.join(missing_evidence)}")
                if not element_in_manifest:
                    continue
                # Whole-page conclusions without a Phase2-confirmed local boundary
                # intentionally use original-page evidence and must not fabricate a red box.
                requires_local_evidence = evidence_mode in {"annotated-region", "hybrid"}
                if args.require_evidence and requires_local_evidence and issue.get("rating") in {"🟡", "达标", "🔴", "不达标"}:
                    evidence_path = issue.get("evidenceImage")
                    if not isinstance(evidence_path, str) or not evidence_path or not Path(evidence_path).is_file():
                        errors.append(f"{skill}/{tab}:problem_issue_evidence_image_missing:{element_id}")
                    if result.get("dimension") == "phase3-single_element-eval":
                        if issue.get("evidenceScope") not in {"component", "card"}:
                            errors.append(f"{skill}/{tab}:single_element_evidence_scope_must_be_component_or_card:{element_id}")
                        if issue.get("evidenceTargetElementId") != element_id:
                            errors.append(f"{skill}/{tab}:single_element_evidence_target_must_equal_issue_element:{element_id}")
                        if issue.get("evidenceTargetCoord") != active_by_id[element_id].get("coord"):
                            errors.append(f"{skill}/{tab}:single_element_evidence_target_coord_must_equal_manifest:{element_id}")
                rating = issue.get("rating")
                if rating in {"🔴", "不达标"}:
                    issue_fail += 1
                elif rating in {"🟡", "达标"}:
                    issue_pass += 1
                else:
                    errors.append(f"{skill}/{tab}:issue_rating_must_be_pass_or_fail:{rating}")
            if evidence_mode == "annotated-region" and (issue_pass + issue_fail) and not args.require_evidence:
                # Phase4 may run later; the mode only declares that these issues are geometrically annotatable.
                pass
            if issue_fail != failed:
                errors.append(f"{skill}/{tab}:fail_count_{failed}_must_equal_fail_issues_{issue_fail}")
            if issue_pass != passed:
                errors.append(f"{skill}/{tab}:pass_count_{passed}_must_equal_pass_issues_{issue_pass}")

    audit = {
        "valid": not errors,
        "expectedTotal": expected_total,
        "errors": errors,
        "phase2ReviewRequired": bool(phase2_review_items),
        "phase2ReviewItems": phase2_review_items,
    }
    if args.phase2_review:
        args.phase2_review.parent.mkdir(parents=True, exist_ok=True)
        args.phase2_review.write_text(json.dumps({"pending": phase2_review_items}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.audit:
        args.audit.parent.mkdir(parents=True, exist_ok=True)
        args.audit.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False))
    return 0 if audit["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
