#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical Phase5 business-dashboard renderer.

This module only presents the accepted governance dataset. It never reads Phase2/
Phase3 artifacts, changes scores, or synthesizes issues/evidence.
"""
from __future__ import annotations

import html
import re
from collections import Counter, defaultdict
from urllib.parse import quote
from typing import Any

DIMENSIONS = (
    ("element", "单一元素", "单一元素维度"),
    ("component", "组件/卡片", "组件/卡片维度"),
    ("page", "页面框架", "页面框架维度"),
)
DIMENSION_ORDER = {"component": 0, "page": 1, "element": 2}
PROBLEM_RATINGS = {"达标", "不达标", "🟡", "🔴"}


def esc(value: Any) -> str:
    return html.escape(str(value or ""))


def score(value: Any) -> str:
    return "—" if not isinstance(value, (int, float)) else f"{value:.1f}"


def sentence(value: Any) -> str:
    return str(value or "").strip().rstrip("。！？!?；;，,")


def finding_text(issue: dict[str, Any]) -> str:
    finding = issue.get("finding") if isinstance(issue.get("finding"), dict) else {}
    required = ("observableFact", "ruleOrThreshold", "verdictReason", "userImpact")
    missing = [key for key in required if not sentence(finding.get(key))]
    if missing:
        target = issue.get("elementId") or issue.get("cardId") or issue.get("query") or "未命名问题"
        raise ValueError(f"问题 {target} 缺少三段式结论字段：{','.join(missing)}")
    # 阈值仍是已验收问题事实的一部分，但明细卡优先呈现用户可快速扫读的
    # “事实（含评级）→影响”主线，避免重复展示规则和计数结论。
    observable_fact = sentence(finding["observableFact"])
    rating = str(issue.get("rating") or "")
    rating_clause = f"，评级为{rating}" if rating and f"评级为{rating}" not in observable_fact else ""
    return "{}{}。{}。".format(
        observable_fact,
        rating_clause,
        sentence(finding["userImpact"]),
    )


def recommendation_text(issue: dict[str, Any]) -> str:
    recommendation = str(issue.get("recommendation") or "").strip()
    if not recommendation:
        target = issue.get("elementId") or issue.get("cardId") or issue.get("query") or "未命名问题"
        raise ValueError(f"问题 {target} 缺少问题级个性化优化建议")
    return recommendation


def priority(issue: dict[str, Any], group: dict[str, Any]) -> str:
    value = str(issue.get("priority") or group.get("priority") or "P2")
    return value if value in {"P0", "P1", "P2"} else "P2"


def issue_target(issue: dict[str, Any]) -> str:
    """Return the reader-facing target while keeping technical IDs only in the dataset."""
    label = str(issue.get("elementLabel") or issue.get("targetLabel") or "").strip()
    if label:
        return label
    component = str(issue.get("componentName") or issue.get("component") or "").strip()
    if component:
        return component
    return "相关页面区域"


def issue_image(issue: dict[str, Any]) -> str:
    return str(issue.get("evidenceImage") or "")


def evidence_html(path: str, label: str) -> str:
    if not path:
        return "<div class='evidence-empty'>暂无截图证据</div>"
    # Evidence paths often contain Chinese query names and spaces. Encode the file URI
    # once at render time so both metric and query views resolve the same local asset.
    safe_uri, safe_label = esc(quote(path, safe="/:")), esc(label)
    return (
        "<a class='evidence-link' href='file://{uri}' target='_blank' rel='noopener'>"
        "<img loading='lazy' src='file://{uri}' alt='{label}'></a>"
    ).format(uri=safe_uri, label=safe_label)


def flattened_issues(groups: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    rows: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for group in groups:
        for issue in group.get("evidence", []):
            if isinstance(issue, dict) and str(issue.get("rating") or "") in PROBLEM_RATINGS:
                rows.append((group, issue))
    return rows


def fill_missing_evidence(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Fill missing evidenceImage from sibling issues sharing the same screenshot.

    Phase4 produces one red-box summary per screenshot. Page-level conclusions
    without coordinates are skipped by Phase4, but the same screenshot's other
    issues already have the red-box evidence. Per SKILL, "同一截图的多个问题
    允许且应当复用同一张汇总红框图" — reuse that image so no issue shows an
    empty placeholder when a screenshot-level red-box exists.
    """
    by_screenshot: dict[str, str] = {}
    for _, issue in entries:
        img = str(issue.get("evidenceImage") or "")
        screenshot = str(issue.get("screenshot") or "")
        if img and screenshot and screenshot not in by_screenshot:
            by_screenshot[screenshot] = img
    filled = []
    for group, issue in entries:
        if not issue.get("evidenceImage"):
            screenshot = str(issue.get("screenshot") or "")
            if screenshot in by_screenshot:
                issue = {**issue, "evidenceImage": by_screenshot[screenshot]}
        filled.append((group, issue))
    return filled


def scope_summary(business: dict[str, Any], groups: list[dict[str, Any]]) -> dict[str, Any]:
    scoped = [group for group in groups if group.get("businessCode") == business.get("businessCode")]
    issues = fill_missing_evidence(flattened_issues(scoped))
    by_level: Counter[str] = Counter(str(group.get("level") or "") for group, _ in issues)
    priority_by_level: dict[str, Counter[str]] = defaultdict(Counter)
    for group, issue in issues:
        priority_by_level[str(group.get("level") or "")][priority(issue, group)] += 1
    return {
        "overall": business.get("overallScore"),
        "dimensionScores": business.get("dimensionScores") if isinstance(business.get("dimensionScores"), dict) else {},
        "issues": issues,
        "issueCounts": by_level,
        "priorityByLevel": priority_by_level,
    }


def overview_summary(businesses: list[dict[str, Any]], groups: list[dict[str, Any]]) -> dict[str, Any]:
    values: dict[str, list[float]] = defaultdict(list)
    for business in businesses:
        for code, value in (business.get("dimensionScores") or {}).items():
            if isinstance(value, (int, float)):
                values[str(code)].append(float(value))
    issues = fill_missing_evidence(flattened_issues(groups))
    issue_counts: Counter[str] = Counter(str(group.get("level") or "") for group, _ in issues)
    priority_by_level: dict[str, Counter[str]] = defaultdict(Counter)
    for group, issue in issues:
        priority_by_level[str(group.get("level") or "")][priority(issue, group)] += 1
    overall_values = [float(item["overallScore"]) for item in businesses if isinstance(item.get("overallScore"), (int, float))]
    return {
        "overall": round(sum(overall_values) / len(overall_values), 1) if overall_values else None,
        "dimensionScores": {code: round(sum(items) / len(items), 1) for code, items in values.items() if items},
        "issues": issues,
        "issueCounts": issue_counts,
        "priorityByLevel": priority_by_level,
    }


def render_summary(summary: dict[str, Any]) -> str:
    score_rows, issue_rows = [], []
    for code, short_name, _ in DIMENSIONS:
        value = summary["dimensionScores"].get(code)
        missing = " missing" if not isinstance(value, (int, float)) else ""
        score_rows.append("<div class='summary-metric-label'>{name}：<b class='{missing}'>{value}</b></div>".format(
            name=short_name, missing=missing.strip(), value=score(value)))
        counts = summary["priorityByLevel"].get(code, Counter())
        issue_rows.append("<div class='summary-metric-label'>{name}：<b>{count}</b><em>P0-{p0}，P1-{p1}</em></div>".format(
            name=short_name, count=summary["issueCounts"].get(code, 0), p0=counts.get("P0", 0), p1=counts.get("P1", 0)))
    return """
<section class='summary-panel'>
  <div class='summary-block'><h2 class='summary-block-title'>评测总分</h2><div class='summary-body'><div class='summary-figure'>{overall}</div><div class='summary-metrics'>{scores}</div></div></div>
  <div class='summary-block warn'><h2 class='summary-block-title'>问题发现</h2><div class='summary-body'><div class='summary-figure'>{issues}</div><div class='summary-metrics'>{issue_rows}</div></div></div>
</section>""".format(overall=score(summary["overall"]), issues=len(summary["issues"]), scores="".join(score_rows), issue_rows="".join(issue_rows))


def render_issue(issue: dict[str, Any], group: dict[str, Any], title: str) -> str:
    issue_priority = priority(issue, group).lower()
    return """
<article class='issue-item'>
  <div class='issue-heading'><h4>{title}</h4><span class='tag {priority}'>{label}</span></div>
  <p class='issue-target'><b>问题元素</b>{target}</p>
  <p class='issue-description'>{description}</p>
  <div class='recommendation'><b>优化建议</b><p>{recommendation}</p></div>
</article>""".format(
        title=esc(title), priority=esc(issue_priority), label=esc(priority(issue, group)),
        target=esc(issue_target(issue)), description=esc(finding_text(issue)), recommendation=esc(recommendation_text(issue)))


def render_by_query(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    grouped: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for group, issue in entries:
        grouped[(str(issue.get("query") or "未命名搜索词"), str(issue.get("tab") or "全部"))].append((group, issue))
    blocks, ordinal = [], 0
    for (query, tab), items in grouped.items():
        items.sort(key=lambda row: (DIMENSION_ORDER.get(str(row[0].get("level")), 99), str(row[0].get("metricName") or "")))
        images = Counter(issue_image(issue) for _, issue in items if issue_image(issue))
        path = images.most_common(1)[0][0] if images else ""
        content, active_level = [], None
        for group, issue in items:
            level = str(group.get("level") or "")
            if level != active_level:
                active_level = level
                content.append("<h3 class='dimension-title'>{}</h3>".format(esc(group.get("levelName") or "评测维度")))
            ordinal += 1
            content.append(render_issue(issue, group, f"问题{ordinal}：{group.get('metricName') or '体验问题'}"))
        blocks.append("""
<section class='query-issue-group'>
  <header class='query-issue-header'><h3>{query}</h3><em>{tab} Tab · {count} 个问题</em></header>
  <div class='query-issue-content'><div class='issue-evidence'>{evidence}</div><div class='issue-copy'>{content}</div></div>
</section>""".format(query=esc(query), tab=esc(tab), count=len(items), evidence=evidence_html(path, f"{query}问题证据"), content="".join(content)))
    return "<div class='issue-grid'>{}</div>".format("".join(blocks)) if blocks else "<div class='empty'>该业务本轮暂无待优化问题。</div>"


def render_by_metric(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    grouped: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for group, issue in entries:
        grouped[(str(group.get("level") or ""), str(group.get("metricName") or "体验问题"))].append((group, issue))
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    blocks, ordinal = [], 0
    ordered_groups = sorted(
        grouped.items(),
        key=lambda row: (
            min(priority_order.get(priority(issue, group), 3) for group, issue in row[1]),
            DIMENSION_ORDER.get(row[0][0], 99),
            row[0][1],
        ),
    )
    for (_, metric), items in ordered_groups:
        group = items[0][0]
        rows = []
        for item_group, issue in sorted(items, key=lambda row: priority_order.get(priority(row[1], row[0]), 3)):
            ordinal += 1
            rows.append("<div class='metric-issue-row'><div class='issue-evidence'>{evidence}</div>{issue}</div>".format(
                evidence=evidence_html(issue_image(issue), f"{issue.get('query') or '搜索词'}问题证据"),
                issue=render_issue(issue, item_group, f"问题{ordinal}：{issue.get('query') or '未命名搜索词'}")))
        blocks.append("""
<section class='metric-issue-group'><header class='metric-issue-header'><h3>{metric}</h3><span class='tag dim'>{dimension}</span><em>{count} 个问题</em></header>{rows}</section>""".format(
            metric=esc(metric), dimension=esc(group.get("levelName") or "评测维度"), count=len(items), rows="".join(rows)))
    return "".join(blocks) or "<div class='empty'>该业务本轮暂无待优化问题。</div>"


def render_dashboard(data: dict[str, Any]) -> str:
    businesses = [item for item in data.get("businesses", []) if isinstance(item, dict) and item.get("businessCode")]
    groups = [item for item in data.get("groups", []) if isinstance(item, dict)]
    if not businesses:
        raise ValueError("治理数据集没有可展示的业务线")
    overview = overview_summary(businesses, groups)
    batch = str(data.get("batch") or "")
    query_count_match = re.search(r"(\d+)词", batch)
    report_query_count = int(query_count_match.group(1)) if query_count_match else int(data.get("queryCount") or 0)
    dimension_order = {"element": "单一元素", "component": "组件/卡片", "page": "页面框架"}
    evaluated = [dimension_order[code] for code, _, _ in DIMENSIONS if any(code in (item.get("dimensionScores") or {}) for item in businesses)]
    tabs = ["<button class='business-tab active' type='button' data-business='overview'>概览</button>"]
    cards, panels = [], []
    for business in businesses:
        code = str(business["businessCode"])
        name = str(business.get("businessName") or code)
        tabs.append("<button class='business-tab' type='button' data-business='{code}'>{name}</button>".format(code=esc(code), name=esc(name)))
        cards.append("<button class='business-card' type='button' data-target='{code}'><span>{name}</span><b>{score}</b><em>问题发现 {issues}</em></button>".format(
            code=esc(code), name=esc(name), score=score(business.get("overallScore")), issues=business.get("issueCount", 0)))
        summary = scope_summary(business, groups)
        panels.append("""
<section class='panel business-panel' data-panel='{code}'>
  {summary}<div class='detail-heading'><h2 class='section-title'>问题明细</h2>
    <div class='detail-tabs' role='tablist' aria-label='问题明细分组方式'>
      <button class='detail-tab' type='button' data-detail-tab='{code}-query'>按搜索词</button>
      <button class='detail-tab active' type='button' data-detail-tab='{code}-metric'>按指标</button>
    </div>
  </div>
  <div class='detail-pane' data-detail-pane='{code}-query'>{by_query}</div>
  <div class='detail-pane active' data-detail-pane='{code}-metric'>{by_metric}</div>
</section>""".format(code=esc(code), summary=render_summary(summary), by_query=render_by_query(summary["issues"]), by_metric=render_by_metric(summary["issues"])))
    return """<!doctype html>
<html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>大搜结果页体验评测看板</title><style>
:root{{--font-sans:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;--bg-gradient:linear-gradient(135deg,#e8eaf6 0%,#ede9fe 35%,#dbeafe 68%,#e0f2fe 100%);--surface:rgba(255,255,255,.9);--surface-border:1px solid rgba(255,255,255,.8);--surface-radius:24px;--surface-shadow:0 18px 40px rgba(71,85,105,.12);--indigo:#6366f1;--indigo-deep:#4338ca;--amber:#f59e0b;--green:#10b981;--blue:#60a5fa;--slate-muted:#94a3b8;--red:#ef4444;--gray-500:#64748b;--gray-700:#334155}}*{{box-sizing:border-box}}body{{margin:0;padding:104px 24px 96px;font-family:var(--font-sans);font-size:14px;line-height:1.6;color:#172033;background:var(--bg-gradient);min-height:100vh;-webkit-font-smoothing:antialiased}}body:before,body:after{{content:'';position:fixed;border-radius:50%;filter:blur(18px);opacity:.32;pointer-events:none;z-index:0}}body:before{{width:360px;height:360px;background:#c4b5fd;right:-100px;top:80px}}body:after{{width:330px;height:330px;background:#7dd3fc;left:-120px;bottom:40px}}.topbar{{position:fixed;z-index:10;top:0;right:0;left:0;display:flex;height:56px;align-items:center;justify-content:space-between;padding:0 max(24px,calc((100vw - 1180px)/2));background:rgba(255,255,255,.55);backdrop-filter:blur(20px) saturate(180%);-webkit-backdrop-filter:blur(20px) saturate(180%);border-bottom:1px solid rgba(255,255,255,.6);box-shadow:0 1px 24px rgba(71,85,105,.08)}}.brand{{color:var(--gray-700);font-weight:700;font-size:13px;letter-spacing:.12em}}.top-links{{display:flex;align-items:center;gap:24px}}.top-links a{{color:var(--gray-500);font-size:12px;letter-spacing:.04em;text-decoration:none;transition:.2s}}.top-links a:hover,.top-links a:focus-visible{{color:var(--indigo-deep)}}.top-links a:last-child{{color:var(--gray-700);font-weight:700}}.page{{position:relative;z-index:1;max-width:1180px;margin:0 auto}}.report-head{{position:relative;padding:28px 0 24px}}.report-head h1{{margin:0;font-size:30px;font-weight:700;letter-spacing:-.5px}}.subtitle{{max-width:760px;margin:10px 0 0;color:var(--gray-500);font-size:14px}}.subtitle a{{color:var(--indigo-deep);text-underline-offset:3px}}.period-select{{position:absolute;top:28px;right:0;appearance:none;border:1px solid #dbe4ff;border-radius:14px;background:#fff;color:var(--gray-700);padding:8px 12px;font-size:12px}}.business-tabs{{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0}}button{{font-family:inherit}}.business-tab{{border:1px solid #dbe4ff;border-radius:999px;background:#fff;color:var(--gray-700);padding:8px 16px;font-size:13px;font-weight:600;cursor:pointer;transition:.2s}}.business-tab:hover{{border-color:var(--indigo);color:var(--indigo-deep);transform:translateY(-1px)}}.business-tab.active{{border-color:var(--indigo);background:var(--indigo);color:#fff}}.panel{{display:none}}.panel.active{{display:block;padding-top:8px}}.summary-panel{{display:grid;grid-template-columns:1fr 1fr;border-radius:var(--surface-radius);background:var(--surface);border:var(--surface-border);box-shadow:var(--surface-shadow);overflow:hidden}}.summary-block{{padding:24px 28px}}.summary-block+.summary-block{{border-left:1px solid #e2e8f0}}.summary-block-title{{margin:0 0 18px;font-size:15px;font-weight:700;color:var(--gray-700)}}.summary-body{{display:flex;align-items:flex-start;gap:24px}}.summary-figure{{flex:0 0 auto;font-size:56px;font-weight:700;line-height:1;color:#172033;letter-spacing:-1px}}.summary-block.warn .summary-figure{{color:var(--red)}}.summary-metrics{{flex:1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));row-gap:12px;column-gap:20px;align-content:start}}.summary-metric-label{{color:var(--gray-700);font-size:13px}}.summary-metric-label b{{font-weight:700}}.summary-metric-label b.missing{{color:var(--slate-muted)}}.summary-metric-label em{{margin-left:8px;color:var(--gray-500);font-size:12px;font-style:normal}}.overview-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-top:20px}}.business-card{{border:var(--surface-border);border-radius:var(--surface-radius);background:var(--surface);box-shadow:var(--surface-shadow);padding:18px;text-align:left;cursor:pointer;transition:transform .2s,box-shadow .2s,border-color .2s}}.business-card:hover{{border-color:var(--indigo);box-shadow:0 8px 18px rgba(99,102,241,.18);transform:translateY(-3px)}}.business-card span{{display:block;color:var(--gray-500);font-size:12px;letter-spacing:.04em}}.business-card b{{display:block;margin:10px 0 6px;font-size:28px;font-weight:700;color:var(--indigo-deep);line-height:1}}.business-card em{{display:block;color:var(--gray-500);font-size:12px;font-style:normal}}.detail-heading{{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-top:40px;margin-bottom:16px;border-bottom:1px solid #e2e8f0}}.section-title{{margin:0;padding-bottom:10px;font-size:22px;font-weight:700}}.detail-tabs{{display:flex;gap:16px;align-self:stretch}}.detail-tab{{margin-bottom:-1px;border:0;border-bottom:2px solid transparent;background:transparent;color:var(--gray-500);padding:9px 3px;font-size:13px;font-weight:600;letter-spacing:.02em;cursor:pointer}}.detail-tab:hover{{color:var(--indigo-deep)}}.detail-tab.active{{border-color:var(--indigo);color:var(--indigo-deep)}}.detail-pane{{display:none}}.detail-pane.active{{display:block}}.issue-grid{{display:grid;gap:16px}}.query-issue-group,.metric-issue-group{{overflow:hidden;border-radius:var(--surface-radius);background:var(--surface);border:var(--surface-border);box-shadow:var(--surface-shadow)}}.metric-issue-group+.metric-issue-group{{margin-top:16px}}.query-issue-header,.metric-issue-header{{display:flex;align-items:center;gap:10px;padding:13px 18px;border-bottom:1px solid #e2e8f0;background:rgba(238,242,255,.6)}}.query-issue-header h3,.metric-issue-header h3{{margin:0;font-size:16px;font-weight:700}}.query-issue-header em,.metric-issue-header em{{margin-left:auto;color:var(--gray-500);font-size:12px;font-style:normal}}.query-issue-content{{display:grid;grid-template-columns:300px minmax(0,1fr);gap:22px;padding:18px}}.metric-issue-row{{display:grid;grid-template-columns:220px minmax(0,1fr);gap:18px;padding:18px}}.metric-issue-row+.metric-issue-row{{border-top:1px solid #eef2ff}}.issue-evidence{{align-self:start}}.evidence-link{{display:block;width:100%;overflow:hidden;border-radius:12px;border:1px solid #dbeafe;background:#f8fafc}}.evidence-link img{{display:block;width:100%;height:auto;transition:.2s}}.evidence-link:hover img{{transform:scale(1.02)}}.evidence-empty{{display:grid;min-height:188px;place-items:center;border:1px dashed #cbd5e1;border-radius:12px;background:#f8fafc;color:var(--gray-500);font-size:12px}}.dimension-title{{margin:0 0 8px;color:var(--indigo-deep);font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase}}.dimension-title:not(:first-child){{margin-top:20px}}.issue-item{{padding:11px 0;border-top:1px solid #eef2ff}}.dimension-title+.issue-item{{padding-top:0;border-top:0}}.issue-heading{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}.issue-heading h4{{margin:0 auto 0 0;font-size:15px;font-weight:700}}.tag{{display:inline-flex;border-radius:999px;padding:3px 9px;font-size:11px;font-weight:700;color:#fff}}.tag.p0{{background:var(--red)}}.tag.p1{{background:var(--amber)}}.tag.p2{{background:var(--green)}}.tag.dim{{background:var(--indigo)}}.issue-target{{margin:7px 0 4px;color:var(--gray-500);font-size:13px;line-height:1.5}}.issue-target b{{margin-right:8px;color:var(--gray-700)}}.issue-description{{margin:5px 0 9px;color:var(--gray-700);font-size:14px;line-height:1.58}}.recommendation{{padding:10px 12px;border-left:3px solid var(--amber);background:#fffbeb;color:#92400e;font-size:13px;line-height:1.55;border-radius:0 10px 10px 0}}.recommendation b{{font-size:11px;letter-spacing:.05em}}.recommendation p{{margin:3px 0 0}}.empty{{padding:34px;border-radius:var(--surface-radius);background:var(--surface);border:var(--surface-border);color:var(--gray-500);text-align:center}}.report-footer{{margin-top:56px;padding-top:20px;border-top:1px solid #e2e8f0;color:var(--gray-500);font-size:12px}}@media(max-width:880px){{.period-select{{position:static;margin-top:16px}}.detail-heading{{align-items:flex-start;flex-direction:column;gap:0}}.summary-panel{{grid-template-columns:1fr}}.summary-block+.summary-block{{border-left:0;border-top:1px solid #e2e8f0}}.overview-grid{{grid-template-columns:repeat(2,1fr)}}.query-issue-content,.metric-issue-row{{grid-template-columns:1fr}}}}@media(max-width:640px){{body{{padding:88px 16px 64px}}.topbar{{height:48px;padding:0 16px}}.top-links{{gap:14px}}.report-head h1{{font-size:24px}}.summary-body{{flex-direction:column;gap:14px}}.summary-figure{{font-size:44px}}.summary-metrics{{grid-template-columns:1fr}}.overview-grid{{grid-template-columns:1fr}}}}
</style></head><body>
<nav class='topbar'><div class='brand'>搜索</div><div class='top-links'><a href='https://km.sankuai.com/collabpage/2771507978' target='_blank' rel='noopener'>白皮书</a><a href='https://km.sankuai.com/collabpage/2770196684' target='_blank' rel='noopener'>体验标准</a><a href='#details'>体验评测</a></div></nav>
<main id='details' class='page'><header class='report-head'><h1>大搜结果页体验评测看板</h1><p class='subtitle'>评测日期：{date}　｜　评测范围：{count} 个搜索词、{dimensions}　<a href='https://km.sankuai.com/collabpage/2772784557' target='_blank' rel='noopener'>详情</a></p><select class='period-select' aria-label='评测周期'><option>{batch}</option></select></header><nav class='business-tabs'>{tabs}</nav><section class='panel active' data-panel='overview'>{overview}<div class='overview-grid'>{cards}</div></section>{panels}</main>
<script>
const businessTabs=[...document.querySelectorAll('.business-tab')],panels=[...document.querySelectorAll('.panel')];function activateBusiness(code){{businessTabs.forEach(tab=>tab.classList.toggle('active',tab.dataset.business===code));panels.forEach(panel=>panel.classList.toggle('active',panel.dataset.panel===code));window.scrollTo({{top:document.querySelector('.business-tabs').getBoundingClientRect().top+window.scrollY-12,behavior:'smooth'}})}}businessTabs.forEach(tab=>tab.addEventListener('click',()=>activateBusiness(tab.dataset.business)));document.querySelectorAll('.business-card').forEach(card=>card.addEventListener('click',()=>activateBusiness(card.dataset.target)));document.querySelectorAll('.detail-tab').forEach(tab=>tab.addEventListener('click',()=>{{const panel=tab.closest('.business-panel'),target=tab.dataset.detailTab;panel.querySelectorAll('.detail-tab').forEach(item=>item.classList.toggle('active',item===tab));panel.querySelectorAll('.detail-pane').forEach(item=>item.classList.toggle('active',item.dataset.detailPane===target))}}));
</script></body></html>""".format(
        date=esc(data.get("generatedAt") or "—"), count=esc(report_query_count),
        dimensions=esc(" / ".join(evaluated) or "未执行维度"), batch=esc(data.get("batch") or "当前批次"),
        tabs="".join(tabs), overview=render_summary(overview), cards="".join(cards), panels="".join(panels))
