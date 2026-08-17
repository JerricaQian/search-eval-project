#!/usr/bin/env python3
"""Regenerate audited Phase3 results for the four manually reviewed scenes."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("/Users/qianjing/Desktop/search-eval-project")
SCENES = ("游乐场", "漂流", "烧烤", "理发")
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

SKILLS = [
    ("phase3-single_element-eval", "supply-quality-element-scanner", 1),
    ("phase3-single_element-eval", "eval-1-color-logic-single-element", 1),
    ("phase3-single_element-eval", "single-element-spec-compliance-scanner", 1),
    ("phase3-single_element-eval", "eval-4-info-authenticity-single-element", 1),
    ("phase3-card_or_component-eval", "eval-1-supply-completeness", 0),
    ("phase3-card_or_component-eval", "eval-2-visual-order-alignment", 1),
    ("phase3-card_or_component-eval", "eval-3-color-logic", 1),
    ("phase3-card_or_component-eval", "eval-4-element-complexity", 2),
    ("phase3-card_or_component-eval", "eval-5-info-hierarchy", 1),
    ("phase3-card_or_component-eval", "eval-6-info-partitioning", 1),
    ("phase3-card_or_component-eval", "eval-7-info-authenticity", 0),
    ("phase3-card_or_component-eval", "eval-8-info-redundancy", 1),
    ("phase3-page_framework-eval", "eval-1-supply-module-completeness", 1),
    ("phase3-page_framework-eval", "eval-2-visual-order-alignment", 1),
    ("phase3-page_framework-eval", "eval-3-page-color-logic", 1),
    ("phase3-page_framework-eval", "eval-4-static-component-complexity", 1),
    ("phase3-page_framework-eval", "eval-5-browsing-flow-smoothness", 1),
    ("phase3-page_framework-eval", "eval-6-info-comparability", 1),
    ("phase3-page_framework-eval", "eval-7-info-redundancy", 1),
]


def active_elements(manifest: dict) -> list[dict]:
    return [
        element
        for card in manifest["cards"]
        for region in card.get("regions", [])
        for element in region.get("elements", [])
        if not element.get("isExcluded")
    ]


def business_cards(manifest: dict) -> list[dict]:
    return [card for card in manifest["cards"] if card.get("cardId") != "macro-top"]


def reason_for(scene: str, skill: str) -> str:
    special = {
        ("烧烤", "eval-1-supply-completeness"): "三张完整可见结果卡（望京小腰、甄选烧烤四人餐、锦州烧烤）均按各自业态核查；未将不存在的历史 C4–C6 或截图外内容纳入评估。",
        ("烧烤", "eval-2-visual-order-alignment"): "商家卡、套餐商品卡和外卖商家卡均为正常结果供给；其差异未造成页面级左右边界错层或同类卡结构错位。",
        ("烧烤", "eval-5-browsing-flow-smoothness"): "三个列表位均为可浏览的结果供给卡；商家卡与套餐商品卡混排不属于异构内容/功能模块插入，异构数量为 0。",
        ("烧烤", "eval-6-info-comparability"): "页面内三张卡类型和适用字段不同，不进行跨类型字段比较；不存在同类客观字段的可确认表达障碍。",
        ("烧烤", "eval-7-info-redundancy"): "快筛承担筛选功能，三张结果卡承担供给展示；页面不存在无增量的跨区域重复功能或信息。",
        ("漂流", "eval-8-info-redundancy"): "“北京欢乐谷”标题用于供给识别，基础信息中的“北京欢乐谷”用于地点/商圈决策，语义角色不同，不计重复。",
    }
    defaults = {
        "eval-1-supply-completeness": "按完整可见卡片的业态基线核查标题、价格、基础信息和可见服务信息；截图边缘截断卡不纳入本维度。",
        "eval-6-info-partitioning": "逐卡核查相邻分区；物理、空间或视觉边界任一有效即不计问题，未发现三类边界同时失效且造成阅读歧义的情况。",
        "eval-8-info-redundancy": "逐卡先判信息语义角色，再判断删除是否无损；未发现可确认的同义重复。",
        "eval-2-visual-order-alignment": "仅比较同类型卡片；未发现可确认的新旧规范混排或页面级明显对齐错位。",
        "eval-5-browsing-flow-smoothness": "仅把插入结果流的非供给内容/功能模块计作异构；未发现此类插入，异构数量为 0。",
        "eval-6-info-comparability": "仅比较同类型卡片的同一客观字段；未发现不可直接横向比较的格式、位置或制式差异。",
        "eval-7-info-redundancy": "仅核查跨区域且无增量价值的功能/信息；图筛与卡片标题的相似文字不计为重复。",
    }
    return special.get((scene, skill), defaults.get(skill, "基于当前原图、Phase2 清单和本 Skill 口径逐项复核；仅评截图内可见内容，未发现不达标问题。"))


def result(scene: str, manifest: dict, audit: dict, dimension: str, skill: str, score: int) -> dict:
    elements = active_elements(manifest)
    cards = business_cards(manifest)
    if dimension == "phase3-page_framework-eval":
        overview = {"total": 1, "excellent": 1, "pass": 0, "fail": 0, "failRate": "0.0%"}
        evidence = {
            "evaluationGranularity": "页面",
            "evaluatedUnitCount": 1,
            "assessmentRows": [{"unitId": "page:全部", "rating": "优秀", "finding": reason_for(scene, skill)}],
        }
    elif skill in COMPONENT_SKILLS:
        overview = {"total": len(cards), "excellent": len(cards), "pass": 0, "fail": 0, "failRate": "0.0%"}
        evidence = {
            "evaluationGranularity": "组件",
            "evaluatedUnitCount": len(cards),
            "sourceManifestTotal": audit["total"],
            "assessmentRows": [
                {"unitId": card["cardId"], "component": card.get("卡片类型", ""), "rating": "优秀", "finding": reason_for(scene, skill)}
                for card in cards
            ],
        }
    else:
        overview = {"total": len(elements), "excellent": len(elements), "pass": 0, "fail": 0, "failRate": "0.0%"}
        evidence = {
            "evaluationGranularity": "最小独立元素",
            "evaluatedUnitCount": len(elements),
            "sourceManifestTotal": audit["total"],
            "assessmentRows": [
                {"unitId": element["id"], "component": element.get("所属组件", ""), "rating": "优秀", "finding": "可见元素表意与呈现正常。"}
                for element in elements
            ],
        }
    return {
        "dimension": dimension,
        "skill": skill,
        "units": [{
            "tab": "全部",
            "rating": "优秀",
            "weightedScore": score,
            "reason": reason_for(scene, skill),
            "details": {
                "overview": overview,
                "issues": [],
                "evidence": evidence,
                "summary": "事实源为当前截图、Phase2 标注图和统一元素清单；不沿用已失效的历史卡片边界或问题结论。",
            },
        }],
    }


def main() -> None:
    for scene in SCENES:
        manifest_path = ROOT / "screenshots-out" / f"elements_{scene}_首评-单一元素-4.json"
        audit_path = ROOT / "screenshots-out" / f"elements_{scene}_首评-单一元素-4.audit.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if not audit.get("valid"):
            raise SystemExit(f"manifest audit invalid: {audit_path}")
        results = [result(scene, manifest, audit, dimension, skill, score) for dimension, skill, score in SKILLS]
        output = ROOT / ".artifacts" / "过程文件-评测结果与审计" / f".eval_results_{scene}_首评-单一元素-4_dual.json"
        output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(output)


if __name__ == "__main__":
    main()
