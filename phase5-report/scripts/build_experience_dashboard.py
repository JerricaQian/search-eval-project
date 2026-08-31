#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the cross-query, issue-centric search-result experience dashboard.

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

PHASE5_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHARED_SCRIPTS_DIR = PROJECT_ROOT / "scripts"
for module_dir in (PHASE5_DIR, SHARED_SCRIPTS_DIR):
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))
from dashboard_renderer import render_dashboard
from skill_frontmatter import load_weight

BUSINESS_LINES = {
    "dine_in": "到餐", "food_delivery": "餐饮外卖", "flash_delivery": "闪购",
    "service_retail": "服务零售", "healthcare": "医药健康", "hotel_travel": "酒店旅行",
    "xiaoxiang": "小象超市", "maoyan": "猫眼",
}
# 报告业务 Tab 的唯一允许集合。每批生成前必须校验输出业务代码与名称；
# 未被治理口径认可的分类（如已废弃的 tuangou_goods）一律阻断交付。
EXPECTED_REPORT_BUSINESS_TABS = BUSINESS_LINES.copy()
PLATFORM_SCOPES = {"宏观组件", "特殊广告卡", "运营聚合卡", "相似推荐提示"}
DEDICATED_BUSINESS_TERMS = (
    ("healthcare", ("医院", "体检", "医药", "药店", "药房", "诊所", "医疗", "门诊", "口腔", "眼科", "中医", "医美", "整形", "OTC", "处方药", "保健品", "医疗器械", "生理盐水", "快药", "布洛芬", "止痛药", "退烧药")),
    ("hotel_travel", ("酒店", "民宿", "房型", "景点", "度假", "露营", "营地", "漂流", "门票", "宾馆", "公寓", "钟点房", "跟团游", "自由行", "租车")),
    ("maoyan", ("电影", "影院", "演出", "场次", "票价", "剧场")),
    ("xiaoxiang", ("小象超市", "小象")),
)
SERVICE_RETAIL_TERMS = ("休闲娱乐", "休闲园区", "KTV", "洗浴", "美发", "美甲", "美睫", "美容院", "美容美体", "皮肤管理", "祛痘", "面部清洁", "丽人", "摄影", "婚礼", "结婚", "教育", "培训", "家政", "亲子", "儿童乐园", "剧本杀", "沉浸式探秘", "团建拓展", "按摩", "理发", "维修")
# 这些服务业态的展示文案可能同时出现“剧场/演绎”等猫眼弱提示词，
# 但其业务身份仍由更具体的服务零售语义决定。
SERVICE_RETAIL_EXCLUSIVE_TERMS = ("剧本杀", "沉浸式探秘", "足道", "足浴", "按摩", "spa")
FLASH_DELIVERY_TERMS = ("闪购", "分钟达", "即时零售", "小时达", "闪电仓", "歪马送酒")
FLASH_CATEGORY_TERMS = ("零食", "饮料", "日用百货", "卫生巾", "安睡裤", "纸巾", "粮油", "调味", "水果", "西瓜", "果切", "榴莲", "蔬菜", "黄瓜", "肉禽蛋", "水产", "生鲜", "鲜生", "盒马", "超市", "鲜花", "花束", "啤酒", "白酒", "红酒", "矿泉水", "咖啡豆", "便利店")
FLASH_CATEGORY_OVERRIDE_TERMS = ("咖啡豆", "咖啡粉", "咖啡胶囊")
FOOD_TERMS = ("餐厅", "饭店", "火锅", "烧烤", "肉串", "猪脚饭", "烧腊", "蛋糕", "面包甜点", "柠檬水", "百香果", "咖啡", "奶茶", "菜品", "美食", "小吃", "快餐", "汉堡", "粉面", "盒饭", "日料", "中餐", "西餐")
DELIVERY_TERMS = ("外卖", "配送", "起送", "送达", "外送")
LEVELS = {
    "phase3-single_element-eval": ("单一元素维度", "element", "#6366f1"),
    "phase3-card_or_component-eval": ("组件/卡片维度", "component", "#10b981"),
    "phase3-page_framework-eval": ("页面框架维度", "page", "#60a5fa"),
}
PASS_RATINGS = {"达标", "🟡"}
FAIL_RATINGS = {"不达标", "🔴"}


def priority_from_vote_counts(fail_count: int, pass_count: int) -> str | None:
    """Return the deterministic governance priority for one business/level/metric unit."""
    if fail_count >= 4 or pass_count >= 6:
        return "P0"
    if fail_count >= 2 or pass_count >= 4:
        return "P1"
    if 1 <= pass_count <= 3:
        return "P2"
    # The three explicit thresholds do not cover a single failing vote with no
    # passing votes. Keep that detected issue visible in the lowest priority
    # instead of silently dropping it from the dashboard.
    if fail_count == 1 and pass_count == 0:
        return "P2"
    return None


def priority_reason_from_vote_counts(fail_count: int, pass_count: int, priority: str) -> str:
    reason = (
        f"同一业务线、同一维度、同一指标本轮统计：不达标 {fail_count} 票，达标 {pass_count} 票。"
        f"按固定阈值（不达标≥4或达标≥6为P0；不达标≥2或达标≥4为P1；达标1至3为P2）判定为 {priority}。"
    )
    if fail_count == 1 and pass_count == 0:
        reason += "该组合未命中三条显式阈值，为避免已检测问题从报告消失，按剩余低频问题收纳为P2。"
    return reason


METRICS = {
    # 该名称用于“待优化项”问题卡，统一描述问题本身而不是理想状态。
    "eval-1-supply-quality-scanner": ("供给呈现问题", "supply_quality"),
    "eval-1-supply-completeness": ("供给呈现问题", "supply_completeness"),
    "eval-1-supply-module-completeness": ("供给呈现问题（页面框架）", "supply_module_completeness"),
    "eval-2-color-logic-single-element": ("单一元素色彩复杂", "color_logic"),
    "eval-2-visual-order-alignment": ("视觉秩序问题", "visual_order"),
    "eval-3-page-color-logic": ("页面色彩复杂", "page_color_logic"),
    "eval-3-color-logic": ("组件色彩复杂", "color_logic"),
    "eval-3-element-compliance-scanner": ("静态元素复杂", "element_compliance"),
    "eval-4-element-complexity": ("元素复杂", "element_complexity"),
    "eval-4-static-component-complexity": ("组件复杂", "static_component_complexity"),
    "eval-4-info-authenticity-single-element": ("信息/功能歧义", "info_authenticity"),
    "eval-5-info-hierarchy": ("信息层级不清", "information_hierarchy"),
    "eval-5-browsing-flow-smoothness": ("浏览动线问题", "browsing_flow"),
    "eval-5-info-redundancy": ("信息冗余", "information_redundancy"),
    "eval-6-info-partitioning": ("信息分区问题", "information_partitioning"),
    "eval-6-info-comparability": ("信息不可比", "information_comparability"),
    "eval-7-info-authenticity": ("信息/功能歧义", "info_authenticity"),
    "eval-7-browsing-flow-smoothness": ("浏览动线问题", "browsing_flow"),
    "eval-7-info-redundancy": ("功能/信息冗余", "page_information_redundancy"),
    "eval-8-info-redundancy": ("信息冗余", "information_redundancy"),
}


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def card_semantic_text(card: dict[str, Any]) -> str:
    """Return current merchant/product semantics, excluding fulfilment facts."""
    values: list[str] = [str(card.get("卡片类型", "")), str(card.get("cardTypeCode", ""))]
    for region in card.get("regions", []):
        for element in region.get("elements", []):
            facts = element.get("textFacts") if isinstance(element.get("textFacts"), dict) else {}
            if facts.get("semanticRole") == "fulfillment" or "履约" in str(region.get("name", "")):
                continue
            values.extend(str(element.get(key, "")) for key in ("内容简述", "content", "text", "visibleText"))
            values.append(str(facts.get("rawText", "")))
    return " ".join(values).lower()


def fulfillment_text(card: dict[str, Any]) -> str:
    """Return only Phase2's confirmed fulfilment table, never the search query."""
    values: list[str] = []
    for region in card.get("regions", []):
        for element in region.get("elements", []):
            facts = element.get("textFacts") if isinstance(element.get("textFacts"), dict) else {}
            if facts.get("semanticRole") == "fulfillment" or "履约" in str(region.get("name", "")):
                values.extend(str(element.get(key, "")) for key in ("内容简述", "content", "text", "visibleText"))
                values.append(str(facts.get("rawText", "")))
    return " ".join(values).lower()


def card_type_code(card_type: str) -> str:
    if "商品" in card_type:
        return "product_card"
    if "图文下挂" in card_type:
        return "merchant_image_append_card"
    if "文字下挂" in card_type:
        return "merchant_text_append_card"
    if "无下挂" in card_type:
        return "merchant_plain_card"
    if "主点" in card_type:
        return "poi_card"
    if "酒店" in card_type:
        return "hotel_card"
    return "merchant_card"


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def classified_business(code: str, kind: str, card_type: str, confidence: str) -> dict[str, str]:
    return {
        "scope": "business", "businessCode": code, "businessName": BUSINESS_LINES[code],
        "confidence": confidence, "cardTypeCode": kind, "cardTypeName": card_type,
    }


def classify_card(card: dict[str, Any]) -> dict[str, str]:
    """Classify one card by current visible facts, in this fixed precedence.

    Dedicated business semantics (healthcare, travel, Maoyan, Xiaoxiang) win
    first. Service-retail semantics identify local-service group-buy cards.
    For delivery cards, a flash label or a recognised flash product category
    distinguishes flash delivery from food delivery. A card type by itself is
    never a flash-delivery fact. Missing evidence remains ``unknown``.
    """
    card_type = str(card.get("卡片类型", ""))
    kind = card_type_code(card_type)
    # Phase2 may explicitly assign a standard business ownership after it has
    # inspected the card.  That fact is stronger than keyword heuristics, but
    # an unsupported code must remain visible and block aggregation below.
    explicit_code = str(card.get("businessCode") or "").strip()
    if card.get("ownershipScope") == "business" and explicit_code:
        if explicit_code in BUSINESS_LINES:
            return classified_business(
                explicit_code,
                kind,
                card_type,
                str(card.get("businessConfidence") or "phase2_explicit"),
            )
        return {
            "scope": "unknown", "businessCode": "unknown", "businessName": "未知待确认",
            "confidence": f"unsupported_explicit_business_code:{explicit_code}",
            "cardTypeCode": kind, "cardTypeName": card_type,
        }
    semantic, fulfillment = card_semantic_text(card), fulfillment_text(card)
    if (card_type in PLATFORM_SCOPES or card.get("cardId") == "macro-top"
            or (card_type == "异构卡" and "大家还在搜" in semantic)):
        return {"scope": "platform", "businessCode": "platform", "businessName": "平台公共组件",
                "confidence": "high", "cardTypeCode": "platform_component", "cardTypeName": card_type}
    if has_any(semantic, SERVICE_RETAIL_EXCLUSIVE_TERMS):
        return classified_business("service_retail", kind, card_type, "specific_service_semantic")
    for business, terms in DEDICATED_BUSINESS_TERMS:
        if has_any(semantic, terms):
            return classified_business(business, kind, card_type, "semantic")

    is_service = has_any(semantic, SERVICE_RETAIL_TERMS)
    is_flash_label = has_any(semantic, FLASH_DELIVERY_TERMS) or has_any(fulfillment, FLASH_DELIVERY_TERMS)
    is_flash_category = has_any(semantic, FLASH_CATEGORY_TERMS)
    is_flash_category_override = has_any(semantic, FLASH_CATEGORY_OVERRIDE_TERMS)
    is_food = has_any(semantic, FOOD_TERMS)
    is_delivery = has_any(fulfillment, DELIVERY_TERMS)

    if is_service:
        return classified_business("service_retail", kind, card_type, "semantic")
    if is_delivery:
        if is_flash_label or (is_flash_category and (not is_food or is_flash_category_override)):
            return classified_business("flash_delivery", kind, card_type, "delivery+flash_category")
        if is_food:
            return classified_business("food_delivery", kind, card_type, "delivery+food_category")
        return {
            "scope": "unknown", "businessCode": "unknown", "businessName": "未知待确认",
            "confidence": "delivery_category_not_confirmed", "cardTypeCode": kind, "cardTypeName": card_type,
        }
    if is_food:
        return classified_business("dine_in", kind, card_type, "food_category+non_delivery")
    # A card container alone is not business evidence.  Defaulting it to a
    # permitted tab makes a dashboard look complete while silently corrupting
    # that tab's score and issue rate; callers must stop and obtain facts.
    return {
        "scope": "unknown", "businessCode": "unknown", "businessName": "未知待确认",
        "confidence": "insufficient_current_facts", "cardTypeCode": kind, "cardTypeName": card_type,
    }


def humanize_element_label(element: dict[str, Any]) -> str:
    """Turn a Phase2 element record into a concise reader-facing object label."""
    element_type = str(element.get("元素类型") or element.get("elementType") or "元素").strip()
    facts = element.get("textFacts") if isinstance(element.get("textFacts"), dict) else {}
    content = str(facts.get("rawText") or element.get("内容简述") or element.get("content") or "").strip()
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


def card_location_labels(cards: list[dict[str, Any]]) -> dict[str, str]:
    """Return reader-facing list positions without exposing card IDs or coordinates."""
    labels: dict[str, str] = {}
    standard_index = 0
    for card in cards:
        card_id = str(card.get("cardId") or "")
        structure = card.get("structure") if isinstance(card.get("structure"), dict) else {}
        card_type = str(card.get("卡片类型") or card.get("cardTypeCode") or "")
        heterogeneous = bool(structure.get("isHeterogeneous")) or card_type in {"异构卡", "heterogeneous"}
        if not heterogeneous:
            standard_index += 1
            labels[card_id] = f"商卡{standard_index}"
            continue
        semantic = card_semantic_text(card)
        if "大家还在搜" in semantic:
            subtype = "大家还在搜"
        elif "直播" in semantic:
            subtype = "直播大卡"
        else:
            subtype = str(card.get("variant") or "其他")
        labels[card_id] = f"异构卡-{subtype}"
    return labels


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
    phase3_dir = project / "phase3-evaluation"
    catalog = json.loads((phase3_dir / "catalog.json").read_text(encoding="utf-8"))
    for item in catalog["dimensions"]:
        dimension = item["id"]
        directory = phase3_dir / item["skillsDir"]
        for skill_file in directory.glob("eval-*/SKILL.md"):
            weight = load_weight(skill_file)
            if weight is not None:
                weights[(dimension, skill_file.parent.name)] = weight
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

    # Golden-JSON exemption runs do not create legacy ``screenshots-out``
    # manifests.  Their read-only Atomic v3 fact packs retain the canonical
    # source manifest, whose loader verifies schema, publication status and
    # source-image hash before exposing the same Phase3 card facts.  Consume
    # those facts directly so the governance report remains tied to the
    # accepted source rather than to a reconstructed Phase2 projection.
    try:
        from phase2_bundle_loader import load_phase2_facts
    except ImportError:
        load_phase2_facts = None
    if load_phase2_facts is not None:
        fact_pack_paths = [
            *artifact_dir.rglob("atomic-facts*.json"),
            *artifact_dir.rglob("*.atomic-fact-pack.v1.json"),
            # Golden-source evaluation runs retain the loader-verified manifest
            # path in their Stage A acceptance audit.  They do not necessarily
            # materialize a second Atomic fact-pack file, so consume that audit
            # as the canonical pointer instead of silently dropping the query.
            *artifact_dir.rglob("golden-acceptance-audit.json"),
        ]
        for fact_pack_path in fact_pack_paths:
            fact_pack = read_json(fact_pack_path)
            if not isinstance(fact_pack, dict):
                continue
            if fact_pack_path.name == "golden-acceptance-audit.json":
                if fact_pack.get("valid") is not True:
                    continue
                manifest_name = fact_pack.get("manifest")
            else:
                source = fact_pack.get("source")
                manifest_name = source.get("manifest") if isinstance(source, dict) else None
            if not isinstance(manifest_name, str) or not manifest_name:
                continue
            try:
                facts = load_phase2_facts(manifest_path=Path(manifest_name))
            except (OSError, ValueError, KeyError):
                continue
            query = str(facts.get("query", ""))
            if not query:
                continue
            # A fact source retained inside the selected artifact batch is
            # stronger than any same-query legacy projection in screenshots-out.
            # Overwrite it so an older, shorter card list cannot shadow the
            # loader-verified golden manifest and orphan current issue IDs.
            manifests[query] = (fact_pack_path, {
                "query": query,
                "screenshot": str(facts.get("screenshot", "")),
                "annotatedImage": "",
                "cards": facts.get("cards", []),
            })

    classifications: dict[str, dict[str, dict[str, str]]] = {}
    element_cards: dict[str, dict[str, str]] = {}
    element_labels: dict[str, dict[str, str]] = {}
    location_labels: dict[str, dict[str, str]] = {}
    for query, (_, manifest) in manifests.items():
        classifications[query] = {}
        element_cards[query] = {}
        element_labels[query] = {}
        location_labels[query] = card_location_labels(manifest.get("cards", []))
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
    for query, cards in classifications.items():
        for card_id, classification in cards.items():
            if classification["scope"] == "unknown":
                unknown.append({
                    "query": query,
                    "cardId": card_id,
                    "reason": "当前商卡语义与履约事实不足以判定业务",
                })
    # Phase3 results are retained under each query's isolated phase3 directory.
    # Discover recursively, then select one combined result per query so compatibility
    # aliases or per-dimension fallback files do not double-count a query.
    candidates_by_query: dict[str, list[Path]] = defaultdict(list)
    # 各词独立执行会保留不同命名的最终合并结果；优先消费已经通过
    # Phase4 回写的 all-results，确保治理看板引用的是最终证据路径而非 Phase3 初稿。
    for pattern in (
        ".eval_results_*.json", "评测原始结果_*.json", "*all-results*.json",
        "eval_results_*.json", "eval-results*.json", "phase3-results.json",
    ):
        for path in artifact_dir.rglob(pattern):
            if "audit" in path.name.lower() or "target" in path.name.lower():
                continue
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
                    elif classification and classification["scope"] == "platform":
                        # Platform components are deliberately outside business
                        # Tab aggregation.  Their ownership is known, so they
                        # must not be reported as an unresolved business card.
                        continue
                    elif level_code == "element":
                        target_classifications = [
                            item for item in classifications[query].values()
                            if item["scope"] == "business"
                        ]
                    else:
                        unknown.append({
                            "query": query,
                            "cardId": card_id,
                            "reason": "平台、混合或无法确认业务归属",
                        })
                        continue
                    if not target_classifications:
                        unknown.append({
                            "query": query,
                            "cardId": card_id,
                            "reason": "未找到可归属的业务卡",
                        })
                        continue
                    finding = issue_code(skill, issue)
                    for target in target_classifications:
                        related_card_ids = [str(value) for value in issue.get("relatedCardIds", []) if value]
                        target_card_id = (
                            "cross:" + "+".join(sorted(related_card_ids))
                            if related_card_ids else (card_id if classification else f"{level_code}:{query}")
                        )
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
                        if level_code == "page" or issue.get("isAssessmentLevel"):
                            location_label = "页面框架"
                        else:
                            location_label = str(issue.get("locationLabel") or location_labels[query].get(card_id) or "页面公共区域")
                        evidence = {"query": query, "tab": tab, "cardId": target_card_id, "elementId": element_id,
                                    "elementLabel": element_label,
                                    "locationLabel": location_label,
                                    "relatedCardIds": related_card_ids,
                                    "rating": str(issue.get("rating", unit.get("rating", ""))),
                                    "priority": str(issue.get("priority", "待判定")),
                                    "priorityReason": str(issue.get("priorityReason", "")),
                                    "assessmentLevel": bool(issue.get("isAssessmentLevel", False)),
                                    "description": str(issue.get("description", "")) or issue_description(issue, str(unit.get("reason", "")) or str(detail.get("summary", ""))),
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
        for card_id, classification in classifications.get(query, {}).items():
            if classification["scope"] != "business":
                continue
            summary = business_summary.setdefault(classification["businessCode"], {
                "businessCode": classification["businessCode"], "businessName": classification["businessName"], "issueCount": 0,
                "problemCards": set(), "evaluatedCards": set(), "componentProblemCards": set(), "componentEvaluatedCards": set(), "levelScores": defaultdict(list),
            })
            # The business card rate uses the full visible-card inventory as
            # denominator, including cards whose component metrics are all
            # excellent and therefore produce no governance group.
            summary["componentEvaluatedCards"].add((query, "全部", card_id))

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
        # Page-level findings use synthetic ``page:<query>`` references.  They
        # remain in issue counts and evidence, but must not inflate the metric
        # explicitly labelled as a business-card problem rate above 100%.
        total = len(item["componentEvaluatedCards"])
        problems = len(item["componentProblemCards"])
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
            # 本批次是月度问题跟踪的首个基线：所有本批发现均计为新增，
            # 尚无可验证的闭环记录时不虚构已解决数量。
            "tracking": {"newIssueCount": int(item["issueCount"]), "resolvedIssueCount": 0, "baseline": "monthly_tracking_initial"},
            # 分数严格来自 Skill weight： (实际原始分 - 理论最低分) / (理论最高分 - 理论最低分) × 100。
            "dimensionScores": dimension_scores, "dimensionBreakdown": dimension_breakdown, "overallScore": overall_score,
        })
    business_rows.sort(key=lambda item: (-item["issueCount"], item["businessName"]))
    return {"generatedAt": str(date.today()), "queryCount": len(used_queries), "groups": groups, "businesses": business_rows, "queryDetails": dict(sorted(query_details.items())), "unknown": unknown, "manifests": len(manifests)}


def validate_dataset(data: dict[str, Any], artifact_dir: Path, expected_business_tabs: set[str]) -> None:
    """Fail early when a dashboard would silently mix batches or lose audit evidence."""
    if not data["queryCount"]:
        raise ValueError(f"未从评测产物读取到有效搜索词：{artifact_dir}")
    if data["queryCount"] != len(data["queryDetails"]):
        raise ValueError("搜索词计数与逐词详情不一致，停止生成以避免交付不完整看板")
    if data.get("unknown"):
        unresolved = "; ".join(
            f"{item.get('query')}:{item.get('cardId')}（{item.get('reason')}）"
            for item in data["unknown"]
        )
        raise ValueError(f"存在无法由当前商卡语义与履约事实判定的业务归属，停止业务Tab聚合：{unresolved}")
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


def render(data: dict[str, Any]) -> str:
    """Render only through the canonical Phase5 dashboard renderer."""
    return render_dashboard(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the search result experience dashboard")
    parser.add_argument("--project-dir", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dataset-output", type=Path)
    parser.add_argument("--batch-name", help="当前隔离评测批次名；不传时使用 artifact-dir 目录名")
    parser.add_argument(
        "--expected-business-tabs",
        required=True,
        help="本批次业务 Tab 断言（逗号分隔 businessCode）；实际输出必须完全一致",
    )
    args = parser.parse_args()
    project = args.project_dir.resolve()
    artifact_dir = args.artifact_dir or project / ".artifacts" / "过程文件-评测结果与审计"
    output = args.output or project / "reports" / "meituan_search_experience_dashboard_五图全维度.html"
    dataset_output = args.dataset_output or project / "reports" / ".governance_dataset_五图全维度.json"
    data = collect(project, artifact_dir)
    data["batch"] = args.batch_name or artifact_dir.name
    expected_business_tabs = {code.strip() for code in args.expected_business_tabs.split(",") if code.strip()}
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
