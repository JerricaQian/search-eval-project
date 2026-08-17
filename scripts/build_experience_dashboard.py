#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the cross-query search result experience dashboard.

The dashboard keeps search terms as evidence only. Business conclusions are
aggregated from result cards that are classified by their visible content.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase5-report"))
from dashboard_renderer import render_dashboard

BUSINESS_LINES = {
    "dine_in": "到餐", "food_delivery": "餐饮外卖", "flash_delivery": "闪购",
    "service_retail": "服务零售", "healthcare": "医药健康", "hotel_travel": "酒店旅行",
    "xiaoxiang": "小象", "maoyan": "猫眼", "bike": "骑行", "youxuan": "优选",
    "errand": "跑腿", "finance": "金融", "power_bank": "充电宝",
    "ride_hailing": "网约车", "xiaoxiang_supermarket": "小象超市",
    "dianping_overseas": "点评境外",
}
# 报告业务 Tab 的唯一允许集合。每批生成前必须校验输出业务代码与名称；
# 未被治理口径认可的分类（如已废弃的 tuangou_goods）一律阻断交付。
EXPECTED_REPORT_BUSINESS_TABS = BUSINESS_LINES.copy()
PLATFORM_SCOPES = {"宏观组件", "特殊广告卡", "运营聚合卡", "相似推荐提示"}
LEVELS = {
    "phase3-single_element-eval": ("单一元素维度", "element", "#6366f1"),
    "phase3-card_or_component-eval": ("组件/卡片维度", "component", "#10b981"),
    "phase3-page_framework-eval": ("页面框架维度", "page", "#60a5fa"),
}
PASS_RATINGS = {"达标", "🟡"}
FAIL_RATINGS = {"不达标", "🔴"}


def priority_from_vote_counts(fail_count: int, pass_count: int) -> str | None:
    """Return the deterministic governance priority for one business/level/metric unit."""
    if fail_count >= 2 or pass_count >= 4:
        return "P0"
    if fail_count >= 1 or pass_count >= 2:
        return "P1"
    if pass_count >= 1:
        return "P2"
    return None


def priority_reason_from_vote_counts(fail_count: int, pass_count: int, priority: str) -> str:
    return (
        f"同一业务线、同一维度、同一指标本轮统计：不达标 {fail_count} 票，达标 {pass_count} 票。"
        f"按固定阈值（不达标≥2或达标≥4为P0；不达标≥1或达标≥2为P1；达标≥1为P2）判定为 {priority}。"
    )


METRICS = {
    "eval-1-supply-quality-scanner": ("供给呈现质量", "supply_quality"),
    "eval-1-supply-completeness": ("供给呈现质量", "supply_completeness"),
    "eval-1-supply-module-completeness": ("供给呈现质量（页面框架完整性）", "supply_module_completeness"),
    "eval-2-color-logic-single-element": ("色彩运用有逻辑", "color_logic"),
    "eval-2-visual-order-alignment": ("视觉秩序统一对齐", "visual_order"),
    "eval-3-page-color-logic": ("色彩运用有逻辑（页面级）", "page_color_logic"),
    "eval-3-color-logic": ("色彩运用有逻辑", "color_logic"),
    "eval-3-element-compliance-scanner": ("静态元素不复杂", "element_compliance"),
    "eval-4-element-complexity": ("静态元素/组件不复杂", "element_complexity"),
    "eval-4-static-component-complexity": ("静态组件不复杂（首屏功能区数量）", "static_component_complexity"),
    "eval-4-info-authenticity-single-element": ("信息与功能真实无歧义", "info_authenticity"),
    "eval-5-info-hierarchy": ("信息主次分明", "information_hierarchy"),
    "eval-5-browsing-flow-smoothness": ("浏览动线顺畅", "browsing_flow"),
    "eval-5-info-redundancy": ("信息无冗余", "information_redundancy"),
    "eval-6-info-partitioning": ("信息分区合理", "information_partitioning"),
    "eval-6-info-comparability": ("信息可比", "information_comparability"),
    "eval-7-info-authenticity": ("信息与功能真实无歧义", "info_authenticity"),
    "eval-7-browsing-flow-smoothness": ("浏览动线顺畅", "browsing_flow"),
    "eval-7-info-redundancy": ("功能/信息无冗余", "page_information_redundancy"),
    "eval-8-info-redundancy": ("信息无冗余", "information_redundancy"),
}


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def text_for_card(card: dict[str, Any]) -> str:
    values: list[str] = [str(card.get("卡片类型", ""))]
    for region in card.get("regions", []):
        for element in region.get("elements", []):
            values.append(str(element.get("内容简述", "")))
    return " ".join(values).lower()


def classify_card(card: dict[str, Any]) -> dict[str, str]:
    """Classify only from card-visible content/structure, never the query."""
    card_type = str(card.get("卡片类型", ""))
    # Phase2 已明确标记归属时，以清单为唯一事实源，避免再由文本关键词
    # 将小象、外卖等异构商品卡误归类。
    explicit_code = str(card.get("businessCode", ""))
    explicit_name = str(card.get("businessName", ""))
    if card.get("ownershipScope") == "business" and explicit_code and explicit_name:
        # businessCode 是业务线口径，businessName 在部分清单中是具体商户名；
        # 看板分组必须稳定使用业务线标准名，避免把“熊本便利店”等商户误作业务线。
        return {
            "scope": "business", "businessCode": explicit_code,
            "businessName": BUSINESS_LINES.get(explicit_code, explicit_name),
            "confidence": str(card.get("businessConfidence", "high")),
            "cardTypeCode": str(card.get("cardTypeCode", "merchant_card")),
            "cardTypeName": str(card.get("cardTypeName", card_type)),
        }
    if card_type in PLATFORM_SCOPES or card.get("cardId") == "macro-top":
        return {"scope": "platform", "businessCode": "platform", "businessName": "平台公共组件",
                "confidence": "high", "cardTypeCode": "platform_component", "cardTypeName": card_type}
    text = text_for_card(card)
    rules = [
        ("healthcare", ("医院", "体检", "医药", "药店", "药房", "诊所", "医疗", "门诊")),
        ("hotel_travel", ("酒店", "民宿", "房型", "景点", "度假", "露营", "漂流", "门票")),
        ("maoyan", ("电影", "影院", "演出", "场次", "票价", "剧场")),
        ("bike", ("骑行", "单车")),
        ("ride_hailing", ("打车", "网约车", "快车", "出租车")),
        ("power_bank", ("充电宝", "借充电")),
        ("finance", ("保险", "借款", "金融", "理财")),
        # 不以“主点卡片”中的“点卡”字样判断业务；充值/游戏电商必须由显式业务标签或专属卡型标注。
        ("xiaoxiang_supermarket", ("小象超市",)),
        # “闪购/分钟达/即时零售”是明确业务标签，必须优先于“配送/起送”等跨业务履约字段。
        ("flash_delivery", ("闪购", "分钟达", "即时零售")),
        ("food_delivery", ("外卖", "配送", "起送", "月售", "外送")),
        ("dine_in", ("人均", "评价", "到店", "团购", "套餐", "堂食", "美食", "烧烤", "咖啡", "餐厅")),
        ("service_retail", ("维修", "理发", "按摩", "清洗", "美容", "美甲", "家政", "摄影")),
        ("youxuan", ("优选",)),
        ("xiaoxiang", ("小象",)),
        ("dianping_overseas", ("境外", "海外")),
        ("errand", ("跑腿", "代取", "代送")),
    ]
    business = next((code for code, words in rules if any(word in text for word in words)), None)
    if not business:
        return {"scope": "unknown", "businessCode": "unknown", "businessName": "未知待确认",
                "confidence": "unknown", "cardTypeCode": "unknown_card", "cardTypeName": card_type}
    if "商品" in card_type:
        kind = "product_card"
    elif "图文下挂" in card_type:
        kind = "merchant_image_append_card"
    elif "文字下挂" in card_type:
        kind = "merchant_text_append_card"
    elif "主点" in card_type:
        kind = "poi_card"
    elif "酒店" in card_type:
        kind = "hotel_card"
    else:
        kind = "merchant_card"
    return {"scope": "business", "businessCode": business, "businessName": BUSINESS_LINES[business],
            "confidence": "high", "cardTypeCode": kind, "cardTypeName": card_type}


def humanize_element_label(element: dict[str, Any]) -> str:
    """Turn a Phase2 element record into a concise reader-facing object label."""
    element_type = str(element.get("元素类型") or element.get("elementType") or "元素").strip()
    content = str(element.get("内容简述") or element.get("content") or "").strip()
    content = re.sub(r"^(?:原文|内容)\s*[:：]\s*", "", content).strip()
    if content:
        return f"{element_type}：「{content}」"
    return element_type or "页面元素"


def humanize_issue_element(issue: dict[str, Any]) -> str:
    """Prefer accepted issue copy when a historical manifest cannot resolve the element."""
    element_type = str(issue.get("elementType") or "元素").strip()
    content = str(issue.get("content") or "").strip()
    content = re.sub(r"^(?:原文|内容)\s*[:：]\s*", "", content).strip()
    return f"{element_type}：「{content}」" if content else (element_type or "页面元素")


def issue_finding(issue: dict[str, Any]) -> dict[str, str]:
    """Return the normalized structured explanation, tolerating historical results."""
    raw = issue.get("finding")
    finding = raw if isinstance(raw, dict) else {}
    return {
        "observableFact": str(finding.get("observableFact", "")),
        "ruleOrThreshold": str(finding.get("ruleOrThreshold", "")),
        "verdictReason": str(finding.get("verdictReason", "")),
        "userImpact": str(finding.get("userImpact", "")),
    }


def issue_description(issue: dict[str, Any], fallback: str = "") -> str:
    """Prefer a structured verdict reason; fall back safely for historical records."""
    finding = issue_finding(issue)
    return (
        finding["verdictReason"]
        or str(issue.get("description", ""))
        or finding["observableFact"]
        or fallback
    )


def issue_recommendation(issue: dict[str, Any], metric_code: str) -> str:
    """Build a concrete, issue-scoped recommendation from accepted evaluation facts."""
    finding = issue_finding(issue)
    target = str(issue.get("elementId") or issue.get("component") or issue.get("cardId") or issue.get("pageArea") or "当前问题区域")
    fact = finding["observableFact"]
    if metric_code == "color_logic":
        action = "收敛该对象内的非语义强调色：保留价格、履约/状态与权益各自的唯一语义色，其余标签和运营装饰降为中性色或合并到同一色系"
    elif metric_code in {"element_complexity", "static_component_complexity", "element_compliance"}:
        action = "合并该对象内语义重复的异色/异形标签与图标，复用标准样式，并将样式数量收敛到本指标优秀阈值内"
    elif metric_code in {"information_partitioning", "info_partitioning"}:
        action = "在该对象涉及的相邻信息区之间补齐一致的留白或分隔边界，并将跨区字段归回标题、基础信息、价格或权益各自的固定区域"
    elif metric_code in {"information_redundancy", "info_redundancy"}:
        action = "删除该对象中与标题或基础信息重复的字段，仅在一个决策位置保留该事实，并将其余位置改为补充信息"
    elif metric_code in {"information_hierarchy", "visual_order_alignment"}:
        action = "将该对象的核心决策信息设为唯一一级强调，其余价格说明、权益和营销标签依次降为二、三级样式"
    elif metric_code in {"supply_completeness", "supply_quality"}:
        action = "补齐该对象缺失的关键决策字段，或在字段不可用时启用同卡型的降级布局，保持同类结果的信息基线一致"
    elif metric_code in {"info_authenticity", "information_authenticity"}:
        action = "改写该对象中的歧义表达，补齐适用对象、条件和价格/权益口径，并与当前可见事实逐项核对"
    else:
        action = "根据该对象的可见字段和触发规则收敛当前实现，避免同类卡片继续复制该问题表现"
    return f"针对 {target}：{action}；验收时复测“{fact}”，确保不再触发“{finding['ruleOrThreshold']}”。"


def issue_code(skill: str, issue: dict[str, Any]) -> str:
    finding = issue_finding(issue)
    desc = (str(issue.get("dimension", "")) + " " + str(issue.get("description", "")) + " " + finding["observableFact"] + " " + finding["verdictReason"]).lower()
    if "层级" in desc or "主次" in desc:
        return "MULTIPLE_PRIMARY_EMPHASIS"
    if "颜色" in desc or "色彩" in desc:
        return "COLOR_LOGIC_CONFLICT"
    if "冗余" in desc or "重复" in desc:
        return "REDUNDANT_INFORMATION"
    if "分区" in desc or "边界" in desc:
        return "WEAK_INFORMATION_PARTITION"
    if "完整" in desc or "缺失" in desc or "截断" in desc:
        return "CONTENT_COMPLETENESS_FAILURE"
    if "真实" in desc or "歧义" in desc or "误导" in desc:
        return "AUTHENTICITY_OR_CLARITY_RISK"
    return f"{skill.upper().replace('-', '_')}_ISSUE"


def query_from_result(path: Path) -> str | None:
    # Recheck artifacts may append a suffix such as `_eval-4-recheck`; their
    # query is reliably the parent query directory, not a fragile filename slice.
    if path.parent.name in {"phase3", "phase3-recheck", "phase4", "phase4-recheck"}:
        return path.parent.parent.name
    if path.parent.name == "results" and path.parent.parent.name:
        parent_name = path.parent.parent.name
        # A few retained batch directories append `_results` to the query name.
        # Prefer the filename parser below for the canonical query in that case.
        if not parent_name.endswith("_results"):
            return parent_name
    match = re.match(r"\.eval_results_(.+?)_(?:首评-单一元素-\d+_dual|试评测(?:_[^.]*)?|single_element|card_component(?:_page_framework)?|page_framework)\.json$", path.name)
    if match:
        return match.group(1)
    match = re.match(r"评测原始结果_(.+?)(?:_[^/]*)?_(?:single_element|card_or_component|page_framework|single_element_card_or_component|card_or_component_page_framework|single_element_card_or_component_page_framework)\.json$", path.name)
    if match:
        return match.group(1)
    # 单词 Phase2-4 子任务的最终交接文件命名为 all-results_<query>... 或
    # <query>.all-results...；目录名是本批次唯一的 query 事实源。
    if "all-results" in path.name and path.parent.name == "results":
        return path.parent.parent.name
    return None


def normalize_results(raw_results: Any) -> list[dict[str, Any]]:
    """Normalize workflow lists and direct phase3 raw result documents.

    The caller resolves Phase2-4 handoff wrappers before invoking this function.
    """
    if isinstance(raw_results, list):
        return raw_results
    if not isinstance(raw_results, dict):
        return []
    dimension = str(raw_results.get("dimension", ""))
    evaluations = raw_results.get("evaluations")
    if not dimension or not isinstance(evaluations, list):
        return []
    normalized: list[dict[str, Any]] = []
    for evaluation in evaluations:
        if not isinstance(evaluation, dict):
            continue
        normalized.append({
            "dimension": dimension,
            "skill": str(evaluation.get("skill", "")),
            "units": [{
                "tab": str(evaluation.get("tab", "全部")),
                "rating": str(evaluation.get("rating", "")),
                "reason": str(evaluation.get("reason", "")),
                "weightedScore": evaluation.get("weightedScore"),
                "details": evaluation.get("details") or {},
            }],
        })
    return normalized


def infer_advice(metric_code: str, evidence: list[dict[str, Any]]) -> tuple[str, str]:
    """Return evidence-led root cause and action; never use a generic recommendation."""
    text = " ".join(str(item.get("description", "")) for item in evidence).lower()
    if metric_code == "information_redundancy" or "重复" in text or "冗余" in text:
        return (
            "标题、基础信息或营销字段由同一源字段重复透传，缺少跨分区的语义去重；同一决策信息在不同信息层重复出现。",
            "建立标题—基础信息字段去重规则：标题仅保留商品/服务主体与必要规格，基础信息仅补充标题未表达的参数；同一规格（如度数、容量、麦汁浓度）只保留一个展示位。",
        )
    if metric_code in {"supply_completeness", "supply_quality"} or "缺失" in text or "截断" in text:
        return (
            "同类卡片的字段拼装或兜底逻辑不一致，部分卡未补齐销量、配送时效或关键决策字段。",
            "为该卡型定义必备字段清单与缺字段兜底：统一校验标题、价格、销量/评价、履约时效等字段；字段为空时降级布局或补充默认表达，避免同类卡信息基线不一致。",
        )
    if metric_code == "information_hierarchy" or "层级" in text or "主次" in text:
        return (
            "价格、权益、营销标签等同时承担高强调样式，视觉权重缺少唯一主信息，导致阅读优先级竞争。",
            "明确价格区层级：核心价格保留唯一一级强调，优惠/权益降为二级，原价与说明降为三级；限制同一区域高强调标签数量并统一样式 token。",
        )
    if metric_code == "information_partitioning" or "边界" in text or "分区" in text:
        return (
            "相邻信息区缺少稳定的留白、容器或色块边界，内容连续堆叠导致用户难以识别分组关系。",
            "按信息任务重划分区：在基础信息、价格、权益/下挂之间建立一致的间距层级或分隔方式；组件模板固定各区块的起止边界，避免字段跨区混排。",
        )
    if metric_code == "color_logic" or "颜色" in text or "色彩" in text:
        return (
            "同一组件内强调色用途未收敛，不同业务标签、价格与运营信息竞争注意力。",
            "收敛语义色：仅保留价格、履约/状态和权益等预定义强调色；同类标签使用同一色系，非关键营销信息降为中性色。",
        )
    if metric_code in {"element_complexity", "element_compliance"} or "样式" in text or "icon" in text:
        return (
            "标签与图标样式由多套配置叠加，缺少卡片级样式数量和形态约束。",
            "建立标签/icon 白名单与数量上限：合并语义相近标签，优先复用标准胶囊和图标；在组件配置侧限制异色、异形标签的并存数量。",
        )
    if metric_code == "info_authenticity" or "歧义" in text or "误导" in text:
        return (
            "当前文案或信息表达缺少明确的业务语义约束，用户无法从可见内容确认真实含义。",
            "回收模糊或可能误导的文案配置，补齐明确的条件、对象与价格/权益口径；对高风险表达建立上线前文案校验。",
        )
    return (
        "同类卡片在当前指标上的实现存在不一致，需结合问题元素确认具体字段与样式来源。",
        "针对命中的卡片、字段和样式配置建立专项排查清单；改造后使用同批搜索词复测，并以问题卡片率验证效果。",
    )


def load_skill_weights(project: Path) -> dict[tuple[str, str], dict[str, float]]:
    """Read scoring weights from skill frontmatter; reports never invent them."""
    weights: dict[tuple[str, str], dict[str, float]] = {}
    for dimension, directory in {
        "phase3-single_element-eval": project / "phase3-single_element-eval" / "eval-skills",
        "phase3-card_or_component-eval": project / "phase3-card_or_component-eval" / "eval-skills",
        "phase3-page_framework-eval": project / "phase3-page_framework-eval" / "eval-skills",
    }.items():
        for skill_file in directory.glob("eval-*/SKILL.md"):
            match = re.search(r"^weight:\s*(\{[^\n]+\})", skill_file.read_text(encoding="utf-8"), re.MULTILINE)
            if not match:
                continue
            try:
                raw = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            weights[(dimension, skill_file.parent.name)] = {str(key): float(value) for key, value in raw.items()}
    return weights


def score_business_codes(
    level: str,
    detail: dict[str, Any],
    issues: list[Any],
    classifications: dict[str, dict[str, str]],
    element_cards: dict[str, str],
) -> set[str]:
    """Resolve score ownership without copying a component result to unrelated businesses."""
    visible = {
        item["businessCode"]
        for item in classifications.values()
        if item.get("scope") == "business"
    }
    if level == "page":
        return visible

    card_ids: set[str] = set()
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        element_id = str(issue.get("elementId", ""))
        card_ids.add(element_cards.get(element_id, str(issue.get("component", ""))))
    evidence = detail.get("evidence") or {}
    for row in evidence.get("assessmentRows") or []:
        if not isinstance(row, dict):
            continue
        for key in ("cardId", "component", "componentId"):
            value = str(row.get(key, ""))
            if value:
                card_ids.add(value)
        for member in row.get("members") or []:
            card_ids.add(str(member))

    resolved = {
        classifications[card_id]["businessCode"]
        for card_id in card_ids
        if classifications.get(card_id, {}).get("scope") == "business"
    }
    # A single-business page does not need a card-level fallback to preserve its score.
    return resolved or (visible if len(visible) == 1 else set())


def collect(project: Path, artifact_dir: Path) -> dict[str, Any]:
    skill_weights = load_skill_weights(project)
    manifests: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in (project / "screenshots-out").glob("elements_*.json"):
        data = read_json(path)
        # recognition-audit files share the `elements_` prefix but are not manifests.
        # Only select a document with the required Phase2 card payload, otherwise a
        # newer audit can shadow the actual screenshot declaration for a query.
        if isinstance(data, dict) and isinstance(data.get("query"), str) and isinstance(data.get("cards"), list):
            current = manifests.get(data["query"])
            if current is None or path.stat().st_mtime > current[0].stat().st_mtime:
                manifests[data["query"]] = (path, data)

    classifications: dict[str, dict[str, dict[str, str]]] = {}
    element_cards: dict[str, dict[str, str]] = {}
    element_labels: dict[str, dict[str, str]] = {}
    for query, (_, manifest) in manifests.items():
        classifications[query] = {}
        element_cards[query] = {}
        element_labels[query] = {}
        for card in manifest.get("cards", []):
            card_id = str(card.get("cardId", ""))
            classifications[query][card_id] = classify_card(card)
            for region in card.get("regions", []):
                for element in region.get("elements", []):
                    element_id = str(element.get("id", ""))
                    element_cards[query][element_id] = card_id
                    element_labels[query][element_id] = humanize_element_label(element)

    stats: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    query_details: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unknown: list[dict[str, str]] = []
    # Phase3 results are retained under each query's isolated phase3 directory.
    # Discover recursively, then select one combined result per query so compatibility
    # aliases or per-dimension fallback files do not double-count a query.
    candidates_by_query: dict[str, list[Path]] = defaultdict(list)
    # 各词独立执行会保留不同命名的最终合并结果；优先消费已经通过
    # Phase4 回写的 all-results，确保治理看板引用的是最终证据路径而非 Phase3 初稿。
    for pattern in (".eval_results_*.json", "评测原始结果_*.json", "*all-results*.json"):
        for path in artifact_dir.rglob(pattern):
            query = query_from_result(path)
            if query not in manifests:
                # Some retained historical-compatible paths use directory suffixes
                # such as `库迪_results` or filename suffixes such as `_dual`.
                # Resolve them only when a known manifest query is an unambiguous
                # result filename prefix; this preserves batch isolation.
                filename_matches = [
                    candidate for candidate in manifests
                    if path.name.startswith(f"评测原始结果_{candidate}_")
                    or path.name.startswith(f".eval_results_{candidate}_")
                ]
                query = max(filename_matches, key=len) if filename_matches else None
            if query:
                candidates_by_query[query].append(path)

    result_paths: list[Path] = []
    for query, candidates in candidates_by_query.items():
        # A verified recheck supersedes the initial result for the same query;
        # otherwise prefer a combined (all-skill) document over partial files.
        rechecks = [path for path in candidates if "phase3-recheck" in path.parts]
        # all-results 是 Phase4 回写后的最终交接文件，优先级高于初始 Phase3 原始结果。
        finalized = [path for path in (rechecks or candidates) if "all-results" in path.name]
        combined = [path for path in (finalized or rechecks or candidates) if "card_or_component_page_framework" in path.name]
        pool = combined or finalized or rechecks or candidates
        result_paths.append(max(pool, key=lambda path: path.stat().st_mtime))

    used_queries: set[str] = set()
    for result_path in sorted(result_paths):
        query = query_from_result(result_path)
        if query not in manifests:
            filename_matches = [
                candidate for candidate in manifests
                if result_path.name.startswith(f"评测原始结果_{candidate}_")
                or result_path.name.startswith(f".eval_results_{candidate}_")
            ]
            query = max(filename_matches, key=len) if filename_matches else None
        if not query:
            continue
        raw_results = read_json(result_path)
        # 每词子任务会额外保留一个 all-results 交接包装文件。它只保存
        # 已验收的原始结果路径和摘要，需在这里解引用，不能把它误当空结果跳过。
        if isinstance(raw_results, dict):
            handoff_path = raw_results.get("resultFile") or raw_results.get("results")
            if isinstance(handoff_path, str) and handoff_path:
                referenced = read_json(Path(handoff_path))
                if referenced is not None:
                    raw_results = referenced
        results = normalize_results(raw_results)
        if not results:
            continue
        used_queries.add(query)
        manifest_path, manifest = manifests[query]
        annotated = str(manifest.get("annotatedImage", ""))
        screenshot = str(manifest.get("screenshot", ""))
        for result in results:
            if not isinstance(result, dict):
                continue
            dimension = str(result.get("dimension", ""))
            skill = str(result.get("skill", ""))
            level_name, level_code, _ = LEVELS.get(dimension, ("其他维度", "other", "#64748b"))
            metric_name, metric_code = METRICS.get(skill, (skill, skill))
            for unit in result.get("units", []):
                if not isinstance(unit, dict):
                    continue
                tab = str(unit.get("tab", "全部"))
                detail = unit.get("details") or {}
                issues = detail.get("issues") or []
                query_details[query].append({
                    "level": level_code, "levelName": level_name, "skill": skill,
                    "metricName": metric_name, "metricCode": metric_code, "tab": tab,
                    "rating": str(unit.get("rating", "")), "reason": str(unit.get("reason", "")),
                    "weightedScore": unit.get("weightedScore"),
                    "weight": skill_weights.get((dimension, skill), {}),
                    "assessmentRows": (detail.get("evidence") or {}).get("assessmentRows") or [],
                    "criterion": str(detail.get("criterion", "")), "evidenceMode": str(detail.get("evidenceMode", "")),
                "summary": str(detail.get("summary", "")), "issues": issues,
                # 轻量 Phase2 不再要求整页标注图。原图来自统一清单；问题图来自 issue.evidenceImage。
                "screenshot": str(detail.get("screenshot") or screenshot), "annotatedImage": annotated,

                })
                # 看板的待优化对象包含“达标”和“不达标”：只有“优秀”不进入问题治理。
                # 若上游仅给出评测项级达标、未提供逐元素 issues，则保留为无坐标的
                # 评测项级待优化项，不能虚构成某张卡的红框问题。
                problem_issues = [
                    issue for issue in issues
                    if isinstance(issue, dict) and str(issue.get("rating", unit.get("rating", ""))) in {"达标", "不达标", "🟡", "🔴"}
                ]
                if not problem_issues and str(unit.get("rating", "")) in {"达标", "不达标", "🟡", "🔴"}:
                    problem_issues = [{
                        "rating": str(unit.get("rating", "")),
                        "description": str(unit.get("reason", "")) or str(detail.get("summary", "")),
                        "dimension": metric_name,
                        "component": "",
                        "elementId": "",
                        "coord": [],
                        "evidenceImage": "",
                        "isAssessmentLevel": True,
                    }]
                for issue in problem_issues:
                    element_id = str(issue.get("elementId", ""))
                    element_label = element_labels[query].get(element_id, humanize_issue_element(issue))
                    card_id = element_cards[query].get(element_id, str(issue.get("component", "")))
                    classification = classifications[query].get(card_id)
                    # 页面框架是评测维度而非业务线。页面级达标/不达标结论按同一截图
                    # 中可见业务归属，写入各业务 Tab 的问题明细；同一业务每页仅保留一份，
                    # 不创建“页面框架”业务 Tab，也不在“全部”页签展示问题明细。
                    if level_code == "page" or issue.get("isAssessmentLevel"):
                        visible_businesses = {
                            item["businessCode"]: item
                            for item in classifications[query].values()
                            if item["scope"] == "business"
                        }
                        target_classifications = [
                            {
                                **item, "cardTypeCode": "page",
                                "cardTypeName": "页面级结论",
                            }
                            for item in visible_businesses.values()
                        ]
                        card_id = f"page:{query}"
                    elif classification and classification["scope"] == "business":
                        target_classifications = [classification]
                    elif level_code == "element":
                        target_classifications = [
                            item for item in classifications[query].values()
                            if item["scope"] == "business"
                        ]
                    else:
                        unknown.append({"query": query, "cardId": card_id, "reason": "平台、混合或无法确认业务归属"})
                        continue
                    if not target_classifications:
                        unknown.append({"query": query, "cardId": card_id, "reason": "未找到可归属的业务卡"})
                        continue
                    finding = issue_code(skill, issue)
                    for target in target_classifications:
                        target_card_id = card_id if classification else f"{level_code}:{query}"
                        # 治理优先级的唯一统计单元：业务线 + 维度 + 指标；卡型只保留为
                        # 覆盖范围元数据，不能将同一指标拆成多个优先级票池。
                        key = (target["businessCode"], metric_code, level_code)
                        group = stats.setdefault(key, {
                            **target, "metricCode": metric_code, "metricName": metric_name,
                            "level": level_code, "levelName": level_name, "issues": [], "problemCards": set(),
                            "evaluatedCards": set(), "queries": set(), "findingCounts": Counter(),
                            "cardTypeCodes": set(), "voteCountedSignatures": set(),
                            "failVoteCount": 0, "passVoteCount": 0,
                        })
                        group["cardTypeCodes"].add(target["cardTypeCode"])
                        evidence = {"query": query, "tab": tab, "cardId": target_card_id, "elementId": element_id,
                                    "elementLabel": element_label,
                                    "rating": str(issue.get("rating", unit.get("rating", ""))),
                                    "priority": str(issue.get("priority", "待判定")),
                                    "priorityReason": str(issue.get("priorityReason", "")),
                                    "assessmentLevel": bool(issue.get("isAssessmentLevel", False)),
                                    "description": issue_description(issue, str(unit.get("reason", "")) or str(detail.get("summary", ""))),
                                    "finding": issue_finding(issue),
                                    "recommendation": str(issue.get("recommendation", "")),
                                    "dimension": str(issue.get("dimension", metric_name)),
                                    "component": str(issue.get("component", "")), "annotatedImage": annotated,
                                    "screenshot": str(detail.get("screenshot") or screenshot), "coord": issue.get("coord", []),
                    "evidenceImage": str(issue.get("evidenceImage", ""))}
                        signature = (query, tab, target_card_id, metric_code, finding)
                        if not any(item["signature"] == signature for item in group["issues"]):
                            group["issues"].append({"signature": signature, **evidence})
                        if signature not in group["voteCountedSignatures"]:
                            vote_rating = str(issue.get("rating", unit.get("rating", "")))
                            if vote_rating in FAIL_RATINGS:
                                group["failVoteCount"] += 1
                            elif vote_rating in PASS_RATINGS:
                                group["passVoteCount"] += 1
                            group["voteCountedSignatures"].add(signature)
                        group["problemCards"].add((query, tab, target_card_id))
                        group["queries"].add(query)
                        group["findingCounts"][finding] += 1

    # Add denominators per business/card-type/metric based on all classified cards.
    for query, cards in classifications.items():
        if query not in used_queries:
            continue
        for card_id, classification in cards.items():
            if classification["scope"] != "business":
                continue
            for key, group in stats.items():
                if key[0] == classification["businessCode"] and classification["cardTypeCode"] in group["cardTypeCodes"]:
                    group["evaluatedCards"].add((query, "全部", card_id))

    groups = []
    for group in stats.values():
        denominator = len(group["evaluatedCards"])
        problems = len(group["problemCards"])
        rate = round(problems / denominator * 100, 1) if denominator else 0
        group["evaluatedCardCount"] = denominator
        group["problemCardCount"] = problems
        group["problemRate"] = rate
        group["queryCount"] = len(group["queries"])
        group["findingDistribution"] = [{"code": code, "count": count} for code, count in group["findingCounts"].most_common()]
        priority = priority_from_vote_counts(group["failVoteCount"], group["passVoteCount"])
        if priority is None:
            raise ValueError("待优化治理分组缺少达标/不达标票，无法计算优先级")
        group["priority"] = priority
        group["priorityReason"] = priority_reason_from_vote_counts(
            group["failVoteCount"], group["passVoteCount"], priority
        )
        group["evidence"] = [{
            **{k: v for k, v in item.items() if k != "signature"},
            "priority": priority,
            "priorityReason": group["priorityReason"],
        } for item in group["issues"]]
        group["rootCause"], group["recommendation"] = infer_advice(group["metricCode"], group["evidence"])
        group["problemCardRefs"] = sorted("|".join(item) for item in group["problemCards"])
        group["evaluatedCardRefs"] = sorted("|".join(item) for item in group["evaluatedCards"])
        for key in ("issues", "problemCards", "evaluatedCards", "queries", "findingCounts", "cardTypeCodes", "voteCountedSignatures"):
            group.pop(key, None)
        groups.append(group)
    groups.sort(key=lambda item: ({"P0": 0, "P1": 1, "P2": 2, "待判定": 3}.get(item["priority"], 4), -item["problemRate"], -item["problemCardCount"]))

    # Keep all three evaluation levels visible in the per-query review. If a
    # selected batch misses one level, show an explicit non-evaluated status
    # rather than silently omitting that level or fabricating a rating.
    for query in sorted(used_queries):
        units = query_details[query]
        if not any(unit["level"] == "page" for unit in units):
            units.append({
                "level": "page", "levelName": "页面框架维度", "skill": "",
                "metricName": "页面框架维度评测", "metricCode": "page_framework_pending",
                "tab": "全部", "rating": "未执行", "reason": "本批次过程评测结果未包含页面框架维度，暂无可复核的页面级结论。",
                "criterion": "未执行，不适用评级规则。", "evidenceMode": "",
                "summary": "请补跑 phase3-page_framework-eval 后重新生成看板；不会将缺失结果误标为优秀或不达标。",
                "issues": [], "annotatedImage": "",
            })

    business_summary: dict[str, dict[str, Any]] = {}
    for group in groups:
        # 页面框架是评测层级，不能成为业务线；页面级问题只用于独立问题展示。
        if group["businessCode"] == "page_framework":
            continue
        item = business_summary.setdefault(group["businessCode"], {
            "businessCode": group["businessCode"], "businessName": group["businessName"], "issueCount": 0,
            "problemCards": set(), "evaluatedCards": set(), "componentProblemCards": set(), "componentEvaluatedCards": set(), "lowMetrics": 0, "levelScores": defaultdict(list),
        })
        item["issueCount"] += group["problemCardCount"]
        item["problemCards"].update(group["problemCardRefs"])
        item["evaluatedCards"].update(group["evaluatedCardRefs"])
        if group["level"] == "component":
            item["componentProblemCards"].update(group["problemCardRefs"])
            item["componentEvaluatedCards"].update(group["evaluatedCardRefs"])
    # 即使某业务没有待优化问题，只要当前批次存在可见业务卡，也要保留业务 Tab 与评分。
    for query in used_queries:
        for classification in classifications.get(query, {}).values():
            if classification["scope"] != "business":
                continue
            business_summary.setdefault(classification["businessCode"], {
                "businessCode": classification["businessCode"], "businessName": classification["businessName"], "issueCount": 0,
                "problemCards": set(), "evaluatedCards": set(), "componentProblemCards": set(), "componentEvaluatedCards": set(), "levelScores": defaultdict(list),
            })

    # 按 Skill frontmatter 的 weight 确定性汇总：先累计实际原始分及同批已执行项的理论 min/max，
    # 再归一化；不再以问题卡片率或评级映射在报告层重算。
    business_dimension_totals: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: {"raw": 0.0, "min": 0.0, "max": 0.0, "count": 0.0}))
    for query, units in query_details.items():
        for unit in units:
            weight = unit.get("weight") or {}
            rating = unit.get("rating")
            if unit["level"] not in {"element", "component", "page"} or rating not in weight:
                continue
            values = [float(value) for value in weight.values()]
            if not values:
                continue
            score_businesses = score_business_codes(
                unit["level"],
                {"evidence": {"assessmentRows": unit.get("assessmentRows") or []}},
                unit.get("issues") or [],
                classifications.get(query, {}),
                element_cards.get(query, {}),
            )
            for business_code in score_businesses:
                bucket = business_dimension_totals[business_code][unit["level"]]
                # 原始分严格取当前 SKILL.md 的 rating 权重；历史产物的 weightedScore
                # 只作审计留存，避免旧产物沿用被修订前的权重。
                bucket["raw"] += float(weight[rating])
                bucket["min"] += min(values)
                bucket["max"] += max(values)
                bucket["count"] += 1

    business_rows = []
    for item in business_summary.values():
        total, problems = len(item["evaluatedCards"]), len(item["problemCards"])
        dimension_scores = {}
        dimension_breakdown = {}
        for level, totals in business_dimension_totals.get(item["businessCode"], {}).items():
            span = totals["max"] - totals["min"]
            normalized = round((totals["raw"] - totals["min"]) / span * 100, 1) if span else 0.0
            dimension_scores[level] = normalized
            dimension_breakdown[level] = {"raw": totals["raw"], "min": totals["min"], "max": totals["max"], "executedSkills": int(totals["count"])}
        overall_score = round(sum(dimension_scores.values()) / len(dimension_scores), 1) if dimension_scores else 0.0
        business_rows.append({
            **{k: v for k, v in item.items() if k not in {"problemCards", "evaluatedCards", "componentProblemCards", "componentEvaluatedCards", "levelScores"}},
            "evaluatedCards": total, "problemCards": problems,
            "problemRate": round(problems / total * 100, 1) if total else 0,
            # 分数严格来自 Skill weight： (实际原始分 - 理论最低分) / (理论最高分 - 理论最低分) × 100。
            "dimensionScores": dimension_scores, "dimensionBreakdown": dimension_breakdown, "overallScore": overall_score,
        })
    business_rows.sort(key=lambda item: (item["overallScore"], -item["issueCount"]))
    return {"generatedAt": str(date.today()), "queryCount": len(used_queries), "groups": groups, "businesses": business_rows, "queryDetails": dict(sorted(query_details.items())), "unknown": unknown, "manifests": len(manifests)}


def validate_dataset(data: dict[str, Any], artifact_dir: Path, expected_business_tabs: set[str]) -> None:
    """Fail early when a dashboard would silently mix batches or lose audit evidence."""
    if not data["queryCount"]:
        raise ValueError(f"未从评测产物读取到有效搜索词：{artifact_dir}")
    if data["queryCount"] != len(data["queryDetails"]):
        raise ValueError("搜索词计数与逐词详情不一致，停止生成以避免交付不完整看板")
    for query, units in data["queryDetails"].items():
        if not units:
            raise ValueError(f"搜索词 {query} 没有评测明细")
        for unit in units:
            if unit.get("rating") != "未执行" and not unit.get("screenshot"):
                raise ValueError(f"搜索词 {query} 缺少统一元素清单声明的原图路径")
            for issue in unit.get("issues", []):
                # 页面/关系型结论可能为追溯保留元素坐标，但未有经 Phase2 确认的
                # 局部边界时只展示原图，不能强制生成伪红框。
                needs_local_evidence = unit.get("evidenceMode") in {"annotated-region", "hybrid"}
                if isinstance(issue, dict) and needs_local_evidence and issue.get("coord") and str(issue.get("rating", "")) in {"达标", "不达标", "🟡", "🔴"} and not issue.get("evidenceImage"):
                    raise ValueError(f"搜索词 {query} 的带坐标待优化元素/组件问题缺少 Phase4 整页红框证据图")
    allowed_codes = set(EXPECTED_REPORT_BUSINESS_TABS)
    actual_businesses = {item.get("businessCode"): item for item in data["businesses"]}
    unexpected_codes = sorted(set(actual_businesses) - allowed_codes)
    if unexpected_codes:
        raise ValueError(f"报告业务Tab不满足预期口径，发现未允许业务：{','.join(unexpected_codes)}")
    missing_codes = sorted(expected_business_tabs - set(actual_businesses))
    extra_codes = sorted(set(actual_businesses) - expected_business_tabs)
    if missing_codes or extra_codes:
        raise ValueError(
            "报告业务Tab不满足本批次预期："
            f"缺失={','.join(missing_codes) or '无'}；多出={','.join(extra_codes) or '无'}"
        )
    mismatched_names = sorted(
        code for code, item in actual_businesses.items()
        if item.get("businessName") != EXPECTED_REPORT_BUSINESS_TABS[code]
    )
    if mismatched_names:
        raise ValueError(f"报告业务Tab名称不满足预期口径：{','.join(mismatched_names)}")
    valid_queries = set(data["queryDetails"])
    for group in data["groups"]:
        for evidence in group.get("evidence", []):
            if evidence.get("query") not in valid_queries:
                raise ValueError("治理卡证据引用了当前批次之外的搜索词")
            if str(evidence.get("rating", "")) in {"达标", "不达标", "🟡", "🔴"}:
                finding = evidence.get("finding") if isinstance(evidence.get("finding"), dict) else {}
                required_finding = ("observableFact", "ruleOrThreshold", "verdictReason", "userImpact")
                missing_finding = [key for key in required_finding if not str(finding.get(key, "")).strip()]
                if missing_finding:
                    raise ValueError(f"问题 {evidence.get('query')}:{evidence.get('elementId') or evidence.get('cardId')} 缺少三段式结论事实：{','.join(missing_finding)}")
                if not str(evidence.get("recommendation", "")).strip():
                    raise ValueError(f"问题 {evidence.get('query')}:{evidence.get('elementId') or evidence.get('cardId')} 缺少问题级个性化优化建议")


def esc(value: Any) -> str:
    return html.escape(str(value))


def render_finding_detail(finding: Any) -> str:
    """Render only complete structured findings; historical records retain compact output."""
    if not isinstance(finding, dict):
        return ""
    rows = [
        ("可见事实", finding.get("observableFact", "")),
        ("判定规则", finding.get("ruleOrThreshold", "")),
        ("结论依据", finding.get("verdictReason", "")),
        ("用户影响", finding.get("userImpact", "")),
    ]
    populated = [(label, str(value)) for label, value in rows if str(value).strip()]
    if not populated:
        return ""
    return "<dl class='finding-detail'>" + "".join(
        "<div><dt>{label}</dt><dd>{value}</dd></div>".format(label=esc(label), value=esc(value))
        for label, value in populated
    ) + "</dl>"


def render_sankey(groups: list[dict[str, Any]], dom_id: str = "all") -> str:
    """Render one evaluation-level Sankey, ordered by volume for readable flows."""
    links = [group for group in groups if group["problemCardCount"] > 0]
    if not links:
        return "<div class='empty'>该评测维度暂无待优化项。</div>"

    palette = ["#E8C55F", "#8B7BB8", "#D99BB5", "#9BC48A", "#7BA7D4", "#E05252", "#E8834A"]
    links.sort(key=lambda item: (-item["problemCardCount"], item["businessName"], item["metricName"]))
    thicknesses = [min(22, max(7, group["problemCardCount"] * 3.5)) for group in links]
    source_totals: dict[str, float] = defaultdict(float)
    target_totals: dict[str, float] = defaultdict(float)
    for group, thickness in zip(links, thicknesses):
        source_totals[group["businessCode"]] += thickness
        target_totals[group["metricCode"]] += thickness
    business_codes = sorted(source_totals, key=lambda code: (-source_totals[code], code))
    metric_codes = sorted(target_totals, key=lambda code: (-target_totals[code], code))
    business_names = {group["businessCode"]: group["businessName"] for group in links}
    metric_names = {group["metricCode"]: group["metricName"] for group in links}
    business_colors = {code: palette[index % len(palette)] for index, code in enumerate(business_codes)}
    metric_colors = {code: palette[(index + 3) % len(palette)] for index, code in enumerate(metric_codes)}

    node_gap, node_min_height = 18, 18
    source_y: dict[str, float] = {}
    target_y: dict[str, float] = {}
    cursor = 24.0
    for code in business_codes:
        source_y[code] = cursor
        cursor += max(node_min_height, source_totals[code]) + node_gap
    source_height = cursor + 12
    cursor = 24.0
    for code in metric_codes:
        target_y[code] = cursor
        cursor += max(node_min_height, target_totals[code]) + node_gap
    height = int(max(source_height, cursor + 12))
    source_offsets: dict[str, float] = defaultdict(float)
    target_offsets: dict[str, float] = defaultdict(float)
    gradients, ribbons = [], []
    for index, (group, thickness) in enumerate(zip(links, thicknesses)):
        source, target = group["businessCode"], group["metricCode"]
        sy = source_y[source] + source_offsets[source]
        ty = target_y[target] + target_offsets[target]
        source_offsets[source] += thickness
        target_offsets[target] += thickness
        gradient_id = f"flow-{dom_id}-{index}"
        gradients.append("<linearGradient id='{id}' x1='0%' y1='0%' x2='100%' y2='0%'><stop offset='0%' stop-color='{source}' stop-opacity='.50'/><stop offset='100%' stop-color='{target}' stop-opacity='.42'/></linearGradient>".format(id=gradient_id, source=business_colors[source], target=metric_colors[target]))
        tooltip = "{business} → {metric}&#10;待优化卡数量：{count} 张&#10;待优化率：{rate}%".format(business=esc(group["businessName"]), metric=esc(group["metricName"]), count=group["problemCardCount"], rate=group["problemRate"])
        ribbons.append("<path class='sankey-link' tabindex='0' data-tooltip='{tooltip}' d='M 250 {sy:.1f} C 415 {sy:.1f}, 545 {ty:.1f}, 710 {ty:.1f} L 710 {ty2:.1f} C 545 {ty2:.1f}, 415 {sy2:.1f}, 250 {sy2:.1f} Z' fill='url(#{id})'></path>".format(id=gradient_id, tooltip=tooltip, sy=sy, sy2=sy + thickness, ty=ty, ty2=ty + thickness))
    business_nodes = "".join("<g><text class='sankey-label source-label' x='238' y='{label}'>{name}</text><rect x='240' y='{y}' width='10' height='{height:.1f}' fill='{color}'/></g>".format(y=y, height=max(node_min_height, source_totals[code]), label=y + max(node_min_height, source_totals[code]) / 2 + 4, name=esc(business_names[code]), color=business_colors[code]) for code, y in source_y.items())
    metric_nodes = "".join("<g><rect x='710' y='{y}' width='10' height='{height:.1f}' fill='{color}'/><text class='sankey-label target-label' x='732' y='{label}'>{name}</text></g>".format(y=y, height=max(node_min_height, target_totals[code]), label=y + max(node_min_height, target_totals[code]) / 2 + 4, name=esc(metric_names[code]), color=metric_colors[code]) for code, y in target_y.items())
    return "<div class='sankey-wrap'><svg class='sankey' viewBox='0 0 960 {height}' role='img' aria-label='业务线到待优化指标的卡片数量关联图'><defs>{gradients}</defs>{links}{business}{metric}</svg><div class='sankey-tooltip' role='tooltip' aria-hidden='true'></div></div>".format(height=height, gradients="".join(gradients), links="".join(ribbons), business=business_nodes, metric=metric_nodes)


def render_dimension_sankeys(groups: list[dict[str, Any]]) -> str:
    """Separate heterogeneous evaluation levels instead of mixing their metrics."""
    dimensions = [
        ("element", "单一元素", "element"),
        ("component", "组件/卡片", "component"),
        ("page", "页面框架", "page"),
    ]
    tabs = "".join(
        "<button class='sankey-tab {active}' data-sankey-tab='{code}' onclick=\"activateSankey('{code}')\">{name}</button>".format(
            code=code, name=name, active="active" if index == 0 else ""
        )
        for index, (code, name, _) in enumerate(dimensions)
    )
    panes = "".join(
        "<section class='sankey-pane {active}' data-sankey-pane='{code}'><p class='sankey-note'>仅呈现{title}内的「业务 × 指标」关联；节点与连线按待优化卡数量从高到低排列。</p>{chart}</section>".format(
            code=code, title=name, active="active" if index == 0 else "",
            chart=render_sankey([group for group in groups if group.get("level") == code], code),
        )
        for index, (code, name, _) in enumerate(dimensions)
    )
    return "<div class='sankey-tabs' role='tablist' aria-label='评测维度'>{tabs}</div>{panes}".format(tabs=tabs, panes=panes)


def render(data: dict[str, Any]) -> str:
    """Render the canonical GOVERNANCE_DASHBOARD_V1 dashboard.

    This is the sole production renderer. Update this function together with the
    Phase5 visual contract when a new approved layout supersedes the current one.
    """
    return render_dashboard(data)

    # Legacy implementation is retained below for historical audit only. It is
    # intentionally unreachable: the Phase5 renderer above is the sole output.
    def score_cell(row: dict[str, Any], level: str) -> str:
        score = row.get("dimensionScores", {}).get(level)
        return "<span class='score-cell muted'>—</span>" if score is None else "<span class='score-cell'>{:.1f}</span>".format(score)

    def issue_position(issue: dict[str, Any]) -> str:
        component = str(issue.get("component", "")).strip()
        card_id = str(issue.get("cardId", "")).strip()
        element_id = str(issue.get("elementId", "")).strip()
        if component:
            return component
        if card_id and element_id:
            return f"{card_id} · {element_id}"
        return card_id or element_id or "页面区域"

    def concise_metric_name(metric_name: str) -> str:
        """移除指标名中的补充括号说明，保留评测主体名称。"""
        return re.sub(r"（[^）]*）|\\([^)]*\\)", "", metric_name).strip()

    def rating_class(rating: str) -> str:
        return "fail" if rating in {"不达标", "🔴"} else "pass"

    problem_ratings = {"达标", "不达标", "🟡", "🔴"}
    screenshot_entries: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for query, units in data.get("queryDetails", {}).items():
        for unit in units:
            problem_issues = [
                issue for issue in unit.get("issues", [])
                if isinstance(issue, dict) and str(issue.get("rating", unit.get("rating", ""))) in problem_ratings
            ]
            if not problem_issues and str(unit.get("rating", "")) in problem_ratings:
                problem_issues = [{
                    "rating": unit["rating"], "description": unit.get("reason") or unit.get("summary", ""),
                    "cardId": "页面级结论", "elementId": "无唯一坐标", "coord": [],
                    "evidenceImage": "", "screenshot": unit.get("screenshot", ""),
                }]
            for issue in problem_issues:
                source = str(issue.get("evidenceImage") or issue.get("screenshot") or unit.get("screenshot") or "")
                key = (query, str(unit.get("tab", "全部")), source)
                screenshot_entries[key].append({
                    **issue, "query": query, "tab": unit.get("tab", "全部"),
                    "metricName": unit.get("metricName", ""), "level": unit.get("level", ""),
                    "levelName": unit.get("levelName", ""), "reason": unit.get("reason", ""),
                })

    screenshot_anchor_by_key: dict[tuple[str, str, str], str] = {}
    screenshot_summary_by_query: dict[str, list[str]] = defaultdict(list)
    for index, (key, entries) in enumerate(screenshot_entries.items()):
        query, tab, source = key
        anchor = f"screenshot-issue-{index}"
        screenshot_anchor_by_key[key] = anchor
        has_red_boxes = any(item.get("evidenceImage") for item in entries)
        label = "整页红框证据图" if has_red_boxes else "原始截图（页面级结论，无元素级红框）"
        image = (
            "<a class='issue-image-link' href='file://{path}' target='_blank' rel='noopener' title='点击查看原尺寸证据图'>"
            "<img loading='lazy' src='file://{path}' alt='{label}'></a>"
        ).format(path=esc(source), label=esc(label)) if source else "<span class='evidence-empty'>无元素级证据</span>"
        issue_list = "".join(
            "<article class='screenshot-issue-item'><span class='level {level}'>{level_name}</span> <b>{metric}</b> · <span class='rating'>{rating}</span><br>"
            "<b>位置：</b>{position}<br>{description}</article>".format(
                level=esc(str(item.get("level", ""))), level_name=esc(str(item.get("levelName", "评测项"))),
                metric=esc(str(item.get("metricName", ""))), rating=esc(str(item.get("rating", "待优化"))),
                position=esc(issue_position(item)), description=esc(str(item.get("description", "")) or str(item.get("reason", ""))),
            ) for item in entries
        )
        screenshot_summary_by_query[query].append(
            "<article class='screenshot-issue-card' id='{anchor}'><div class='screenshot-evidence'>{image}</div>"
            "<div class='screenshot-issue-content'><p class='issue-meta'><b>{tab} Tab</b> · {label} · 汇总 {count} 条待优化结论</p>"
            "<div class='screenshot-issue-items'>{issues}</div></div></article>".format(
                anchor=esc(anchor), image=image, tab=esc(tab), label=esc(label), count=len(entries), issues=issue_list
            )
        )

    # 页面框架是评测维度而非业务线：其问题已按截图内可见业务归入对应业务 Tab；“全部”只展示总览。
    business_rows_data = [row for row in data["businesses"] if row["businessCode"] != "page_framework"]
    business_rows = "".join(
        "<tr><td><b>{business}</b></td><td>{element}</td><td>{component}</td><td>{page}</td>"
        "<td><span class='overall-score'>{overall:.1f}</span></td><td><span class='rate'>{rate:.1f}%</span> <small>{problems} / {evaluated} 张</small></td>"
        "<td><button onclick=\"activateBusiness('{code}')\">查看问题</button></td></tr>".format(
            business=esc(row["businessName"]), element=score_cell(row, "element"), component=score_cell(row, "component"),
            page=score_cell(row, "page"), overall=row["overallScore"], rate=row["problemRate"], problems=row["problemCards"],
            evaluated=row["evaluatedCards"], code=esc(row["businessCode"])
        ) for row in business_rows_data
    ) or "<tr><td colspan='7' class='empty-cell'>本批次暂无可归属业务的评测结果。</td></tr>"

    groups_by_business: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in data["groups"]:
        groups_by_business[group["businessCode"]].append(group)

    def render_issue_rows(groups: list[dict[str, Any]]) -> tuple[str, Counter[str]]:
        severity_counts: Counter[str] = Counter()
        issues_by_screenshot: dict[tuple[str, str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
        for group in groups:
            for issue in group["evidence"]:
                severity_counts[group["priority"]] += 1
                screenshot = str(issue.get("screenshot") or issue.get("evidenceImage") or "")
                key = (str(issue.get("query", "")), str(issue.get("tab", "全部")), screenshot)
                issues_by_screenshot[key].append((group, issue))
        issue_rows: list[str] = []
        for (query, tab, screenshot), screenshot_issues in issues_by_screenshot.items():
            evidence_path = next((str(issue.get("evidenceImage", "")) for _, issue in screenshot_issues if issue.get("evidenceImage")), "")
            display_path = evidence_path or screenshot
            label = "整页红框证据图" if evidence_path else "原始截图（页面级结论，无元素级红框）"
            image = ("<a class='issue-image-link' href='file://{path}' target='_blank' rel='noopener' title='点击查看原尺寸证据图'><img loading='lazy' src='file://{path}' alt='{label}'></a>".format(path=esc(display_path), label=esc(label)) if display_path else "<span class='evidence-empty'>无元素级证据</span>")
            issue_items = "".join(
                "<article class='issue-item'><span class='level {level}'>{level_name}</span> <b>{metric}</b> <span class='issue-rating {rating_class}'>{rating}</span><br><b>位置：</b>{position}<br>{description}<div class='advice'><b>优化建议</b><br>{advice}</div></article>".format(
                    level=esc(group["level"]), level_name=esc(group["levelName"]), metric=esc(concise_metric_name(group["metricName"])),
                    rating_class=rating_class(str(issue.get("rating", "待优化"))), rating=esc(issue.get("rating", "待优化")),
                    position=esc(issue_position(issue)), description=esc(issue.get("description", "")) or esc(group["rootCause"]), advice=esc(group["recommendation"]),
                ) for group, issue in screenshot_issues
            )
            issue_rows.append("<article class='issue-row'><div class='issue-content'><p class='issue-meta'><b>{query}</b> · {tab} Tab · {label} · 汇总 {count} 条待优化结论</p><div class='issue-items'>{issues}</div></div><div class='issue-evidence'>{image}</div></article>".format(query=esc(query), tab=esc(tab), label=esc(label), count=len(screenshot_issues), issues=issue_items, image=image))
        return "".join(issue_rows), severity_counts

    panes = [
        "<section class='business-pane active' data-business-pane='all'><div class='overview-head'><h2>① 各业务线问题项汇总与待优化项归因建议</h2>"
        "<span class='badge'>选择业务查看归因、建议与证据</span></div><div class='table-wrap'><table><thead><tr>"
        "<th>业务线</th><th>单一元素维度得分</th><th>组件/卡片维度得分</th><th>页面框架维度得分</th>"
        "<th>总体得分</th><th>待优化率</th><th>操作</th></tr></thead><tbody>" + business_rows + "</tbody></table></div></section>"
    ]
    for business in business_rows_data:
        code = business["businessCode"]
        groups = sorted(groups_by_business.get(code, []), key=lambda group: ({"P0": 0, "P1": 1, "P2": 2, "待判定": 3}.get(group["priority"], 4), -group["problemCardCount"]))
        severity_counts = Counter()
        issues_by_screenshot: dict[tuple[str, str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
        for group in groups:
            for issue in group["evidence"]:
                severity_counts[group["priority"]] += 1
                screenshot = str(issue.get("screenshot") or issue.get("evidenceImage") or "")
                key = (str(issue.get("query", "")), str(issue.get("tab", "全部")), screenshot)
                issues_by_screenshot[key].append((group, issue))

        issue_rows: list[str] = []
        for (query, tab, screenshot), screenshot_issues in issues_by_screenshot.items():
            evidence_path = next((str(issue.get("evidenceImage", "")) for _, issue in screenshot_issues if issue.get("evidenceImage")), "")
            display_path = evidence_path or screenshot
            label = "整页红框证据图" if evidence_path else "原始截图（页面级结论，无元素级红框）"
            image = (
                "<a class='issue-image-link' href='file://{path}' target='_blank' rel='noopener' title='点击查看原尺寸证据图'>"
                "<img loading='lazy' src='file://{path}' alt='{label}'></a>"
            ).format(path=esc(display_path), label=esc(label)) if display_path else "<span class='evidence-empty'>无元素级证据</span>"
            issue_items_by_level: dict[str, list[str]] = defaultdict(list)
            for group, issue in screenshot_issues:
                issue_items_by_level[group["level"]].append(
                    "<article class='issue-item'><b>{metric}</b> <span class='issue-rating {rating_class}'>{rating}</span><br>"
                    "<b>位置：</b>{position}<br>{description}{finding_detail}"
                    "<div class='advice'><b>优化建议</b><br>{advice}</div></article>".format(
                        metric=esc(concise_metric_name(group["metricName"])),
                        rating_class=rating_class(str(issue.get("rating", "待优化"))), rating=esc(issue.get("rating", "待优化")),
                        position=esc(issue_position(issue)),
                        description=esc(issue_description(issue, group["rootCause"])),
                        finding_detail=render_finding_detail(issue.get("finding", {})),
                        advice=esc(group["recommendation"]),
                    )
                )
            issue_sections = "".join(
                "<section class='screenshot-issue-section'><span class='dimension-section-label {level}'>{title}</span><div class='issue-items'>{items}</div></section>".format(
                    level=esc(level), title=esc(title), items="".join(issue_items_by_level[level])
                )
                for level, title in (("page", "页面框架问题"), ("component", "组件/卡片问题"), ("element", "单一元素问题"))
                if issue_items_by_level[level]
            )
            issue_rows.append(
                "<article class='issue-row'><div class='issue-content'><p class='issue-meta'><b>{query}</b> · {tab} Tab · {label} · 汇总 {count} 条待优化结论</p>"
                "{issues}</div><div class='issue-evidence'>{image}</div></article>".format(
                    query=esc(query), tab=esc(tab), label=esc(label), count=len(screenshot_issues), issues=issue_sections, image=image
                )
            )
        score_items = "".join(
            "<div class='dimension-score'><span>{name}</span><b>{score:.1f}</b></div>".format(
                name=esc({"element": "单一元素", "component": "组件/卡片", "page": "页面框架"}[level]), score=score
            ) for level, score in business.get("dimensionScores", {}).items()
        ) or "<span class='muted'>暂无已执行维度得分</span>"
        panes.append(
            "<section class='business-pane' data-business-pane='{code}'><div class='business-summary'>"
            "<div class='score-overview'><span class='overview-label'>总分</span><strong class='big-score'>{overall:.1f}</strong>"
            "<div class='dimension-scores'>{scores}</div></div><div class='issue-overview'><span class='overview-label'>问题总数</span>"
            "<strong class='big-score issue-total'>{total}</strong><div class='priority-counts'><span class='priority P0'>P0 {p0}</span>"
            "<span class='priority P1'>P1 {p1}</span><span class='priority P2'>P2 {p2}</span><span class='priority pending-priority'>待判定 {pending}</span></div></div></div>"
            "<div class='issues-heading'><h2>问题明细</h2><span class='muted'>按严重程度由高到低排列；点击证据图可查看大图</span></div>"
            "<div class='issue-list'>{issues}</div></section>".format(
                code=esc(code), overall=business["overallScore"], scores=score_items, total=sum(severity_counts.values()),
                p0=severity_counts["P0"], p1=severity_counts["P1"], p2=severity_counts["P2"], pending=severity_counts["待判定"],
                issues="".join(issue_rows) or "<div class='empty'><b>暂无待优化问题</b><br>该业务在本批次已完成的评测维度中未发现待优化项；当前分数仅基于实际已执行维度计算。</div>"
            )
        )

    business_tabs = "".join("<button class='business-tab' data-business-tab='{code}' onclick=\"activateBusiness('{code}')\">{name}</button>".format(
        code=esc(row["businessCode"]), name=esc(row["businessName"])) for row in business_rows_data)
    query_detail_cards = []
    for query, units in data.get("queryDetails", {}).items():
        unit_cards = "".join("<article class='query-unit'><div class='level {level}'>{level_name}</div><h4>{metric} · {tab} Tab <span class='rating'>{rating}</span></h4><p>{reason}</p><p class='muted'>{summary}</p></article>".format(
            level=esc(unit["level"]), level_name=esc(unit["levelName"]), metric=esc(unit["metricName"]), tab=esc(unit["tab"]),
            rating=esc(unit["rating"]), reason=esc(unit["reason"]), summary=esc(unit["summary"])) for unit in units)
        query_detail_cards.append("<details class='query-group'><summary><b>{query}</b><span>{count} 个评测项</span></summary><div class='query-units'>{units}</div></details>".format(query=esc(query), count=len(units), units=unit_cards))
    rule_rows = "".join(f"<li><b>{esc(name)}</b><code>{esc(path)}</code></li>" for name, path in [("单一元素维度", "phase3-single_element-eval/eval-skills/"), ("组件/卡片维度", "phase3-card_or_component-eval/eval-skills/"), ("页面框架维度", "phase3-page_framework-eval/eval-skills/")])
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><style>
:root{{--indigo:#6366f1;--green:#10b981;--blue:#60a5fa;--ink:#172033;--muted:#64748b}}*{{box-sizing:border-box}}body{{margin:0;color:var(--ink);font:14px -apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;background:linear-gradient(135deg,#e8eaf6 0%,#ede9fe 35%,#dbeafe 68%,#e0f2fe 100%);min-height:100vh}}.wrap{{max-width:1440px;margin:auto;padding:22px 24px 56px}}.hero,.panel,article{{background:rgba(255,255,255,.9);border:1px solid rgba(255,255,255,.8);box-shadow:0 18px 40px rgba(71,85,105,.12);border-radius:24px}}.hero{{padding:18px 24px;background:linear-gradient(135deg,#f5f3ff,#eff6ff)}}.hero-row{{display:flex;align-items:center;justify-content:space-between;gap:18px}}h1{{margin:0;font-size:24px;letter-spacing:-.5px}}h2{{font-size:19px;margin:0}}h3{{margin:0}}.sub,.muted{{color:var(--muted);line-height:1.55}}.sub{{margin:5px 0 0;font-size:13px}}.tabs,.business-tabs{{display:flex;gap:8px;flex-wrap:wrap}}button{{border:1px solid #dbe4ff;background:#fff;color:#334155;padding:9px 13px;border-radius:14px;font-weight:700;cursor:pointer;transition:.2s}}button:hover{{transform:translateY(-2px);box-shadow:0 8px 18px rgba(99,102,241,.18)}}.tab.active{{background:var(--indigo);border-color:var(--indigo);color:#fff}}.view{{display:none;margin-top:18px}}.view.active{{display:block}}.panel{{padding:22px;margin-bottom:18px}}.business-tabs{{margin-bottom:18px;padding-bottom:16px;border-bottom:1px solid #e8edf8}}.business-tab.active{{background:#f59e0b;border-color:#f59e0b;color:#fff}}.business-pane{{display:none}}.business-pane.active{{display:block}}.overview-head,.issues-heading{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}}.badge{{padding:5px 9px;border-radius:999px;background:#eef2ff;color:#4f46e5;font-weight:700;font-size:12px}}.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:separate;border-spacing:0;overflow:hidden;border-radius:16px;min-width:800px}}th{{background:linear-gradient(135deg,#4338ca,#6366f1);color:#fff;text-align:left;padding:13px;font-size:13px}}td{{background:rgba(255,255,255,.74);padding:12px;border-bottom:1px solid #e8edf8}}tr:last-child td{{border-bottom:0}}.score-cell,.overall-score{{display:inline-block;min-width:50px;padding:4px 9px;border-radius:999px;text-align:center;font-weight:800;background:#eef2ff;color:#4338ca}}.overall-score{{background:#fff1f2;color:#be123c}}.score-cell.muted{{background:#f1f5f9;color:#94a3b8}}.rate{{font-weight:800;color:#dc2626}}.business-summary{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}}.score-overview,.issue-overview{{display:flex;align-items:center;gap:16px;padding:20px;border-radius:18px;border:1px solid #e0e7ff;background:linear-gradient(135deg,#f8faff,#eff6ff)}}.issue-overview{{border-color:#fde68a;background:linear-gradient(135deg,#fffdf5,#fffbeb)}}.overview-label{{font-weight:800;color:#475569}}.big-score{{float:none;color:#4338ca;font-size:34px;line-height:1}}.issue-total{{color:#dc2626}}.dimension-scores,.priority-counts{{display:flex;flex:1;gap:8px;flex-wrap:wrap}}.dimension-score{{padding:5px 8px;border-radius:10px;background:#fff;color:#475569;font-size:12px}}.dimension-score b{{color:#4338ca;margin-left:5px}}.priority{{display:inline-block;padding:4px 8px;border-radius:999px;color:#fff;font-size:12px;font-weight:800}}.priority.P0{{background:#ef4444}}.priority.P1{{background:#f59e0b}}.priority.P2{{background:#10b981}}.pending-priority{{background:#94a3b8}}.level{{display:inline-block;padding:5px 9px;border-radius:999px;color:#fff;font-size:12px;font-weight:700}}.level.element{{background:var(--indigo)}}.level.component{{background:var(--green)}}.level.page{{background:var(--blue)}}.issue-list{{display:flex;flex-direction:column;gap:12px}}.issue-row{{display:grid;grid-template-columns:minmax(0,1fr) 180px;gap:14px;padding:16px;align-items:start;transition:.2s}}.issue-row:hover{{transform:translateY(-2px)}}.issue-severity{{display:flex;gap:7px;flex-wrap:wrap}}.issue-title{{margin:0;line-height:1.6}}.issue-meta{{margin:7px 0;color:var(--muted);font-size:12px}}.advice{{margin-top:10px;padding:10px 11px;border-radius:12px;background:#eff6ff;border:1px solid #bfdbfe;color:#1e40af;line-height:1.55}}.finding-detail{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px 12px;margin:10px 0 0;padding:10px 11px;border:1px solid #e0e7ff;border-radius:12px;background:#fafaff}}.finding-detail div{{min-width:0}}.finding-detail dt{{margin:0 0 2px;color:#4f46e5;font-size:11px;font-weight:800}}.finding-detail dd{{margin:0;color:#475569;font-size:12px;line-height:1.5}}.issue-items{{margin:8px 0 0}}.issue-item{{margin-bottom:14px}}.issue-item:last-child{{margin-bottom:0}}.issue-evidence{{align-self:start}}.screenshot-issue-section{{padding:0 0 16px}}.dimension-section-label{{display:inline-block;margin:14px 0 4px;padding:5px 9px;border-radius:999px;color:#fff;font-size:12px;font-weight:800}}.dimension-section-label.page{{padding:7px 12px;border-radius:12px;background:linear-gradient(135deg,#2563eb,#60a5fa);font-size:14px;letter-spacing:.2px;box-shadow:0 5px 12px rgba(37,99,235,.22)}}.dimension-section-label.component{{padding:7px 12px;border-radius:12px;background:linear-gradient(135deg,#059669,#34d399);font-size:14px;letter-spacing:.2px;box-shadow:0 5px 12px rgba(5,150,105,.22)}}.dimension-section-label.element{{background:var(--indigo)}}.screenshot-issue-card{{display:grid;grid-template-columns:minmax(0,1fr) 180px;gap:14px;margin:12px 0;padding:14px;border:1px solid #dbeafe;border-radius:16px;background:#f8fbff;box-shadow:none}}.screenshot-evidence{{order:2;align-self:start}}.issue-image-link{{display:block;line-height:0}}.issue-image-link img{{width:170px;max-height:220px;object-fit:cover;border-radius:12px;border:1px solid #dbeafe;cursor:zoom-in;transition:.2s}}.issue-image-link:hover img{{transform:scale(1.03);box-shadow:0 8px 18px rgba(30,64,175,.24)}}.screenshot-issue-items{{margin:8px 0 0}}.screenshot-issue-item{{margin-bottom:12px}}.screenshot-issue-item:last-child{{margin-bottom:0}}.screenshot-issue-content .level{{margin-right:4px}}.evidence-empty{{display:block;padding:12px;color:var(--muted);font-size:12px;line-height:1.5;background:#f8fafc;border-radius:10px}}.query-group{{display:block;background:#fff;border:1px solid #e2e8f0;border-radius:18px;margin:12px 0;padding:0 16px}}summary{{cursor:pointer;padding:16px 0;font-weight:700}}.query-group>summary{{display:flex;justify-content:space-between;font-size:16px}}.query-group>summary span{{font-size:12px;color:var(--muted)}}.query-units{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px;padding:0 0 16px}}.query-unit{{padding:15px;border-radius:16px;background:#f8fafc;box-shadow:none;border:1px solid #e2e8f0}}.query-unit h4{{margin:10px 0 6px}}.rating{{float:right;padding:3px 7px;border-radius:999px;background:#fff1f2;color:#be123c;font-size:12px}}.issue-rating{{display:inline-block;margin-left:6px;padding:3px 7px;border-radius:999px;color:#fff;font-size:12px;font-weight:800;vertical-align:middle}}.issue-rating.pass{{background:#f59e0b}}.issue-rating.fail{{background:#ef4444}}.standard{{display:block;padding:16px;border-radius:16px;background:linear-gradient(135deg,#ede9fe,#dbeafe);text-decoration:none;color:#312e81;font-weight:700}}code{{display:block;margin-top:5px;padding:5px;background:#f8fafc;border-radius:7px;color:#475569;font-size:12px;word-break:break-all}}.empty{{padding:28px;color:var(--muted);text-align:center;background:#fff;border-radius:18px}}.empty-cell{{text-align:center;color:var(--muted)}}@media(max-width:760px){{.wrap{{padding:16px}}.hero-row,.business-summary{{grid-template-columns:1fr;flex-direction:column;align-items:stretch}}.issue-row,.screenshot-issue-card{{grid-template-columns:1fr}}.issue-image-link img{{width:130px}}.overview-head,.issues-heading{{align-items:flex-start;flex-direction:column}}}}
</style></head><body><main class='wrap'><header class='hero'><div class='hero-row'><div><h1>大搜结果页体验评测看板</h1><p class='sub'>评测批次：{esc(data['batch'])} ｜ 更新日期：{esc(data['generatedAt'])} ｜ 已接入 {data['queryCount']} 个搜索词样本</p></div><nav class='tabs'><button class='tab active' data-target='findings'>待优化项（业务维度）</button><button class='tab' data-target='details'>评测详情</button><button class='tab' data-target='rules'>评测规则</button></nav></div></header><section id='findings' class='view active'><div class='panel' id='governance-panel'><div class='business-tabs'><button class='business-tab active' data-business-tab='all' onclick=\"activateBusiness('all')\">全部</button>{business_tabs}</div>{''.join(panes)}</div></section><section id='details' class='view'><div class='panel'><div class='overview-head'><h2>评测详情</h2><span class='badge'>逐词审计</span></div>{''.join(query_detail_cards) or "<div class='empty'>暂无逐词评测详情。</div>"}</div></section><section id='rules' class='view'><div class='panel'><div class='overview-head'><h2>评测规则</h2></div><a class='standard' href='https://km.sankuai.com/collabpage/2770196684' target='_blank'>打开《搜索结果页-体验标准》</a><ul>{rule_rows}</ul></div></section></main><script>
document.querySelectorAll('.tab').forEach(button=>button.onclick=()=>{{document.querySelectorAll('.tab').forEach(item=>item.classList.remove('active'));document.querySelectorAll('.view').forEach(item=>item.classList.remove('active'));button.classList.add('active');document.getElementById(button.dataset.target).classList.add('active')}});
function activateBusiness(code){{document.querySelectorAll('.business-tab').forEach(item=>item.classList.toggle('active',item.dataset.businessTab===code));document.querySelectorAll('.business-pane').forEach(item=>item.classList.toggle('active',item.dataset.businessPane===code));if(code!=='all'){{document.getElementById('governance-panel').scrollIntoView({{behavior:'smooth',block:'start'}})}}}}
</script></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the search result experience dashboard")
    parser.add_argument("--project-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dataset-output", type=Path)
    parser.add_argument("--batch-name", help="当前隔离评测批次名；不传时使用 artifact-dir 目录名")
    parser.add_argument(
        "--expected-business-tabs", required=True,
        help="本批次预期业务 Tab 的逗号分隔 businessCode 列表；实际输出必须与其完全一致",
    )
    args = parser.parse_args()
    project = args.project_dir.resolve()
    artifact_dir = args.artifact_dir or project / ".artifacts" / "过程文件-评测结果与审计"
    output = args.output or project / "reports" / "meituan_search_experience_dashboard_五图全维度.html"
    dataset_output = args.dataset_output or project / "reports" / ".governance_dataset_五图全维度.json"
    data = collect(project, artifact_dir)
    data["batch"] = args.batch_name or artifact_dir.name
    expected_business_tabs = {
        code.strip() for code in args.expected_business_tabs.split(",") if code.strip()
    }
    if not expected_business_tabs:
        raise ValueError("--expected-business-tabs 不能为空")
    invalid_expected_codes = sorted(expected_business_tabs - set(EXPECTED_REPORT_BUSINESS_TABS))
    if invalid_expected_codes:
        raise ValueError(f"--expected-business-tabs 包含未允许的业务：{','.join(invalid_expected_codes)}")
    validate_dataset(data, artifact_dir, expected_business_tabs)
    output.parent.mkdir(parents=True, exist_ok=True)
    dataset_output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output.write_text(render(data), encoding="utf-8")
    print(json.dumps({"dashboard": str(output), "dataset": str(dataset_output), "businesses": len(data["businesses"]), "groups": len(data["groups"]), "queries": data["queryCount"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
