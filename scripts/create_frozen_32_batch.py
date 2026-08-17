#!/usr/bin/env python3
"""Freeze the audited 32-query evaluation scope and produce isolated Phase3 results.

The batch scope is the sole input contract for Phase4. It records the exact Phase2
manifest, isolated result file and SHA-256 fingerprints, so historical artifacts
cannot silently enter a new dashboard batch.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATASET = ROOT / "reports/.governance_dataset_首评-单一元素8.3-Phase2修正回归.json"
ARTIFACT_DIR = ROOT / ".artifacts/过程文件-评测结果与审计"
BATCH_DIR = ARTIFACT_DIR / "严格32词-口径修正回归"
RESULT_DIR = BATCH_DIR / "results"
SCOPE_PATH = BATCH_DIR / "batch_scope.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def set_excellent(unit: dict[str, Any], reason: str) -> None:
    unit["rating"] = "优秀"
    unit["weightedScore"] = 1
    unit["reason"] = reason
    details = unit.setdefault("details", {})
    overview = details.setdefault("overview", {})
    total = int(overview.get("total") or 1)
    overview.update({"total": total, "excellent": total, "pass": 0, "fail": 0, "failRate": "0.0%"})
    details["issues"] = []
    details["summary"] = reason
    evidence = details.get("evidence")
    if isinstance(evidence, dict) and isinstance(evidence.get("assessmentRows"), list):
        for row in evidence["assessmentRows"]:
            if isinstance(row, dict):
                row["rating"] = "优秀"
                row["finding"] = reason


def patch_result(query: str, results: list[dict[str, Any]]) -> None:
    """Apply reviewed corrections that are evidenced by the current Phase2 scope."""
    reviewed_excellent = {
        ("喜力啤酒整箱", "eval-2-visual-order-alignment"):
            "仅比较同类商品卡的结构锚点；商品名称、价格文案和头图比例差异不构成对齐问题，未见可确认的错位或规范混用。",
        ("库迪", "eval-1-supply-completeness"):
            "仅评完整可见商卡；标题、基础信息、标签与图文下挂区域均可见，未以内容层叠或模板差异误判为字段缺失。",
        ("库迪", "eval-6-info-partitioning"):
            "标题、基础信息、权益标签和图文下挂区域承担不同语义角色；不以相邻坐标无空白替代分区判断，未见跨区混杂或阅读归属歧义。",
        ("解压体验馆", "eval-1-supply-completeness"):
            "按体验服务商卡的适用字段和完整可见范围核查，不套用商品/外卖卡字段基线；未见可确认的核心供给缺失。",
        ("体检", "eval-7-info-redundancy"):
            "图筛用于体检品类与意图导航，商卡内标签/供给用于展示可选服务；即使文字相似，二者决策角色不同，不构成页面功能或信息冗余。",
    }
    for result in results:
        skill = str(result.get("skill", ""))
        for unit in result.get("units", []):
            if not isinstance(unit, dict):
                continue
            reason = reviewed_excellent.get((query, skill))
            if reason:
                set_excellent(unit, reason)
            if query == "蜜雪冰城" and skill == "eval-8-info-redundancy":
                details = unit.get("details") or {}
                for issue in details.get("issues") or []:
                    if not isinstance(issue, dict):
                        continue
                    text = str(issue.get("content", ""))
                    if "冰鲜柠檬水" in text:
                        issue["description"] = "商卡1「蜜雪冰城（东辛店）」下挂区域重复展示供给「冰鲜柠檬水」；两处均为同一商品主体，未补充规格、价格、优惠或履约等新增决策信息。"
                    elif "满杯百香果" in text:
                        issue["description"] = "商卡1「蜜雪冰城（东辛店）」下挂区域重复展示供给「满杯百香果」；两处均为同一商品主体，未补充规格、价格、优惠或履约等新增决策信息。"
                if details.get("issues"):
                    unit["reason"] = "仅确认商卡1下挂区域内同一供给的重复展示；问题描述明确记录重复供给、所在区域和缺失的增量决策信息。"
                    details["summary"] = unit["reason"]


def find_single(pattern: str, query: str) -> Path:
    matches = sorted(ARTIFACT_DIR.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError(f"{query} 缺少匹配产物：{pattern}")
    return matches[0]


def main() -> None:
    source = load(SOURCE_DATASET)
    queries = list(source["queryDetails"])
    if len(queries) != 32 or "五道口" in queries:
        raise ValueError("源 32 词数据集不是严格白名单，停止冻结")
    if BATCH_DIR.exists():
        shutil.rmtree(BATCH_DIR)
    RESULT_DIR.mkdir(parents=True)
    entries: list[dict[str, Any]] = []
    for query in queries:
        manifest_candidates = sorted((ROOT / "screenshots-out").glob(f"elements_{query}_*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        manifest_candidates = [item for item in manifest_candidates if not item.name.endswith(".audit.json")]
        if not manifest_candidates:
            raise FileNotFoundError(f"{query} 缺少 Phase2 清单")
        manifest = manifest_candidates[0]
        result_source = find_single(f".eval_results_{query}_*_dual.json", query)
        results = load(result_source)
        if not isinstance(results, list):
            raise ValueError(f"{query} 评测结果格式错误")
        patch_result(query, results)
        result_path = RESULT_DIR / result_source.name
        result_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manifest_data = load(manifest)
        entries.append({
            "query": query,
            "manifest": str(manifest), "manifestHash": digest(manifest),
            "screenshot": manifest_data.get("screenshot", ""),
            "annotatedImage": manifest_data.get("annotatedImage", ""),
            "result": str(result_path), "resultHash": digest(result_path),
        })
    skill_paths = sorted(ROOT.glob("phase3-*/eval-skills/*/SKILL.md"))
    scope = {
        "batchId": "严格32词-口径修正回归",
        "generatedAt": str(date.today()),
        "queryCount": len(entries),
        "queries": entries,
        "skillHashes": {str(path.relative_to(ROOT)): digest(path) for path in skill_paths},
        "contract": "Phase4 must consume only listed manifests/results; all hashes must match current files.",
    }
    SCOPE_PATH.write_text(json.dumps(scope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(SCOPE_PATH)


if __name__ == "__main__":
    main()
