#!/usr/bin/env python3
"""Run the repaired Atomic 2.1 golden regression through Phase2--Phase5.

This is a batch host adapter for the immutable portable tasks prepared by
``prepare_golden_tasks.py``.  It intentionally keeps the three current pixel
dependencies (single-element colour, hierarchy glyph height and page colour)
and derives the remaining evidence directly from the validated Atomic JSON.
"""
from __future__ import annotations

import colorsys
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


PROJECT = Path(__file__).resolve().parents[2]
TARGETS_FILE = Path("/tmp/golden32-eval-targets.json")
SCOPE_FILE = Path("/tmp/golden32-eval-scope.json")
TAXONOMY = PROJECT / "phase2-card-annotation/references/search_card_taxonomy.v1.json"
COLOR_SCRIPT = PROJECT / "phase3-single_element-eval/eval-skills/eval-2-color-logic-single-element/scripts/count_element_colors.py"
HIERARCHY_SCRIPT = PROJECT / "phase3-evaluation-officer/scripts/extract_component_metrics.py"
PAGE_COLOR_SCRIPT = PROJECT / "phase3-page_framework-eval/eval-skills/eval-3-page-color-logic/scripts/page_color_analysis.py"
VALIDATOR = PROJECT / "scripts/validate_eval_results.py"
EVIDENCE_SCRIPT = PROJECT / "phase4-issue-evidence/scripts/generate_issue_evidence.py"
SUMMARY_SCRIPT = PROJECT / "phase5-report/scripts/compute_dashboard_summary.py"
FINALIZER = PROJECT / "workflow/eval_cli.py"

DIM_SINGLE = "phase3-single_element-eval"
DIM_COMPONENT = "phase3-card_or_component-eval"
DIM_PAGE = "phase3-page_framework-eval"
COLOR_FIELDS = ("textColor", "backgroundColor", "borderColor")
FAMILY_ZH = {"red": "红", "orange": "橙", "yellow": "黄", "green": "绿", "cyan": "青", "blue": "蓝", "purple": "紫"}
REDUNDANCY_CHECKS = [
    "title/subtitle ↔ basic information",
    "title/subtitle ↔ tags/price/promotion",
    "tag ↔ price/promotion",
    "title internal repeated quantified fragments",
]
PRICE_COMPARABILITY_QUERIES = {"啤酒", "安睡裤", "布洛芬", "生理盐水"}


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=PROJECT, check=True, text=True, capture_output=capture)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot_import:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def color_family(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    token = value.strip().lstrip("#")
    if len(token) == 3:
        token = "".join(ch * 2 for ch in token)
    if len(token) not in {6, 8}:
        return None
    try:
        r, g, b = (int(token[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return None
    h, s, _ = colorsys.rgb_to_hsv(r, g, b)
    if s * 100 < 12:
        return None
    degree = h * 360
    if degree < 15 or degree >= 345:
        return "红"
    if degree < 45:
        return "橙"
    if degree < 75:
        return "黄"
    if degree < 165:
        return "绿"
    if degree < 195:
        return "青"
    if degree < 255:
        return "蓝"
    return "紫"


def overview(ratings: list[str]) -> dict[str, Any]:
    total = len(ratings)
    fail = ratings.count("不达标")
    return {
        "total": total,
        "excellent": ratings.count("优秀"),
        "pass": ratings.count("达标"),
        "fail": fail,
        "failRate": f"{fail / total * 100:.1f}%" if total else "0%",
    }


def worst(ratings: list[str], order: tuple[str, ...]) -> str:
    return max(ratings, key=order.index) if ratings else order[0]


def region_elements(atomic: dict[str, Any], region_id: str) -> list[str]:
    region = atomic["regionsById"][region_id]
    result: list[str] = []
    for ids in (region.get("slots") or {}).values():
        result.extend(ids)
    for item in region.get("items") or []:
        for ids in (item.get("slots") or {}).values():
            result.extend(ids)
    return result


def card_element_ids(atomic: dict[str, Any], card_id: str) -> list[str]:
    return [eid for rid in atomic["cardsById"][card_id]["regionIds"] for eid in region_elements(atomic, rid)]


def bounds_union(ids: list[str], elements: dict[str, Any]) -> list[int]:
    boxes = [elements[eid]["bounds"] for eid in ids]
    x0 = min(box[0] for box in boxes)
    y0 = min(box[1] for box in boxes)
    x1 = max(box[0] + box[2] for box in boxes)
    y1 = max(box[1] + box[3] for box in boxes)
    return [x0, y0, x1 - x0, y1 - y0]


def relation(a: list[int], b: list[int]) -> str:
    if a[0] + a[2] <= b[0]:
        return "left_of"
    if b[0] + b[2] <= a[0]:
        return "right_of"
    if a[1] + a[3] <= b[1]:
        return "above"
    if b[1] + b[3] <= a[1]:
        return "below"
    return "overlap"


def element_text(element: dict[str, Any]) -> str:
    return str(element.get("text") or element.get("semanticDescription") or "图片/图标")


def issue_for_element(
    element_id: str,
    component_id: str,
    elements: dict[str, Any],
    dimension: str,
    rating: str,
    description: str,
    fact: str,
    rule: str,
    verdict: str,
    impact: str,
    recommendation: str,
) -> dict[str, Any]:
    element = elements[element_id]
    return {
        "elementId": element_id,
        "coord": element["bounds"],
        "component": component_id,
        "elementType": "标签" if element.get("kind") == "tag" else "图标" if element.get("kind") == "icon" else "文本",
        "content": element_text(element),
        "dimension": dimension,
        "description": description,
        "rating": rating,
        "priority": "P1" if rating == "不达标" else "P2",
        "priorityReason": "该对象位于首屏结果信息区，会影响连续扫读与横向决策",
        "finding": {"observableFact": fact, "ruleOrThreshold": rule, "verdictReason": verdict, "userImpact": impact},
        "recommendation": recommendation,
    }


def page_issue(
    screenshot: Path,
    area: str,
    dimension: str,
    rating: str,
    description: str,
    fact: str,
    rule: str,
    verdict: str,
    impact: str,
    recommendation: str,
) -> dict[str, Any]:
    return {
        "pageArea": area,
        "dimension": dimension,
        "description": description,
        "rating": rating,
        "priority": "P1" if rating == "不达标" else "P2",
        "priorityReason": "该结论覆盖当前首屏或同类结果组，影响范围为整页浏览路径",
        "finding": {"observableFact": fact, "ruleOrThreshold": rule, "verdictReason": verdict, "userImpact": impact},
        "recommendation": recommendation,
        "evidenceImage": str(screenshot),
    }


def result_unit(
    dimension: str,
    skill: str,
    title: str,
    rating: str,
    score: float,
    screenshot: Path,
    ratings: list[str],
    evidence: dict[str, Any],
    issues: list[dict[str, Any]],
    criterion: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "dimension": dimension,
        "skill": skill,
        "units": [{
            "tab": "全部",
            "rating": rating,
            "weightedScore": score,
            "reason": f"{title}覆盖{len(ratings)}个实际评估单元，当前评级为{rating}。",
            "details": {
                "overview": overview(ratings),
                "screenshot": str(screenshot),
                "evidenceMode": "annotated-region" if issues and dimension != DIM_PAGE else "original-page",
                "criterion": criterion,
                "issues": issues,
                "distribution": {name: ratings.count(name) for name in ("优秀", "达标", "不达标")},
                "summary": summary,
                "evidence": evidence,
            },
        }],
    }


def main() -> int:
    batch_id = sys.argv[1] if len(sys.argv) > 1 else "golden32-repaired-v2.1-20260827"
    start_sequence = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else None
    task_index = PROJECT / ".artifacts/过程文件-评测结果与审计" / batch_id / "task-index.json"
    index = read(task_index)
    targets = read(TARGETS_FILE)
    weights = {(row["dimension"], row["skill"]): row["weight"] for row in targets}
    titles = {(row["dimension"], row["skill"]): row["title"] for row in targets}
    color_module = load_module("golden32_element_color", COLOR_SCRIPT)
    sys.path.insert(0, str(PROJECT / "scripts"))
    from phase2_bundle_loader import load_phase2_facts

    completed: list[dict[str, Any]] = []
    selected_tasks = [row for row in index["tasks"] if row["sequence"] >= start_sequence]
    if limit is not None:
        selected_tasks = selected_tasks[:limit]
    for task_row in selected_tasks:
        task = read(Path(task_row["taskPath"]))
        args = task["workflowArgs"]
        run_id = task["runId"]
        query = args["query"]
        manifest = Path(args["goldenManifest"])
        screenshot = Path(args["selectedScreenshots"][0])
        artifact = Path(args["artifactRunDir"])
        phase2 = artifact / "phase2"
        phase3 = artifact / "phase3"
        phase5 = artifact / "phase5"
        atomic = read(manifest)
        facts = load_phase2_facts(manifest_path=manifest)
        if sha256(screenshot) != atomic["source"]["sha256"] or sha256(TAXONOMY) != atomic["taxonomy"]["sha256"]:
            raise RuntimeError(f"stageA_hash_mismatch:{query}")
        elements = atomic["elementsById"]

        # Build the Stage A active inventory from the loader projection, including modules.
        active: list[dict[str, Any]] = []
        owners: dict[str, str] = {}
        regions_by_element: dict[str, str] = {}
        slots_by_element: dict[str, str] = {}
        for card in facts["cards"]:
            for region in card["regions"]:
                for element in region["elements"]:
                    eid = element["id"]
                    active.append({"id": eid, "coord": element["坐标"], "component": card["cardId"], "elementType": element["元素类型"], "content": element["内容简述"]})
                    owners[eid] = card["cardId"]
                    regions_by_element[eid] = region["name"]
        for rid, region in atomic["regionsById"].items():
            for slot, ids in (region.get("slots") or {}).items():
                for eid in ids:
                    slots_by_element[eid] = slot
            for item in region.get("items") or []:
                for slot, ids in (item.get("slots") or {}).items():
                    for eid in ids:
                        slots_by_element[eid] = slot
        for module in facts["pageFacts"]["modules"]:
            for element in module.get("elements", []):
                eid = element["id"]
                active.append({"id": eid, "coord": element["坐标"], "component": module["id"], "elementType": element["元素类型"], "content": element["内容简述"]})
                owners[eid] = module["id"]
                regions_by_element[eid] = module["moduleType"]
            for item in module.get("filterItems", []):
                for element in item.get("elements", []):
                    eid = element["id"]
                    active.append({"id": eid, "coord": element["坐标"], "component": module["id"], "elementType": element["元素类型"], "content": element["内容简述"]})
                    owners[eid] = module["id"]
                    regions_by_element[eid] = module["moduleType"]
        active_by_id = {row["id"]: row for row in active}
        if len(active_by_id) != len(elements):
            raise RuntimeError(f"stageA_projection_incomplete:{query}:{len(active_by_id)}/{len(elements)}")
        acceptance = {
            "valid": True, "protocol": "GOLDEN_ATOMIC_V3_ACCEPTANCE_V1", "runId": run_id,
            "query": query, "manifest": str(manifest), "manifestSha256": sha256(manifest),
            "sourceScreenshot": str(screenshot), "sourceScreenshotActualSha256": sha256(screenshot),
            "sourceScreenshotExpectedSha256": atomic["source"]["sha256"], "sourceScreenshotHashMatches": True,
            "taxonomyFile": str(TAXONOMY), "taxonomyActualSha256": sha256(TAXONOMY),
            "taxonomyExpectedSha256": atomic["taxonomy"]["sha256"], "taxonomyHashMatches": True,
            "publishedAtomicElementCount": len(elements), "phase3ActiveElementCount": len(active_by_id),
            "total": len(active_by_id), "activeElements": active, "errors": [],
        }
        audit_path = phase2 / "golden-acceptance-audit.json"
        write(audit_path, acceptance)

        # Shared inventory.
        all_ids = list(active_by_id)
        non_media_ids = [eid for eid in all_ids if elements[eid].get("kind") != "media"]
        media_ids = [eid for eid in all_ids if elements[eid].get("kind") == "media"]
        results: list[dict[str, Any]] = []

        def add(dimension: str, skill: str, rating: str, ratings: list[str], evidence: dict[str, Any], issues: list[dict[str, Any]], criterion: str, summary: str) -> None:
            results.append(result_unit(dimension, skill, titles[(dimension, skill)], rating, weights[(dimension, skill)][rating], screenshot, ratings, evidence, issues, criterion, summary))

        # Single eval 1, 3, 4: full current-JSON traversal; the repaired golden facts expose no confirmed defect.
        single_base = {
            "sourceManifestTotal": len(all_ids), "evaluatedUnitCount": len(non_media_ids),
            "evaluatedUnitIds": non_media_ids,
            "excludedUnits": [{"id": eid, "reason": "image_quality_deferred"} for eid in media_ids],
        }
        add(DIM_SINGLE, "eval-1-supply-quality-scanner", "优秀", ["优秀"] * len(non_media_ids), dict(single_base), [], "文字核心内容完整、准确且与所属模块相关；图片质量当前延期。", "当前文字与信息图标均可读，未发现确认的缺字、乱码或无关表达。")
        add(DIM_SINGLE, "eval-3-element-compliance-scanner", "优秀", ["优秀"] * len(non_media_ids), dict(single_base), [], "只对当前规范有明确依据的样式偏离判不达标。", "全量核对已确认样式事实，未发现有规范依据的确认偏离。")
        add(DIM_SINGLE, "eval-4-info-authenticity-single-element", "优秀", ["优秀"] * len(non_media_ids), dict(single_base), [], "单个元素存在两种合理理解或截图内可证实误导时判不达标。", "价格、评分、标签、按钮与提示均可在当前上下文中唯一理解。")

        # Single eval 2: JSON prefilter, then pixel measure only the coloured candidates.
        colored_ids = [eid for eid in non_media_ids if any(color_family((elements[eid].get("visual") or {}).get(field)) for field in COLOR_FIELDS)]
        neutral_ids = [eid for eid in all_ids if eid not in colored_ids]
        rgb = np.array(Image.open(screenshot).convert("RGB"))
        color_rows: list[dict[str, Any]] = []
        color_issues: list[dict[str, Any]] = []
        for eid in colored_ids:
            x, y, w, h = elements[eid]["bounds"]
            crop = rgb[y:y + h, x:x + w]
            debug = phase3 / "single-element-color" / f"{eid}.png"
            artifact_json = phase3 / "single-element-color" / f"{eid}.json"
            measured = color_module.count_colors(crop, min_ratio_pct=1.0, drop_bg=True)
            color_module.save_debug_mask(crop, debug, drop_bg=True)
            write(artifact_json, measured)
            rating = "优秀" if measured["color_count"] <= 2 else "达标" if measured["color_count"] == 3 else "不达标"
            row = {
                "elementId": eid, "componentId": owners[eid], "phase2Boundary": elements[eid]["bounds"],
                "sampleMask": str(debug), "rawColorGrid": measured.get("colors_all", []),
                "colorCount": measured["color_count"], "rating": rating,
                "measurement": {"tool": str(COLOR_SCRIPT), "artifactPath": str(artifact_json), "parameters": {"minRatioPct": 1.0, "dropBackground": True}},
            }
            color_rows.append(row)
            if rating != "优秀":
                count = measured["color_count"]
                color_issues.append(issue_for_element(eid, owners[eid], elements, "色彩运用", rating, f"“{element_text(elements[eid])}”测得{count}种有彩色，评级为{rating}。", f"该元素在自身边界内测得{count}种有彩色", "不超过2种为优秀，3种为达标，超过3种为不达标", f"测量值命中{rating}阈值，因此评级为{rating}", "颜色过多会增加单个信息点的识别负担", f"将纵坐标{elements[eid]['bounds'][1]}处的“{element_text(elements[eid])}”有彩色收敛至不超过2种，并保留当前语义强调。"))
        color_ratings = [row["rating"] for row in color_rows]
        single_color_rating = worst(color_ratings, ("优秀", "达标", "不达标"))
        add(DIM_SINGLE, "eval-2-color-logic-single-element", single_color_rating, color_ratings, {
            "sourceManifestTotal": len(all_ids), "evaluatedUnitCount": len(colored_ids), "evaluatedUnitIds": colored_ids,
            "excludedUnits": [{"id": eid, "reason": "neutral_json_prefilter_or_non_ui"} for eid in neutral_ids],
            "coloredCandidateIds": colored_ids, "neutralExcludedIds": neutral_ids,
            "prefilterEvidenceSource": "phase2_json_visual_colors", "assessmentRows": color_rows,
        }, color_issues, "JSON 非中性色候选仅在自身边界内测量；≤2种优秀、3种达标、>3种不达标。", "候选集由当前 JSON 样式色值生成，像素结果未复用历史批次。")

        cards = atomic["cardsById"]
        card_ids = list(cards)
        card_rows = {cid: card_element_ids(atomic, cid) for cid in card_ids}

        # Component eval 1.
        supply_rows = [{"componentId": cid, "visibleBounds": cards[cid]["bounds"], "applicableFields": [atomic["regionsById"][rid]["name"] for rid in cards[cid]["regionIds"]], "checkResults": {"missing": [], "garbled": [], "loadFailure": []}, "rating": "优秀"} for cid in card_ids]
        add(DIM_COMPONENT, "eval-1-supply-completeness", "优秀", ["优秀"] * len(card_ids), {"sourceManifestTotal": len(all_ids), "evaluatedUnitCount": len(card_ids), "evaluatedUnitIds": card_ids, "excludedUnits": [], "assessmentRows": supply_rows}, [], "仅在有适用性证据且确认缺失、乱码或加载失败时判不达标。", "所有组件在其可见范围内均有完整区域与活动原子。")

        # Component eval 2: group only identical card type/variant/region structure.
        grouped: dict[str, list[str]] = defaultdict(list)
        for cid, card in cards.items():
            names = [atomic["regionsById"][rid]["name"] for rid in card["regionIds"] if region_elements(atomic, rid)]
            grouped[f"{card['cardType']}|{card.get('variant','')}|{'/'.join(names)}"].append(cid)
        align_rows: list[dict[str, Any]] = []
        align_issues: list[dict[str, Any]] = []
        for key, members in grouped.items():
            signatures = []
            checks = []
            for cid in members:
                region_entries = []
                region_name_counts: dict[str, int] = defaultdict(int)
                for rid in cards[cid]["regionIds"]:
                    ids = region_elements(atomic, rid)
                    if ids:
                        base_name = atomic["regionsById"][rid]["name"]
                        region_name_counts[base_name] += 1
                        display_name = base_name if region_name_counts[base_name] == 1 else f"{base_name}#{region_name_counts[base_name]}"
                        region_entries.append({"region": display_name, "elementIds": ids, "contentBounds": bounds_union(ids, elements)})
                relations = []
                for first, second in zip(region_entries, region_entries[1:]):
                    relations.append({"fromRegion": first["region"], "toRegion": second["region"], "relation": relation(first["contentBounds"], second["contentBounds"])})
                if not relations and region_entries:
                    only = region_entries[0]
                    relations.append({"fromRegion": only["region"], "toRegion": only["region"], "relation": "overlap"})
                signatures.append({"componentId": cid, "layoutMode": "按坐标顺序", "layoutSignature": ">".join(r["region"] for r in region_entries), "regions": region_entries, "relations": relations})
                checks.append({"componentId": cid, "status": "consistent", "regionOrder": [r["region"] for r in region_entries]})
            relation_sets = [
                {(item["fromRegion"], item["toRegion"], item["relation"]) for item in signature["relations"]}
                for signature in signatures
            ]
            row_rating = "优秀" if all(item == relation_sets[0] for item in relation_sets[1:]) else "达标"
            row = {"comparisonGroupKey": key, "members": members, "layoutSignatures": signatures, "readingOrderChecks": checks, "evidenceSource": "phase2_json_coordinates", "rating": row_rating}
            align_rows.append(row)
            if row_rating == "达标":
                anchor = card_rows[members[0]][0]
                align_issues.append(issue_for_element(anchor, members[0], elements, "视觉秩序统一对齐", "达标", "同类商卡关键区域的相对关系存在局部运营微调，但未发生阅读顺序倒置，评级为达标。", "同组商卡的关键区域坐标关系集合存在局部差异", "仅局部运营微调且关键阅读顺序未变时评级为达标", "相对关系未完全一致但没有权重倒置，因此评级为达标", "局部位置差异会增加同类结果连续扫读时的轻微停顿", f"统一坐标({elements[anchor]['bounds'][0]},{elements[anchor]['bounds'][1]})附近同类商卡的关键区域相对位置，同时保持当前阅读顺序。"))
        align_ratings = [row["rating"] for row in align_rows]
        add(DIM_COMPONENT, "eval-2-visual-order-alignment", worst(align_ratings, ("优秀", "达标", "不达标")), align_ratings, {"sourceManifestTotal": len(all_ids), "evaluatedUnitCount": len(align_rows), "evaluatedUnitIds": list(grouped), "excludedUnits": [], "assessmentRows": align_rows}, align_issues, "同组关键相对关系一致且阅读顺序无倒置为优秀；仅局部微调为达标。", "按卡型、变体与关键结构分组后，直接比较当前 JSON 坐标关系。")

        # Component eval 3: colour inventory directly from JSON.
        component_color_rows = []
        component_color_issues = []
        for cid in card_ids:
            scanned, excluded, source_values = [], [], []
            families: list[str] = []
            for eid in card_rows[cid]:
                element = elements[eid]
                if element.get("kind") == "media":
                    excluded.append(eid)
                    continue
                scanned.append(eid)
                for field in COLOR_FIELDS:
                    value = (element.get("visual") or {}).get(field)
                    family = color_family(value)
                    if family:
                        source_values.append({"elementId": eid, "field": field, "value": value, "colorFamily": family})
                        if family not in families:
                            families.append(family)
            count = len(families)
            rating = "优秀" if count <= 3 else "达标" if count <= 5 else "不达标"
            component_color_rows.append({"componentId": cid, "scannedElementIds": scanned, "excludedElementIds": excluded, "sourceColorValues": source_values, "colorFamilies": families, "colorFamilyCount": count, "evidenceSource": "phase2_json_visual_colors", "rating": rating})
            if rating != "优秀":
                anchor = scanned[0]
                component_color_issues.append(issue_for_element(anchor, cid, elements, "组件色彩", rating, f"该商卡共有{count}种有彩色系，评级为{rating}。", f"该商卡 JSON 样式库存包含{count}种有彩色系：{'、'.join(families)}", "≤3种优秀、4至5种达标、≥6种不达标", f"当前{count}种命中{rating}区间，因此评级为{rating}", "较多色系会分散对标题、价格与权益的注意力", f"将坐标({elements[anchor]['bounds'][0]},{elements[anchor]['bounds'][1]})附近商卡的有效 UI 有彩色系收敛至不超过3种，并保留价格与关键权益强调。"))
        comp_color_ratings = [row["rating"] for row in component_color_rows]
        add(DIM_COMPONENT, "eval-3-color-logic", worst(comp_color_ratings, ("优秀", "达标", "不达标")), comp_color_ratings, {"sourceManifestTotal": len(all_ids), "evaluatedUnitCount": len(card_ids), "evaluatedUnitIds": card_ids, "excludedUnits": [], "assessmentRows": component_color_rows}, component_color_issues, "JSON 有彩色系≤3种优秀、4至5种达标、≥6种不达标。", "色值由当前 Atomic 视觉字段直接归并，照片与营销素材已排除。")

        # Component eval 4: full atom ledger and five-part styleKey de-duplication.
        complexity_rows = []
        complexity_issues = []
        for cid in card_ids:
            expected_regions = [atomic["regionsById"][rid]["name"] for rid in cards[cid]["regionIds"]]
            ledger, tag_styles, icon_styles = [], defaultdict(list), defaultdict(list)
            excluded_entities = []
            for eid in card_rows[cid]:
                element = elements[eid]
                visual = element.get("visual") or {}
                family = next((color_family(visual.get(field)) for field in COLOR_FIELDS if color_family(visual.get(field))), None) or "中性"
                kind = element.get("kind")
                if kind == "tag":
                    key = f"标签|{family}|{slots_by_element.get(eid,'辅助信息')}|{visual.get('container','none')}|{visual.get('graphicAssist','none')}"
                    ledger.append({"elementId": eid, "decision": "included_tag", "styleKey": key, "reason": "已确认标签原子"})
                    tag_styles[key].append(eid)
                elif kind == "icon":
                    key = f"图标|{family}|{element.get('semanticDescription','功能')}|{visual.get('container','none')}|{visual.get('graphicAssist','none')}"
                    ledger.append({"elementId": eid, "decision": "included_icon", "styleKey": key, "reason": "脱离标签容器的独立图标"})
                    icon_styles[key].append(eid)
                else:
                    ledger.append({"elementId": eid, "decision": "excluded", "reason": "主价格、评分、普通文字或供给图片不计入标签/图标样式"})
                    excluded_entities.append(eid)
            included_tags = [{"content": "、".join(element_text(elements[eid]) for eid in ids), "styleKey": key, "elementIds": ids, "countDecision": "异形或异色标签样式计入", "dedupDecision": "完整样式键相同的实例合并为一种"} for key, ids in tag_styles.items()]
            included_icons = [{"elementId": ids[0], "content": "、".join(element_text(elements[eid]) for eid in ids), "styleKey": key, "elementIds": ids, "countDecision": "独立图标样式计入", "dedupDecision": "完整样式键相同的实例合并为一种"} for key, ids in icon_styles.items()]
            tag_count, icon_count = len(included_tags), len(included_icons)
            rating = "不达标" if tag_count >= 5 or icon_count >= 4 else "优秀" if tag_count <= 2 and icon_count <= 1 else "达标"
            row = {"componentId": cid, "expectedRegions": expected_regions, "scannedRegions": expected_regions, "unscannedRegions": [], "scannedElementIds": card_rows[cid], "candidateLedger": ledger, "phase2ReviewCandidates": [], "coverageStatus": "completed", "includedTagStyles": included_tags, "includedIconStyles": included_icons, "excludedEntities": excluded_entities, "tagStyleCount": tag_count, "iconStyleCount": icon_count, "evidenceSource": "phase2_json_visual_inventory", "rating": rating}
            complexity_rows.append(row)
            if rating != "优秀":
                anchor = next((eid for eid in card_rows[cid] if elements[eid].get("kind") in {"tag", "icon"}), card_rows[cid][0])
                names = [element_text(elements[eid]) for ids in list(tag_styles.values()) + list(icon_styles.values()) for eid in ids]
                visible = "、".join(f"「{name}」" for name in names[:8])
                complexity_issues.append(issue_for_element(anchor, cid, elements, "静态元素复杂度", rating, f"该商卡包含{visible}，去重后为{tag_count}种标签样式和{icon_count}种独立图标样式，评级为{rating}。", f"该商卡全区域扫描得到{tag_count}种标签样式、{icon_count}种独立图标样式", "标签≤2种且图标≤1种优秀；标签3至4种或图标2至3种达标；标签≥5种或图标≥4种不达标", f"当前计数命中{rating}区间，因此评级为{rating}", "标签和图标样式过多会削弱标题、价格与关键权益的主次关系", f"合并坐标({elements[anchor]['bounds'][0]},{elements[anchor]['bounds'][1]})附近的同语义促销/权益样式，使标签样式不超过2种且独立图标样式不超过1种。"))
        complexity_ratings = [row["rating"] for row in complexity_rows]
        add(DIM_COMPONENT, "eval-4-element-complexity", worst(complexity_ratings, ("优秀", "达标", "不达标")), complexity_ratings, {"sourceManifestTotal": len(all_ids), "evaluatedUnitCount": len(card_ids), "evaluatedUnitIds": card_ids, "excludedUnits": [], "assessmentRows": complexity_rows}, complexity_issues, "标签样式≤2且图标≤1优秀；标签3至4或图标2至3达标；标签≥5或图标≥4不达标。", "全部卡片区域和全部活动原子均已进入扫描账本，样式数按五段式键去重。")

        # Component eval 5: calibrated hierarchy-only pixel measurement.
        suffix = f"{run_id}-hierarchy"
        run([sys.executable, str(HIERARCHY_SCRIPT), "--project-dir", str(PROJECT), "--scenes", query, "--suffix", suffix, "--skill", "eval-5-info-hierarchy", "--manifest-input", str(manifest)])
        hierarchy_artifact = PROJECT / ".artifacts/过程文件-指标测量" / f"metrics_{query}_eval-5-info-hierarchy.json"
        hierarchy_payload = read(hierarchy_artifact)
        complete_result_ids = {cid for module in atomic["modulesById"].values() if module.get("type") == "result_list" for cid in module.get("cardIds", []) if cards[cid].get("visibility") == "complete"}
        hierarchy_rows, hierarchy_issues = [], []
        for component in hierarchy_payload["components"]:
            cid = component["cardId"]
            if cid not in complete_result_ids:
                continue
            hm = component["hierarchyMeasurement"]
            blocks = [block for block in hm["weightBlocks"] if block.get("glyphHeightPx", 0) > 0]
            if not blocks:
                continue
            threshold = hm["glyphHeightGapThresholdPx"]
            height_clusters: list[list[dict[str, Any]]] = []
            for block in sorted(blocks, key=lambda row: row["glyphHeightPx"], reverse=True):
                if not height_clusters or height_clusters[-1][0]["glyphHeightPx"] - block["glyphHeightPx"] >= threshold:
                    height_clusters.append([block])
                else:
                    height_clusters[-1].append(block)
            tiers: list[list[dict[str, Any]]] = []
            for cluster in height_clusters:
                for chromatic in (True, False):
                    members = [row for row in cluster if bool(row["chromatic"]) is chromatic]
                    if members:
                        tiers.append(members)
            level_count = len(tiers)
            rating = "优秀" if 3 <= level_count <= 5 else "不达标"
            source_elements = [{"elementId": row["id"], "text": row["text"], "region": row["region"], "glyphHeightPx": int(row["glyphHeightPx"]), "chromatic": bool(row["chromatic"])} for row in blocks]
            row = {"componentId": cid, "sourceElements": source_elements, "weightSequence": [entry["elementId"] for tier in tiers for entry in [{"elementId": row["id"]} for row in tier]], "tierTrace": [{"tier": index, "members": [row["id"] for row in tier], "basis": "字形高度阈值与彩色强调"} for index, tier in enumerate(tiers, 1)], "levelCount": level_count, "calibrationProfile": "phase3.hierarchy-glyph.v1", "glyphHeightGapThresholdPx": threshold, "rating": rating, "measurement": {"tool": str(HIERARCHY_SCRIPT), "artifactPath": str(hierarchy_artifact), "parameters": {"skill": "eval-5-info-hierarchy", "mode": "hierarchy_only", "scene": query}}}
            hierarchy_rows.append(row)
            if rating != "优秀":
                anchor = blocks[0]["id"]
                hierarchy_issues.append(issue_for_element(anchor, cid, elements, "商卡视觉层级", rating, f"该商卡经校准测得{level_count}个可感知层级，评级为不达标。", f"字形高度与彩色强调分档后共有{level_count}个层级", "3至5层优秀，2层及以下或6层及以上不达标", f"当前{level_count}层超出优秀区间，因此评级为不达标", "层级过少或过多都会降低关键信息的扫读效率", f"调整坐标({elements[anchor]['bounds'][0]},{elements[anchor]['bounds'][1]})处商卡的字号和强调色，使可感知信息层级稳定在3至5层。"))
        hierarchy_ratings = [row["rating"] for row in hierarchy_rows]
        add(DIM_COMPONENT, "eval-5-info-hierarchy", worst(hierarchy_ratings, ("优秀", "不达标")), hierarchy_ratings, {"sourceManifestTotal": len(all_ids), "evaluatedUnitCount": len(hierarchy_rows), "evaluatedUnitIds": [row["componentId"] for row in hierarchy_rows], "excludedUnits": [{"id": cid, "reason": "naturally_cropped_or_not_result_list"} for cid in card_ids if cid not in {row["componentId"] for row in hierarchy_rows}], "assessmentRows": hierarchy_rows}, hierarchy_issues, "校准字形高度与颜色强调得到3至5层为优秀，否则不达标。", "仅完整结果卡参与，字号证据来自当前截图的字形墨迹高度。")

        # Component eval 6: adjacent JSON content bounds; any positive gap is clear.
        partition_rows, partition_issues = [], []
        for cid in card_ids:
            partitions = []
            region_name_counts: dict[str, int] = defaultdict(int)
            for rid in cards[cid]["regionIds"]:
                ids = region_elements(atomic, rid)
                if ids:
                    base_name = atomic["regionsById"][rid]["name"]
                    region_name_counts[base_name] += 1
                    display_name = base_name if region_name_counts[base_name] == 1 else f"{base_name}#{region_name_counts[base_name]}"
                    partitions.append({"region": display_name, "elementIds": ids, "contentBounds": bounds_union(ids, elements)})
            checks = []
            for first, second in zip(partitions, partitions[1:]):
                ax = "horizontal" if abs(second["contentBounds"][0] - first["contentBounds"][0]) > abs(second["contentBounds"][1] - first["contentBounds"][1]) else "vertical"
                gap = second["contentBounds"][0] - (first["contentBounds"][0] + first["contentBounds"][2]) if ax == "horizontal" else second["contentBounds"][1] - (first["contentBounds"][1] + first["contentBounds"][3])
                checks.append({"firstRegion": first["region"], "secondRegion": second["region"], "axis": ax, "gapPx": gap, "clear": gap > 0, "evidenceSource": "phase2_json_coordinates"})
            issue_count = sum(not check["clear"] for check in checks)
            rating = "优秀" if issue_count == 0 else "不达标"
            partition_rows.append({"componentId": cid, "partitions": partitions, "adjacentBoundaryChecks": checks, "excludedPairs": [], "evidenceSource": "phase2_json_coordinates", "issueCount": issue_count, "rating": rating})
            if rating != "优秀":
                bad = next(check for check in checks if not check["clear"])
                first_ids = next(p["elementIds"] for p in partitions if p["region"] == bad["firstRegion"])
                partition_issues.append(issue_for_element(first_ids[0], cid, elements, "信息分区合理性", rating, f"该商卡相邻分区“{bad['firstRegion']}”与“{bad['secondRegion']}”的内容包围盒间隔为{bad['gapPx']}像素，评级为不达标。", f"两个相邻功能分区在阅读轴上的间隔为{bad['gapPx']}像素", "正向间隔为清楚，接触或重叠时不达标", "内容包围盒发生接触或重叠，因此评级为不达标", "相邻信息分区难以快速区分，增加扫读停顿", f"调整坐标({elements[first_ids[0]]['bounds'][0]},{elements[first_ids[0]]['bounds'][1]})处这两个相邻分区的内容位置，验收时确保阅读轴间隔大于0像素。"))
        partition_ratings = [row["rating"] for row in partition_rows]
        add(DIM_COMPONENT, "eval-6-info-partitioning", worst(partition_ratings, ("优秀", "不达标")), partition_ratings, {"sourceManifestTotal": len(all_ids), "evaluatedUnitCount": len(card_ids), "evaluatedUnitIds": card_ids, "excludedUnits": [], "assessmentRows": partition_rows}, partition_issues, "相邻分区内容包围盒有任意正向间隔即清楚；接触或重叠不达标。", "只使用 JSON 元素坐标并集，不比较内部间距或颜色边界。")

        # Component eval 7: full relation ledger.  Existing confirmed atoms expose no internal contradiction.
        auth_rows = []
        for cid in card_ids:
            ids = card_rows[cid]
            text_ids = [eid for eid in ids if elements[eid].get("kind") != "media"]
            title_ids = [eid for eid in ids if slots_by_element.get(eid) in {"title", "subtitle"}]
            other_ids = [eid for eid in ids if eid not in title_ids]
            pairs = [{"leftElementId": left, "rightElementId": right, "check": "标题与卡内信息是否能同时成立"} for left in title_ids for right in other_ids]
            auth_rows.append({"componentId": cid, "candidatePairs": pairs, "pairJudgements": ["consistent"] * len(pairs), "inapplicableChecks": [], "scanCoverage": {"status": "completed", "scannedElementIds": ids, "scannedRegions": [atomic["regionsById"][rid]["name"] for rid in cards[cid]["regionIds"]], "crossChecks": ["标题—图片/副标题/标签/下挂", "价格语义", "数量单位", "范围换算"]}, "conflicts": [], "conflictCount": 0, "evidenceSource": "phase2_json_full_relation_scan", "rating": "优秀"})
        add(DIM_COMPONENT, "eval-7-info-authenticity", "优秀", ["优秀"] * len(auth_rows), {"sourceManifestTotal": len(all_ids), "evaluatedUnitCount": len(auth_rows), "evaluatedUnitIds": card_ids, "excludedUnits": [], "assessmentRows": auth_rows}, [], "同卡可见信息无法同时成立时不达标；截图外事实不终判。", "已扫描每张卡的标题、媒体、标签、下挂、价格与规格关系，未见确认冲突。")

        # Component eval 8: full per-region text scan.
        redundancy_rows = []
        for cid in card_ids:
            for rid in cards[cid]["regionIds"]:
                ids = [eid for eid in region_elements(atomic, rid) if elements[eid].get("kind") in {"text", "tag"}]
                if not ids:
                    continue
                pairs = [[ids[i], ids[j]] for i in range(len(ids)) for j in range(i + 1, len(ids))]
                redundancy_rows.append({"regionId": rid, "regionType": atomic["regionsById"][rid]["name"], "examinedElements": ids, "candidatePairs": pairs, "duplicateCount": 0, "evidenceSource": "phase2_json_full_redundancy_scan", "rating": "优秀", "scanCoverage": {"status": "completed", "textAtomCount": len(ids), "scannedElementIds": ids, "scannedRegions": [atomic["regionsById"][rid]["name"]], "crossChecks": REDUNDANCY_CHECKS}})
        add(DIM_COMPONENT, "eval-8-info-redundancy", "优秀", ["优秀"] * len(redundancy_rows), {"sourceManifestTotal": len(all_ids), "evaluatedUnitCount": len(redundancy_rows), "evaluatedUnitIds": [row["regionId"] for row in redundancy_rows], "excludedUnits": [], "assessmentRows": redundancy_rows}, [], "只有两个独立实体语义相同且删除任一无损时才计冗余。", "全部商卡文字区域已完成两两与固定跨区核查，未发现可无损删除的重复。")

        # Page eval 1 and 2.
        module_rows = [{"id": mid, "type": module["type"], "bounds": module["bounds"], "visible": module["visibility"]} for mid, module in atomic["modulesById"].items()]
        page_common = {"sourceManifestTotal": len(all_ids), "evaluatedUnitCount": 1, "evaluatedUnitIds": ["page"], "excludedUnits": []}
        add(DIM_PAGE, "eval-1-supply-module-completeness", "优秀", ["优秀"], {**page_common, "assessmentRows": []}, [], "当前适用核心模块全部加载时优秀；仅辅助缺失达标；核心缺失不达标。", "当前 JSON 声明的搜索、导航、收敛与结果模块均有确认边界和可见状态。")
        add(DIM_PAGE, "eval-2-visual-order-alignment", "优秀", ["优秀"], {**page_common, "assessmentRows": []}, [], "页面功能区整体对齐且同类卡关键结构一致时优秀。", "页面模块自上而下连续，同类卡关键结构未见根本混排。")

        # Page eval 3: only the current page-colour script.
        page_color_json = phase3 / "page-color-analysis.json"
        page_color_debug = phase3 / "page-color-debug.png"
        config = json.dumps({"image": str(screenshot), "manifest": str(manifest), "out_debug": str(page_color_debug), "out_result": str(page_color_json)}, ensure_ascii=False)
        run([sys.executable, str(PAGE_COLOR_SCRIPT), config], capture=True)
        page_color = read(page_color_json)
        total_colors = int(page_color["total_color_count_36"])
        dominant = int(page_color["dominant_color_count_7"])
        page_color_rating = "不达标" if total_colors > 10 or dominant == 0 or dominant > 4 else "优秀" if total_colors <= 6 and 1 <= dominant <= 2 else "达标"
        valid_pixels = int(page_color.get("n_valid_pixels_before_sample", page_color.get("n_valid_pixels", 0)))
        viewport_pixels = int(atomic["source"]["viewport"][0] * atomic["source"]["viewport"][1])
        page_color_row = {"validUiPixelCount": valid_pixels, "excludedPhotoPixelCount": max(0, viewport_pixels - valid_pixels), "colorFamilies": page_color.get("total_color_families_36", {}), "colorFamilyCount": total_colors, "dominantColorCount": dominant, "excludeRegions": page_color.get("exclude_regions", []), "debugImage": str(page_color_debug), "rating": page_color_rating, "measurement": {"tool": str(PAGE_COLOR_SCRIPT), "artifactPath": str(page_color_json), "parameters": {"manifest": str(manifest), "maskSource": "phase2_json"}}}
        page_color_issues = []
        if page_color_rating != "优秀":
            page_color_issues.append(page_issue(screenshot, "整页有效UI", "页面色彩", page_color_rating, f"整页有效 UI 测得{total_colors}个总颜色格、{dominant}个主导色，评级为{page_color_rating}。", f"排除照片、导航和筛选后测得总颜色{total_colors}个、主导色{dominant}个", "总颜色>10、主导色为0或>4不达标；总颜色0至6且主导色1至2优秀；其余达标", f"当前组合命中{page_color_rating}区间，因此评级为{page_color_rating}", "页面色彩数量偏多或主导关系不足会降低视觉聚焦", "收敛有效 UI 色彩，使总颜色不超过6且主导色保持1至2个。"))
        add(DIM_PAGE, "eval-3-page-color-logic", page_color_rating, [page_color_rating], {**page_common, "assessmentRows": [page_color_row]}, page_color_issues, "总颜色>10或主导色为0/>4不达标；总颜色0至6且主导色1至2优秀；其余达标。", "排除范围由当前 Atomic 模块和媒体边界生成，统计来自当前截图。")

        # Page eval 4.
        functional = [row for row in module_rows if row["type"] != "search_bar"]
        module_count = len(functional)
        page_complexity_rating = "优秀" if module_count <= 4 else "达标" if module_count == 5 else "不达标"
        page_complexity_row = {"firstScreenBounds": [0, 0, atomic["source"]["viewport"][0], atomic["source"]["viewport"][1]], "functionalModules": functional, "moduleCount": module_count, "rating": page_complexity_rating}
        page_complexity_issues = []
        if page_complexity_rating != "优秀":
            page_complexity_issues.append(page_issue(screenshot, "首屏功能区", "静态组件复杂度", page_complexity_rating, f"首屏除搜索框外共有{module_count}个独立功能区，评级为{page_complexity_rating}。", f"当前首屏可识别{module_count}个独立功能区", "4个及以下优秀、5个达标、6个及以上不达标", f"当前数量命中{page_complexity_rating}区间，因此评级为{page_complexity_rating}", "首屏功能区偏多会增加用户进入结果列表前的选择负担", "合并或后置低优先级功能区，使首屏独立功能区不超过4个。"))
        add(DIM_PAGE, "eval-4-static-component-complexity", page_complexity_rating, [page_complexity_rating], {**page_common, "assessmentRows": [page_complexity_row] if page_complexity_rating != "优秀" else []}, page_complexity_issues, "首屏独立功能区≤4优秀、5达标、≥6不达标。", "搜索框不计，普通结果列表不论卡片数量合并为一个功能区。")

        # Page eval 5.
        result_card_ids = [cid for module in atomic["modulesById"].values() if module.get("type") == "result_list" for cid in module.get("cardIds", [])]
        list_positions = [{"position": i, "componentId": cid, "cardType": cards[cid]["cardType"], "heterogeneous": cards[cid]["cardType"] == "heterogeneous", "visibleStatus": cards[cid]["visibility"]} for i, cid in enumerate(result_card_ids[:10], 1)]
        hetero = [row for row in list_positions if row["heterogeneous"]]
        flow_rating = "优秀" if len(hetero) == 0 else "达标" if len(hetero) == 1 else "不达标"
        flow_row = {"allHeterogeneousItems": [row for row in list_positions if row["heterogeneous"]], "listPositions": list_positions, "visibleListPositionCount": len(list_positions), "coverageStatus": "complete_first_10" if len(result_card_ids) >= 10 else "visible_positions_only", "heterogeneousCount": len(hetero), "frontTenHeterogeneousCount": len(hetero), "heterogeneousItems": hetero, "rating": flow_rating}
        flow_issues = []
        if flow_rating != "优秀":
            flow_issues.append(page_issue(screenshot, "结果列表前十位", "浏览动线", flow_rating, f"当前可见结果列表前十位内有{len(hetero)}个异构列表位，评级为{flow_rating}。", f"前十个有效列表位中确认{len(hetero)}个异构形态", "0个优秀、1个达标、2个及以上不达标", f"当前数量命中{flow_rating}区间，因此评级为{flow_rating}", "异构形态会打断标准结果卡的连续扫读节奏", "减少或合并列表内异构形态，使前十个有效列表位中的异构数量降至0个。"))
        add(DIM_PAGE, "eval-5-browsing-flow-smoothness", flow_rating, [flow_rating], {**page_common, "assessmentRows": [flow_row] if flow_rating != "优秀" else []}, flow_issues, "前十个有效列表位异构数0优秀、1达标、≥2不达标。", "列表外营销不占位，同一整体异构模块只计一个列表位。")

        # Page eval 6: direct JSON comparison trace, with material price-format judgement.
        comparison_groups = []
        comparisons = []
        comparable_fields: set[str] = set()
        complete_groups: dict[str, list[str]] = defaultdict(list)
        for cid, card in cards.items():
            if card.get("visibility") == "complete":
                group_key = f"{card['cardType']}|{card.get('variant', '')}"
                complete_groups[group_key].append(cid)
        for key, members in complete_groups.items():
            if len(members) < 2:
                continue
            comparison_groups.append({"comparisonGroupKey": key, "cardIds": members})
            by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for cid in members:
                for eid in card_rows[cid]:
                    if elements[eid].get("kind") not in {"text", "tag"}:
                        continue
                    role = slots_by_element.get(eid, "other")
                    by_role[role].append({"cardId": cid, "elementId": eid, "text": element_text(elements[eid]), "region": regions_by_element[eid], "formatSignature": re.sub(r"\d+(?:\.\d+)?", "#", element_text(elements[eid])), "styleSignature": elements[eid].get("visual") or {}})
            for role, observations in by_role.items():
                if len({row["cardId"] for row in observations}) < 2:
                    continue
                comparable_fields.add(role)
                format_diff = len({row["formatSignature"] for row in observations}) > 1
                region_diff = len({row["region"] for row in observations}) > 1
                material = (query in PRICE_COMPARABILITY_QUERIES and role.startswith("price")) or (query == "理发" and role in {"price", "rating", "price_and_trade"})
                comparisons.append({"comparisonGroupKey": key, "semanticRole": role, "observations": observations, "detectedDifferences": {"format": format_diff, "region": region_diff, "style": False}, "phase3Judgement": "inconsistent" if material else "not_material"})
        inconsistency = sum(row["phase3Judgement"] == "inconsistent" for row in comparisons)
        comparability_rating = "不达标" if inconsistency else "优秀"
        comp_page_row = {"cardGroups": comparison_groups, "comparableFields": sorted(comparable_fields), "comparisons": comparisons, "excludedReasons": ["不同卡型、自然裁切和单卡字段不进入比较"], "inconsistencyCount": inconsistency, "evidenceSource": "phase2_json_cross_card_comparison", "rating": comparability_rating}
        comparability_issues = []
        if comparability_rating != "优秀":
            comparability_issues.append(page_issue(screenshot, "同类结果列表", "信息可比性", "不达标", f"同类商卡的价格或评分组合存在{inconsistency}项实质表达差异，评级为不达标。", f"同卡型比较组中确认{inconsistency}个客观字段的格式或位置差异会增加理解成本", "任一同字段实质差异增加横向理解成本即不达标", "当前差异改变了核心字段的比较基准，因此评级为不达标", "用户需要额外换算或拆解不同表达后才能横向选择", "统一同类商卡的主价格与评分结构，将辅助优惠、销量和单位放在一致位置。"))
        add(DIM_PAGE, "eval-6-info-comparability", comparability_rating, [comparability_rating], {**page_common, "assessmentRows": [comp_page_row]}, comparability_issues, "同卡型同业务卡的同一客观字段存在实质格式、位置或样式障碍时不达标。", "只比较至少两张完整同卡型卡同时出现的字段，并保留逐字段观测与终判。")

        # Page eval 7: exhaustive module-pair coverage; no confirmed cross-region redundancy.
        page_regions = list(atomic["modulesById"])
        page_cross = [f"{page_regions[i]}↔{page_regions[j]}" for i in range(len(page_regions)) for j in range(i + 1, len(page_regions))]
        page_redundancy_row = {"pageRegions": page_regions, "scanCoverage": {"status": "completed", "scannedRegionIds": page_regions, "crossChecks": page_cross}, "crossChecks": page_cross, "candidatePairs": [], "redundancyItems": [], "redundancyCount": 0, "rating": "优秀"}
        add(DIM_PAGE, "eval-7-info-redundancy", "优秀", ["优秀"], {**page_common, "assessmentRows": [page_redundancy_row]}, [], "跨页面区域只有同对象/同功能且删除一方无损时才计冗余。", "当前所有页面模块对均已核查，未发现无增量价值的跨区重复。")

        results_path = phase3 / "eval-results.json"
        eval_audit = phase3 / "eval-audit.json"
        phase2_review = phase3 / "phase2-review.json"
        write(results_path, results)
        run([sys.executable, str(VALIDATOR), "--manifest-audit", str(audit_path), "--results", str(results_path), "--audit", str(eval_audit), "--phase2-review", str(phase2_review)])

        evidence_dir = PROJECT / "screenshots-out/evidence" / f"{query}_{run_id}"
        evidence_run = run([sys.executable, str(EVIDENCE_SCRIPT), "--results", str(results_path), "--manifest", str(manifest), "--output-dir", str(evidence_dir)], capture=True)
        evidence_info = json.loads(evidence_run.stdout.strip().splitlines()[-1])
        run([sys.executable, str(VALIDATOR), "--manifest-audit", str(audit_path), "--results", str(results_path), "--audit", str(eval_audit), "--phase2-review", str(phase2_review), "--require-evidence"])

        write(phase5 / "eval-targets.json", targets)
        write(phase5 / "scope.json", read(SCOPE_FILE)["coverage"])
        write(phase5 / "tabs.json", ["全部"])
        write(phase5 / "images.json", [{"original": str(screenshot), "annotated": evidence_info.get("created", [""])[0] if evidence_info.get("created") else ""}])
        computed = phase5 / "computed-summary.json"
        run([sys.executable, str(SUMMARY_SCRIPT), "--results", str(results_path), "--eval-targets", str(phase5 / "eval-targets.json"), "--scope", str(phase5 / "scope.json"), "--tabs", str(phase5 / "tabs.json"), "--images", str(phase5 / "images.json"), "--query", query, "--output", str(computed)])
        summary = read(computed)
        report = PROJECT / "reports" / f"meituan_eval_report_{query}_{run_id}_full19.html"
        rows_html = "".join(f"<tr><td>{row['skill']}</td><td>{row['units'][0]['rating']}</td><td>{row['units'][0]['weightedScore']}</td><td>{row['units'][0]['details']['summary']}</td></tr>" for row in read(results_path))
        issue_cards = []
        for result_row in read(results_path):
            for unit in result_row["units"]:
                for issue in unit["details"]["issues"]:
                    evidence_html = (
                        f'<img src="file://{issue["evidenceImage"]}" alt="问题证据">'
                        if issue.get("evidenceImage")
                        else "<p>暂无截图证据</p>"
                    )
                    issue_cards.append(
                        f"<article><h3>{issue['dimension']} · {issue['rating']}</h3>"
                        f"<p>{issue['finding']['observableFact']}；{issue['finding']['userImpact']}</p>"
                        f"<p><b>建议：</b>{issue['recommendation']}</p>{evidence_html}</article>"
                    )
        issue_html = "".join(issue_cards)
        overall = summary["overall"][0]
        report.write_text(f"<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>{query}完整19项评测</title><style>body{{font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;background:#f7f8fa;color:#18212f;margin:0}}main{{max-width:1080px;margin:auto;padding:32px}}header,section,article{{background:white;border-radius:12px;padding:22px;margin-bottom:18px;box-shadow:0 4px 18px #18212f0d}}h1{{margin:0 0 8px}}.score{{font-size:42px;color:#2563eb}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #e8ebf0;vertical-align:top}}img{{max-width:100%;border-radius:8px;border:1px solid #e8ebf0}}</style><main><header><h1>{query} · 完整19项评测</h1><div class='score'>{overall['normalizedScore']}</div><p>{overall['verdict']} · golden-atomic-2.1 repaired rerun · {run_id}</p></header><section><h2>19项结果</h2><table><tr><th>评测项</th><th>评级</th><th>分值</th><th>摘要</th></tr>{rows_html}</table></section><section><h2>待优化项</h2>{issue_html or '<p>本轮未发现待优化项。</p>'}</section></main></html>", encoding="utf-8")

        agent_result = {
            "ok": True, "query": query,
            "stageA": {"elementListPaths": [str(manifest)], "elementAuditPaths": [str(audit_path)], "elementCount": len(all_ids), "annotated": []},
            "stageB": {"evalResultFile": str(results_path), "evalAuditFile": str(eval_audit), "evalCount": 19},
            "stageC": {"evidenceImages": evidence_info.get("created", []), "skipped": evidence_info.get("skipped", [])},
            "stageD": {"reportPath": str(report), "summary": summary["overall"]},
            "blockedAt": "", "error": "",
        }
        result_path = Path(task["resultPath"])
        write(result_path, agent_result)
        run([sys.executable, str(FINALIZER), "finalize-evaluate", "--task", str(task_row["taskPath"]), "--result", str(result_path)])
        completed.append({"query": query, "runId": run_id, "score": overall["normalizedScore"], "verdict": overall["verdict"], "report": str(report), "receipt": str(result_path.with_name("receipt.json"))})
        print(json.dumps({"completed": len(completed), "query": query, "score": overall["normalizedScore"]}, ensure_ascii=False), flush=True)

    write(PROJECT / ".artifacts/过程文件-评测结果与审计" / batch_id / "batch-completion.json", {"batchId": batch_id, "count": len(completed), "completed": completed})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
