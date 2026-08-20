#!/usr/bin/env python3
"""Create a compact per-Skill run plan from a Phase3 Atomic Fact Pack."""
from __future__ import annotations
import argparse, json
from pathlib import Path

PHOTO_EXCLUDED_SKILLS = {"eval-2-color-logic-single-element"}

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("fact_pack", type=Path); p.add_argument("--skill", required=True); p.add_argument("--dimension", required=True); p.add_argument("--output", type=Path, required=True); a=p.parse_args()
    pack=json.loads(a.fact_pack.read_text(encoding="utf-8")); elements=pack["manifestAudit"]["activeElements"]
    excluded=[]
    if a.skill in PHOTO_EXCLUDED_SKILLS:
        excluded=[{"id": e["id"], "reason": "商家/商品图片"} for e in elements if e.get("render", {}).get("isPhoto")]
    excluded_ids={x["id"] for x in excluded}; evaluated=[e["id"] for e in elements if e["id"] not in excluded_ids]
    if a.dimension == "phase3-page_framework-eval": evaluated=["page"]
    elif a.dimension == "phase3-card_or_component-eval":
        evaluated=[c["cardId"] for c in pack["structureFacts"]["cards"]]
    plan={"contractVersion":"phase3.skill-run-plan.v1","skill":a.skill,"dimension":a.dimension,"factPack":str(a.fact_pack),"sourceManifestTotal":pack["inventory"]["sourceManifestTotal"],"excludedUnits":excluded,"evaluatedUnitIds":evaluated,"evaluatedUnitCount":len(evaluated),"overviewTotal":len(evaluated),"measurementRequired":a.skill in {"eval-2-color-logic-single-element","eval-3-color-logic","eval-4-element-complexity","eval-6-info-partitioning","eval-3-page-color-logic","eval-6-info-comparability","eval-7-info-authenticity","eval-8-info-redundancy"}}
    a.output.parent.mkdir(parents=True, exist_ok=True); a.output.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(plan,ensure_ascii=False))
if __name__ == "__main__": raise SystemExit(main())
