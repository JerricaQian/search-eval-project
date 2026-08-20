#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical Phase5 issue-centric dashboard renderer.

It only presents an accepted governance dataset: no upstream artifact reads,
score recalculation, or synthesized issues/evidence are permitted here.
"""
from __future__ import annotations

import html
import re
from collections import Counter, defaultdict
from typing import Any
from urllib.parse import quote

DIMENSIONS = (("element", "单一元素", "单一元素维度"), ("component", "组件/卡片", "组件/卡片维度"), ("page", "页面框架", "页面框架维度"))
DIMENSION_ORDER = {"component": 0, "page": 1, "element": 2}
PROBLEM_RATINGS = {"达标", "不达标", "🟡", "🔴"}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


def esc(value: Any) -> str: return html.escape(str(value or ""))
def score(value: Any) -> str: return "—" if not isinstance(value, (int, float)) else f"{value:.1f}"
def sentence(value: Any) -> str: return str(value or "").strip().rstrip("。！？!?；;，,")


def priority(issue: dict[str, Any], group: dict[str, Any]) -> str:
    value = str(issue.get("priority") or group.get("priority") or "P2")
    return value if value in PRIORITY_ORDER else "P2"


def issue_target(issue: dict[str, Any]) -> str:
    return str(issue.get("elementLabel") or issue.get("targetLabel") or issue.get("componentName") or issue.get("component") or "相关页面区域").strip()


def finding_text(issue: dict[str, Any]) -> str:
    finding = issue.get("finding") if isinstance(issue.get("finding"), dict) else {}
    required = ("observableFact", "ruleOrThreshold", "verdictReason", "userImpact")
    missing = [key for key in required if not sentence(finding.get(key))]
    if missing:
        target = issue.get("elementId") or issue.get("cardId") or issue.get("query") or "未命名问题"
        raise ValueError(f"问题 {target} 缺少三段式结论字段：{','.join(missing)}")
    fact, rating = sentence(finding["observableFact"]), str(issue.get("rating") or "")
    return f"{fact}{f'，评级为{rating}' if rating and f'评级为{rating}' not in fact else ''}。{sentence(finding['userImpact'])}。"


def recommendation_text(issue: dict[str, Any]) -> str:
    value = str(issue.get("recommendation") or "").strip()
    if not value:
        target = issue.get("elementId") or issue.get("cardId") or issue.get("query") or "未命名问题"
        raise ValueError(f"问题 {target} 缺少问题级个性化优化建议")
    return value


def evidence_html(path: str, label: str) -> str:
    if not path: return "<div class='evidence-empty'>暂无截图证据</div>"
    uri = esc(quote(path, safe="/:"))
    return "<a class='evidence-link' href='file://{0}' target='_blank' rel='noopener'><img loading='lazy' src='file://{0}' alt='{1}'></a>".format(uri, esc(label))


def flattened_issues(groups: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [(group, issue) for group in groups for issue in group.get("evidence", []) if isinstance(issue, dict) and str(issue.get("rating") or "") in PROBLEM_RATINGS]


def fill_missing_evidence(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    by_screenshot: dict[str, str] = {}
    for _, issue in entries:
        if issue.get("screenshot") and issue.get("evidenceImage"): by_screenshot.setdefault(str(issue["screenshot"]), str(issue["evidenceImage"]))
    return [(group, {**issue, "evidenceImage": by_screenshot.get(str(issue.get("screenshot") or ""), "")}) if not issue.get("evidenceImage") else (group, issue) for group, issue in entries]


def summary_for(business: dict[str, Any] | None, groups: list[dict[str, Any]]) -> dict[str, Any]:
    scoped = groups if business is None else [group for group in groups if group.get("businessCode") == business.get("businessCode")]
    issues = fill_missing_evidence(flattened_issues(scoped))
    counts: Counter[str] = Counter(str(group.get("level") or "") for group, _ in issues)
    priorities: dict[str, Counter[str]] = defaultdict(Counter)
    for group, issue in issues: priorities[str(group.get("level") or "")][priority(issue, group)] += 1
    return {"overall": business.get("overallScore") if business else None, "dimensionScores": business.get("dimensionScores", {}) if business else {}, "issues": issues, "issueCounts": counts, "priorityCounts": priorities}


def overview_summary(businesses: list[dict[str, Any]], groups: list[dict[str, Any]]) -> dict[str, Any]:
    result, values = summary_for(None, groups), defaultdict(list)
    for business in businesses:
        for code, value in (business.get("dimensionScores") or {}).items():
            if isinstance(value, (int, float)): values[str(code)].append(float(value))
    overalls = [float(item["overallScore"]) for item in businesses if isinstance(item.get("overallScore"), (int, float))]
    result["overall"] = round(sum(overalls) / len(overalls), 1) if overalls else None
    result["dimensionScores"] = {code: round(sum(items) / len(items), 1) for code, items in values.items() if items}
    return result


def render_summary(summary: dict[str, Any]) -> str:
    score_rows, issue_rows = [], []
    for code, short, _ in DIMENSIONS:
        value = summary["dimensionScores"].get(code)
        score_rows.append("<div class='summary-metric-label'><span>{}</span><b class='{}'>{}</b></div>".format(esc(short), "missing" if not isinstance(value, (int, float)) else "", score(value)))
        counts = summary["priorityCounts"].get(code, Counter())
        issue_rows.append("<div class='summary-metric-label'><span>{}</span><b>{}</b><em>P0 {}，P1 {}</em></div>".format(esc(short), summary["issueCounts"].get(code, 0), counts.get("P0", 0), counts.get("P1", 0)))
    return "<section class='summary-panel'><div class='summary-block'><h2 class='summary-block-title'>评测总分</h2><div class='summary-figure'>{}</div><div class='summary-metrics'>{}</div></div><div class='summary-block warn'><h2 class='summary-block-title'>问题发现</h2><div class='summary-figure'>{}</div><div class='summary-metrics'>{}</div></div></section>".format(score(summary["overall"]), "".join(score_rows), len(summary["issues"]), "".join(issue_rows))


def render_issue(issue: dict[str, Any], group: dict[str, Any], title: str, show_query: bool = False) -> str:
    query = str(issue.get("query") or "")
    meta = f"<span class='problem-query-meta'>搜索词：{esc(query)}</span>" if show_query and query else ""
    return "<article class='issue-item'><div class='issue-heading'><h4>{}{}</h4><span class='tag {}'>{}</span></div><p class='issue-target'><b>问题对象</b>{}</p><p class='issue-description'>{}</p><div class='recommendation'><b>优化建议</b><p>{}</p></div></article>".format(esc(title), meta, priority(issue, group).lower(), esc(priority(issue, group)), esc(issue_target(issue)), esc(finding_text(issue)), esc(recommendation_text(issue)))


def render_by_query(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    grouped: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for group, issue in entries: grouped[(str(issue.get("query") or "未命名搜索词"), str(issue.get("tab") or "全部"))].append((group, issue))
    blocks, ordinal = [], 0
    for (query, tab), items in sorted(grouped.items()):
        items.sort(key=lambda row: (DIMENSION_ORDER.get(str(row[0].get("level")), 99), str(row[0].get("metricName") or "")))
        image, copy, active_level = next((str(issue.get("evidenceImage") or "") for _, issue in items if issue.get("evidenceImage")), ""), [], None
        for group, issue in items:
            if group.get("level") != active_level:
                active_level = group.get("level"); copy.append("<h3 class='dimension-title'>{}</h3>".format(esc(group.get("levelName") or "评测维度")))
            ordinal += 1; copy.append(render_issue(issue, group, f"问题{ordinal}：{group.get('metricName') or '体验问题'}"))
        blocks.append("<section class='query-issue-group'><header class='query-issue-header'><h3>{}</h3><em>{} Tab · {} 个问题</em></header><div class='query-issue-content'><div class='issue-evidence'>{}</div><div class='issue-copy'>{}</div></div></section>".format(esc(query), esc(tab), len(items), evidence_html(image, f"{query}问题证据"), "".join(copy)))
    return "<div class='issue-grid'>{}</div>".format("".join(blocks)) if blocks else "<div class='empty'>该业务本轮暂无待优化问题。</div>"


def render_by_metric(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    grouped: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    for group, issue in entries: grouped[(str(group.get("level") or ""), str(group.get("metricName") or "体验问题"))].append((group, issue))
    blocks, ordinal = [], 0
    for (_, metric), items in sorted(grouped.items(), key=lambda row: (min(PRIORITY_ORDER[priority(issue, group)] for group, issue in row[1]), DIMENSION_ORDER.get(row[0][0], 99), row[0][1])):
        group, rows = items[0][0], []
        for item_group, issue in sorted(items, key=lambda row: PRIORITY_ORDER[priority(row[1], row[0])]):
            ordinal += 1; rows.append("<div class='metric-issue-row'><div class='issue-evidence'>{}</div><div class='issue-copy'>{}</div></div>".format(evidence_html(str(issue.get("evidenceImage") or ""), f"{issue.get('query') or '搜索词'}问题证据"), render_issue(issue, item_group, f"问题{ordinal}：{issue.get('query') or '未命名搜索词'}")))
        blocks.append("<section class='metric-issue-group'><header class='metric-issue-header'><h3>{}</h3><span class='tag dim'>{}</span><em>{} 个问题</em></header>{}</section>".format(esc(metric), esc(group.get("levelName") or "评测维度"), len(items), "".join(rows)))
    return "".join(blocks) or "<div class='empty'>该业务本轮暂无待优化问题。</div>"


def render_by_problem(entries: list[tuple[dict[str, Any], dict[str, Any]]]) -> str:
    ordered = sorted(entries, key=lambda row: (PRIORITY_ORDER[priority(row[1], row[0])], DIMENSION_ORDER.get(str(row[0].get("level")), 99), str(row[0].get("metricName") or ""), str(row[1].get("query") or "")))
    cards = []
    for ordinal, (group, issue) in enumerate(ordered, 1):
        cards.append("<section class='metric-issue-group problem-card'><header class='metric-issue-header'><h3>{}</h3><span class='tag dim'>{}</span></header><div class='metric-issue-row problem-card-row'><div class='issue-evidence'>{}</div><div class='issue-copy'>{}</div></div></section>".format(esc(group.get("metricName") or "体验问题"), esc(group.get("levelName") or "评测维度"), evidence_html(str(issue.get("evidenceImage") or ""), f"{issue.get('query') or '搜索词'}问题证据"), render_issue(issue, group, f"问题{ordinal}", True)))
    return "<div class='problem-card-grid'>{}</div>".format("".join(cards)) if cards else "<div class='empty'>该业务本轮暂无待优化问题。</div>"


STYLE = r''' :root{--ink:#0c0d10;--paper:#fafbfc;--white:#fff;--muted:#5e5f66;--quiet:#8a8b90;--wash:rgba(12,13,16,.04);--line:rgba(12,13,16,.13);--p0:#b42318;--p1:#c65f16;--p2:#6b7280;--font-sans:"Inter",ui-sans-serif,-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}*{box-sizing:border-box}body{margin:0;padding:80px 22px 96px;background:var(--paper);color:var(--ink);font-family:var(--font-sans);font-size:16px;line-height:1.75}.topbar{position:fixed;z-index:10;top:0;right:0;left:0;display:flex;height:52px;align-items:center;justify-content:space-between;padding:0 max(22px,calc((100vw - 960px)/2));background:rgba(250,251,252,.96);border-bottom:1px solid var(--line)}.brand{font-size:13px;font-weight:700;letter-spacing:.14em}.top-links{display:flex;gap:20px}.top-links a{color:var(--muted);font-size:12px;text-decoration:none}.top-links a:hover{color:var(--ink)}.page{max-width:920px;margin:0 auto}.report-head{padding:48px 0 24px;border-bottom:1px solid var(--line)}.report-head h1{max-width:640px;margin:0;font-size:40px;line-height:1.18;letter-spacing:-.035em}.subtitle{max-width:700px;margin:14px 0 0;color:var(--muted);font-size:15px}.subtitle a{color:var(--ink);text-decoration:underline;text-underline-offset:3px}.period-select{display:block;width:min(100%,540px);margin-top:20px;padding:7px 0;border:0;border-bottom:1px solid var(--line);background:transparent;color:var(--muted);font:inherit;font-size:12px}.business-tabs{position:sticky;z-index:5;top:52px;display:flex;gap:2px;flex-wrap:nowrap;overflow-x:auto;margin:0 -8px 36px;padding:14px 8px 12px;background:rgba(250,251,252,.96);border-bottom:1px solid var(--line)}button{font-family:inherit}.business-tab{flex:0 0 auto;border:0;background:transparent;color:var(--muted);padding:7px 10px;font-size:13px;font-weight:600;cursor:pointer}.business-tab:hover{background:var(--wash);color:var(--ink)}.business-tab.active,.detail-tab.active{background:var(--ink);color:var(--white)}.panel,.detail-pane{display:none}.panel.active,.detail-pane.active{display:block}.summary-panel{display:grid;grid-template-columns:1fr 1fr}.summary-block{padding:0 34px 0 0}.summary-block+.summary-block{padding:0 0 0 34px;border-left:1px solid var(--line)}.summary-block-title{margin:0 0 14px;color:var(--quiet);font-size:12px;letter-spacing:.12em}.summary-figure{margin-bottom:16px;font-size:60px;font-weight:700;line-height:1;letter-spacing:-.06em}.warn .summary-figure{color:var(--p0)}.summary-metric-label{display:grid;grid-template-columns:1fr auto auto;gap:12px;align-items:baseline;padding:8px 0;color:var(--muted);font-size:13px;border-top:1px solid var(--line)}.summary-metric-label b{color:var(--ink);font-size:15px}.summary-metric-label b.missing{color:var(--quiet)}.summary-metric-label em{color:var(--quiet);font-size:11px;font-style:normal}.overview-grid{display:block;margin-top:58px;border-top:1px solid var(--line)}.business-card{display:grid;grid-template-columns:minmax(130px,1fr) 90px 120px;align-items:center;gap:20px;width:100%;padding:18px 0;border:0;border-bottom:1px solid var(--line);background:transparent;text-align:left;cursor:pointer}.business-card:hover{background:var(--wash)}.business-card span{font-size:16px;font-weight:700}.business-card b{font-size:22px}.business-card em{color:var(--quiet);font-size:12px;font-style:normal}.detail-heading{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-top:64px;margin-bottom:20px;padding-bottom:12px;border-bottom:1px solid var(--line)}.section-title{margin:0;font-size:24px}.detail-tabs{display:flex;gap:3px;flex-wrap:wrap}.detail-tab{border:0;background:transparent;color:var(--muted);padding:6px 9px;font-size:13px;font-weight:600;cursor:pointer}.detail-tab:hover{background:var(--wash);color:var(--ink)}.issue-grid{display:grid;gap:18px}.query-issue-group,.metric-issue-group{border-top:1px solid var(--line)}.query-issue-header,.metric-issue-header{display:flex;align-items:baseline;gap:10px;padding:13px 0;border-bottom:1px solid var(--line)}.query-issue-header h3,.metric-issue-header h3{margin:0;font-size:16px}.query-issue-header em,.metric-issue-header em{margin-left:auto;color:var(--quiet);font-size:12px;font-style:normal}.query-issue-content{display:grid;grid-template-columns:260px minmax(0,1fr);gap:24px;padding:20px 0}.metric-issue-row{display:grid;grid-template-columns:180px minmax(0,1fr);gap:20px;padding:20px 0}.metric-issue-row+.metric-issue-row{border-top:1px solid var(--line)}.evidence-link{display:block;overflow:hidden;border:1px solid var(--line);background:var(--wash)}.evidence-link img{display:block;width:100%;height:auto;transition:transform 160ms ease}.evidence-link:hover img{transform:scale(1.01)}.evidence-empty{display:grid;min-height:150px;place-items:center;border:1px dashed var(--line);color:var(--quiet);font-size:12px}.dimension-title{margin:0 0 9px;color:var(--quiet);font-size:11px;letter-spacing:.1em}.dimension-title:not(:first-child){margin-top:20px}.issue-item{padding:12px 0;border-top:1px solid var(--line)}.dimension-title+.issue-item{padding-top:0;border-top:0}.issue-heading{display:flex;align-items:flex-start;gap:8px}.issue-heading h4{margin:0 auto 0 0;font-size:15px;line-height:1.45}.problem-query-meta{display:block;margin-top:3px;color:var(--quiet);font-size:12px;font-weight:400}.tag{display:inline-flex;flex:0 0 auto;padding:3px 8px;border-radius:999px;background:var(--ink);color:var(--white);font-size:10px;font-weight:700}.tag.p0{background:var(--p0)}.tag.p1{background:var(--p1)}.tag.p2{background:var(--p2)}.issue-target{margin:7px 0 3px;color:var(--muted);font-size:13px}.issue-target b{margin-right:8px;color:var(--ink)}.issue-description{margin:5px 0 10px;color:var(--muted);font-size:14px}.recommendation{padding:10px 13px;border-left:2px solid var(--ink);background:var(--wash);font-size:13px}.recommendation b{font-size:10px;letter-spacing:.08em}.recommendation p{margin:3px 0 0}.problem-card-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:26px 20px}.problem-card{border-bottom:1px solid var(--line)}.problem-card-row{grid-template-columns:minmax(0,1fr) 150px;gap:16px}.problem-card-row .issue-evidence{order:2}.problem-card-row .issue-copy{order:1}.problem-card .issue-item{padding-top:0;border-top:0}.empty{padding:32px 0;border-top:1px dashed var(--line);border-bottom:1px dashed var(--line);color:var(--muted);text-align:center}@media(max-width:720px){body{padding:72px 16px 64px;font-size:14px}.topbar{height:48px;padding:0 16px}.report-head{padding-top:30px}.report-head h1{font-size:30px}.business-tabs{top:48px;margin-bottom:28px}.summary-panel,.problem-card-grid{grid-template-columns:1fr}.summary-block,.summary-block+.summary-block{padding:0;border:0}.summary-block+.summary-block{margin-top:30px}.detail-heading{align-items:flex-start;flex-direction:column}.query-issue-content,.metric-issue-row,.problem-card-row{grid-template-columns:1fr}.problem-card-row .issue-evidence,.problem-card-row .issue-copy{order:initial}.business-card{grid-template-columns:1fr auto}.business-card em{grid-column:1/-1}}'''

# Adaptive SaaS dashboard visual layer. It deliberately overrides the archived
# monochrome experiment above while keeping the same three deterministic views.
STYLE += r'''
:root{--ink:#313742;--paper:#f0f2f6;--white:#fff;--muted:#697180;--quiet:#99a1ad;--wash:#f7f8fa;--line:#e7eaf0;--p0:#d95d61;--p1:#d9a441;--p2:#697180;--primary:#456af4;--primary-deep:#3156d8;--accent:#6747f5;--font-sans:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif}body{padding:92px 24px 72px;background:var(--paper);font-size:14px;line-height:1.6}.topbar{height:58px;background:#fff;border-bottom:1px solid var(--line);box-shadow:0 1px 3px rgba(29,39,59,.04);padding:0 max(24px,calc((100vw - 1440px)/2))}.brand{color:var(--ink);letter-spacing:.08em}.top-links a{font-size:13px}.page{max-width:1440px}.report-head{margin-top:26px;padding:26px 30px;background:var(--white);border:1px solid var(--line);border-radius:16px;box-shadow:0 1px 3px rgba(29,39,59,.04)}.report-head h1{max-width:none;font-size:28px;line-height:1.3;letter-spacing:-.02em}.subtitle{max-width:none;margin-top:8px;font-size:13px}.period-select{position:absolute;right:30px;top:32px;width:auto;margin:0;padding:8px 11px;border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--muted)}.business-tabs{position:static;gap:8px;overflow:visible;margin:18px 0;padding:0;border:0;background:transparent}.business-tab,.detail-tab{border:1px solid var(--line);border-radius:8px;background:#fff;color:var(--muted);padding:8px 14px;font-size:13px;transition:background 160ms ease,border-color 160ms ease,box-shadow 160ms ease}.business-tab:hover,.detail-tab:hover{background:#fff;border-color:#b8c6fd;color:var(--primary-deep);box-shadow:0 1px 3px rgba(29,39,59,.04)}.business-tab.active,.detail-tab.active{background:var(--primary);border-color:var(--primary);color:#fff}.summary-panel{gap:16px;grid-template-columns:1fr 1fr}.summary-block,.summary-block+.summary-block{padding:22px 24px;border:1px solid var(--line);border-radius:12px;background:#fff;box-shadow:0 1px 3px rgba(29,39,59,.04)}.summary-block+.summary-block{margin:0}.summary-block-title{color:var(--muted);font-size:13px;letter-spacing:0}.summary-figure{color:var(--ink);font-size:38px;letter-spacing:-.04em}.warn .summary-figure{color:var(--p0)}.summary-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.summary-metric-label{display:block;padding:8px 0;border-top:1px solid var(--line);font-size:12px}.summary-metric-label b{display:block;margin-top:2px;font-size:16px}.summary-metric-label em{display:block;margin-top:2px}.overview-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin-top:18px;border:0}.business-card{display:block;padding:18px;border:1px solid var(--line);border-radius:12px;background:#fff;box-shadow:0 1px 3px rgba(29,39,59,.04);transition:transform 160ms ease,box-shadow 160ms ease}.business-card:hover{background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(29,39,59,.06)}.business-card span{font-size:13px}.business-card b{display:block;margin:8px 0 4px;color:var(--primary-deep);font-size:28px}.detail-heading{margin-top:36px;margin-bottom:16px;padding:0;border:0}.section-title{font-size:20px}.query-issue-group,.metric-issue-group{overflow:hidden;border:1px solid var(--line);border-radius:12px;background:#fff;box-shadow:0 1px 3px rgba(29,39,59,.04)}.query-issue-header,.metric-issue-header{padding:13px 18px;background:#f7f8fa;border-color:var(--line)}.query-issue-content{grid-template-columns:260px minmax(0,1fr);padding:18px}.metric-issue-row{grid-template-columns:180px minmax(0,1fr);padding:18px}.metric-issue-row+.metric-issue-row,.issue-item{border-color:var(--line)}.evidence-link{border-color:var(--line);border-radius:8px;background:#f7f8fa}.evidence-empty{border-color:var(--line);border-radius:8px;background:#f7f8fa}.dimension-title{color:var(--primary-deep)}.tag{border-radius:6px}.tag.dim{background:var(--accent)}.issue-target{color:var(--muted)}.issue-description{color:var(--ink)}.recommendation{border-left:3px solid var(--primary);border-radius:6px;background:#f2f5ff;color:var(--ink)}.problem-card-grid{gap:16px}.problem-card{border-bottom:1px solid var(--line)}.problem-card-row{grid-template-columns:minmax(0,1fr) 170px}.empty{padding:32px;border:1px dashed var(--line);border-radius:12px;background:#fff}@media(max-width:720px){body{padding:74px 16px 48px}.report-head{margin-top:16px;padding:20px}.report-head h1{font-size:24px}.period-select{position:static;width:100%;margin-top:14px}.summary-panel,.problem-card-grid{grid-template-columns:1fr}.summary-block+.summary-block{margin-top:0}.summary-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.query-issue-content,.metric-issue-row,.problem-card-row{grid-template-columns:1fr}.problem-card-row .issue-evidence,.problem-card-row .issue-copy{order:initial}}
'''


def render_dashboard(data: dict[str, Any]) -> str:
    businesses = [item for item in data.get("businesses", []) if isinstance(item, dict) and item.get("businessCode")]
    groups = [item for item in data.get("groups", []) if isinstance(item, dict)]
    if not businesses: raise ValueError("治理数据集没有可展示的业务线")
    overview, batch = overview_summary(businesses, groups), str(data.get("batch") or "当前批次")
    match = re.search(r"(\d+)词", batch); query_count = int(match.group(1)) if match else int(data.get("queryCount") or 0)
    evaluated = [label for code, _, label in DIMENSIONS if any(code in (item.get("dimensionScores") or {}) for item in businesses)]
    tabs = ["<button class='business-tab active' type='button' data-business='overview'>概览</button>"]; cards = []; panels = []
    for business in businesses:
        code, name, summary = str(business["businessCode"]), str(business.get("businessName") or business["businessCode"]), summary_for(business, groups)
        tabs.append("<button class='business-tab' type='button' data-business='{0}'>{1}</button>".format(esc(code), esc(name)))
        cards.append("<button class='business-card' type='button' data-target='{0}'><span>{1}</span><b>{2}</b><em>问题发现 {3}</em></button>".format(esc(code), esc(name), score(business.get("overallScore")), business.get("issueCount", 0)))
        panels.append("<section class='panel business-panel' data-panel='{0}'>{1}<div class='detail-heading'><h2 class='section-title'>问题明细</h2><div class='detail-tabs' role='tablist' aria-label='问题明细分组方式'><button class='detail-tab' type='button' data-detail-tab='{0}-query'>按搜索词</button><button class='detail-tab' type='button' data-detail-tab='{0}-metric'>按指标</button><button class='detail-tab active' type='button' data-detail-tab='{0}-problem'>按问题</button></div></div><div class='detail-pane' data-detail-pane='{0}-query'>{2}</div><div class='detail-pane' data-detail-pane='{0}-metric'>{3}</div><div class='detail-pane active' data-detail-pane='{0}-problem'>{4}</div></section>".format(esc(code), render_summary(summary), render_by_query(summary["issues"]), render_by_metric(summary["issues"]), render_by_problem(summary["issues"])))
    return """<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>大搜结果页体验评测看板</title><style>{style}</style></head><body><nav class='topbar'><div class='brand'>搜索</div><div class='top-links'><a href='https://km.sankuai.com/collabpage/2771507978' target='_blank' rel='noopener'>白皮书</a><a href='https://km.sankuai.com/collabpage/2770196684' target='_blank' rel='noopener'>体验标准</a><a href='#details'>体验评测</a></div></nav><main id='details' class='page'><header class='report-head'><h1>大搜结果页体验评测看板</h1><p class='subtitle'>评测日期：{date}　｜　评测范围：{count} 个搜索词、{dimensions}　<a href='https://km.sankuai.com/collabpage/2772784557' target='_blank' rel='noopener'>详情</a></p><select class='period-select' aria-label='评测周期'><option>{batch}</option></select></header><nav class='business-tabs'>{tabs}</nav><section class='panel active' data-panel='overview'>{overview}<div class='overview-grid'>{cards}</div></section>{panels}</main><script>const businessTabs=[...document.querySelectorAll('.business-tab')],panels=[...document.querySelectorAll('.panel')];function activateBusiness(code){{businessTabs.forEach(tab=>tab.classList.toggle('active',tab.dataset.business===code));panels.forEach(panel=>panel.classList.toggle('active',panel.dataset.panel===code));window.scrollTo({{top:document.querySelector('.business-tabs').getBoundingClientRect().top+window.scrollY-12,behavior:'smooth'}})}}businessTabs.forEach(tab=>tab.addEventListener('click',()=>activateBusiness(tab.dataset.business)));document.querySelectorAll('.business-card').forEach(card=>card.addEventListener('click',()=>activateBusiness(card.dataset.target)));document.querySelectorAll('.detail-tab').forEach(tab=>tab.addEventListener('click',()=>{{const panel=tab.closest('.business-panel'),target=tab.dataset.detailTab;panel.querySelectorAll('.detail-tab').forEach(item=>item.classList.toggle('active',item===tab));panel.querySelectorAll('.detail-pane').forEach(item=>item.classList.toggle('active',item.dataset.detailPane===target))}}));</script></body></html>""".format(style=STYLE, date=esc(data.get("generatedAt") or "—"), count=esc(query_count), dimensions=esc(" / ".join(evaluated) or "未执行维度"), batch=esc(batch), tabs="".join(tabs), overview=render_summary(overview), cards="".join(cards), panels="".join(panels))


def render(data: dict[str, Any]) -> str:
    """Sole production rendering entry for GOVERNANCE_DASHBOARD_V2."""
    return render_dashboard(data)
