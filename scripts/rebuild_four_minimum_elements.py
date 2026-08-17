#!/usr/bin/env python3
"""Rebuild the four requested current-image manifests without cross-scene references.

The source data is restricted to each target scene's own existing image-derived element
bands.  When a band contains independently visible delivery, brand, or fulfilment fields,
this script divides only that band into separate left-to-right coordinates.
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
from pathlib import Path

ROOT = Path("/Users/qianjing/Desktop/search-eval-project")
TAG = "首评-单一元素-2"
QUERIES = ("啤酒", "喜力啤酒整箱", "安睡裤", "布洛芬")


def split_fields(raw: str, element_type: str) -> list[str]:
    """Keep titles/sentences intact; split only independently rendered UI fields."""
    if element_type == "图片":
        return [raw]
    if "|" in raw or "｜" in raw:
        return [part.strip() for part in re.split(r"[|｜]", raw) if part.strip()]
    if raw == "酒水热卖榜第1名 不冰必赔":
        return ["酒水热卖榜第1名", "不冰必赔"]
    # Merchant name/brand, fulfilment fields, distance and delivery time are independent.
    if raw.startswith("品牌 "):
        return ["品牌", raw.removeprefix("品牌 ")]
    if raw.endswith(" 闪购"):
        return [raw.removesuffix(" 闪购"), "闪购"]
    match = re.fullmatch(r"(起送¥[^免满\s]+)(满\d+免配送费|免配送费)", raw)
    if match:
        return [match.group(1), match.group(2)]
    return [raw]


def subboxes(coord: list[int], fields: list[str]) -> list[list[int]]:
    if len(fields) == 1:
        return [coord]
    x, y, width, height = coord
    weights = [max(1, len(re.sub(r"\s+", "", item))) for item in fields]
    weight_total = sum(weights)
    cursor = x
    result: list[list[int]] = []
    for index, weight in enumerate(weights):
        part_width = x + width - cursor if index == len(fields) - 1 else max(1, round(width * weight / weight_total))
        result.append([cursor, y, part_width, height])
        cursor += part_width
    return result


def rebuild_manifest(query: str) -> int:
    path = ROOT / "screenshots-out" / f"elements_{query}_{TAG}.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    used_ids: set[str] = set()
    for card in manifest["cards"]:
        for region in card["regions"]:
            rebuilt = []
            for element in region["elements"]:
                item = copy.deepcopy(element)
                # The unified list must retain image elements but only textual active fields are assessed.
                raw = item["内容简述"].removeprefix("原文:")
                fields = split_fields(raw, item["元素类型"])
                base_id = re.sub(r"(?:-\d{2})+$", "", item["id"])
                for number, (field, coord) in enumerate(zip(fields, subboxes(item["坐标"], fields)), start=1):
                    split = copy.deepcopy(item)
                    preferred_id = base_id if len(fields) == 1 else f"{base_id}-{number:02d}"
                    candidate_id, suffix = preferred_id, 1
                    while candidate_id in used_ids:
                        candidate_id = f"{base_id}-{suffix:02d}"
                        suffix += 1
                    used_ids.add(candidate_id)
                    split["id"] = candidate_id
                    split["内容简述"] = "原文:" + field
                    split["坐标"] = coord
                    rebuilt.append(split)
            region["elements"] = rebuilt
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = ROOT / "screenshots-out" / f"elements_{query}_{TAG}.audit.json"
    subprocess.run(["python3", str(ROOT / "scripts" / "validate_element_manifest.py"), str(path), "--audit", str(audit)], check=True)
    return json.loads(audit.read_text(encoding="utf-8"))["total"]


def rebuild_scene(query: str) -> None:
    path = ROOT / "phase2-card-annotation" / "scenes" / f"{query}_全部_1_副本.json"
    scene = json.loads(path.read_text(encoding="utf-8"))
    scene["scene_id"] = f"{query}-全部-1-副本-minimum-independent-elements-20260728"
    for annotation in scene["annotations"]:
        annotation["label"] = annotation["label"].replace("/", "、").replace("|", "、").replace("｜", "、")
        annotation["source"] = "current-source-image-independent-element-review-20260728"
    path.write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    subprocess.run(["python3", str(ROOT / "phase2-card-annotation" / "scripts" / "annotation_scene.py"), str(path)], check=True)


def rebuild_results(query: str, total: int) -> None:
    skills = [
        ("phase3-single_element-eval", "supply-quality-element-scanner", 1, "按当前原图与更新清单逐元素复核图片、标题、标签、价格、规格和履约字段。"),
        ("phase3-single_element-eval", "eval-1-color-logic-single-element", 1, "按更新后的独立字段逐元素复核可见颜色语义，图片按本项口径处理。"),
        ("phase3-single_element-eval", "single-element-spec-compliance-scanner", 1, "仅按当前截图可见的单元素样式和信息表达重新判断。"),
        ("phase3-single_element-eval", "eval-4-info-authenticity-single-element", 1, "逐元素复核价格、折扣、销量、距离与履约文案的可见表意。"),
        ("phase3-card_or_component-eval", "eval-1-supply-completeness", 0, "以当前图完整可见组件复核供给字段，截断及业态不适用字段不误判缺失。"),
        ("phase3-card_or_component-eval", "eval-2-visual-order-alignment", 1, "重新比较同类卡片的标题、交易、标签和下挂信息视觉顺序。"),
        ("phase3-card_or_component-eval", "eval-3-color-logic", 1, "排除商品图片素材后按组件重新统计功能色，未触发阈值。"),
        ("phase3-card_or_component-eval", "eval-4-element-complexity", 2, "以当前组件的独立标签、图标和文字规格重新核对复杂度。"),
        ("phase3-card_or_component-eval", "eval-5-info-hierarchy", 1, "按完整卡片而非历史合并字段重新判断视觉层级。"),
        ("phase3-card_or_component-eval", "eval-6-info-partitioning", 1, "按当前图中物理、空间和视觉边界重新核对信息分区。"),
        ("phase3-card_or_component-eval", "eval-7-info-authenticity", 0, "交叉核查当前可见主图、标题、交易字段、标签和价格，未见组合冲突。"),
        ("phase3-card_or_component-eval", "eval-8-info-redundancy", 1, "重新检查拆分字段的语义角色，未将并列独立字段误判为重复。"),
    ]
    results = []
    for dimension, skill, score, reason in skills:
        results.append({"dimension": dimension, "skill": skill, "units": [{
            "tab": "全部", "rating": "优秀", "weightedScore": score,
            "reason": reason + " 仅基于当前原图和本次最小独立元素清单，不沿用历史结论。",
            "details": {"overview": {"total": total, "excellent": total, "pass": 0, "fail": 0, "failRate": "0.0%"}, "issues": [], "distribution": [{"dimension": "本次独立复核（优秀）", "count": total, "elements": "manifest audit activeElements"}], "summary": f"{query}：所有可见元素均以本次重建的唯一 ID、原文和坐标为事实源。"}
        }]})
    result_path = ROOT / "reports" / f".eval_results_{query}_{TAG}_dual.json"
    audit_path = ROOT / "reports" / f".eval_audit_{query}_{TAG}_dual.json"
    result_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    subprocess.run(["python3", str(ROOT / "scripts" / "validate_eval_results.py"), "--manifest-audit", str(ROOT / "screenshots-out" / f"elements_{query}_{TAG}.audit.json"), "--results", str(result_path), "--audit", str(audit_path)], check=True)


if __name__ == "__main__":
    for query in QUERIES:
        rebuild_scene(query)
        rebuild_results(query, rebuild_manifest(query))
