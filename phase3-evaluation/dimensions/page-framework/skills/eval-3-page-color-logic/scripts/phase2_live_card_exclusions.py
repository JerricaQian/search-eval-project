#!/usr/bin/env python3
"""从当前图片的 Phase2 manifest 提取直播卡页面色彩强制候选排除框。

Phase2 bounds 使用 [x, y, w, h]；页面色彩脚本 exclude_regions 使用
[y1, y2, x1, x2]。本工具只做确定性遍历和坐标换算，不根据像素颜色猜测边界。
如直播卡内另有独立 UI 子元素，应在调试图核查阶段拆分候选框以保留这些元素。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable


LIVE_CARD_TYPES = {"live_card", "heterogeneous_live_card"}
CONFIRMED_VISIBILITY = {"confirmed", "complete"}


def iter_modules(data: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    """兼容 atomic-v3 modulesById 与 pageFacts.modules 两种承载位置。"""
    candidates = [data.get("modulesById")]
    page_facts = data.get("pageFacts")
    if isinstance(page_facts, dict):
        candidates.extend([page_facts.get("modulesById"), page_facts.get("modules")])

    seen: set[tuple[str, int]] = set()
    for candidate in candidates:
        if isinstance(candidate, dict):
            items = candidate.items()
        elif isinstance(candidate, list):
            items = (
                (str(module.get("id") or module.get("moduleId") or f"module-{index}"), module)
                for index, module in enumerate(candidate)
                if isinstance(module, dict)
            )
        else:
            continue

        for module_id, module in items:
            if not isinstance(module, dict):
                continue
            key = (str(module_id), id(module))
            if key in seen:
                continue
            seen.add(key)
            yield str(module_id), module


def convert_bounds(bounds: Any) -> list[int]:
    if not isinstance(bounds, list) or len(bounds) != 4:
        raise ValueError(f"bounds 必须是 [x,y,w,h]，实际为：{bounds!r}")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in bounds):
        raise ValueError(f"bounds 必须全部为数值，实际为：{bounds!r}")
    x, y, width, height = bounds
    if width <= 0 or height <= 0:
        raise ValueError(f"bounds 宽高必须大于 0，实际为：{bounds!r}")
    return [round(y), round(y + height), round(x), round(x + width)]


def extract_live_card_regions(data: dict[str, Any]) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    for module_id, module in iter_modules(data):
        module_type = module.get("type") or module.get("module") or module.get("moduleType")
        visibility = module.get("visibility") or module.get("status")
        if module_type not in LIVE_CARD_TYPES or visibility not in CONFIRMED_VISIBILITY:
            continue
        bounds = module.get("bounds") or module.get("coord")
        regions.append(
            {
                "sourceModuleId": module_id,
                "sourceType": module_type,
                "visibility": visibility,
                "phase2Bounds": bounds,
                "excludeRegion": convert_bounds(bounds),
                "reason": "live_card_content_image_not_ui_design_color",
            }
        )
    return regions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="当前图片的 Phase2 manifest JSON")
    args = parser.parse_args()

    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    regions = extract_live_card_regions(data)
    result = {
        "manifest": str(args.manifest),
        "regionCount": len(regions),
        "exclude_regions": [region["excludeRegion"] for region in regions],
        "regions": regions,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
