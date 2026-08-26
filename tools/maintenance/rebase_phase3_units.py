#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a new audited Phase3 result file by replacing named Tab units.

Used for a bounded re-evaluation after Phase2 facts or a deterministic metric
scope changes.  Unchanged units remain byte-for-meaning copies of the prior
validated result; callers must supply the complete re-assessed unit payloads.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--updates", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    results: list[dict[str, Any]] = json.loads(args.base.read_text(encoding="utf-8"))
    updates: list[dict[str, Any]] = json.loads(args.updates.read_text(encoding="utf-8"))
    update_map = {(item["dimension"], item["skill"], item["tab"]): item["unit"] for item in updates}
    seen: set[tuple[str, str, str]] = set()
    for evaluation in results:
        dimension = str(evaluation.get("dimension", ""))
        skill = str(evaluation.get("skill", ""))
        for index, unit in enumerate(evaluation.get("units") or []):
            key = (dimension, skill, str(unit.get("tab", "")))
            if key in update_map:
                evaluation["units"][index] = update_map[key]
                seen.add(key)
    missing = sorted(set(update_map) - seen)
    if missing:
        raise ValueError(f"update_target_missing:{missing}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updated": len(seen), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
