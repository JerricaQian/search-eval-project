#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修正经原图复核确认的 Phase2 元素清单事实，并重新生成标注与审计产物。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path("/Users/qianjing/Desktop/search-eval-project")
OUT = ROOT / "screenshots-out"
SCENES = ROOT / "phase2-card-annotation" / "scenes"
ANNOTATOR = ROOT / "phase2-card-annotation" / "scripts" / "annotation_scene.py"
VALIDATOR = ROOT / "scripts" / "validate_element_manifest.py"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_card(manifest: dict[str, Any], card_id: str) -> dict[str, Any]:
    return next(card for card in manifest["cards"] if card["cardId"] == card_id)


def repair_beer() -> None:
    manifest_path = OUT / "elements_啤酒_首评-单一元素-2.json"
    scene_path = SCENES / "啤酒_全部_1_副本.json"
    manifest = read_json(manifest_path)
    scene = read_json(scene_path)
    card = find_card(manifest, "C1")
    price_region = next(region for region in card["regions"] if region["name"] == "价格区")
    element = {
        "id": "C1R3E1-02", "所属组件": "C1", "元素类型": "文本",
        "内容简述": "原文:31分钟", "坐标": [1044, 1264, 125, 50],
        "isExcluded": False, "excludeReason": "",
    }
    if not any(item["id"] == element["id"] for item in price_region["elements"]):
        price_region["elements"].append(element)
    price_region["coord"] = [412, 1246, 757, 68]
    write_json(manifest_path, manifest)

    if not any(item["id"] == "c1-delivery-time" for item in scene["annotations"]):
        scene["annotations"].append({
            "id": "c1-delivery-time", "label": "商品卡1_配送时效", "x": 1044, "y": 1264,
            "w": 125, "h": 50, "kind": "part", "parent": "c1-border",
            "source": "original-image-recheck-20260805", "semantic_role": "delivery_time",
            "elementId": "C1R3E1-02",
        })
    write_json(scene_path, scene)
    subprocess.run(["python3", str(ANNOTATOR), str(scene_path)], check=True)
    subprocess.run([
        "python3", str(VALIDATOR), str(manifest_path),
        "--audit", str(OUT / "elements_啤酒_首评-单一元素-2.audit.json"),
    ], check=True)


def repair_barbecue() -> None:
    manifest_path = OUT / "elements_烧烤_首评-单一元素-4.json"
    manifest = read_json(manifest_path)
    for card_id, evidence in {
        "C2": ["甄选烧烤四人餐", "可随时退", "过期退"],
        "C6": ["朝日扎啤烧烤季 日料放题", "烧烤双人餐 酒水梅子酒"],
    }.items():
        card = find_card(manifest, card_id)
        card["卡片类型"] = "到餐团购套餐卡片"
        card.update({
            "ownershipScope": "business",
            "businessCode": "dine_in",
            "businessName": "到餐",
            "businessConfidence": "high",
            "cardTypeCode": "dine_in_package_card",
            "cardTypeName": "到餐团购套餐卡片",
            "resultType": "package",
            "classificationEvidence": evidence,
        })
    write_json(manifest_path, manifest)
    subprocess.run([
        "python3", str(VALIDATOR), str(manifest_path),
        "--audit", str(OUT / "elements_烧烤_首评-单一元素-4.audit.json"),
    ], check=True)


if __name__ == "__main__":
    repair_beer()
    repair_barbecue()
    print("phase2 repairs completed")
