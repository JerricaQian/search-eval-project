#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the V2 search experience report from an accepted governance dataset.

This is a preview-only renderer. It deliberately does not replace the V1
production generator or alter evaluation facts, scores, evidence, or datasets.
"""
from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DIMENSIONS = (
    ("element", "单一元素"),
    ("component", "组件/卡片"),
    ("page", "页面框架"),
)
PROBLEM_RATINGS = {"达标", "不达标", "🟡", "🔴"}


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("治理数据集顶层必须是对象")
    return data


def esc(value: Any) -> str:
    return html.escape(str(value or ""))


def score(value: Any) -> str:
    return "—" if value is None else f"{float(value):.1f}"


def metric_title(group: dict[str, Any]) -> str:
    return str(group.get("metricName") or "体验问题").replace("（页面框架完整性）", "")


def priority(issue: dict[str, Any], group: dict[str, Any]) -> str:
    value = str(issue.get("priority") or group.get("priority") or "P2")
    return value if value in {"P0", "P1", "P2"} else "P2"


def normalize_sentence(value: Any) -> str:
    """Normalize upstream prose before composing the fixed report narrative."""
    return str(value or "").strip().rstrip("。！？!?；;，,")


def issue_description(issue: dict[str, Any], group: dict[str, Any]) -> str:
    """Render an unlabeled, consistent fact → basis → impact narrative."""
    finding = issue.get("finding") if isinstance(issue.get("finding"), dict) else {}
    required = ("observableFact", "ruleOrThreshold", "verdictReason", "userImpact")
    missing = [key for key in required if not normalize_sentence(finding.get(key))]
    if missing:
        target = issue.get("elementId") or issue.get("cardId") or issue.get("query") or "未命名问题"
        raise ValueError(f"问题 {target} 缺少三段式结论字段：{','.join(missing)}")
    fact = normalize_sentence(finding["observableFact"])
    rule = normalize_sentence(finding["ruleOrThreshold"])
    verdict = normalize_sentence(finding["verdictReason"])
    impact = normalize_sentence(finding["userImpact"])
    return f"{fact}。{rule}，{verdict}。{impact}。"


def issue_recommendation(issue: dict[str, Any]) -> str:
    recommendation = str(issue.get("recommendation") or "").strip()
    if not recommendation:
        target = issue.get("elementId") or issue.get("cardId") or issue.get("query") or "未命名问题"
        raise ValueError(f"问题 {target} 缺少问题级个性化优化建议")
    return recommendation


def build_scope_summary(business: dict[str, Any], groups: list[dict[str, Any]]) -> dict[str, Any]:
    dimension_scores = business.get("dimensionScores") if isinstance(business.get("dimensionScores"), dict) else {}
    scoped_groups = [group for group in groups if group.get("businessCode") == business.get("businessCode")]
    issue_count_by_level: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()
    for group in scoped_groups:
        for item in group.get("evidence", []):
            if not isinstance(item, dict):
                continue
            issue_count_by_level[str(group.get("level") or "")] += 1
            priority_counts[priority(item, group)] += 1
    return {
        "overall": business.get("overallScore"),
        "dimensionScores": dimension_scores,
        "issueCounts": issue_count_by_level,
        "priorityCounts": priority_counts,
        "issueTotal": sum(issue_count_by_level.values()),
        "groups": scoped_groups,
    }


def render_score_panel(summary: dict[str, Any]) -> str:
    dimension_scores = summary["dimensionScores"]
    score_rows = "".join(
        f"<div class='dimension-row'><span>{name}</span><b>{score(dimension_scores.get(code))}</b></div>"
        for code, name in DIMENSIONS
    )
    issue_rows = "".join(
        "<div class='dimension-row'><span>{name}</span><b>{count}</b>"
        "<em>P0-{p0}，P1-{p1}</em></div>".format(
            name=name,
            count=summary["issueCounts"].get(code, 0),
            p0=summary["priorityCounts"].get("P0", 0),
            p1=summary["priorityCounts"].get("P1", 0),
        )
        for code, name in DIMENSIONS
    )
    return """
<section class='summary-card'>
  <div class='summary-block score-block'>
    <div class='summary-primary'><div class='summary-kicker'>评测总分</div><div class='summary-main'>{overall}</div></div>
    <div class='dimension-list'>{score_rows}</div>
  </div>
  <div class='summary-divider'></div>
  <div class='summary-block issue-block'>
    <div class='summary-primary'><div class='summary-kicker'>问题发现</div><div class='summary-main'>{issues}</div></div>
    <div class='dimension-list'>{issue_rows}</div>
  </div>
</section>""".format(
        overall=score(summary["overall"]),
        issues=summary["issueTotal"],
        score_rows=score_rows,
        issue_rows=issue_rows,
    )


DIMENSION_ORDER = {"component": 0, "page": 1, "element": 2}


def issue_image_path(issue: dict[str, Any]) -> str:
    return str(issue.get("evidenceImage") or issue.get("screenshot") or "")


def render_issue_cards(groups: list[dict[str, Any]]) -> str:
    """Render one evidence image per query, with its issues ordered by dimension."""
    grouped: dict[tuple[str, str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for group in groups:
        for issue in group.get("evidence", []):
            if not isinstance(issue, dict) or str(issue.get("rating", "")) not in PROBLEM_RATINGS:
                continue
            screenshot = str(issue.get("screenshot") or issue_image_path(issue))
            key = (str(issue.get("query") or "未命名搜索词"), str(issue.get("tab") or "全部"), screenshot)
            grouped[key].append((group, issue))

    blocks: list[str] = []
    ordinal = 0
    for (query, tab, _), entries in grouped.items():
        entries.sort(key=lambda item: (DIMENSION_ORDER.get(str(item[0].get("level")), 99), metric_title(item[0]), str(item[1].get("cardId") or "")))
        image_path = next((issue_image_path(issue) for _, issue in entries if issue_image_path(issue)), "")
        if image_path:
            evidence = (
                "<a class='evidence-link' href='file://{path}' target='_blank' rel='noopener'>"
                "<img loading='lazy' src='file://{path}' alt='{alt}'></a>"
            ).format(path=esc(image_path), alt=esc(f"{query}问题证据"))
        else:
            evidence = "<div class='evidence-empty'>暂无截图证据</div>"

        issue_rows: list[str] = []
        current_level = None
        for group, issue in entries:
            level = str(group.get("level") or "")
            if level != current_level:
                current_level = level
                issue_rows.append("<h3 class='dimension-title'>{level}</h3>".format(
                    level=esc(group.get("levelName") or "评测维度")
                ))
            ordinal += 1
            issue_rows.append("""
<article class='issue-item'>
  <div class='issue-heading'><h4>问题{ordinal}：{metric}</h4><span class='tag'>{priority}</span></div>
  <p class='issue-description'>{description}</p>
  <div class='recommendation'><b>优化建议</b><p>{recommendation}</p></div>
</article>""".format(
                ordinal=ordinal,
                metric=esc(metric_title(group)),
                priority=esc(priority(issue, group)),
                description=esc(issue_description(issue, group)),
                recommendation=esc(issue_recommendation(issue)),
            ))
        blocks.append("""
<section class='query-issue-group'>
  <header class='query-issue-header'><h3>{query}</h3><em>{count} 个问题</em></header>
  <div class='query-issue-content'><div class='issue-evidence'>{evidence}</div><div class='issue-copy'>{issues}</div></div>
</section>""".format(query=esc(query), count=len(entries), evidence=evidence, issues="".join(issue_rows)))
    return "".join(blocks) or "<div class='empty'>当前业务没有待优化问题。</div>"


def render_html(data: dict[str, Any], period: str) -> str:
    businesses = [item for item in data.get("businesses", []) if isinstance(item, dict) and item.get("businessCode")]
    groups = [item for item in data.get("groups", []) if isinstance(item, dict)]
    if not businesses:
        raise ValueError("治理数据集没有可展示的业务线")

    overall_scores: dict[str, list[float]] = defaultdict(list)
    all_issue_levels: Counter[str] = Counter()
    all_priorities: Counter[str] = Counter()
    for business in businesses:
        for code, value in (business.get("dimensionScores") or {}).items():
            if isinstance(value, (int, float)):
                overall_scores[str(code)].append(float(value))
    for group in groups:
        for issue in group.get("evidence", []):
            if isinstance(issue, dict):
                all_issue_levels[str(group.get("level") or "")] += 1
                all_priorities[priority(issue, group)] += 1
    overview_summary = {
        "overall": round(sum(item.get("overallScore", 0) for item in businesses) / len(businesses), 1),
        "dimensionScores": {code: round(sum(values) / len(values), 1) for code, values in overall_scores.items() if values},
        "issueCounts": all_issue_levels,
        "priorityCounts": all_priorities,
        "issueTotal": sum(all_issue_levels.values()),
    }

    tabs = ["<button class='business-tab active' data-business='overview'>概览</button>"] + [
        "<button class='business-tab' data-business='{code}'>{name}</button>".format(
            code=esc(item["businessCode"]), name=esc(item.get("businessName") or item["businessCode"])
        ) for item in businesses
    ]
    business_cards = "".join(
        "<button class='business-card' data-target='{code}'><span>{name}</span><b>{score}</b><em>问题发现 {issues}</em></button>".format(
            code=esc(item["businessCode"]), name=esc(item.get("businessName") or item["businessCode"]),
            score=score(item.get("overallScore")), issues=item.get("issueCount", 0),
        ) for item in businesses
    )
    business_panels = []
    for item in businesses:
        summary = build_scope_summary(item, groups)
        business_panels.append("""
<section class='panel business-panel' data-panel='{code}'>
  {summary}
  <h2 class='section-title'>问题明细</h2>
  <div class='issue-grid'>{issues}</div>
</section>""".format(code=esc(item["businessCode"]), summary=render_score_panel(summary), issues=render_issue_cards(summary["groups"])))

    return """<!doctype html>
<html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>搜索结果页体验评测报告</title>
<style>
:root{{--indigo:#6366f1;--green:#10b981;--blue:#60a5fa;--ink:#172033;--muted:#64748b;--line:#e0e7ff;--paper:rgba(255,255,255,.9);--soft:#f8fafc}}*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(135deg,#e8eaf6 0%,#ede9fe 35%,#dbeafe 68%,#e0f2fe 100%);color:var(--ink);font:14px -apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;min-height:100vh}}.topbar{{height:48px;background:#111;color:#fff;display:flex;align-items:center;justify-content:space-between;padding:0 max(24px,calc((100vw - 1240px)/2));font-size:13px}}.brand{{font-weight:700;letter-spacing:.4px}}.top-links{{display:flex;gap:26px}}.top-links a{{color:#fff;text-decoration:none;opacity:.82}}.top-links a:hover{{opacity:1}}.page{{max-width:1440px;margin:0 auto;padding:30px 24px 56px}}.report-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:30px;margin:22px 0 0;padding:28px 30px;background:linear-gradient(135deg,#f5f3ff,#eff6ff);border:1px solid rgba(255,255,255,.8);border-radius:24px;box-shadow:0 18px 40px rgba(71,85,105,.12)}}h1{{margin:0;font-size:30px;line-height:1.25;letter-spacing:-.8px}}.subtitle{{margin:9px 0 0;color:var(--muted);font-size:13px}}.subtitle a{{color:#333;text-underline-offset:3px}}.period-select{{appearance:none;border:1px solid #d5d5d5;border-radius:4px;background:#fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14'%3E%3Cpath d='M3 5l4 4 4-4' fill='none' stroke='%23666' stroke-width='1.5'/%3E%3C/svg%3E") no-repeat right 11px center;padding:9px 34px 9px 12px;color:#222;font-size:14px}}.business-tabs{{display:flex;gap:26px;border-bottom:1px solid var(--line);overflow:auto;white-space:nowrap}}.business-tab{{position:relative;border:0;background:transparent;padding:14px 0;color:#777;font:inherit;cursor:pointer}}.business-tab.active{{color:#111;font-weight:700}}.business-tab.active:after{{position:absolute;left:0;right:0;bottom:-1px;height:2px;background:#111;content:''}}.panel{{display:none;padding-top:28px}}.panel.active{{display:block}}.summary-card{{display:grid;grid-template-columns:1fr 1px 1fr;align-items:stretch;border:1px solid var(--line);border-radius:4px;background:#fff;min-height:180px}}.summary-block{{display:grid;grid-template-columns:150px minmax(0,1fr);align-self:stretch;align-items:start;padding:27px 32px;column-gap:24px}}.summary-divider{{align-self:stretch;background:var(--line);margin:20px 0}}.summary-primary{{display:flex;flex-direction:column;justify-content:flex-start;align-self:start;gap:12px}}.summary-kicker{{color:#444;font-size:15px}}.summary-main{{font-size:48px;font-weight:700;line-height:1;letter-spacing:-2px}}.dimension-list{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-self:start;gap:14px 24px;align-content:start}}.dimension-row{{display:grid;grid-template-columns:auto auto;gap:8px;align-items:baseline;color:#666;font-size:13px}}.dimension-row b{{color:#111;font-size:17px}}.dimension-row em{{grid-column:1 / span 2;color:#8a8a8a;font-style:normal;font-size:12px}}.overview-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-top:24px}}.business-card{{border:1px solid var(--line);border-radius:4px;background:#fff;text-align:left;padding:18px;cursor:pointer;transition:border-color .18s,background .18s}}.business-card:hover{{border-color:#111;background:#fafafa}}.business-card span,.business-card em{{display:block;font-style:normal;color:#777;font-size:13px}}.business-card b{{display:block;margin:12px 0 7px;font-size:28px;letter-spacing:-1px}}.section-title{{margin:32px 0 16px;font-size:18px}}.issue-grid{{display:grid;gap:16px}}.query-issue-group{{border:1px solid rgba(255,255,255,.8);border-radius:24px;background:var(--paper);box-shadow:0 18px 40px rgba(71,85,105,.12);overflow:hidden}}.query-issue-header{{display:flex;align-items:center;gap:8px;padding:14px 18px;border-bottom:1px solid var(--line);background:rgba(238,242,255,.65)}}.query-issue-header h3{{margin:0;font-size:16px}}.query-issue-header em{{margin-left:auto;color:var(--muted);font-size:12px;font-style:normal}}.query-issue-content{{display:grid;grid-template-columns:280px minmax(0,1fr);gap:18px;padding:16px}}.issue-evidence{{display:flex;align-items:flex-start}}.dimension-title{{margin:0 0 10px;color:#4338ca;font-size:14px}}.dimension-title:not(:first-child){{margin-top:22px}}.issue-item{{padding:12px 0;border-top:1px solid #e8edf8}}.dimension-title+.issue-item{{border-top:0;padding-top:0}}.evidence-link{{display:block;width:100%}}.evidence-link img{{display:block;width:100%;height:auto;max-height:none;object-fit:contain;border:1px solid #eee;border-radius:2px}}.evidence-empty{{display:flex;align-items:center;justify-content:center;width:100%;min-height:188px;background:var(--soft);color:#888;font-size:12px}}.issue-heading{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}.issue-heading h3,.issue-heading h4{{margin:0 auto 0 0;font-size:15px;line-height:1.5}}.tag{{background:#111;color:#fff;padding:3px 6px;font-size:11px;line-height:1;white-space:nowrap}}.issue-description{{margin:7px 0 10px;color:#333;line-height:1.65}}.recommendation{{border-top:1px solid #eee;padding-top:10px;color:#666;line-height:1.55;font-size:13px}}.recommendation b{{color:#222;font-size:12px}}.recommendation p{{margin:5px 0 0}}.empty{{padding:42px;border:1px dashed #d8d8d8;color:#888;text-align:center}}@media(max-width:820px){{.page{{padding:28px 16px 48px}}.topbar{{padding:0 16px}}.top-links{{gap:14px}}.report-head{{align-items:flex-start;flex-direction:column}}.summary-card{{grid-template-columns:1fr}}.summary-divider{{height:1px;margin:0 20px}}.summary-block{{grid-template-columns:118px 1fr;padding:22px}}.overview-grid,.issue-grid{{grid-template-columns:1fr}}}}@media(max-width:820px){{.query-issue-content{{grid-template-columns:1fr}}}}@media(max-width:500px){{.top-links a:not(:last-child){{display:none}}.dimension-list{{grid-template-columns:1fr}}.evidence-link img{{height:auto}}.evidence-empty{{min-height:152px}}.summary-main{{font-size:40px}}}}
</style></head><body>
<nav class='topbar'><div class='brand'>搜索</div><div class='top-links'><a href='#whitepaper'>白皮书</a><a href='https://km.sankuai.com/collabpage/2770196684' target='_blank'>体验标准</a><a href='#details'>体验评测</a></div></nav>
<main class='page'><header class='report-head'><div><h1>搜索结果页体验评测报告</h1><p class='subtitle'>评测日期：{date}　｜　评测范围：{count} 个搜索词、单一元素 / 组件卡片 / 页面框架　｜　<a href='#details'>详情</a></p></div><select class='period-select' aria-label='评测周期'><option>{period}</option></select></header>
<nav class='business-tabs'>{tabs}</nav>
<section id='overview' class='panel active' data-panel='overview'>{overview}<div class='overview-grid'>{cards}</div></section>
{business_panels}
</main>
<script>
const tabs=[...document.querySelectorAll('.business-tab')];const panels=[...document.querySelectorAll('.panel')];
function activateBusiness(code){{tabs.forEach(tab=>tab.classList.toggle('active',tab.dataset.business===code));panels.forEach(panel=>panel.classList.toggle('active',panel.dataset.panel===code));window.scrollTo({{top:document.querySelector('.business-tabs').getBoundingClientRect().top+window.scrollY-12,behavior:'smooth'}})}}
tabs.forEach(tab=>tab.addEventListener('click',()=>activateBusiness(tab.dataset.business)));document.querySelectorAll('.business-card').forEach(card=>card.addEventListener('click',()=>activateBusiness(card.dataset.target)));
</script></body></html>""".format(
        date=esc(data.get("generatedAt") or "—"),
        count=data.get("queryCount", 0),
        period=esc(period),
        tabs="".join(tabs),
        overview=render_score_panel(overview_summary),
        cards=business_cards,
        business_panels="".join(business_panels),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the V2 search experience report preview")
    parser.add_argument("--dataset", type=Path, required=True, help="V1 已验收治理数据集 JSON")
    parser.add_argument("--output", type=Path, required=True, help="V2 HTML 输出路径")
    parser.add_argument("--period", default="2026年8月", help="标题区评测周期")
    args = parser.parse_args()
    data = read_json(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(data, args.period), encoding="utf-8")
    print(json.dumps({"dashboard": str(args.output), "queries": data.get("queryCount", 0), "businesses": len(data.get("businesses", []))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
