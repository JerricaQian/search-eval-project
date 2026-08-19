#!/usr/bin/env python3
"""Apply the 2026-08-19 pixel-reviewed golden feedback repairs.

This is deliberately an offline golden-calibration utility.  It is never
imported by the production Phase2 runner and every value below was reviewed in
the corresponding bounded screenshot.  Keeping the fixes here makes the
feedback repeatable and prevents a future broad recalibration from restoring
the known OCR merges.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image

from enrich_golden_visual_facts import enrich_element


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "phase2-card-annotation" / "golden-sample-results"
TRUTH = ROOT / "phase2-card-annotation" / "references" / "golden_page_truth.v2.json"
SOURCE = "model_pixel_calibrated_feedback_2026_08_19"


def result_cards(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        card
        for component in payload["pageStructure"]["components"]
        if component.get("componentType") == "results_list"
        for card in component.get("components", [])
        if card.get("componentType") == "result_card"
    ]


def card(payload: dict[str, Any], position: int) -> dict[str, Any]:
    matches = [item for item in result_cards(payload) if item.get("listPosition") == position]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one result card at C{position}, got {len(matches)}")
    return matches[0]


def element(rgb: np.ndarray, kind: str, region: str, coord: list[int], text: str) -> dict[str, Any]:
    value = {
        "elementType": kind,
        "sourceRegion": region,
        "coord": coord,
        "visibleText": text,
        "status": "confirmed",
        "source": SOURCE,
        "boundedEvidence": [{"coord": coord}],
    }
    enrich_element(value, rgb)
    return value


def region_elements(card_value: dict[str, Any], region: str) -> list[dict[str, Any]]:
    return card_value.setdefault("regions", {}).setdefault(region, {"elements": []}).setdefault("elements", [])


def insert_info(rgb: np.ndarray, card_value: dict[str, Any], values: Iterable[tuple[str, list[int], str]]) -> None:
    entries = region_elements(card_value, "商家信息区")
    for kind, coord, text in values:
        if any(value.get("elementType") == kind and value.get("coord") == coord and value.get("visibleText") == text for value in entries):
            continue
        entries.append(element(rgb, kind, "商家信息区", coord, text))
    entries.sort(key=lambda item: (item["coord"][1], item["coord"][0]))


def replace_text(rgb: np.ndarray, card_value: dict[str, Any], region: str, old: str, values: Iterable[tuple[str, list[int], str]]) -> None:
    entries = region_elements(card_value, region)
    indexes = [index for index, item in enumerate(entries) if item.get("visibleText") == old]
    values = list(values)
    if not indexes and all(any(item.get("elementType") == kind and item.get("coord") == coord and item.get("visibleText") == text for item in entries) for kind, coord, text in values):
        return
    if len(indexes) != 1:
        raise ValueError(f"{card_value.get('listPosition')}: expected one {old!r} in {region}, got {len(indexes)}")
    index = indexes[0]
    entries[index:index + 1] = [element(rgb, kind, region, coord, text) for kind, coord, text in values]
    entries.sort(key=lambda item: (item["coord"][1], item["coord"][0]))


def remove_text(card_value: dict[str, Any], region: str, text: str) -> None:
    entries = region_elements(card_value, region)
    before = len(entries)
    entries[:] = [item for item in entries if item.get("visibleText") != text]
    if len(entries) not in {before, before - 1}:
        raise ValueError(f"{card_value.get('listPosition')}: expected one removable {text!r} in {region}")


def append_element(rgb: np.ndarray, card_value: dict[str, Any], region: str, kind: str, coord: list[int], text: str) -> None:
    entries = region_elements(card_value, region)
    existing = next((value for value in entries if value.get("elementType") == kind and value.get("visibleText") == text), None)
    if existing is None:
        entries.append(element(rgb, kind, region, coord, text))
    elif existing.get("coord") != coord:
        existing.update(element(rgb, kind, region, coord, text))


def union(coords: list[list[int]]) -> list[int]:
    x0, y0 = min(value[0] for value in coords), min(value[1] for value in coords)
    x1 = max(value[0] + value[2] for value in coords)
    y1 = max(value[1] + value[3] for value in coords)
    return [x0, y0, x1 - x0, y1 - y0]


def item(card_value: dict[str, Any], index: int) -> dict[str, Any]:
    values = card_value["regions"]["下挂商品区"]["items"]
    matches = [value for value in values if value.get("itemIndex") == index]
    if len(matches) != 1:
        raise ValueError(f"C{card_value.get('listPosition')}: missing item {index}")
    return matches[0]


def set_item_prices(rgb: np.ndarray, card_value: dict[str, Any], index: int, prices: list[tuple[str, list[int], str]]) -> None:
    target = item(card_value, index)
    target["priceElements"] = [element(rgb, kind, "下挂商品区", coord, text) for kind, coord, text in prices]
    owned = target.get("imageElements", []) + target.get("textElements", []) + target["priceElements"] + target.get("auxiliaryElements", [])
    target["coord"] = union([value["coord"] for value in owned])


def load(path: Path) -> tuple[dict[str, Any], np.ndarray]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    image_path = Path(payload["screenshot"])
    return payload, np.asarray(Image.open(image_path).convert("RGB"))


def write(path: Path, payload: dict[str, Any], repairs: list[str]) -> None:
    verification = payload.setdefault("verification", {})
    verification["feedbackRepairs"] = {
        "reviewDate": "2026-08-19",
        "source": "user_report_plus_bounded_pixel_review",
        "repairs": repairs,
        "policy": "Offline golden calibration only; values must not be injected into Phase2 production recognition.",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def repair_graphic_ratings() -> list[Path]:
    rating_values = {
        "烧烤": ["4.5分", "4.6分", "4.6分", "4.8分"],
        "生日蛋糕": ["4.6分", "4.4分"],
        "盒马": ["4.6分", "4.2分", "4.8分"],
        "药店": ["4.9分", "5.0分", "4.5分"],
        "隆江猪脚饭": ["4.4分", "4.7分", "4.8分", "4.6分"],
    }
    changed: list[Path] = []
    for name, ratings in rating_values.items():
        path = RESULTS / "merchant-graphic-hang" / f"{name}.elements.json"
        payload, rgb = load(path)
        for position, rating in enumerate(ratings, 1):
            current = card(payload, position)
            info = region_elements(current, "商家信息区")
            if any(value.get("elementType") == "评分" for value in info):
                continue
            first = min(info, key=lambda value: (value["coord"][1], value["coord"][0]))
            x = 227
            y, h = first["coord"][1], first["coord"][3]
            insert_info(rgb, current, [("评分", [x, y, 102, h], rating)])
        write(path, payload, ["merchant_graphic_rating_backfill"])
        changed.append(path)

    path = RESULTS / "merchant-graphic-hang" / "蜜雪冰城.elements.json"
    payload, rgb = load(path)
    first = card(payload, 1)
    insert_info(rgb, first, [("评分", [227, 1398, 102, 41], "4.9分")])
    second = card(payload, 2)
    remove_text(second, "商家信息区", "茶山季(合生汇店）")
    for duplicated_tag in ("茶饮果汁", "九龙山", "12.8km"):
        remove_text(second, "标签区", duplicated_tag)
    insert_info(rgb, second, [
        ("评分", [227, 2136, 102, 42], "4.5分"),
        ("评价条数", [341, 2136, 108, 42], "2629条"),
        ("人均消费", [470, 2136, 133, 42], "人均¥19"),
        ("商家品类", [626, 2136, 160, 42], "茶饮果汁"),
        ("商家基础信息", [807, 2136, 118, 42], "九龙山"),
        ("距离", [1080, 2136, 114, 42], "12.8km"),
    ])
    second["visibleStatus"] = "complete"
    write(path, payload, ["merchant_graphic_rating_backfill", "tea_shan_ji_complete_card_and_info_backfill"])
    changed.append(path)
    return changed


def repair_text_merges() -> list[Path]:
    changed: list[Path] = []
    path = RESULTS / "merchant-text-hang" / "商家卡片-文下挂-搜索词为体检.elements.json"
    payload, rgb = load(path)
    replace_text(rgb, card(payload, 4), "商家信息区", "3.9分1", [("评分", [308, 2179, 102, 44], "3.9分")])
    write(path, payload, ["rating_suffix_glue_removed"])
    changed.append(path)

    path = RESULTS / "merchant-text-hang" / "商家卡片-文下挂-搜索词为剧本杀.elements.json"
    payload, rgb = load(path)
    replace_text(rgb, card(payload, 4), "商家信息区", "图6.0km", [("距离", [1050, 2507, 140, 37], "6.0km")])
    write(path, payload, ["distance_prefix_glue_removed"])
    changed.append(path)

    path = RESULTS / "merchant-text-hang" / "商家卡片-文下挂-搜索词为手机维修.elements.json"
    payload, rgb = load(path)
    replace_text(rgb, card(payload, 3), "商家信息区", "4.5分4.8万条家电维修", [
        ("评分", [307, 1897, 102, 46], "4.5分"),
        ("评价条数", [426, 1897, 144, 46], "4.8万条"),
        ("商家品类", [587, 1897, 146, 46], "家电维修"),
    ])
    write(path, payload, ["rating_comment_category_split"])
    changed.append(path)

    path = RESULTS / "merchant-text-hang" / "商家卡片-文下挂-搜索词为理发.elements.json"
    payload, rgb = load(path)
    replace_text(rgb, card(payload, 4), "商家信息区", "4.7分2", [("评分", [310, 2376, 102, 41], "4.7分")])
    write(path, payload, ["rating_suffix_glue_removed"])
    changed.append(path)

    path = RESULTS / "merchant-text-hang" / "商家卡片-文下挂-搜索词为空调清洗.elements.json"
    payload, rgb = load(path)
    insert_info(rgb, card(payload, 3), [("评分", [227, 1899, 102, 44], "3.9分")])
    insert_info(rgb, card(payload, 4), [("评分", [227, 2375, 102, 39], "4.4分")])
    write(path, payload, ["air_conditioner_service_rating_backfill"])
    changed.append(path)

    path = RESULTS / "merchant-text-hang" / "商家卡片-文下挂-搜索词为露营.elements.json"
    payload, rgb = load(path)
    first = card(payload, 1)
    insert_info(rgb, first, [
        ("评分", [308, 954, 102, 44], "4.2分"),
        ("评价条数", [429, 954, 120, 44], "5176条"),
        ("人均消费", [570, 954, 146, 44], "¥137/人"),
        ("商家品类", [737, 954, 200, 44], "休闲园区"),
        ("距离", [1080, 954, 114, 44], "4.3km"),
    ])
    write(path, payload, ["camping_primary_merchant_core_info_backfill"])
    changed.append(path)
    return changed


def repair_performance() -> list[Path]:
    path = RESULTS / "performance-movie-card" / "演出卡.elements.json"
    payload, rgb = load(path)
    venues = {
        1: ([312, 618, 312, 43], "听云轩望京麒麟社"),
        2: ([310, 1031, 331, 42], "德云社-广德楼戏园"),
        3: ([312, 1504, 489, 42], "咂摸剧场（南锣鼓巷观乐茶馆）"),
        4: ([312, 1920, 307, 36], "德云社学院路剧场"),
        5: ([313, 2312, 424, 42], "北京前门盛世园相声茶馆"),
    }
    for position, (coord, venue) in venues.items():
        current = card(payload, position)
        entries = region_elements(current, "演出信息区")
        entries[:] = [value for value in entries if value.get("elementType") != "演出场馆"]
        append_element(rgb, current, "演出信息区", "演出场馆", coord, venue)
        entries.sort(key=lambda value: (value["coord"][1], value["coord"][0]))
    write(path, payload, ["performance_venue_price_field_separation"])

    movie_path = RESULTS / "performance-movie-card" / "电影卡.elements.json"
    movie, movie_rgb = load(movie_path)
    replace_text(movie_rgb, card(movie, 3), "商家信息区", "17:555", [("近期场次", [276, 2110, 134, 42], "17:55")])
    write(movie_path, movie, ["movie_session_trailing_digit_removed"])
    return [path, movie_path]


def repair_wanda_prices() -> list[Path]:
    path = RESULTS / "primary-point-card" / "万达广场.elements.json"
    payload, rgb = load(path)
    first = card(payload, 1)
    first_prices = {
        1: [("下挂商品价格", [310, 1923, 102, 46], "¥30.6"), ("下挂商品原价", [423, 1923, 67, 46], "¥42")],
        2: [("下挂商品价格", [586, 1922, 96, 47], "¥10.9"), ("下挂商品原价", [691, 1922, 55, 47], "¥17")],
        3: [("下挂商品价格", [862, 1922, 111, 47], "¥18.04"), ("下挂商品原价", [980, 1922, 64, 47], "¥22")],
        4: [("下挂商品价格", [1156, 1924, 67, 44], "¥15.6")],
    }
    for index, values in first_prices.items():
        set_item_prices(rgb, first, index, values)
    second = card(payload, 2)
    second_prices = {
        1: [("下挂商品价格", [309, 2637, 92, 46], "¥113"), ("下挂商品原价", [408, 2637, 74, 46], "¥254")],
        2: [("下挂商品价格", [604, 2639, 92, 44], "¥118"), ("下挂商品原价", [704, 2639, 75, 44], "¥168")],
        3: [("下挂商品价格", [863, 2639, 92, 44], "¥158"), ("下挂商品原价", [963, 2639, 75, 44], "¥254")],
        4: [("下挂商品价格", [1141, 2637, 83, 45], "¥188")],
    }
    for index, values in second_prices.items():
        set_item_prices(rgb, second, index, values)
    write(path, payload, ["primary_point_downhang_price_cross_talk_split"])
    return [path]


def repair_products() -> list[Path]:
    changed: list[Path] = []
    path = RESULTS / "product-card" / "布洛芬.elements.json"
    payload, rgb = load(path)
    for position, coord, value in ((2, [395, 1466, 150, 62], "¥22.4"), (4, [394, 2470, 130, 62], "¥21.7")):
        append_element(rgb, card(payload, position), "价格区", "商品价格", coord, value)
    write(path, payload, ["ibuprofen_missing_product_prices_backfill"])
    changed.append(path)

    path = RESULTS / "product-card" / "喜力啤酒整箱.elements.json"
    payload, rgb = load(path)
    second = card(payload, 2)
    for old in ("82/", "前2件￥", "/件"):
        remove_text(second, "基础信息区", old)
    append_element(rgb, second, "价格区", "商品价格", [394, 1504, 273, 62], "前2件¥82/件")
    fourth = card(payload, 4)
    append_element(rgb, fourth, "副标题区", "商品属性", [396, 2395, 352, 42], "麦香浓郁｜口感均衡")
    write(path, payload, ["heineken_price_fragments_rejoined", "heineken_missing_subtitle_backfill"])
    changed.append(path)

    for name, values in {
        "榴莲": {
            2: ("神券52减18", [("神券", [395, 1643, 75, 43], "神券"), ("满减券", [478, 1643, 136, 43], "52减18"), ("满减券", [630, 1643, 136, 43], "62减20")]),
            3: ("神券立减5坏必赔", [("神券", [395, 2250, 75, 43], "神券"), ("立减券", [478, 2250, 110, 43], "立减5"), ("保障标签", [606, 2250, 130, 43], "坏必赔")]),
        },
        "西瓜": {
            1: ("神券立减5坏必赔", [("神券", [395, 1194, 75, 43], "神券"), ("立减券", [478, 1194, 110, 43], "立减5"), ("保障标签", [606, 1194, 130, 43], "坏必赔")]),
            2: ("神券52减1862减20坏必赔", [("神券", [395, 1757, 75, 43], "神券"), ("满减券", [478, 1757, 136, 43], "52减18"), ("满减券", [630, 1757, 136, 43], "62减20"), ("保障标签", [784, 1757, 130, 43], "坏必赔")]),
            3: ("神券52减1862减20坏必赔", [("神券", [395, 2320, 75, 43], "神券"), ("满减券", [478, 2320, 136, 43], "52减18"), ("满减券", [630, 2320, 136, 43], "62减20"), ("保障标签", [784, 2320, 130, 43], "坏必赔")]),
        },
    }.items():
        path = RESULTS / "product-card" / f"{name}.elements.json"
        payload, rgb = load(path)
        for position, (old, replacements) in values.items():
            replace_text(rgb, card(payload, position), "基础信息区", old, replacements)
        write(path, payload, ["promotion_tokens_split_by_visual_chip"])
        changed.append(path)

    path = RESULTS / "product-card" / "生理盐水.elements.json"
    payload, rgb = load(path)
    replace_text(rgb, card(payload, 1), "基础信息区", "5已优惠￥1已售700+", [
        ("优惠信息", [514, 800, 154, 43], "已优惠¥1"),
        ("商品销量", [688, 800, 162, 43], "已售700+"),
    ])
    replace_text(rgb, card(payload, 3), "基础信息区", "115分钟", [("配送时长", [1034, 1806, 159, 42], "15分钟")])
    write(path, payload, ["saline_price_discount_and_delivery_time_glue_removed"])
    changed.append(path)

    path = RESULTS / "product-card" / "安睡裤.elements.json"
    payload, rgb = load(path)
    replace_text(rgb, card(payload, 3), "基础信息区", "1约15分钟", [("配送时长", [996, 2264, 196, 41], "约15分钟")])
    write(path, payload, ["sleep_pants_delivery_time_prefix_removed"])
    changed.append(path)
    return changed


def repair_page_truth() -> list[Path]:
    """Keep the independent card-boundary truth aligned with a reviewed status."""
    payload = json.loads(TRUTH.read_text(encoding="utf-8"))
    key = "phase2-card-annotation/golden-samples/merchant-graphic-hang/component-level/商家卡片-图文下挂-搜索词为蜜雪冰城.png"
    card_truth = payload["pages"][key]["resultCards"][1]
    if card_truth["visibleStatus"] != "complete":
        card_truth["visibleStatus"] = "complete"
        TRUTH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return [TRUTH]


def main() -> int:
    changed = repair_graphic_ratings() + repair_text_merges() + repair_performance() + repair_wanda_prices() + repair_products() + repair_page_truth()
    print(json.dumps({"changed": [str(path.relative_to(ROOT)) for path in changed], "count": len(changed)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
