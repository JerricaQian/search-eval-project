#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render a single-query Phase5 DETAIL_V1 report from validated upstream data."""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from screenshot_naming import parse_screenshot_name


DIMENSION_NAMES = {
    "phase3-single_element-eval": "单一元素维度",
    "phase3-card_or_component-eval": "组件/卡片维度",
    "phase3-page_framework-eval": "页面维度",
}
RATING_CLASS = {"优秀": "good", "达标": "pass", "不达标": "bad"}


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def screen_label(image_path: str) -> str:
    parsed = parse_screenshot_name(image_path)
    return f"第{parsed.screen}屏" if parsed else "当前截图"


def rating_tag(rating: str) -> str:
    return f"<span class='rating {RATING_CLASS.get(rating, 'pass')}'>{esc(rating)}</span>"


def json_block(value: Any) -> str:
    return f"<pre>{esc(json.dumps(value, ensure_ascii=False, indent=2))}</pre>"


def readable_target(issue: dict[str, Any]) -> str:
    component = issue.get("component") or issue.get("pageArea") or "当前区域"
    content = issue.get("content")
    element_type = issue.get("elementType")
    if content and element_type:
        return f"{esc(component)} · {esc(element_type)}：「{esc(content)}」"
    return esc(component)


def render_issue(issue: dict[str, Any], screenshot: str) -> str:
    finding = issue.get("finding") or {}
    evidence = issue.get("evidenceImage")
    evidence_html = "<div class='evidence-empty'>无元素级证据，待人工定位</div>"
    if evidence:
        src = "file://" + str(evidence)
        evidence_html = (
            f"<a class='evidence' href='{esc(src)}' target='_blank' rel='noopener'>"
            f"<img src='{esc(src)}' alt='问题整页证据图'></a>"
        )
    return f"""
      <article class='issue'>
        <div class='issue-head'>{rating_tag(str(issue.get('rating', '达标')))}<strong>{readable_target(issue)}</strong><span>{esc(screen_label(screenshot))}</span></div>
        <p><b>问题类型：</b>{esc(issue.get('dimension', '—'))}</p>
        <p>{esc(issue.get('description', '—'))}</p>
        <dl><dt>事实</dt><dd>{esc(finding.get('observableFact', '—'))}</dd><dt>判定依据</dt><dd>{esc(finding.get('ruleOrThreshold', '—'))}</dd><dt>用户影响</dt><dd>{esc(finding.get('userImpact', '—'))}</dd></dl>
        <div class='rec'><b>建议</b>{esc(issue.get('recommendation', '—'))}</div>
        {evidence_html}
      </article>"""


def render_eval(unit: dict[str, Any], title: str) -> str:
    details = unit.get("details") or {}
    screenshot = str(details.get("screenshot") or "")
    issues = details.get("issues") or []
    body = "".join(render_issue(issue, screenshot) for issue in issues)
    if not issues:
        body = "<p class='none'>无问题项</p>"
    overview = details.get("overview") or {}
    distribution = details.get("distribution") or {}
    return f"""
      <article class='eval-card' data-state={'problem' if unit.get('rating') != '优秀' else 'clear'}>
        <header><div><h3>{esc(title)}</h3><p>{esc(unit.get('reason', '—'))}</p><p class='summary'>{esc(details.get('summary', '—'))}</p></div>{rating_tag(str(unit.get('rating', '达标')))}</header>
        <details><summary>评测项概览与分布</summary><h4>概览</h4>{json_block(overview)}<h4>分布</h4>{json_block(distribution)}</details>
        <div class='issues'>{body}</div>
      </article>"""


def render_dimension(dimension: dict[str, Any]) -> str:
    by_skill = {item.get("skill"): item for item in dimension.get("evals", [])}
    cards: list[str] = []
    for skill in dimension.get("skills", []):
        result = by_skill.get(skill.get("skill"))
        if not result:
            cards.append(f"<article class='eval-card'><h3>{esc(skill.get('title', skill.get('skill')))}</h3><p>未发现评测结果。</p></article>")
            continue
        unit = next((item for item in result.get("units", []) if item.get("tab") == "全部"), None)
        if unit:
            cards.append(render_eval(unit, str(skill.get("title") or skill.get("skill"))))
    problem_count = sum("data-state=problem" in card for card in cards)
    clear_count = len(cards) - problem_count
    key = esc(dimension["dimension"])
    return f"""
      <section class='dimension-pane' data-dimension-pane='{key}'>
        <div class='subtabs'><button class='subtab active' data-subtab='{key}-problem'>待优化结论（{problem_count}）</button><button class='subtab' data-subtab='{key}-clear'>无待优化结论（{clear_count}）</button></div>
        <div class='subpane active' data-subpane='{key}-problem'>{''.join(card for card in cards if 'data-state=problem' in card) or '<p class="none">未发现待优化项</p>'}</div>
        <div class='subpane' data-subpane='{key}-clear'>{''.join(card for card in cards if 'data-state=clear' in card) or '<p class="none">未发现无问题结论</p>'}</div>
      </section>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--computed", required=True, type=Path)
    parser.add_argument("--scope", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    data = load(args.computed)
    scope = load(args.scope)
    dimensions = data.get("dimensions") or []
    overall = (data.get("overall") or [{}])[0]
    all_units = [unit for dim in dimensions for ev in dim.get("evals", []) for unit in ev.get("units", [])]
    issues = [issue for unit in all_units for issue in (unit.get("details") or {}).get("issues") or []]
    fail = [issue for issue in issues if issue.get("rating") == "不达标"]
    passed = [issue for issue in issues if issue.get("rating") == "达标"]
    title = f"{data.get('query', '截图')}｜{len(dimensions)}维度｜{screen_label((data.get('images') or [{}])[0].get('original', ''))}"
    tabs = "".join(
        f"<button class='dimension-tab {'active' if index == 0 else ''}' data-dimension-tab='{esc(dim['dimension'])}'>{esc(DIMENSION_NAMES.get(dim['dimension'], dim['dimension']))}</button>"
        for index, dim in enumerate(dimensions)
    )
    panes = "".join(render_dimension(dim) for dim in dimensions)
    raw_rows = []
    for dim in dimensions:
        score = (dim.get("perTab") or {}).get("全部") or {}
        raw_rows.append(f"<tr><td>{esc(DIMENSION_NAMES.get(dim['dimension'], dim['dimension']))}</td><td>{esc(score.get('raw', '—'))}</td><td>{esc(score.get('min', '—'))}</td><td>{esc(score.get('max', '—'))}</td><td>{esc(score.get('normalized', '—'))}</td></tr>")
    html_text = f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{esc(title)}</title><style>
    :root{{--ink:#17171b;--muted:#65656d;--line:#e7e7ec;--bg:#f7f7fa;--card:#fff;--good:#2e7d32;--pass:#f9a825;--bad:#c62828}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;line-height:1.55}}main{{max-width:1040px;margin:auto;padding:42px 24px 80px}}h1{{font-size:32px;margin:0 0 10px}}h2{{font-size:19px;margin:0}}h3{{margin:0;font-size:17px}}p{{margin:7px 0}}.muted,.summary{{color:var(--muted)}}.score{{font-size:46px;font-weight:800;letter-spacing:-1.5px}}.overview{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin:22px 0}}.overview section,.eval-card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}.overview b{{display:block;font-size:13px;color:var(--muted)}}.rating{{display:inline-block;white-space:nowrap;border-radius:7px;padding:3px 9px;color:#fff;font-size:12px;font-weight:700}}.good{{background:var(--good)}}.pass{{background:var(--pass)}}.bad{{background:var(--bad)}}.dimension-tabs,.subtabs{{display:flex;gap:8px;flex-wrap:wrap;margin:30px 0 16px}}button{{border:1px solid var(--line);background:#fff;border-radius:8px;padding:8px 12px;color:var(--ink);font:inherit;cursor:pointer}}button.active{{background:#1d1d22;color:#fff;border-color:#1d1d22}}.dimension-pane,.subpane{{display:none}}.dimension-pane.active,.subpane.active{{display:block}}.eval-card{{margin:14px 0}}.eval-card>header{{display:flex;gap:16px;justify-content:space-between;align-items:flex-start}}details{{margin-top:12px;border-top:1px solid var(--line);padding-top:10px}}summary{{cursor:pointer;color:var(--muted)}}pre{{overflow:auto;border-radius:8px;background:#f5f5f7;padding:10px;font-size:12px}}.issue{{border-top:1px solid var(--line);margin-top:16px;padding-top:16px}}.issue-head{{display:flex;gap:9px;align-items:center;flex-wrap:wrap}}.issue-head span{{color:var(--muted);font-size:13px}}dl{{display:grid;grid-template-columns:80px 1fr;gap:6px 10px;font-size:14px}}dt{{font-weight:700}}dd{{margin:0;color:var(--muted)}}.rec{{margin-top:12px;padding:10px 12px;border-left:3px solid #1d1d22;background:#f5f5f7;font-size:14px}}.rec b{{margin-right:8px}}.evidence{{display:block;margin-top:14px;border:1px solid var(--line);border-radius:9px;overflow:hidden}}.evidence img{{display:block;width:100%;height:auto}}.evidence-empty,.none{{padding:16px;color:var(--muted);text-align:center;border:1px dashed var(--line);border-radius:8px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:9px;border:1px solid var(--line);text-align:left}}th{{background:#24242a;color:#fff}}tr:nth-child(even){{background:#f6f6f8}}@media(max-width:720px){{main{{padding:28px 14px 60px}}.overview{{grid-template-columns:1fr}}h1{{font-size:26px}}.score{{font-size:40px}}}}
    </style></head><body><main><header><h1>{esc(title)}</h1><p class='muted'>范围：{esc(scope.get('label', '—'))}</p></header><section class='overview'><section><b>整体得分</b><div class='score'>{esc(overall.get('normalizedScore', '—'))}</div><p>{esc(overall.get('verdict', '—'))}</p></section><section><b>评测项概览</b><p>已执行 {len(all_units)} 项评测；覆盖 {len(dimensions)} 个维度。</p><p>优秀 {sum(unit.get('rating') == '优秀' for unit in all_units)} 项，达标 {sum(unit.get('rating') == '达标' for unit in all_units)} 项，不达标 {sum(unit.get('rating') == '不达标' for unit in all_units)} 项。</p></section><section><b>问题概要</b><p>不达标：{len(fail)} 项；达标：{len(passed)} 项。</p><p>{'待优化项涉及当前第1屏。' if issues else '未发现待优化项。'}</p></section></section><details><summary>跨维度综合分计算明细</summary><table><thead><tr><th>维度</th><th>原始分</th><th>最低分</th><th>最高分</th><th>归一化分</th></tr></thead><tbody>{''.join(raw_rows)}</tbody></table></details><nav class='dimension-tabs'>{tabs}</nav>{panes}</main><script>
    const dTabs=[...document.querySelectorAll('.dimension-tab')],dPanes=[...document.querySelectorAll('.dimension-pane')];function activateDimension(key){{dTabs.forEach(x=>x.classList.toggle('active',x.dataset.dimensionTab===key));dPanes.forEach(x=>x.classList.toggle('active',x.dataset.dimensionPane===key));}}dTabs.forEach(x=>x.addEventListener('click',()=>activateDimension(x.dataset.dimensionTab)));document.querySelectorAll('.dimension-pane').forEach((pane,index)=>{{if(index===0)pane.classList.add('active');pane.querySelectorAll('.subtab').forEach(tab=>tab.addEventListener('click',()=>{{const key=tab.dataset.subtab;pane.querySelectorAll('.subtab').forEach(x=>x.classList.toggle('active',x===tab));pane.querySelectorAll('.subpane').forEach(x=>x.classList.toggle('active',x.dataset.subpane===key));}}));}});
    </script></body></html>"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html_text, encoding="utf-8")
    print(f"REPORT_OK={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
