#!/usr/bin/env python3
"""Classify validation failures without mutating Phase2 or fabricating measurements."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def main() -> int:
 p=argparse.ArgumentParser(); p.add_argument("audit",type=Path);p.add_argument("--output",type=Path,required=True);a=p.parse_args(); d=json.loads(a.audit.read_text())
 errors=d.get("errors",[]); categories=[]
 for e in errors:
  if "measurement_" in e or "debugImage" in e: kind="measurement_missing"; action="rerun_affected_phase3_skill"
  elif "overview_total" in e or "sourceManifestTotal" in e: kind="count_contract_conflict"; action="regenerate_skill_run_plan_and_result"
  elif "assessmentRow_missing" in e or "issue_missing" in e: kind="result_schema_missing"; action="regenerate_affected_result_template"
  else: kind="phase3_result_invalid"; action="rerun_affected_phase3_skill"
  categories.append({"error":e,"category":kind,"action":action})
 out={"valid":not errors,"categories":categories,"phase2MutationAllowed":False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
