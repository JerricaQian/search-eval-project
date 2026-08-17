#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将历史 Phase2 清单的卡片类型收敛为稳定的展示结构分类。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("/Users/qianjing/Desktop/search-eval-project")
OUT = ROOT / "screenshots-out"
MAPPING = {
    "酒店卡片": "商家卡片-无下挂",
    "度假/酒店套餐卡片": "商品卡片",
    "到餐团购套餐卡片": "商品卡片",
    "宏观组件": "其他异构组件",
}


def main() -> None:
    changed_files = 0
    changed_cards = 0
    for path in sorted(OUT.glob("elements_*.json")):
        if path.name.endswith(".audit.json"):
            continue
        manifest = json.loads(path.read_text(encoding="utf-8"))
        dirty = False
        for card in manifest.get("cards", []):
            old_type = card.get("卡片类型")
            new_type = MAPPING.get(old_type)
            if new_type:
                card["卡片类型"] = new_type
                dirty = True
                changed_cards += 1
        if dirty:
            path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed_files += 1
    print(json.dumps({"files": changed_files, "cards": changed_cards}, ensure_ascii=False))


if __name__ == "__main__":
    main()
