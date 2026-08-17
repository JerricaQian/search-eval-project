#!/usr/bin/env python3
"""生成 debug 图片用于 eval-3-color-logic 验证"""
import cv2, json
from pathlib import Path
import sys

project = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
scene = sys.argv[2] if len(sys.argv) > 2 else "安睡裤"

img_path = project / "screenshots" / f"{scene}_全部_1.png"
metrics_path = project / ".artifacts/过程文件-指标测量" / f"metrics_{scene}_eval-3-color-logic.json"
out_dir = project / ".artifacts/过程文件-指标测量"

img = cv2.imread(str(img_path))
metrics = json.loads(metrics_path.read_text())

for comp in metrics["components"]:
    cid = comp["cardId"]
    x, y, w, h = comp["coord"]
    crop = img[y:y+h, x:x+w].copy()
    out = out_dir / f"debug_{cid}_{scene}.png"
    cv2.imwrite(str(out), crop)
    print(f"wrote {out}")

out_page = out_dir / f"debug_page_{scene}.png"
cv2.imwrite(str(out_page), img)
print(f"wrote {out_page}")
