#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用已修正的 Phase2 清单撤销已确认的假阳性 Phase3 问题。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ARTIFACTS = Path("/tmp/first-element-32-artifacts")
RESULT = ARTIFACTS / ".eval_results_啤酒_首评-单一元素-2_dual.json"


def main() -> None:
    data: list[dict[str, Any]] = json.loads(RESULT.read_text(encoding="utf-8"))
    result = next(item for item in data if item.get("skill") == "eval-1-supply-completeness")
    unit = result["units"][0]
    details: dict[str, Any] = unit["details"]
    issues = details["issues"]
    details["issues"] = [issue for issue in issues if issue.get("component") != "C1"]
    details["overview"] = {"total": 6, "excellent": 5, "pass": 0, "fail": 1, "failRate": "16.7%"}
    details["distribution"] = [
        {"dimension": "优秀", "count": 5, "elements": "图筛、快筛、C1、C2、C3"},
        {"dimension": "不达标", "count": 1, "elements": "C4"},
    ]
    details["summary"] = (
        "逐组件复核图筛、快筛与 C1-C4 四张商品卡。C1 已由修正后的 Phase2 清单确认存在“31分钟”配送时效，"
        "撤销原配送时效缺失结论；C4 在可见截断区域内仍缺少核心价格信息。"
    )
    details["evidence"]["sourceManifestTotal"] = 40
    for row in details["evidence"]["assessmentRows"]:
        if row.get("unitId") == "C1":
            row["rating"] = "优秀"
            row["finding"] = (
                "标题、价格¥23.9、头图、月售500+、配送时效31分钟、商家、闪购、起送¥25、"
                "免配送费、2.4km及促销标签均完整可视，缺失=0。"
            )
    unit["rating"] = "不达标"
    unit["weightedScore"] = -2
    unit["reason"] = "按 eval-1 两档制逐组件复核：C1 配送时效已确认存在；仅 C4 因可见截断导致核心价格不可视，取最差聚合为 Tab 级不达标。"
    RESULT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(RESULT)


if __name__ == "__main__":
    main()
