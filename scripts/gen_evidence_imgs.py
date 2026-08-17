#!/usr/bin/env python3
"""Phase 4: Generate full-page red-box evidence images for all issues with evidenceImage paths."""
import json
import sys
from pathlib import Path
import cv2
import numpy as np

PROJECT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
SCENE = sys.argv[2] if len(sys.argv) > 2 else "安睡裤"
TAB = sys.argv[3] if len(sys.argv) > 3 else "全部"

results_path = PROJECT / ".artifacts/过程文件-评测结果与审计/32词2.0_20260816" / SCENE / "phase3" / f"eval_results_{SCENE}_{TAB}.json"
screenshot_path = PROJECT / "screenshots" / f"{SCENE}_{TAB}_1.png"
evidence_dir = PROJECT / "screenshots-out/evidence" / SCENE
evidence_dir.mkdir(parents=True, exist_ok=True)

results = json.loads(results_path.read_text(encoding="utf-8"))
img_orig = cv2.imread(str(screenshot_path))
h, w = img_orig.shape[:2]

generated = []
skipped = []

for r in results:
    skill = r["skill"]
    dim = r.get("dimension", "")
    for u in r.get("units", []):
        details = u.get("details") or {}
        issues = details.get("issues") or []
        for iss in issues:
            ev_path_str = iss.get("evidenceImage", "")
            if not ev_path_str:
                continue
            ev_path = PROJECT / ev_path_str
            
            # Draw red box on a copy
            img = img_orig.copy()
            
            # For component-level issues: use coord
            coord = iss.get("coord")
            if coord and len(coord) == 4:
                x, y, bw, bh = [int(c) for c in coord]
                x0 = max(0, x)
                y0 = max(0, y)
                x1 = min(w, x + bw)
                y1 = min(h, y + bh)
                cv2.rectangle(img, (x0, y0), (x1, y1), (0, 0, 255), 6)
                # Also draw component card outline if component field present
                comp = iss.get("component")
                if comp:
                    # Find component coord from manifest
                    pass
            
            cv2.imwrite(str(ev_path), img)
            generated.append(str(ev_path))
            print(f"generated: {ev_path.name}")

print(f"\nTotal generated: {len(generated)}")
