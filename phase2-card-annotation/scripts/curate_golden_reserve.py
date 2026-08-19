#!/usr/bin/env python3
"""Add provenance to legacy golden JSON without deleting element truth.

Golden files contain both page/card structure and nested component elements.
The curator may normalise card-type IDs and attach provenance, but it must never
replace a populated card with a boundary-only object or project objects through
a field whitelist.  Card-boundary calibration belongs in golden_page_truth.v2
and is deliberately kept separate from the element-bearing golden manifests.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "phase2-card-annotation" / "golden-sample-results"
TRUTH = ROOT / "phase2-card-annotation" / "references" / "golden_page_truth.v2.json"

TYPE_ALIASES = {
    "商家卡片-图文下挂": "商家卡片_图文下挂",
    "商家卡片-文字下挂": "商家卡片_文字下挂",
    "商家卡片-文下挂": "商家卡片_文字下挂",
    "演出卡": "演出电影卡片",
    "电影影院卡": "演出电影卡片",
    "酒店卡片（商家商品卡）": "酒店卡片",
    "演出/电影卡片": "演出电影卡片",
    "度假/酒店套餐卡片": "度假酒店套餐卡片",
    "特殊广告卡": "广告卡",
}


def card(card_type: str, coord: list[int], position: int, *, name: str = "",
         cropped: bool = False, variant: str = "") -> dict[str, Any]:
    value: dict[str, Any] = {
        "componentType": "result_card",
        "listPosition": position,
        "cardType": card_type,
        "coord": coord,
        "visibleStatus": "naturally_cropped" if cropped else "complete",
        "status": "confirmed",
    }
    if name:
        value["name"] = name
    if variant:
        value["variant"] = variant
    return value


def hetero(coord: list[int], position: int, name: str, *, cropped: bool = False) -> dict[str, Any]:
    return {
        "componentType": "heterogeneous_card",
        "name": name,
        "listPosition": position,
        "cardType": "异构卡",
        "coord": coord,
        "visibleStatus": "naturally_cropped" if cropped else "complete",
        "status": "confirmed",
    }


# Coordinates below are the reviewed component boundaries from the matching
# annotation image (or golden_page_truth.v2 where already calibrated).  They
# intentionally describe only visible screenshot geometry, never OCR fields.
OVERRIDES: dict[str, list[dict[str, Any]]] = {
    "merchant-graphic-hang/库迪.elements.json": [
        card("商家卡片_图文下挂", [0, 554, 1224, 627], 1),
        card("商家卡片_图文下挂", [0, 1269, 1224, 627], 2),
        card("商家卡片_图文下挂", [0, 1984, 1224, 651], 3),
    ],
    "merchant-graphic-hang/烧烤.elements.json": [
        card("商家卡片_图文下挂", [0, 554, 1224, 627], 1),
        card("商家卡片_图文下挂", [0, 1217, 1224, 627], 2),
        card("商家卡片_图文下挂", [0, 1880, 1224, 627], 3),
        card("商家卡片_图文下挂", [0, 2540, 1224, 160], 4, cropped=True),
    ],
    "merchant-graphic-hang/蜜雪冰城.elements.json": [
        card("商家卡片_图文下挂", [0, 1326, 1224, 598], 1),
        card("商家卡片_图文下挂", [0, 1947, 1224, 753], 2, cropped=True),
    ],
    "merchant-graphic-hang/盒马.elements.json": [
        card("商家卡片_图文下挂", [0, 710, 1224, 720], 1),
        card("商家卡片_图文下挂", [0, 1430, 1224, 655], 2),
        card("商家卡片_图文下挂", [0, 2085, 1224, 615], 3, cropped=True),
    ],
    "merchant-graphic-hang/隆江猪脚饭.elements.json": [
        card("商家卡片_图文下挂", [0, 554, 1224, 627], 1),
        card("商家卡片_图文下挂", [0, 1217, 1224, 627], 2),
        card("商家卡片_图文下挂", [0, 1932, 1224, 627], 3),
        card("商家卡片_图文下挂", [0, 2565, 1224, 135], 4, cropped=True),
    ],
    "merchant-text-hang/商家卡片-文下挂-搜索词为体检.elements.json": [
        card("商家卡片_文字下挂", [0, 849, 1224, 386], 1),
        card("商家卡片_文字下挂", [0, 1258, 1224, 386], 2),
        card("商家卡片_文字下挂", [0, 1667, 1224, 386], 3),
        card("商家卡片_文字下挂", [0, 2071, 1224, 391], 4),
        card("商家卡片_文字下挂", [0, 2485, 1224, 215], 5, cropped=True),
    ],
    "merchant-text-hang/商家卡片-文下挂-搜索词为手机维修.elements.json": [
        card("商家卡片_文字下挂", [0, 843, 1224, 443], 1),
        card("商家卡片_文字下挂", [0, 1325, 1224, 442], 2),
        card("商家卡片_文字下挂", [0, 1807, 1224, 441], 3),
        card("商家卡片_文字下挂", [0, 2289, 1224, 382], 4),
    ],
    "merchant-text-hang/商家卡片-文下挂-搜索词为面部清洁.elements.json": [
        card("商家卡片_文字下挂", [0, 843, 1224, 394], 1),
        card("商家卡片_文字下挂", [0, 1254, 1224, 394], 2),
        card("商家卡片_文字下挂", [0, 1665, 1224, 394], 3),
        card("商家卡片_文字下挂", [0, 2076, 1224, 394], 4),
        card("商家卡片_文字下挂", [0, 2487, 1224, 213], 5, cropped=True),
    ],
    "merchant-text-hang/商家卡片-文下挂-搜索词为解压体验馆.elements.json": [
        card("商家卡片_文字下挂", [0, 554, 1224, 475], 1),
        card("商家卡片_文字下挂", [0, 1029, 1224, 475], 2),
        card("商家卡片_文字下挂", [0, 1504, 1224, 475], 3),
        card("商家卡片_文字下挂", [0, 1979, 1224, 475], 4),
        card("商家卡片_文字下挂", [0, 2454, 1224, 246], 5, cropped=True),
    ],
    "performance-movie-card/演出卡.elements.json": [
        card("演出电影卡片", [0, 414, 1224, 404], 1, variant="performance"),
        card("演出电影卡片", [0, 818, 1224, 414], 2, variant="performance"),
        card("演出电影卡片", [0, 1232, 1224, 472], 3, variant="performance"),
        card("演出电影卡片", [0, 1704, 1224, 411], 4, variant="performance"),
        card("演出电影卡片", [0, 2115, 1224, 404], 5, variant="performance"),
        card("演出电影卡片", [0, 2519, 1224, 181], 6, cropped=True, variant="performance"),
    ],
    "performance-movie-card/电影卡.elements.json": [
        card("演出电影卡片", [0, 1395, 1224, 230], 1, variant="cinema"),
        card("演出电影卡片", [0, 1655, 1224, 239], 2, variant="cinema"),
        card("演出电影卡片", [0, 1916, 1224, 247], 3, variant="cinema"),
        card("演出电影卡片", [0, 2177, 1224, 254], 4, variant="cinema"),
        card("演出电影卡片", [0, 2461, 1224, 239], 5, cropped=True, variant="cinema"),
    ],
    "primary-point-card/万达广场.elements.json": [
        card("商家卡片_图文下挂", [0, 1290, 1224, 685], 1),
        card("商家卡片_图文下挂", [0, 2015, 1224, 685], 2, cropped=True),
    ],
    "primary-point-card/迪士尼.elements.json": [
        card("商家卡片_文字下挂", [0, 1950, 1224, 371], 1),
        card("商家卡片_文字下挂", [0, 2346, 1224, 354], 2, cropped=True),
    ],
    "product-card/安睡裤.elements.json": [
        card("商品卡片", [0, 952, 1224, 477], 1),
        card("商品卡片", [0, 1454, 1224, 532], 2),
        card("商品卡片", [0, 2017, 1224, 530], 3),
        card("商品卡片", [0, 2547, 1224, 153], 4, cropped=True),
    ],
    "product-card/啤酒.elements.json": [
        card("商品卡片", [0, 1108, 1224, 478], 1),
        card("商品卡片", [0, 1675, 1224, 474], 2),
        card("商品卡片", [0, 2233, 1224, 467], 3, cropped=True),
    ],
    "product-card/布洛芬.elements.json": [
        hetero([0, 849, 1224, 348], 1, "大家还在搜"),
        card("商品卡片", [0, 1256, 1224, 502], 2),
        card("商品卡片", [0, 1758, 1224, 502], 3),
        card("商品卡片", [0, 2260, 1224, 440], 4, cropped=True),
    ],
    "product-card/榴莲.elements.json": [
        card("商品卡片", [0, 1077, 1224, 393], 1),
        card("商品卡片", [0, 1511, 1224, 518], 2),
        card("商品卡片", [0, 2068, 1224, 518], 3),
        card("商品卡片", [0, 2628, 1224, 72], 4, cropped=True),
    ],
    "product-card/生理盐水.elements.json": [
        card("商品卡片", [0, 554, 1224, 502], 1),
        card("商品卡片", [0, 1056, 1224, 502], 2),
        card("商品卡片", [0, 1558, 1224, 487], 3),
        card("商品卡片", [0, 2045, 1224, 517], 4),
        card("商品卡片", [0, 2562, 1224, 138], 5, cropped=True),
    ],
    "product-card/西瓜.elements.json": [
        card("商品卡片", [0, 1037, 1224, 538], 1),
        card("商品卡片", [0, 1600, 1224, 462], 2),
        card("商品卡片", [0, 2092, 1224, 544], 3),
        card("商品卡片", [0, 2636, 1224, 64], 4, cropped=True),
    ],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def project_path(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def find_component_annotation(screenshot: Path) -> Path:
    candidates = sorted(
        path for path in screenshot.parent.glob(f"{screenshot.stem}*.png")
        if path != screenshot and ("标注后" in path.name or "标记后" in path.name) and "元素" not in path.name
    )
    if not candidates:
        raise FileNotFoundError(f"component annotation not found for {screenshot}")
    return candidates[0]


def find_element_annotations(screenshot: Path) -> list[Path]:
    direct = sorted(path for path in screenshot.parent.glob(f"{screenshot.stem}*.png") if "元素" in path.name)
    sibling = screenshot.parent.parent / "element-level"
    related = sorted(path for path in sibling.glob("*.png") if screenshot.stem.split("-搜索词为")[-1].split("-")[0] in path.name) if sibling.is_dir() else []
    return sorted(set(direct + related))


def minimal_component(value: dict[str, Any]) -> dict[str, Any]:
    # Historical name retained for compatibility.  This must be lossless:
    # page-level elements and nested component payloads are golden data.
    result = deepcopy(value)
    result.setdefault("status", "confirmed")
    return result


def minimal_card(value: dict[str, Any]) -> dict[str, Any]:
    # Preserve regions/elements/items, evidence, confidence, and source fields.
    # Earlier code used a whitelist here and erased every nested element.
    result = deepcopy(value)
    original_type = result.get("cardType", "")
    if original_type:
        result["cardType"] = TYPE_ALIASES.get(original_type, original_type)
    if original_type == "演出卡":
        result.setdefault("variant", "performance")
    elif original_type == "电影影院卡":
        result.setdefault("variant", "cinema")
    # A reviewed visibleStatus supersedes stale legacy ``cropped`` flags.
    # Several old extractors marked the last fully visible card as cropped
    # merely because it was last in their truncated candidate list.
    cropped = result.get("visibleStatus") == "naturally_cropped" or (
        "visibleStatus" not in result and bool(result.get("cropped", False))
    )
    result["visibleStatus"] = "naturally_cropped" if cropped else result.get("visibleStatus", "complete")
    result.setdefault("status", "confirmed")
    return result


def strip_published_ocr_debug(value: Any) -> None:
    """Keep pixel provenance without duplicating OCR payload in goldens."""
    if isinstance(value, dict):
        value.pop("ocrConfidence", None)
        evidence = value.get("boundedEvidence")
        if isinstance(evidence, list):
            value["boundedEvidence"] = [
                {"coord": item["coord"]}
                for item in evidence
                if isinstance(item, dict) and isinstance(item.get("coord"), list)
            ]
        for child in value.values():
            strip_published_ocr_debug(child)
    elif isinstance(value, list):
        for child in value:
            strip_published_ocr_debug(child)


def curate(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    screenshot = Path(payload["screenshot"])
    annotation = find_component_annotation(screenshot)
    components: list[dict[str, Any]] = []
    for original in payload["pageStructure"]["components"]:
        component = minimal_component(original)
        if original.get("componentType") == "results_list":
            # OVERRIDES are page-level calibration facts.  They used to replace
            # the full cards here, which deleted regions/elements and also
            # manufactured boundary-only cards when counts differed.  Keep the
            # element-bearing cards intact; calibration is synced separately.
            component["components"] = [minimal_card(item) for item in original.get("components", [])]
        components.append(component)

    for order, component in enumerate(components, 1):
        component["order"] = order
        if component.get("componentType") == "results_list":
            for position, item in enumerate(component.get("components", []), 1):
                item["listPosition"] = position

    curated: dict[str, Any] = deepcopy(payload)
    previous_contract = payload.get("contractVersion")
    curated["contractVersion"] = "phase2.golden-structural-truth.v2"
    strip_published_ocr_debug(curated)
    curated["screenshot"] = str(screenshot)
    if previous_contract and previous_contract != curated["contractVersion"]:
        curated["legacyContractVersion"] = previous_contract
    existing_verification = deepcopy(payload.get("verification", {}))
    structural_claims = ["page_component_order", "result_card_count", "result_card_type", "result_card_boundary", "visible_crop_state"]
    existing_claims = existing_verification.get("claimScope", [])
    curated["verification"] = {
        **existing_verification,
        "status": "pixel_verified",
        "claimScope": sorted(set(structural_claims + existing_claims)),
        "excludedClaims": existing_verification.get("excludedClaims", ["runtime_ocr_text", "ocr_confidence"]),
        "reviewedAt": "2026-08-19",
        "rawScreenshot": project_path(screenshot),
        "rawSha256": sha256(screenshot),
        "componentAnnotation": project_path(annotation),
        "componentAnnotationSha256": sha256(annotation),
        "elementAnnotations": [
            {"path": project_path(item), "sha256": sha256(item), "status": "reference_only_not_transcribed"}
            for item in find_element_annotations(screenshot)
        ],
        "policy": "Nested elements are preserved. Their source/status fields determine whether they are human-annotated truth or runtime recognition evidence; provenance enrichment must never delete them.",
    }
    curated["pageStructure"] = {"components": components}
    strip_published_ocr_debug(curated)
    path.write_text(json.dumps(curated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sync_page_truth(paths: list[Path]) -> None:
    pages: dict[str, Any] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        result_cards: list[dict[str, Any]] = []
        calibration = OVERRIDES.get(str(path.relative_to(RESULTS)))
        if calibration is not None:
            # Boundary calibration is intentionally consumed only here.  It
            # must not replace the element-bearing cards in the golden JSON.
            card_items = calibration
        else:
            card_items = [
                item
                for component in payload["pageStructure"]["components"]
                if component.get("componentType") == "results_list"
                for item in component.get("components", [])
            ]
        for item in card_items:
            result_cards.append({
                "cardType": TYPE_ALIASES.get(item["cardType"], item["cardType"]),
                "coord": item["coord"],
                "visibleStatus": item.get(
                    "visibleStatus",
                    "naturally_cropped" if item.get("cropped") else "complete",
                ),
                **({"variant": item["variant"]} if item.get("variant") else {}),
            })
        screenshot = Path(payload["screenshot"])
        pages[project_path(screenshot)] = {
            "calibrationStatus": "component_annotation_pixel_verified",
            "sourceGolden": project_path(path),
            "rawSha256": payload["verification"]["rawSha256"],
            "componentAnnotationSha256": payload["verification"]["componentAnnotationSha256"],
            "resultCards": result_cards,
        }
    truth = {
        "contractVersion": "phase2.golden-page-truth.v2",
        "sourcePolicy": "34张离线组件标注图逐图校准；只用于推理后的卡数、卡型、边界与截断状态回归，禁止作为生产识别输入。哈希变化必须重新核验。",
        "pages": dict(sorted(pages.items())),
    }
    TRUTH.write_text(json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    paths = sorted(RESULTS.rglob("*.elements.json"))
    if len(paths) != 34:
        raise RuntimeError(f"expected 34 golden JSON files, found {len(paths)}")
    for path in paths:
        curate(path)
    sync_page_truth(paths)
    print(json.dumps({"curated": len(paths), "overrides": len(OVERRIDES)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
