#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a V3 Acme-editorial preview from an accepted governance dataset.

V3 intentionally imports the V2 fact aggregation and grouping behavior, while
replacing only the visual presentation. V1 and V2 remain unchanged.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from build_experience_dashboard_v2 import DIMENSIONS, build_scope_summary, read_json, render_html, score


ACME_CSS = r"""
:root {
  --ivory:#FAF9F5; --slate:#141413; --clay:#D97757; --clay-d:#B85C3E;
  --oat:#E3DACC; --olive:#788C5D; --rust:#B04A3F; --white:#FFFFFF;
  --gray-100:#F0EEE6; --gray-200:#E6E3DA; --gray-300:#D1CFC5;
  --gray-500:#87867F; --gray-700:#3D3D3A; --success:#788C5D;
  --warning:#C78E3F; --danger:#B04A4A; --info:#5C7CA3;
  --serif:ui-serif,Georgia,"Times New Roman",Times,serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,"SF Mono",Menlo,Monaco,Consolas,monospace;
  --radius-panel:12px; --radius-row:8px; --radius-pill:999px;
  --border:1.5px solid var(--gray-300);
  --shadow-sm:0 1px 2px rgba(20,20,19,.06);
  --shadow-md:0 4px 10px rgba(20,20,19,.08);
}
* { box-sizing:border-box; }
body { margin:0; padding:104px 24px 96px; background:var(--ivory); color:var(--slate); font:15px/1.55 var(--sans); -webkit-font-smoothing:antialiased; }
.topbar { position:fixed; z-index:10; top:0; right:0; left:0; display:flex; height:56px; align-items:center; justify-content:space-between; padding:0 max(24px,calc((100vw - 1180px)/2)); border-bottom:1px solid var(--gray-300); background:rgba(250,249,245,.96); backdrop-filter:blur(10px); }
.brand { color:var(--slate); font:700 13px var(--mono); letter-spacing:.12em; }
.top-links { display:flex; align-items:center; gap:24px; }
.top-links a { color:var(--gray-500); font:12px var(--mono); letter-spacing:.04em; text-decoration:none; transition:color .12s ease; }
.top-links a:hover,.top-links a:focus-visible { color:var(--clay-d); }
.top-links a:last-child { color:var(--slate); font-weight:700; }
.page { max-width:1180px; margin:0 auto; padding:0; }
.report-head { position:relative; display:block; margin:0; padding:0 0 30px; border-bottom:1px solid var(--gray-300); }
.report-head::before { content:'SEARCH EXPERIENCE / EVALUATION'; display:block; margin-bottom:16px; color:var(--gray-500); font:12px/1 var(--mono); letter-spacing:.12em; }
h1 { margin:0; font:500 40px/1.14 var(--serif); letter-spacing:-.02em; }
.subtitle { max-width:760px; margin:12px 0 0; color:var(--gray-500); font-size:14px; }
.subtitle a { color:var(--clay); text-underline-offset:3px; }
.period-select { position:absolute; top:33px; right:0; appearance:none; border:var(--border); border-radius:var(--radius-row); background:var(--white); color:var(--gray-700); padding:8px 12px; font:12px var(--mono); }
.business-tabs { display:flex; flex-wrap:wrap; gap:8px; margin:24px 0 0; border:0; }
.business-tab { border:var(--border); border-radius:var(--radius-pill); background:var(--white); color:var(--gray-700); padding:7px 14px; font:12px var(--mono); letter-spacing:.03em; cursor:pointer; transition:border-color .12s ease,color .12s ease,background .12s ease; }
.business-tab:hover { border-color:var(--slate); color:var(--slate); }
.business-tab.active { border-color:var(--clay); background:rgba(217,119,87,.14); color:var(--clay-d); }
.business-tab.active::after { display:none; }
.panel { display:none; padding-top:32px; }
.panel.active { display:block; }
.summary-card,.summary-block,.summary-divider,.summary-primary,.summary-kicker,.summary-main,.dimension-list,.dimension-row { display:contents; }
.acme-summary { display:grid; grid-template-columns:1fr 1fr; gap:24px; }
.summary-section { min-width:0; }
.summary-section-head { display:flex; align-items:baseline; justify-content:space-between; margin-bottom:12px; padding-bottom:10px; border-bottom:1px solid var(--gray-300); }
.summary-section-head h2 { margin:0; font:500 24px/1.2 var(--serif); letter-spacing:-.01em; }
.summary-total { color:var(--clay-d); font:500 32px/1 var(--serif); letter-spacing:-.02em; }
.stat-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }
.stat-card { min-height:120px; padding:16px; border:var(--border); border-radius:var(--radius-panel); background:var(--white); box-shadow:var(--shadow-sm); }
.stat-card.score,.stat-card.warn { border-left:4px solid var(--clay); padding-left:13px; }
.stat-label { color:var(--gray-500); font:11px var(--mono); letter-spacing:.05em; }
.stat-num { margin:12px 0 6px; color:var(--slate); font:500 34px/1 var(--serif); letter-spacing:-.02em; }
.stat-delta { color:var(--gray-500); font:11px var(--mono); }
.overview-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin-top:20px; }
.business-card { border:var(--border); border-radius:var(--radius-panel); background:var(--white); color:var(--slate); padding:18px; text-align:left; box-shadow:var(--shadow-sm); cursor:pointer; transition:transform .15s ease,box-shadow .15s ease,border-color .15s ease; }
.business-card:hover { border-color:var(--slate); box-shadow:var(--shadow-md); transform:translateY(-3px); }
.business-card span,.business-card em { display:block; color:var(--gray-500); font:11px var(--mono); font-style:normal; letter-spacing:.04em; }
.business-card b { display:block; margin:10px 0 7px; font:500 32px/1 var(--serif); letter-spacing:-.02em; }
.section-title { margin:48px 0 14px; padding-bottom:12px; border-bottom:1px solid var(--gray-300); font:500 26px/1.3 var(--serif); letter-spacing:-.01em; }
.issue-grid { display:grid; gap:16px; }
.query-issue-group { overflow:hidden; border:var(--border); border-radius:var(--radius-panel); background:var(--white); box-shadow:var(--shadow-sm); }
.query-issue-header { display:flex; align-items:center; gap:10px; padding:13px 18px; border-bottom:1px solid var(--gray-300); background:var(--gray-100); }
.query-issue-header h3 { margin:0; font:500 18px var(--serif); }
.query-issue-header em { margin-left:auto; color:var(--gray-500); font:11px var(--mono); font-style:normal; letter-spacing:.04em; }
.query-issue-content { display:grid; grid-template-columns:300px minmax(0,1fr); gap:22px; padding:18px; }
.issue-evidence { align-self:start; }
.evidence-link { display:block; width:100%; background:var(--gray-100); border:1px solid var(--gray-300); border-radius:var(--radius-row); overflow:hidden; }
.evidence-link img { display:block; width:100%; height:auto; }
.evidence-empty { display:grid; min-height:188px; place-items:center; border:1px solid var(--gray-300); border-radius:var(--radius-row); background:var(--gray-100); color:var(--gray-500); font:12px var(--mono); }
.dimension-title { margin:0 0 8px; color:var(--clay-d); font:11px var(--mono); letter-spacing:.08em; text-transform:uppercase; }
.dimension-title:not(:first-child) { margin-top:22px; }
.issue-item { padding:11px 0; border-top:1px solid var(--gray-200); }
.dimension-title + .issue-item { padding-top:0; border-top:0; }
.issue-heading { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.issue-heading h4 { margin:0 auto 0 0; color:var(--slate); font:500 16px/1.4 var(--serif); }
.tag { border-radius:var(--radius-xs); background:rgba(176,74,74,.12); color:var(--danger); padding:3px 7px; font:11px var(--mono); letter-spacing:.04em; }
.issue-description { margin:5px 0 9px; color:var(--gray-700); font-size:14px; line-height:1.58; }
.recommendation { padding:9px 11px; border-left:3px solid var(--oat); background:var(--ivory); color:var(--gray-700); font-size:13px; line-height:1.55; }
.recommendation b { color:var(--clay-d); font:11px var(--mono); letter-spacing:.05em; }
.recommendation p { margin:3px 0 0; }
.empty { padding:34px; border:var(--border); border-radius:var(--radius-panel); background:var(--white); color:var(--gray-500); text-align:center; }
.report-footer { margin-top:64px; padding-top:20px; border-top:1px solid var(--gray-300); color:var(--gray-500); font:12px var(--mono); }
@media (max-width:880px) { .period-select { position:static; margin-top:16px; } .acme-summary { grid-template-columns:1fr; gap:32px; } .overview-grid { grid-template-columns:repeat(2,1fr); } .query-issue-content { grid-template-columns:1fr; } }
@media (max-width:640px) { body { padding:88px 16px 64px; } .topbar { height:48px; padding:0 16px; } .top-links { gap:14px; } .top-links a { font-size:11px; } h1 { font-size:32px; } .stat-grid { grid-template-columns:1fr; } .overview-grid { grid-template-columns:1fr; } }
"""


def priority_counts_by_dimension(groups: list[dict]) -> dict[str, Counter[str]]:
    """Count P0/P1/P2 from the actual issue evidence in each evaluation dimension."""
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for group in groups:
        level = str(group.get("level") or "")
        for issue in group.get("evidence", []):
            if not isinstance(issue, dict):
                continue
            value = str(issue.get("priority") or group.get("priority") or "P2")
            counts[level][value if value in {"P0", "P1", "P2"} else "P2"] += 1
    return counts


def render_acme_summary(summary: dict, groups: list[dict]) -> str:
    priority_by_dimension = priority_counts_by_dimension(groups)
    score_items = "".join(
        "<div class='stat-card score'><div class='stat-label'>{name}</div><div class='stat-num'>{value}</div><div class='stat-delta'>维度得分</div></div>".format(
            name=name, value=score(summary["dimensionScores"].get(code))
        )
        for code, name in DIMENSIONS
    )
    issue_items = "".join(
        "<div class='stat-card warn'><div class='stat-label'>{name}</div><div class='stat-num'>{count}</div><div class='stat-delta'>P0-{p0} · P1-{p1} · P2-{p2}</div></div>".format(
            name=name,
            count=summary["issueCounts"].get(code, 0),
            p0=priority_by_dimension[code].get("P0", 0),
            p1=priority_by_dimension[code].get("P1", 0),
            p2=priority_by_dimension[code].get("P2", 0),
        )
        for code, name in DIMENSIONS
    )
    return """
<section class='acme-summary'>
  <div class='summary-section'><div class='summary-section-head'><h2>评测总分</h2><div class='summary-total'>{overall}</div></div><div class='stat-grid'>{score_items}</div></div>
  <div class='summary-section'><div class='summary-section-head'><h2>问题发现</h2><div class='summary-total'>{issues}</div></div><div class='stat-grid'>{issue_items}</div></div>
</section>""".format(overall=score(summary["overall"]), issues=summary["issueTotal"], score_items=score_items, issue_items=issue_items)


def render_v3(data: dict, period: str) -> str:
    document = render_html(data, period)
    document = document.replace("<a href='#whitepaper'>白皮书</a>", "<a href='https://km.sankuai.com/collabpage/2771507978' target='_blank' rel='noopener'>白皮书</a>")
    document = document.replace("<a href='#details'>详情</a>", "<a href='https://km.sankuai.com/collabpage/2772784557' target='_blank' rel='noopener'>详情</a>", 1)
    document = document.replace("<main class='page'>", "<main id='details' class='page'>", 1)
    groups = [item for item in data.get("groups", []) if isinstance(item, dict)]
    businesses = [item for item in data.get("businesses", []) if isinstance(item, dict) and item.get("businessCode")]
    overall_scores: dict[str, list[float]] = defaultdict(list)
    issue_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()
    for business in businesses:
        for code, value in (business.get("dimensionScores") or {}).items():
            if isinstance(value, (int, float)):
                overall_scores[str(code)].append(float(value))
    for group in groups:
        for issue in group.get("evidence", []):
            if isinstance(issue, dict):
                issue_counts[str(group.get("level") or "")] += 1
                value = str(issue.get("priority") or group.get("priority") or "P2")
                priority_counts[value if value in {"P0", "P1", "P2"} else "P2"] += 1
    overview = {
        "overall": round(sum(item.get("overallScore", 0) for item in businesses) / len(businesses), 1),
        "dimensionScores": {code: round(sum(values) / len(values), 1) for code, values in overall_scores.items() if values},
        "issueCounts": issue_counts,
        "priorityCounts": priority_counts,
        "issueTotal": sum(issue_counts.values()),
    }
    document = re.sub(r"<style>.*?</style>", f"<style>{ACME_CSS}</style>", document, count=1, flags=re.DOTALL)
    document = re.sub(r"<section id='overview' class='panel active' data-panel='overview'>.*?<div class='overview-grid'>(.*?)</div></section>", lambda match: "<section id='overview' class='panel active' data-panel='overview'>" + render_acme_summary(overview, groups) + "<div class='overview-grid'>" + match.group(1) + "</div></section>", document, count=1, flags=re.DOTALL)
    for business in businesses:
        code = re.escape(str(business["businessCode"]))
        scope_summary = build_scope_summary(business, groups)
        summary = render_acme_summary(scope_summary, scope_summary["groups"])
        pattern = r"(<section class='panel business-panel' data-panel='" + code + r"'>).*?(<h2 class='section-title'>问题明细</h2>)"
        document = re.sub(pattern, lambda match: match.group(1) + summary + match.group(2), document, count=1, flags=re.DOTALL)
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the V3 Acme-editorial search experience preview")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--period", default="2026年8月")
    args = parser.parse_args()
    data = read_json(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_v3(data, args.period), encoding="utf-8")
    print(json.dumps({"dashboard": str(args.output), "queries": data.get("queryCount", 0), "businesses": len(data.get("businesses", []))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
