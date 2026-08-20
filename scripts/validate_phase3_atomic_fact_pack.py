#!/usr/bin/env python3
"""Validate Phase3 facts derived from a valid Atomic v3 manifest."""
from __future__ import annotations
import argparse, json
from pathlib import Path

def main() -> int:
 p=argparse.ArgumentParser();p.add_argument("fact_pack",type=Path);p.add_argument("--require",action="append",default=[]);a=p.parse_args();d=json.loads(a.fact_pack.read_text())
 errors=[]
 if d.get("contractVersion")!="phase3.atomic-fact-pack.v1" or not d.get("valid"): errors.append("fact_pack_invalid")
 if not all(d.get("integrity",{}).get(k) is True for k in ("atomicSchemaValid","publicationReady","sourceHashValid")): errors.append("atomic_integrity_invalid")
 required={"hierarchy":"hierarchyFacts","alignment":"alignmentFacts","structure":"structureFacts"}
 for name in a.require:
  if name not in required: errors.append(f"unknown_requirement:{name}")
  elif not d.get(required[name]): errors.append(f"missing_phase3_facts:{name}")
 result={"valid":not errors,"errors":errors,"total":d.get("inventory",{}).get("sourceManifestTotal",0)};print(json.dumps(result,ensure_ascii=False));return 0 if not errors else 2
if __name__=="__main__":raise SystemExit(main())
