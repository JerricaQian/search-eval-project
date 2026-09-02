#!/usr/bin/env python3
"""Deterministically package one query's validated Phase3 results for Phase5.

This script performs no rating or score calculation. It only groups validated
results with the selected scope, tabs, and report images.

Input contracts:
  --results        Phase3 evalResultFile path: JSON array of
                    {dimension, skill, units:[{tab, rating, ...}]}
  --eval-targets    JSON array of {dimension, skill, title, weight, aggregate, extra}
                    (same shape as workflow's `evalTargets`)
  --tabs            JSON array of tab name strings
  --images          JSON array of {original, annotated} (optional, default [])
  --scope           JSON object with selected/full coverage (optional, default {})
  --query           current query string
  --output          path to write the computed summary JSON
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--eval-targets", required=True)
    parser.add_argument("--tabs", required=True)
    parser.add_argument("--images", default="[]")
    parser.add_argument("--scope", default="{}")
    parser.add_argument("--query", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    evals: list[dict[str, Any]] = json.loads(Path(args.results).read_text(encoding="utf-8"))
    eval_targets: list[dict[str, Any]] = json.loads(Path(args.eval_targets).read_text(encoding="utf-8"))
    tabs: list[str] = json.loads(Path(args.tabs).read_text(encoding="utf-8"))
    images_raw = args.images
    images = json.loads(Path(images_raw).read_text(encoding="utf-8")) if Path(images_raw).exists() else json.loads(images_raw)
    scope_raw = args.scope
    scope = json.loads(Path(scope_raw).read_text(encoding="utf-8")) if Path(scope_raw).exists() else json.loads(scope_raw)
    if not isinstance(scope, dict):
        raise ValueError("scope_must_be_object")

    evals_by_dim: dict[str, dict[str, Any]] = {}
    for t in eval_targets:
        dim = t["dimension"]
        evals_by_dim.setdefault(dim, {"skills": [], "evals": []})
        evals_by_dim[dim]["skills"].append({"skill": t["skill"], "title": t.get("title", ""), "extra": t.get("extra", "")})
    for e in evals:
        dim = e.get("dimension")
        if dim in evals_by_dim:
            evals_by_dim[dim]["evals"].append(e)

    dimension_summaries = []
    for dim, info in evals_by_dim.items():
        dimension_summaries.append({
            "dimension": dim,
            "skills": [{"skill": s["skill"], "title": s["title"], "extra": s["extra"]} for s in info["skills"]],
            "evals": info["evals"],
        })

    computed = {
        "query": args.query,
        "tabs": tabs,
        "images": images,
        "overall": [{"tab": tab} for tab in tabs],
        "dimensions": dimension_summaries,
        "scope": scope,
    }

    Path(args.output).write_text(json.dumps(computed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"COMPUTED_OK=true OUTPUT={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
