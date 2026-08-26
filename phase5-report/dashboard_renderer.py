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
from typing import Any
from urllib.parse import quote

DIMENSIONS = (
    ("element", "单一元素"),
    ("component", "组件/卡片"),
    ("page", "页面框架"),
)
DIMENSION_ORDER = {"component": 0, "page": 1, "element": 2}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
PROBLEM_RATINGS = {"达标", "不达标", "🟡", "🔴"}


def esc(value: Any) -> str:
    return html.escape(str(value or ""))


def sentence(value: Any) -> str:
    return str(value or "").strip().rstrip("。！？!?；;，,")


def finding_text(issue: dict[str, Any]) -> str:
    finding = issue.get("finding") if isinstance(issue.get("finding"), dict) else {}
    required = ("observableFact", "ruleOrThreshold", "verdictReason", "userImpact")
    missing = [key for key in required if not sentence(finding.get(key))]
    if missing:
        target = issue.get("elementId") or issue.get("cardId") or issue.get("query") or "未命名问题"
        raise ValueError(f"问题 {target} 缺少三段式结论字段：{','.join(missing)}")
    observable_fact = sentence(finding["observableFact"])
    rating = str(issue.get("rating") or "")
    rating_clause = f"，评级为{rating}" if rating and f"评级为{rating}" not in observable_fact else ""
    return f"{observable_fact}{rating_clause}。{sentence(finding['userImpact'])}。"


def recommendation_text(issue: dict[str, Any]) -> str:
    recommendation = str(issue.get("recommendation") or "").strip()
    if not recommendation:
        target = issue.get("elementId") or issue.get("cardId") or issue.get("query") or "未命名问题"
        raise ValueError(f"问题 {target} 缺少问题级个性化优化建议")
    return recommendation


def priority(issue: dict[str, Any], group: dict[str, Any]) -> str:
    value = str(issue.get("priority") or group.get("priority") or "P2")
    return value if value in PRIORITY_ORDER else "P2"


def issue_target(issue: dict[str, Any]) -> str:
    return str(
        issue.get("elementLabel") or issue.get("targetLabel")
        or issue.get("componentName") or issue.get("component") or "相关页面区域"
    ).strip()


def issue_image(issue: dict[str, Any]) -> str:
    return str(issue.get("evidenceImage") or "")


def evidence_html(path: str, label: str) -> str:
    if not path:
        return "<div class='evidence-empty'>暂无截图证据</div>"
    safe_uri = esc(quote(path, safe="/:"))
    return (
        f"<a class='evidence-link' href='file://{safe_uri}' target='_blank' rel='noopener'>"
        f"<img loading='lazy' src='file://{safe_uri}' alt='{esc(label)}'></a>"
    )


def flattened_issues(groups: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [
        (group, issue)
        for group in groups
        for issue in group.get("evidence", [])
        if isinstance(issue, dict) and str(issue.get("rating") or "") in PROBLEM_RATINGS
    ]


def fill_missing_evidence(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    by_screenshot: dict[str, str] = {}
    for _, issue in entries:
        image, screenshot = issue_image(issue), str(issue.get("screenshot") or "")
        if image and screenshot:
            by_screenshot.setdefault(screenshot, image)
    return [
        (group, {**issue, "evidenceImage": by_screenshot.get(str(issue.get("screenshot") or ""), "")})
        if not issue_image(issue) and str(issue.get("screenshot") or "") in by_screenshot else (group, issue)
        for group, issue in entries
    ]


def make_summary(businesses: list[dict[str, Any]], groups: list[dict[str, Any]], code: str | None = None) -> dict[str, Any]:
    scoped_businesses = [item for item in businesses if code is None or item.get("businessCode") == code]
    scoped_groups = [item for item in groups if code is None or item.get("businessCode") == code]
    issues = fill_missing_evidence(flattened_issues(scoped_groups))
    priority_counts = Counter(priority(issue, group) for group, issue in issues)
    level_counts = Counter(str(group.get("level") or "") for group, _ in issues)
    return {
        "issues": issues,
        "priorityCounts": priority_counts,
        "levelCounts": level_counts,
        "tracking": {
            "newIssueCount": sum(int(((item.get("tracking") or {}).get("newIssueCount", item.get("issueCount", 0))) or 0) for item in scoped_businesses),
            "resolvedIssueCount": sum(int(((item.get("tracking") or {}).get("resolvedIssueCount", 0)) or 0) for item in scoped_businesses),
        },
    }


def render_summary(summary: dict[str, Any]) -> str:
    dimension_text = "".join(
        f"<span class='dimension-text'>{name}：{summary['levelCounts'].get(code, 0)}</span>"
        for code, name in DIMENSIONS
    )
    issue_count = len(summary["issues"])
    tracking = summary["tracking"]
    cumulative_text = (
        f"<span class='cumulative-text added'>↗ {tracking['newIssueCount']} 新增问题数</span>"
        f"<span class='cumulative-text resolved'>↘ {tracking['resolvedIssueCount']} 已解决问题数</span>"
    )
    return f"""
<div class='section-heading stats-heading'><h2>问题统计</h2></div>
<section class='stat-grid'>
  <article class='stat-card'><p>本次检测问题数</p><strong>{issue_count}<small>项</small></strong><div class='stat-text'>{dimension_text}</div></article>
  <article class='stat-card'><p>累计检测问题数</p><strong>{issue_count}<small>项</small></strong><div class='stat-text'>{cumulative_text}</div></article>
</section>"""


def render_issue(issue: dict[str, Any], group: dict[str, Any], title: str) -> str:
    issue_priority = priority(issue, group)
    return f"""
<article class='issue-copy'>
  <div class='issue-heading'><h4>{esc(title)}</h4><span class='priority-chip {issue_priority.lower()}'>{issue_priority}</span></div>
  <p class='issue-target'>{esc(issue_target(issue))}</p>
  <p class='issue-description'>{esc(finding_text(issue))}</p>
  <div class='recommendation'><b>优化建议</b><p>{esc(recommendation_text(issue))}</p></div>
</article>"""


def render_by_query(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    buckets: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for group, issue in entries:
        buckets[(str(issue.get("query") or "未命名搜索词"), str(issue.get("tab") or "全部"))].append((group, issue))
    blocks, ordinal = [], 0
    for (query, tab), items in sorted(buckets.items()):
        items.sort(key=lambda row: (DIMENSION_ORDER.get(str(row[0].get("level")), 99), str(row[0].get("metricName") or "")))
        images = Counter(issue_image(issue) for _, issue in items if issue_image(issue))
        copy = []
        for group, issue in items:
            ordinal += 1
            copy.append(render_issue(issue, group, f"问题{ordinal}：{group.get('metricName') or '体验问题'}"))
        blocks.append(f"""
<section class='issue-group'><header><div><b>{esc(query)}</b><span>{esc(tab)} Tab · {len(items)} 个问题</span></div></header>
<div class='query-layout'><div>{evidence_html(images.most_common(1)[0][0] if images else '', f'{query}问题证据')}</div><div>{''.join(copy)}</div></div>
</section>""")
    return "".join(blocks) or "<div class='empty'>该业务本轮暂无待优化问题。</div>"


def render_by_issue(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    """Render every detected issue independently without screenshot or query aggregation."""
    blocks = []
    ordered = sorted(
        entries,
        key=lambda row: (
            PRIORITY_ORDER.get(priority(row[1], row[0]), 3),
            str(row[1].get("query") or ""),
            DIMENSION_ORDER.get(str(row[0].get("level")), 99),
            str(row[0].get("metricName") or ""),
        ),
    )
    for ordinal, (group, issue) in enumerate(ordered, start=1):
        query = str(issue.get("query") or "未命名搜索词")
        tab = str(issue.get("tab") or "全部")
        blocks.append(f"""
<section class='issue-group'><header><div><b>{esc(query)}</b><span>{esc(tab)} Tab · 单个问题</span></div></header>
<div class='query-layout'><div>{evidence_html(issue_image(issue), f'{query}问题证据')}</div><div>{render_issue(issue, group, f"问题{ordinal}：{group.get('metricName') or '体验问题'}")}</div></div>
</section>""")
    return "".join(blocks) or "<div class='empty'>该业务本轮暂无待优化问题。</div>"


def render_by_metric(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    buckets: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for group, issue in entries:
        buckets[(str(group.get("level") or ""), str(group.get("metricName") or "体验问题"))].append((group, issue))
    blocks, ordinal = [], 0
    ordered = sorted(
        buckets.items(),
        key=lambda row: (min(PRIORITY_ORDER.get(priority(issue, group), 3) for group, issue in row[1]), DIMENSION_ORDER.get(row[0][0], 99), row[0][1]),
    )
    for (_, metric), items in ordered:
        first = items[0][0]
        rows = []
        for group, issue in sorted(items, key=lambda row: PRIORITY_ORDER.get(priority(row[1], row[0]), 3)):
            ordinal += 1
            query = str(issue.get("query") or "未命名搜索词")
            evidence = evidence_html(issue_image(issue), f"{query}问题证据")
            copy = render_issue(issue, group, f"问题{ordinal}：{query}")
            rows.append(f"<div class='metric-row'><div>{evidence}</div>{copy}</div>")
        blocks.append(f"<section class='issue-group metric-group'><header><div><b>{esc(metric)}</b><span class='level-tag'>{esc(first.get('levelName') or '评测维度')}</span></div><span>{len(items)} 个问题</span></header>{''.join(rows)}</section>")
    return "".join(blocks) or "<div class='empty'>该业务本轮暂无待优化问题。</div>"


def render_dashboard(data: dict[str, Any]) -> str:
    businesses = [item for item in data.get("businesses", []) if isinstance(item, dict) and item.get("businessCode")]
    groups = [item for item in data.get("groups", []) if isinstance(item, dict)]
    if not businesses:
        raise ValueError("治理数据集没有可展示的业务线")

    overview = make_summary(businesses, groups)
    batch = str(data.get("batch") or "当前批次")
    match = re.search(r"(\d+)词", batch)
    query_count = int(match.group(1)) if match else int(data.get("queryCount") or 0)
    evaluated = [name for code, name in DIMENSIONS if any(code in (item.get("dimensionScores") or {}) for item in businesses)]

    tabs = ["<button class='business-tab active' type='button' data-business='overview' aria-selected='true'>概览</button>"]
    cards, panels = [], []
    for business in businesses:
        code, name = str(business["businessCode"]), str(business.get("businessName") or business["businessCode"])
        summary = make_summary(businesses, groups, code)
        tabs.append(f"<button class='business-tab' type='button' data-business='{esc(code)}' aria-selected='false'>{esc(name)}</button>")
        priority_text = "".join(
            f"<span>P{level[1:]}问题 {summary['priorityCounts'].get(level, 0)}</span>"
            for level in ("P0", "P1", "P2")
        )
        cards.append(f"""<button class='business-card' type='button' data-target='{esc(code)}' aria-label='查看{esc(name)}问题明细'><div><h3>{esc(name)}</h3><span class='business-trend'>↗ {summary['tracking']['newIssueCount']}</span></div><strong>{len(summary['issues'])}<small>项</small></strong><i>{priority_text}</i></button>""")
        panels.append(f"""
<section class='panel business-panel' data-panel='{esc(code)}'>
  {render_summary(summary)}
  <div class='detail-heading'><h2>问题明细</h2><div class='detail-tabs' role='tablist' aria-label='{esc(name)}问题分组'><button class='detail-tab active' type='button' data-detail-tab='{esc(code)}-issue'>按问题</button><button class='detail-tab' type='button' data-detail-tab='{esc(code)}-query'>按搜索词</button><button class='detail-tab' type='button' data-detail-tab='{esc(code)}-metric'>按指标</button></div></div>
  <div class='detail-pane active' data-detail-pane='{esc(code)}-issue'>{render_by_issue(summary['issues'])}</div>
  <div class='detail-pane' data-detail-pane='{esc(code)}-query'>{render_by_query(summary['issues'])}</div>
  <div class='detail-pane' data-detail-pane='{esc(code)}-metric'>{render_by_metric(summary['issues'])}</div>
</section>""")

    return f"""<!doctype html>
<html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>大搜结果页体验评测看板</title><style>
:root{{--ink:#182230;--muted:#667085;--line:#e4e7ec;--bg:#f7f8fa;--blue:#2563eb;--blue-soft:#eff6ff;--p0:#dc2626;--p1:#d97706;--p2:#059669}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif}}button{{font:inherit}}button:focus-visible,a:focus-visible{{outline:3px solid rgba(37,99,235,.35);outline-offset:2px}}.topbar{{height:56px;background:#fff;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 max(24px,calc((100vw - 1280px)/2));position:sticky;top:0;z-index:5}}.brand{{font-weight:800;font-size:16px;letter-spacing:.04em}}.top-links{{display:flex;gap:28px}}.top-links a,.top-links a:last-child{{color:#475467;text-decoration:none;font-size:13px;font-weight:500}}.page{{max-width:1280px;margin:auto;padding:32px 24px 72px}}.report-head{{padding:0;margin-bottom:12px}}.head-row{{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}}h1{{margin:0 0 12px;font-size:26px;letter-spacing:-.04em}}.subtitle{{margin:0 0 22px;color:var(--muted);font-size:13px}}.subtitle a{{color:var(--blue);text-decoration:none}}.period-select{{appearance:none;background:#fff;border:1px solid #d0d5dd;border-radius:8px;padding:8px 34px 8px 12px;color:#344054;font-size:13px}}.business-tabs{{display:flex;gap:24px;flex-wrap:wrap;margin:0 0 24px;border-bottom:1px solid var(--line)}}.business-tab{{border:0;border-bottom:2px solid transparent;background:transparent;color:#475467;padding:8px 0 10px;cursor:pointer;font-weight:600;font-size:13px;transition:.18s}}.business-tab:hover{{color:var(--blue)}}.business-tab.active{{border-color:var(--blue);color:var(--blue)}}.panel{{display:none}}.panel.active{{display:block}}.stat-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;margin-bottom:32px}}.stat-card{{min-height:170px;background:#fff;border:0;border-radius:8px;padding:24px;box-shadow:0 10px 28px rgba(16,24,40,.08)}}.stat-card p{{margin:0 0 12px;color:#475467;font-size:16px;font-weight:650}}.stat-card strong{{display:block;color:#dc2626;font-size:48px;line-height:1;font-weight:650;letter-spacing:-.05em;margin-bottom:22px}}.stat-card strong small{{margin-left:4px;font-size:15px;font-weight:500;letter-spacing:0}}.stat-text{{display:flex;gap:16px;flex-wrap:wrap;color:var(--blue);font-size:12px;font-weight:450}}.dimension-text{{color:var(--blue)}}.cumulative-text{{font-weight:450}}.cumulative-text.added{{color:#dc2626}}.cumulative-text.resolved{{color:#059669}}.priority-chip,.new-badge,.level-tag{{display:inline-flex;align-items:center;border-radius:999px;padding:4px 8px;font-size:11px;font-weight:650}}.priority-chip.p0{{background:#fef2f2;color:var(--p0)}}.priority-chip.p1{{background:#fffbeb;color:var(--p1)}}.priority-chip.p2{{background:#ecfdf3;color:var(--p2)}}.section-heading,.detail-heading{{display:flex;align-items:center;justify-content:space-between;gap:20px;margin:10px 0 16px}}h2{{font-size:18px;margin:0}}.overview-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px}}.business-card{{min-height:170px;background:#fff;border:0;border-radius:8px;padding:22px;text-align:left;cursor:pointer;box-shadow:0 8px 22px rgba(16,24,40,.06);transition:box-shadow .18s,transform .18s}}.business-card:hover{{box-shadow:0 12px 28px rgba(16,24,40,.11);transform:translateY(-2px)}}.business-card>div{{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:12px}}.business-card h3{{margin:0;color:#475467;font-size:16px}}.business-trend{{color:#dc2626;font-size:12px;font-weight:450}}.business-card>span{{display:block;color:var(--muted);font-size:12px}}.business-card strong{{display:block;color:var(--blue);font-size:40px;line-height:1;margin:12px 0 20px}}.business-card strong small{{margin-left:3px;font-size:14px;font-weight:500}}.business-card i{{display:flex;gap:16px;color:#667085;font-size:11px;font-style:normal;font-weight:450}}.business-card i span{{white-space:nowrap}}.detail-heading{{padding-bottom:12px;border-bottom:1px solid var(--line);margin-top:38px}}.detail-tabs{{display:flex;gap:16px;align-self:stretch}}.detail-tab{{border:0;border-bottom:2px solid transparent;background:transparent;color:var(--muted);padding:7px 2px;cursor:pointer;font-weight:600}}.detail-tab.active{{color:var(--ink);border-color:var(--ink)}}.detail-pane{{display:none}}.detail-pane.active{{display:block}}.issue-group{{background:#fff;border:1px solid var(--line);border-radius:8px;overflow:hidden;margin-bottom:16px}}.issue-group>header{{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 18px;background:#fcfcfd;border-bottom:1px solid var(--line);color:var(--muted);font-size:12px}}.issue-group header b{{margin-right:8px;color:var(--ink);font-size:15px}}.level-tag{{background:#f2f4f7;color:#475467}}.query-layout,.metric-row{{display:grid;grid-template-columns:240px minmax(0,1fr);gap:20px;padding:18px}}.metric-row+.metric-row{{border-top:1px solid var(--line)}}.evidence-link{{display:block;overflow:hidden;border-radius:8px;border:1px solid #d0d5dd;background:#f2f4f7}}.evidence-link img{{display:block;width:100%;height:auto;transition:transform .18s}}.evidence-link:hover img{{transform:scale(1.02)}}.evidence-empty{{display:grid;min-height:150px;place-items:center;border:1px dashed #d0d5dd;border-radius:8px;color:var(--muted);font-size:12px}}.issue-copy{{padding:0 0 14px}}.issue-copy+.issue-copy{{padding-top:14px;border-top:1px solid #eaecf0}}.issue-heading{{display:flex;gap:10px;align-items:center}}.issue-heading h4{{margin:0;flex:1;font-size:14px}}.issue-target{{margin:7px 0 3px;color:#475467;font-size:12px}}.issue-description{{margin:6px 0 10px;color:#344054}}.recommendation{{border-left:3px solid #f59e0b;background:#fffbeb;border-radius:0 6px 6px 0;padding:9px 11px;color:#854d0e;font-size:12px}}.recommendation p{{margin:3px 0 0}}.empty{{padding:36px;background:#fff;border:1px dashed #d0d5dd;border-radius:8px;text-align:center;color:var(--muted)}}@media(max-width:980px){{.overview-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:850px){{.stat-grid{{grid-template-columns:1fr 1fr}}.query-layout,.metric-row{{grid-template-columns:1fr}}}}@media(max-width:580px){{.page{{padding:20px 14px}}.topbar{{padding:0 14px}}.top-links{{gap:14px}}.head-row{{display:block}}.period-select{{margin-bottom:18px}}.stat-grid,.overview-grid{{grid-template-columns:1fr}}.detail-heading{{align-items:flex-start;flex-direction:column}}h1{{font-size:22px}}}}
</style></head><body>
<nav class='topbar'><div class='brand'>搜索</div><div class='top-links'><a href='https://km.sankuai.com/collabpage/2771507978' target='_blank' rel='noopener'>白皮书</a><a href='https://km.sankuai.com/collabpage/2770196684' target='_blank' rel='noopener'>体验标准</a><a href='#details' aria-current='page'>体验评测</a></div></nav>
<main class='page' id='details'><header class='report-head'><div class='head-row'><div><h1>大搜结果页体验评测看板</h1><p class='subtitle'>评测日期：{esc(data.get('generatedAt') or '—')}　|　评测范围：{query_count} 个搜索词、{esc(' / '.join(evaluated) or '未执行维度')}　<a href='https://km.sankuai.com/collabpage/2772784557' target='_blank' rel='noopener'>详情</a></p></div><select class='period-select' aria-label='评测批次'><option>{esc(batch)}</option></select></div></header><nav class='business-tabs' role='tablist'>{''.join(tabs)}</nav><section class='panel active' data-panel='overview'>{render_summary(overview)}<div class='section-heading'><h2>问题明细</h2></div><div class='overview-grid'>{''.join(cards)}</div></section>{''.join(panels)}</main>
<script>
const tabs=[...document.querySelectorAll('.business-tab')],panels=[...document.querySelectorAll('.panel')];function activateBusiness(code){{tabs.forEach(tab=>{{const active=tab.dataset.business===code;tab.classList.toggle('active',active);tab.setAttribute('aria-selected',String(active))}});panels.forEach(panel=>panel.classList.toggle('active',panel.dataset.panel===code));if(code!=='overview')document.querySelector('.report-head').scrollIntoView({{behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'}})}}tabs.forEach(tab=>tab.addEventListener('click',()=>activateBusiness(tab.dataset.business)));document.querySelectorAll('.business-card').forEach(card=>card.addEventListener('click',()=>activateBusiness(card.dataset.target)));document.querySelectorAll('.detail-tab').forEach(tab=>tab.addEventListener('click',()=>{{const panel=tab.closest('.business-panel'),target=tab.dataset.detailTab;panel.querySelectorAll('.detail-tab').forEach(item=>item.classList.toggle('active',item===tab));panel.querySelectorAll('.detail-pane').forEach(item=>item.classList.toggle('active',item.dataset.detailPane===target))}}));
</script></body></html>"""
