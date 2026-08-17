#!/usr/bin/env python3
"""Synchronize approved scene evaluation results into the fixed consolidated report layout.

This script only replaces the report-data payload. The report's HTML structure and CSS remain
unchanged; evidence is rendered by the existing details panel in the client-side template.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path("/Users/qianjing/Desktop/search-eval-project")
REPORT = ROOT / "reports" / "meituan_eval_report_首评-单一元素_32张_最终.html"
SCORE_BY_RATING = {"优秀": 100, "达标": 65, "不达标": 0}


def report_unit(result: dict) -> tuple[str, dict]:
    """Flatten a phase3 result while preserving its skill-specific evidence."""
    unit = result["units"][0]
    details = unit.get("details", {})
    issues = []
    for issue in details.get("issues", []):
        normalized = dict(issue)
        # The fixed report displays `reason`; phase3 evidence records `finding`.
        normalized.setdefault("reason", normalized.get("finding", ""))
        issues.append(normalized)
    return result["skill"], {
        "skill": result["skill"],
        "label": "",  # Kept from the existing report unit below.
        "rating": unit["rating"],
        "score": SCORE_BY_RATING[unit["rating"]],
        "reason": unit.get("reason", ""),
        "summary": details.get("summary", ""),
        "overview": details.get("overview", {}),
        "issues": issues,
        "details": {"evidence": details.get("evidence", {})},
    }


html = REPORT.read_text(encoding="utf-8")
match = re.search(r'<script id="report-data" type="application/json">(.*?)</script>', html)
if not match:
    raise SystemExit("report-data JSON not found")
data = json.loads(match.group(1))

for target in data["scenes"]:
    scene_name = target["name"]
    result_stem = target["id"]
    # 原始评测结果属于过程文件；报告目录仅保留交付 HTML。
    # 兼容已归档的历史命名和工作流后续生成的中文命名。
    artifact_dir = ROOT / ".artifacts" / "过程文件-评测结果与审计"
    candidates = [
        artifact_dir / f".eval_results_{result_stem}_dual.json",
        artifact_dir / f"评测原始结果_{result_stem}.json",
    ]
    result_path = next((path for path in candidates if path.exists()), None)
    if result_path is None:
        raise SystemExit(f"result file missing from report synchronization: {candidates}")
    for result in json.loads(result_path.read_text(encoding="utf-8")):
        skill, refreshed = report_unit(result)
        old = target["units"].get(skill)
        if old is None:
            raise SystemExit(f"skill missing from report data: {scene_name}/{skill}")
        refreshed["label"] = old["label"]
        target["units"][skill] = refreshed

all_units = [unit for scene in data["scenes"] for unit in scene["units"].values()]
data["meta"]["totalElements"] = sum(int(scene.get("totalElements", 0)) for scene in data["scenes"])
data["meta"]["totalScore"] = sum(unit["score"] for unit in all_units)
data["meta"]["scoreAverage"] = round(data["meta"]["totalScore"] / len(all_units), 1)
data["meta"]["issueCount"] = sum(len(unit.get("issues", [])) for unit in all_units)

payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
html = html[:match.start(1)] + payload + html[match.end(1):]

# Keep all existing markup/CSS intact. Only add evidence rows inside the existing details pane.
evidence_render = "${u.details?.evidence?.assessmentRows?.length?`<p class=\"muted\"><b>评测证据（${esc(u.details.evidence.evaluationGranularity)}，${u.details.evidence.evaluatedUnitCount}个原始单位）</b></p>${u.details.evidence.assessmentRows.map(r=>`<p class=\"muted\">${esc(r.unitId)}｜${esc(r.component??r.scope??'')}｜${esc(r.rating)}｜${esc(r.finding)}</p>`).join('')}`:''}"
issue_render = "${u.issues.length?u.issues.map(i=>issue(i,s)).join(''):'<p class=\"none\">无问题项</p>'}"
# Previous retries could append the exact evidence fragment repeatedly. Remove every copy,
# then insert it exactly once immediately before the existing issue renderer.
while evidence_render in html:
    html = html.replace(evidence_render, "")
if issue_render not in html:
    raise SystemExit("fixed report issue render anchor not found")
html = html.replace(issue_render, evidence_render + issue_render, 1)
REPORT.write_text(html, encoding="utf-8")

print(json.dumps({
    "report": str(REPORT),
    "totalElements": data["meta"]["totalElements"],
    "totalScore": data["meta"]["totalScore"],
    "scoreAverage": data["meta"]["scoreAverage"],
    "issues": data["meta"]["issueCount"],
    "scenesSynchronized": len(data["scenes"]),
}, ensure_ascii=False))
