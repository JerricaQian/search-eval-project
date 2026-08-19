#!/usr/bin/env python3
"""Add pixel-reviewed coordinates to legacy non-result-card components.

The four legacy pages below predate the element contract and stored semantic
names without geometry.  Coordinates are transcribed from their committed
element-annotation images and checked against local OCR where text exists.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "phase2-card-annotation" / "golden-sample-results"


COORDS: dict[str, dict[str, list[list[int]]]] = {
    "演出卡.elements.json": {
        "搜索关键词": [[158, 168, 90, 42]],
    },
    "电影卡.elements.json": {
        "搜索关键词": [[157, 158, 280, 64]],
        "电影海报": [[64, 410, 269, 359]],
        "电影横幅/轮播": [[345, 410, 810, 359]],
        "电影名": [[65, 805, 340, 55]],
        "上映信息": [[65, 878, 730, 48]],
        "演员": [[65, 940, 370, 42]],
        "好评率": [[65, 1001, 270, 48]],
        "评分": [[955, 887, 145, 65]],
        "评论数": [[920, 966, 215, 38]],
        "热映计数": [[195, 1135, 295, 55]],
        "待映计数": [[730, 1134, 315, 55]],
        "日期": [[27, 1276, 285, 84], [326, 1276, 285, 84], [624, 1276, 285, 84]],
    },
    "万达广场.elements.json": {
        "搜索关键词": [[158, 168, 178, 42]],
        "主点候选": [[53, 390, 543, 84], [610, 390, 560, 84]],
        "商场头图": [[64, 531, 247, 247]],
        "主点标题": [[346, 526, 540, 63]],
        "导航icon": [[1042, 514, 129, 75]],
        "评分": [[344, 595, 88, 66]],
        "评价条数": [[444, 595, 132, 66]],
        "距离": [[1056, 607, 101, 30]],
        "品类": [[344, 663, 86, 54]],
        "地址": [[464, 652, 330, 68]],
        "下挂标签": [[344, 757, 82, 45], [344, 823, 82, 45]],
        "下挂文本": [[443, 759, 695, 40], [443, 823, 695, 45]],
    },
    "迪士尼.elements.json": {
        "搜索关键词": [[158, 168, 133, 42]],
        "直播视频": [[0, 376, 1224, 775]],
        "直播状态": [[46, 390, 360, 108]],
        "观看人数": [[175, 447, 200, 50]],
        "直播商品横滑项": [[33, 938, 1170, 210]],
        "景点头图": [[64, 1192, 247, 247]],
        "主点标题": [[346, 1188, 378, 45]],
        "评分": [[344, 1263, 88, 45]],
        "评价条数": [[454, 1264, 180, 38]],
        "AOI": [[1084, 1248, 78, 69]],
        "榜单标签": [[344, 1325, 110, 48]],
        "属性标签": [[475, 1325, 240, 48], [740, 1325, 120, 48], [875, 1325, 150, 48]],
        "下挂商品价格": [[344, 1485, 105, 48]],
        "下挂商品名": [[470, 1484, 500, 48]],
        "下挂商品销量": [[1020, 1487, 175, 42]],
    },
}


COMPONENT_COORDS = {
    "演出卡.elements.json": {"search_bar": [0, 122, 1224, 128]},
    "电影卡.elements.json": {
        "search_bar": [0, 122, 1224, 128], "movie_primary_info": [0, 398, 1224, 832], "date_filter": [0, 1253, 1224, 126],
    },
    "万达广场.elements.json": {
        "search_bar": [0, 122, 1224, 128], "primary_point_disambiguation": [0, 382, 1224, 100], "primary_point_card": [0, 497, 1224, 406],
    },
    "迪士尼.elements.json": {
        "search_bar": [0, 122, 1224, 128], "heterogeneous_live_card": [0, 376, 1224, 775], "primary_point_card": [0, 1170, 1224, 407],
    },
}


COMPONENT_REGIONS = {
    "search_bar": "搜索框", "movie_primary_info": "电影主信息区", "date_filter": "日期筛选区",
    "primary_point_disambiguation": "主点消歧区", "heterogeneous_live_card": "直播区",
}


def element(kind: str, region: str, coord: list[int], text: str) -> dict[str, Any]:
    return {"elementType": kind, "sourceRegion": region, "coord": coord, "visibleText": text, "status": "confirmed", "source": "committed_element_annotation_model_calibrated"}


def normalize_primary_downhang(path: Path, component: dict[str, Any]) -> None:
    region = component.get("regions", {}).get("文字下挂区")
    if not isinstance(region, dict) or not isinstance(region.get("items"), list):
        return
    if region["items"] and "imageElements" in region["items"][0]:
        return
    if path.name == "万达广场.elements.json":
        tag_coords = COORDS[path.name]["下挂标签"]
        text_coords = COORDS[path.name]["下挂文本"]
        output = []
        for index, raw in enumerate(region["items"], 1):
            tag = element("下挂标签", "文字下挂区", tag_coords[index - 1], raw["tag"]["visibleText"])
            text_value = element("下挂文本", "文字下挂区", text_coords[index - 1], raw["text"]["visibleText"])
            output.append({"itemIndex": index, "coord": [344, tag_coords[index - 1][1], 794, max(tag_coords[index - 1][3], text_coords[index - 1][3])], "imageElements": [], "textElements": [tag, text_value], "priceElements": [], "auxiliaryElements": [], "visibleStatus": "confirmed"})
        region.clear(); region["items"] = output
    elif path.name == "迪士尼.elements.json":
        raw = region["items"][0]
        price = element("下挂商品价格", "文字下挂区", COORDS[path.name]["下挂商品价格"][0], raw["price"]["visibleText"])
        name = element("下挂商品名", "文字下挂区", COORDS[path.name]["下挂商品名"][0], raw["name"]["visibleText"].replace("｜", "|"))
        sales = element("下挂商品销量", "文字下挂区", COORDS[path.name]["下挂商品销量"][0], raw["sales"]["visibleText"])
        region.clear(); region["items"] = [{"itemIndex": 1, "coord": [344, 1484, 851, 51], "imageElements": [], "textElements": [name], "priceElements": [price], "auxiliaryElements": [sales], "visibleStatus": "confirmed"}]


def enrich(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    coords = COORDS.get(path.name, {})
    seen: dict[str, int] = defaultdict(int)
    changed = 0
    for component in payload["pageStructure"]["components"]:
        component_type = component.get("componentType", "")
        if component_type in COMPONENT_COORDS.get(path.name, {}):
            component["coord"] = COMPONENT_COORDS[path.name][component_type]
        if component_type == "primary_point_card":
            component["visibleStatus"] = "complete"
            normalize_primary_downhang(path, component)

        def visit(value: Any, region: str) -> None:
            nonlocal changed
            if isinstance(value, dict):
                if "elementType" in value:
                    kind = str(value["elementType"])
                    index = seen[kind]; seen[kind] += 1
                    options = coords.get(kind, [])
                    if "coord" not in value and index < len(options):
                        value["coord"] = options[index]; changed += 1
                    value.setdefault("sourceRegion", region)
                    value.setdefault("visibleText", "")
                    value.setdefault("status", "confirmed")
                    value.setdefault("source", "committed_element_annotation_model_calibrated")
                if isinstance(value.get("regions"), dict):
                    for region_name, child in value["regions"].items():
                        visit(child, region_name)
                    for key, child in value.items():
                        if key != "regions":
                            visit(child, region)
                    return
                for child in value.values():
                    visit(child, region)
            elif isinstance(value, list):
                for child in value:
                    visit(child, region)

        visit(component, COMPONENT_REGIONS.get(component_type, component_type or "页面组件"))
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    summary = {}
    for name in COORDS:
        path = next(RESULTS.rglob(name))
        summary[str(path.relative_to(ROOT))] = enrich(path)
    # Image/icon elements in other files legitimately have no text; make the
    # empty visual value explicit so every element shares one schema.
    for path in RESULTS.rglob("*.elements.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        dirty = False
        stack = [payload]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                if "elementType" in value and "visibleText" not in value:
                    value["visibleText"] = ""; dirty = True
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
        if dirty:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
