#!/usr/bin/env python3
"""Deterministic score normalization for a single query's Phase3 eval results.

Moves the JS-side arithmetic (formerly inline in meituan_eval_workflow.js)
into a standalone script so the merged phase2345-query-pipeline agent can
compute its own `computedJson` for Stage D without a round-trip to the
orchestrator between Stage B and Stage D.

Input contracts:
  --results        Phase3 evalResultFile path: JSON array of
                    {dimension, skill, units:[{tab, weightedScore, ...}]}
  --eval-targets    JSON array of {dimension, skill, title, weight, aggregate, extra}
                    (same shape as workflow's `evalTargets`)
  --tabs            JSON array of tab name strings
  --images          JSON array of {original, annotated} (optional, default [])
  --query           current query string
  --output          path to write the computed summary JSON
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def verdict_for(score: float) -> str:
    if score >= 80:
        return "⭐优质"
    if score >= 60:
        return "✅良好"
    if score >= 40:
        return "⚠️一般"
    if score >= 20:
        return "❗较差"
    return "🚫极差"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--eval-targets", required=True)
    parser.add_argument("--tabs", required=True)
    parser.add_argument("--images", default="[]")
    parser.add_argument("--query", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    evals: list[dict[str, Any]] = json.loads(Path(args.results).read_text(encoding="utf-8"))
    eval_targets: list[dict[str, Any]] = json.loads(Path(args.eval_targets).read_text(encoding="utf-8"))
    tabs: list[str] = json.loads(Path(args.tabs).read_text(encoding="utf-8"))
    images_raw = args.images
    images = json.loads(Path(images_raw).read_text(encoding="utf-8")) if Path(images_raw).exists() else json.loads(images_raw)

    evals_by_dim: dict[str, dict[str, Any]] = {}
    for t in eval_targets:
        dim = t["dimension"]
        evals_by_dim.setdefault(dim, {"skills": [], "evals": []})
        evals_by_dim[dim]["skills"].append({"skill": t["skill"], "title": t.get("title", ""), "extra": t.get("extra", ""), "weight": t.get("weight", {})})
    for e in evals:
        dim = e.get("dimension")
        if dim in evals_by_dim:
            evals_by_dim[dim]["evals"].append(e)

    dimension_summaries = []
    overall_per_tab = {t: {"sum": 0.0, "count": 0} for t in tabs}

    for dim, info in evals_by_dim.items():
        max_raw = 0.0
        min_raw = 0.0
        for s in info["skills"]:
            w = s["weight"]
            vals = [float(v) for v in [w.get("优秀"), w.get("达标"), w.get("不达标")] if v is not None]
            if not vals:
                continue
            max_raw += max(vals)
            min_raw += min(vals)

        eval_by_skill = {e["skill"]: e for e in info["evals"]}
        per_tab = {}
        for t in tabs:
            raw = 0.0
            for s in info["skills"]:
                ev = eval_by_skill.get(s["skill"])
                if not ev:
                    continue
                unit = next((u for u in ev.get("units", []) if u.get("tab") == t), None)
                if unit:
                    raw += float(unit.get("weightedScore") or 0)
            normalized = 0.0
            if max_raw > min_raw:
                normalized = (raw - min_raw) / (max_raw - min_raw) * 100
            normalized = round(normalized, 1)
            per_tab[t] = {"raw": raw, "min": min_raw, "max": max_raw, "normalized": normalized, "verdict": verdict_for(normalized)}
            overall_per_tab[t]["sum"] += normalized
            overall_per_tab[t]["count"] += 1

        dimension_summaries.append({
            "dimension": dim,
            "skills": [{"skill": s["skill"], "title": s["title"], "extra": s["extra"]} for s in info["skills"]],
            "perTab": per_tab,
            "evals": info["evals"],
        })

    overall_summary = []
    for t in tabs:
        o = overall_per_tab[t]
        normalized = round(o["sum"] / o["count"], 1) if o["count"] > 0 else 0.0
        overall_summary.append({"tab": t, "normalizedScore": normalized, "verdict": verdict_for(normalized)})

    computed = {
        "query": args.query,
        "tabs": tabs,
        "images": images,
        "overall": overall_summary,
        "dimensions": dimension_summaries,
    }

    Path(args.output).write_text(json.dumps(computed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"COMPUTED_OK=true OUTPUT={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
