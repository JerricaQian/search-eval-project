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
LEVEL_META = {
    "element": ("单一元素", "#2563EB"),
    "component": ("组件/卡片", "#0E9384"),
    "page": ("页面框架", "#667085"),
}
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


def donut(slices: list[tuple[str, int, str]], label: str) -> str:
    total = sum(value for _, value, _ in slices)
    if not total:
        paths = "<circle cx='50' cy='50' r='40' fill='none' stroke='#F2F4F7' stroke-width='16'/>"
    else:
        circumference, offset, paths = 251.327, 0.0, []
        for name, value, color in slices:
            length = value / total * circumference
            paths.append(
                f"<circle cx='50' cy='50' r='40' fill='none' stroke='{color}' stroke-width='16' "
                f"stroke-dasharray='{length} {circumference - length}' "
                f"transform='rotate({offset / circumference * 360 - 90} 50 50)'><title>"
                f"{esc(name)} {value} 项（占 {value / total * 100:.1f}%）</title></circle>"
            )
            offset += length
        paths = "".join(paths)
    legend = "".join(
        f"<div class='legend'><i style='background:{color}'></i><span>{esc(name)}</span><b>{value}</b></div>"
        for name, value, color in slices
    )
    return f"<div class='donut-block'><svg viewBox='0 0 100 100' role='img' aria-label='{esc(label)}'>{paths}</svg><div class='legend-list'>{legend}</div></div>"


def render_summary(summary: dict[str, Any]) -> str:
    rows = summary["issues"]
    issue_count = len(rows)
    priorities = Counter(priority(issue, group) for group, issue in rows)
    metrics = Counter(str(group.get("metricName") or "体验问题") for group, _ in rows)
    top = metrics.most_common(3)
    other = issue_count - sum(value for _, value in top)
    top_slices = [
        (name, value, color)
        for (name, value), color in zip(top, ("rgba(217,45,32,.55)", "rgba(220,104,3,.55)", "rgba(37,99,235,.55)"))
    ]
    if other:
        top_slices.append(("其他", other, "#E4E7EC"))
    tracking = summary["tracking"]
    return f"""<section class='stats-section'><h2>问题统计</h2><article class='summary-card'><div class='summary-numbers'>
<div><b>{issue_count}</b><span>累计问题</span></div><div><b>{tracking['newIssueCount']}</b><span>本月新增</span></div><div><b>{tracking['resolvedIssueCount']}</b><span>累计解决</span></div>
</div><div class='summary-divider'></div>{donut([('P0问题', priorities['P0'], 'rgba(217,45,32,.55)'), ('P1问题', priorities['P1'], 'rgba(220,104,3,.55)'), ('P2问题', priorities['P2'], 'rgba(37,99,235,.55)')], 'P0/P1/P2 问题占比')}<div class='summary-divider'></div>{donut(top_slices, 'TOP 问题占比')}</article></section>"""


def render_issue(issue: dict[str, Any], group: dict[str, Any], number: int, title: str | None = None) -> str:
    level, color = LEVEL_META.get(str(group.get("level") or ""), (str(group.get("levelName") or "未标注层级"), "#667085"))
    label = title or f"问题{number}：{group.get('metricName') or '体验问题'}"
    return f"""<div class='issue-copy'><div class='issue-title'><span class='priority'>{priority(issue, group)}</span><h3>{esc(label)}</h3></div><dl>
<div><dt>所属搜索词</dt><dd>{esc(issue.get('query') or '-')}</dd></div><div><dt>层级</dt><dd style='color:{color}'>{esc(level)}</dd></div><div><dt>对象定位</dt><dd>{esc(issue_target(issue))}</dd></div><div><dt>问题描述</dt><dd>{esc(finding_text(issue))}</dd></div><div><dt>优化建议</dt><dd>{esc(recommendation_text(issue))}</dd></div></dl></div>"""


def ordered(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return sorted(entries, key=lambda row: (PRIORITY_ORDER.get(priority(row[1], row[0]), 3), str(row[1].get("query") or ""), str(row[0].get("metricName") or "")))


def render_by_issue(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    return "".join(
        f"<article class='issue-card'><div class='issue-layout'><div>{evidence_html(issue_image(issue), '问题证据')}</div>{render_issue(issue, group, number)}</div></article>"
        for number, (group, issue) in enumerate(ordered(entries), 1)
    ) or "<div class='empty'>该业务暂无问题。</div>"


def render_by_query(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    buckets: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for group, issue in entries:
        buckets[(str(issue.get("query") or "未命名搜索词"), str(issue.get("tab") or "全部"))].append((group, issue))
    blocks, number = [], 0
    for (query, tab), items in sorted(buckets.items()):
        items = ordered(items)
        image = next((issue_image(issue) for _, issue in items if issue_image(issue)), "")
        copies = []
        for group, issue in items:
            number += 1
            copies.append(render_issue(issue, group, number))
        blocks.append(f"<article class='issue-card'><div class='issue-layout'><div>{evidence_html(image, query + ' 证据')}</div><div><h3 class='group-title'>{esc(query)} <small>{esc(tab)} Tab · {len(items)} 条问题</small></h3>{''.join(copies)}</div></div></article>")
    return "".join(blocks) or "<div class='empty'>该业务暂无问题。</div>"


def render_by_metric(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    buckets: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for group, issue in entries:
        buckets[(str(group.get("level") or ""), str(group.get("metricName") or "体验问题"))].append((group, issue))
    blocks, number = [], 0
    for (level, metric), items in sorted(buckets.items()):
        level_name, color = LEVEL_META.get(level, ("未标注层级", "#667085"))
        rows = []
        for group, issue in ordered(items):
            number += 1
            query = str(issue.get("query") or "未命名搜索词")
            title = f"问题{number}：{query}"
            rows.append(f"<div class='metric-row'><div>{evidence_html(issue_image(issue), '问题证据')}</div>{render_issue(issue, group, number, title)}</div>")
        blocks.append(f"<article class='issue-card'><h3 class='group-title'>{esc(metric)} <small style='color:{color}'>{esc(level_name)} · {len(items)} 条问题</small></h3>{''.join(rows)}</article>")
    return "".join(blocks) or "<div class='empty'>该业务暂无问题。</div>"


def render_dashboard(data: dict[str, Any]) -> str:
    businesses = [item for item in data.get("businesses", []) if isinstance(item, dict) and item.get("businessCode")]
    groups = [item for item in data.get("groups", []) if isinstance(item, dict)]
    if not businesses:
        raise ValueError("治理数据集没有可展示的业务线")

    overview = make_summary(businesses, groups)
    batch = str(data.get("batch") or "当前批次")
    tabs = ["<button class='business-tab active' type='button' data-business='overview' aria-selected='true'>概览</button>"]
    cards, panels = [], []
    for business in businesses:
        code, name = str(business["businessCode"]), str(business.get("businessName") or business["businessCode"])
        summary = make_summary(businesses, groups, code)
        tabs.append(f"<button class='business-tab' type='button' data-business='{esc(code)}' aria-selected='false'>{esc(name)}</button>")
        priorities = summary["priorityCounts"]
        cards.append(f"<button class='business-card' type='button' data-target='{esc(code)}' aria-label='查看{esc(name)}问题明细'><div><h3>{esc(name)}</h3><b>新增 {summary['tracking']['newIssueCount']}</b></div><strong>{len(summary['issues'])} <small>累计问题</small></strong><p><span>P0 {priorities['P0']}</span><span>P1 {priorities['P1']}</span><span>P2 {priorities['P2']}</span></p></button>")
        panels.append(f"<section class='panel business-panel' data-panel='{esc(code)}'>{render_summary(summary)}<div class='detail-heading'><h2>问题明细</h2><div class='detail-tabs' role='tablist' aria-label='{esc(name)}问题分组'><button class='detail-tab active' type='button' data-detail-tab='{esc(code)}-issue'>按问题</button><button class='detail-tab' type='button' data-detail-tab='{esc(code)}-query'>按搜索词</button><button class='detail-tab' type='button' data-detail-tab='{esc(code)}-metric'>按指标</button></div></div><div class='detail-pane active' data-detail-pane='{esc(code)}-issue'>{render_by_issue(summary['issues'])}</div><div class='detail-pane' data-detail-pane='{esc(code)}-query'>{render_by_query(summary['issues'])}</div><div class='detail-pane' data-detail-pane='{esc(code)}-metric'>{render_by_metric(summary['issues'])}</div></section>")

    scope = " / ".join(sorted({LEVEL_META.get(str(group.get("level") or ""), ("其他维度", ""))[0] for group in groups}))
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>大搜结果页体验评测看板</title><style>
:root{{--bg:#f7f8fa;--ink:#182230;--second:#475467;--muted:#667085;--line:#eaecf0;--blue:#2563eb}}*{{box-sizing:border-box}}html{{scroll-padding-top:56px}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei','Helvetica Neue',Arial,sans-serif}}button{{font:inherit}}button:focus-visible,a:focus-visible,select:focus-visible{{outline:3px solid rgba(37,99,235,.45);outline-offset:2px}}.page{{max-width:1180px;margin:0 auto;padding:40px 32px 48px}}.head{{display:flex;justify-content:space-between;gap:24px;flex-wrap:wrap;margin-bottom:20px}}h1{{margin:0;font-size:28px;line-height:36px;font-weight:600}}.sub{{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 0;color:var(--muted);font-size:14px}}.sub i{{font-style:normal;color:#d0d5dd}}.sub a{{color:var(--blue);font-weight:500;text-decoration:none}}select{{width:280px;height:44px;border:1px solid #d0d5dd;border-radius:8px;background:#fff;padding:0 12px;color:var(--second)}}.business-tabs{{position:sticky;top:0;z-index:5;display:flex;gap:24px;margin:0 -32px 28px;padding:12px 32px;background:var(--bg);border-bottom:1px solid var(--line)}}.business-tab,.detail-tab{{position:relative;min-height:44px;padding:0 0 12px;border:0;background:none;color:var(--second);font-size:14px;cursor:pointer}}.business-tab.active,.detail-tab.active{{color:var(--blue);font-weight:600}}.business-tab.active:after,.detail-tab.active:after{{position:absolute;right:0;bottom:-1px;left:0;height:2px;background:var(--blue);content:''}}.panel{{display:none}}.panel.active{{display:block}}h2{{margin:0 0 12px;font-size:18px;line-height:28px;font-weight:600}}.summary-card,.business-card,.issue-card{{border:0;border-radius:12px;background:#fff;box-shadow:0 2px 8px rgba(16,24,40,.06)}}.summary-card{{display:flex;align-items:center;gap:32px;min-height:160px;padding:20px 24px;flex-wrap:wrap}}.summary-numbers{{display:flex;gap:24px;flex:1;min-width:240px}}.summary-numbers div{{display:flex;min-width:72px;flex:1;flex-direction:column;gap:6px}}.summary-numbers b{{font-size:36px;line-height:44px;font-weight:600;color:var(--ink)}}.summary-numbers span{{font-size:13px;line-height:18px;color:var(--muted)}}.summary-divider{{align-self:stretch;width:1px;background:var(--line)}}.donut-block{{display:flex;align-items:center;gap:16px}}.donut-block svg{{width:120px;height:120px}}.legend-list{{display:flex;flex-direction:column;gap:8px}}.legend{{display:flex;align-items:center;gap:8px;color:var(--second);font-size:13px;line-height:18px}}.legend i{{width:10px;height:10px;border-radius:50%}}.legend b{{color:var(--ink)}}.stats-section{{margin-bottom:20px}}.overview-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}}.business-card{{min-height:170px;padding:16px 20px;text-align:left;cursor:pointer}}.business-card>div{{display:flex;justify-content:space-between;gap:8px}}.business-card h3{{margin:0;color:var(--ink);font-size:16px;font-weight:500}}.business-card>div b{{font-size:13px;font-weight:600}}.business-card strong{{display:block;margin-top:10px;font-size:28px;line-height:34px;font-weight:600}}.business-card strong small{{font-size:13px;font-weight:400;color:var(--muted)}}.business-card p{{display:flex;gap:8px;margin:14px 0 0}}.business-card p span{{padding:2px 10px;border:1px solid var(--line);border-radius:4px;background:#f2f4f7;color:var(--second);font-size:12px;line-height:18px}}.detail-heading{{display:flex;justify-content:space-between;align-items:center;margin:24px 0 20px;border-bottom:1px solid var(--line)}}.detail-heading h2{{margin:0;padding-bottom:12px}}.detail-tabs{{display:flex;gap:24px}}.detail-pane{{display:none}}.detail-pane.active{{display:block}}.issue-card{{margin-bottom:16px;padding:20px}}.issue-layout,.metric-row{{display:grid;grid-template-columns:240px minmax(0,1fr);gap:20px;align-items:start}}.metric-row+.metric-row{{margin-top:16px;padding-top:16px;border-top:1px solid var(--line)}}.evidence-link,.evidence-link img,.evidence-empty{{display:block;width:240px;height:180px;border-radius:8px}}.evidence-link{{overflow:hidden;background:#f2f4f7}}.evidence-link img{{object-fit:cover;object-position:top}}.evidence-empty{{display:flex;align-items:center;justify-content:center;background:#f2f4f7;color:var(--muted);font-size:13px}}.issue-title{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}.issue-title h3,.group-title{{margin:0;color:var(--ink);font-size:16px;line-height:24px;font-weight:600}}.priority{{padding:2px 8px;border-radius:4px;background:#f2f4f7;color:var(--second);font-size:12px;font-weight:600}}dl{{display:grid;grid-template-columns:auto 1fr;column-gap:8px;row-gap:6px;margin:12px 0 0;font-size:14px;line-height:22px}}dt{{color:var(--muted)}}dd{{margin:0;color:var(--second)}}.issue-copy+.issue-copy{{margin-top:12px;padding-top:12px;border-top:1px solid var(--line)}}.group-title{{margin-bottom:12px}}.group-title small{{margin-left:8px;color:var(--muted);font-size:13px;font-weight:400}}.empty{{padding:36px;border-radius:12px;background:#fff;color:var(--muted);text-align:center}}@media(max-width:900px){{.overview-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:720px){{.page{{padding:24px 16px}}.business-tabs{{margin:0 -16px 28px;padding:12px 16px;overflow:auto}}.summary-divider{{display:none}}.overview-grid{{grid-template-columns:1fr}}.issue-layout,.metric-row{{grid-template-columns:1fr}}select{{width:100%}}.detail-heading{{align-items:flex-start;flex-direction:column}}}}
</style></head><body><main class='page'><header class='head'><div><h1>大搜结果页体验评测看板</h1><p class='sub'><span>评测日期：{esc(data.get('generatedAt') or '—')}</span><i>/</i><span>评测范围：{int(data.get('queryCount') or 0)} 个搜索词、{esc(scope)}</span><a href='https://km.sankuai.com/collabpage/2772784557' target='_blank' rel='noopener'>详情</a></p></div><select aria-label='评测批次'><option>{esc(batch)}</option></select></header><nav class='business-tabs' role='tablist'>{''.join(tabs)}</nav><section class='panel active' data-panel='overview'>{render_summary(overview)}<section><h2>问题明细</h2><div class='overview-grid'>{''.join(cards)}</div></section></section>{''.join(panels)}</main><script>const tabs=[...document.querySelectorAll('.business-tab')],panels=[...document.querySelectorAll('.panel')];tabs.forEach(tab=>tab.addEventListener('click',()=>{{tabs.forEach(item=>{{const active=item===tab;item.classList.toggle('active',active);item.setAttribute('aria-selected',String(active))}});panels.forEach(panel=>panel.classList.toggle('active',panel.dataset.panel===tab.dataset.business))}}));document.querySelectorAll('.business-card').forEach(card=>card.addEventListener('click',()=>document.querySelector(`[data-business="${{card.dataset.target}}"]`).click()));document.querySelectorAll('.detail-tab').forEach(tab=>tab.addEventListener('click',()=>{{const section=tab.closest('.business-panel'),target=tab.dataset.detailTab;section.querySelectorAll('.detail-tab').forEach(item=>item.classList.toggle('active',item===tab));section.querySelectorAll('.detail-pane').forEach(item=>item.classList.toggle('active',item.dataset.detailPane===target))}}));</script></body></html>"""
