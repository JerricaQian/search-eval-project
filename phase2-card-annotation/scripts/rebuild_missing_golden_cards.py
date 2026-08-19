#!/usr/bin/env python3
"""Rebuild missing legacy golden cards from bounded, reviewed OCR evidence."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


# User/model pixel-reviewed visible truth for ambiguous clipped glyphs and
# spacing that OCR line boxes alone cannot recover.  This is golden-only and
# always retains the bounded observations as provenance.
REVIEWED_GRAPHIC_ITEMS: dict[tuple[str, int, int], tuple[str, str]] = {
    ("盒马.elements.json", 1, 1): ("盒马 左旋肉碱水 960ml", "¥10 限1件"),
    ("盒马.elements.json", 1, 2): ("黄瓜 约600g", "¥3.23 限1件"),
    ("盒马.elements.json", 1, 3): ("盒马 红豆薏米水 900ml", "¥8.51 限1件"),
    ("盒马.elements.json", 1, 4): ("国产富士...粒装 约6...", "¥13.44 限..."),
    ("蜜雪冰城.elements.json", 1, 1): ("冰鲜柠檬水", "¥11"),
    ("蜜雪冰城.elements.json", 1, 2): ("满杯百香果", "¥13.46 30天低价"),
    ("蜜雪冰城.elements.json", 1, 3): ("冰鲜柠檬水", "¥0.8 神券价"),
    ("蜜雪冰城.elements.json", 1, 4): ("心想事“橙...", "¥25..."),
}


def union(coords: list[list[int]]) -> list[int]:
    x0, y0 = min(item[0] for item in coords), min(item[1] for item in coords)
    x1 = max(item[0] + item[2] for item in coords)
    y1 = max(item[1] + item[3] for item in coords)
    return [x0, y0, x1 - x0, y1 - y0]


def usable(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item for item in observations
        if float(item.get("ocrConfidence", 0)) >= 0.80
        and len(re.sub(r"\s+", "", str(item.get("text", "")))) > 1
        and not re.fullmatch(r"[^0-9A-Za-z\u4e00-\u9fff¥￥]+", str(item.get("text", "")))
    ]


def element(kind: str, region: str, observations: list[dict[str, Any]], text: str | None = None) -> dict[str, Any]:
    return {
        "elementType": kind,
        "sourceRegion": region,
        "coord": union([item["coord"] for item in observations]),
        "visibleText": text if text is not None else "".join(str(item["text"]) for item in observations),
        "status": "confirmed",
        "source": "bounded_paddleocr_model_calibrated",
        "boundedEvidence": [
            {"text": str(item.get("text", "")), "coord": item["coord"], "ocrConfidence": item.get("ocrConfidence")}
            for item in observations
        ],
    }


def text_units(value: str) -> float:
    return sum(1.0 if "\u2e80" <= char <= "\uffff" else 0.56 for char in value) or 1.0


def observation_slice(item: dict[str, Any], start: int, end: int, text: str) -> dict[str, Any]:
    """Approximate a semantic sub-box only after OCR saw the complete row.

    This is intentionally different from the removed fixed-slot crop: the
    source observation covers the complete visible line first, then the box is
    divided using the recognised glyph sequence.  No clipped substring is sent
    back through OCR.
    """
    raw = str(item["text"])
    x, y, width, height = item["coord"]
    total = text_units(raw)
    left = round(width * text_units(raw[:start]) / total) if start else 0
    right = round(width * text_units(raw[:end]) / total)
    return {**item, "text": text, "coord": [x + left, y, max(1, right - left), height]}


def image(kind: str, region: str, coord: list[int]) -> dict[str, Any]:
    return {"elementType": kind, "sourceRegion": region, "coord": coord, "visibleText": "", "status": "confirmed", "source": "model_reviewed_card_geometry"}


def blank_card(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "componentType": "result_card",
        "listPosition": source["listPosition"],
        "cardType": source["cardType"],
        "coord": source["coord"],
        "visibleStatus": source["visibleStatus"],
        "status": "confirmed",
        **({"variant": source["variant"]} if source.get("variant") else {}),
        "regions": {},
        "elementContract": {
            "version": "golden.element-level.v3",
            "titleRequiredForCompleteKnownCard": True,
            "downhangGrouping": "one item owns imageElements/textElements/priceElements/auxiliaryElements",
            "semanticAtomicity": "basic-info and tags split by semantic field; one-character elements forbidden",
        },
    }


def has_elements(value: Any) -> bool:
    if isinstance(value, dict):
        return "elementType" in value or any(has_elements(child) for child in value.values())
    if isinstance(value, list):
        return any(has_elements(child) for child in value)
    return False


def add(regions: dict[str, Any], region: str, value: dict[str, Any]) -> None:
    regions.setdefault(region, {"elements": []})["elements"].append(value)


def build_performance(source: dict[str, Any]) -> dict[str, Any]:
    card = blank_card(source)
    obs = usable(source["observations"])
    x, y, width, height = source["coord"]
    add(card["regions"], "头图区", image("演出海报", "头图区", [28, y + 16, 254, max(1, min(height - 32, 330))]))
    for token, kind in (("演出", "履约标签"), ("北京", "城市")):
        value = next((item for item in obs if item["text"] == token and item["coord"][0] >= 300), None)
        if value:
            add(card["regions"], "标题区", element(kind, "标题区", [value]))
    structured = re.compile(r"\d(?:\.\d)?分|20\d{2}-|^[¥￥]?\d{2,4}-\d{2,4}")
    title_parts = [item for item in obs if item["coord"][0] >= 300 and item["coord"][1] < y + 145 and item["text"] not in {"演出", "北京"} and not structured.search(item["text"])]
    if title_parts:
        title_parts = [item for group in row_groups(title_parts) for item in sorted(group, key=lambda value: value["coord"][0])]
        add(card["regions"], "标题区", element("演出标题", "标题区", title_parts))
    for item in obs:
        text = str(item["text"])
        if re.fullmatch(r"\d(?:\.\d)?分", text):
            add(card["regions"], "演出信息区", element("评分", "演出信息区", [item]))
        elif re.search(r"20\d{2}-\d{2}-\d{2}至20\d{2}-\d{2}-\d{2}", text):
            add(card["regions"], "演出信息区", element("演出日期", "演出信息区", [item]))
        elif (text.startswith("¥") or text.startswith("￥") or re.fullmatch(r"\d{2,4}-\d{2,4}", text)) and item["coord"][1] >= y + height * .65:
            add(card["regions"], "价格区", element("价格区间", "价格区", [item], text.replace("￥", "¥") if text[0] in "￥¥" else "¥" + text))
    candidates = [item for item in obs if item["coord"][0] >= 300 and item["coord"][1] >= y + 150 and item["coord"][1] < y + height * .78 and not re.search(r"20\d{2}-|\d(?:\.\d)?分", item["text"])]
    if candidates:
        venue = max(candidates, key=lambda item: (item["coord"][1], len(item["text"])))
        add(card["regions"], "演出信息区", element("演出场馆", "演出信息区", [venue]))
    return card


def build_movie(source: dict[str, Any]) -> dict[str, Any]:
    card = blank_card(source)
    obs = usable(source["observations"])
    x, y, width, height = source["coord"]
    title = next((item for item in obs if item["coord"][0] < 950 and item["coord"][1] < y + 85 and not re.search(r"近期场次|km|^[¥￥]", item["text"])), None)
    if title:
        add(card["regions"], "标题区", element("电影标题", "标题区", [title], str(title["text"]).replace("(", "（").replace(")", "）")))
    sessions = [item for item in obs if "近期场次" in item["text"] or (item["coord"][1] >= y + height * .70 and re.search(r"\d{1,2}:\d{2}", item["text"]))]
    if sessions:
        sessions.sort(key=lambda item: item["coord"][0])
        add(card["regions"], "商家信息区", element("近期场次", "商家信息区", sessions))
    for item in obs:
        text = str(item["text"])
        if re.match(r"^[¥￥]\d", text):
            add(card["regions"], "价格区", element("起价", "价格区", [item], text.replace("￥", "¥")))
        elif re.fullmatch(r"\d+(?:\.\d+)?km", text):
            add(card["regions"], "商家信息区", element("距离", "商家信息区", [item]))
        elif item is not title and item not in sessions and item["coord"][0] < 950 and y + 65 <= item["coord"][1] < y + height * .70:
            add(card["regions"], "商家信息区", element("地址", "商家信息区", [item]))
    return card


def merchant_header(card: dict[str, Any], source: dict[str, Any], obs: list[dict[str, Any]]) -> None:
    x, y, width, height = source["coord"]
    card_type = source["cardType"]
    add(card["regions"], "头图区", image("商家头图", "头图区", [32, y, 247, max(1, min(247, height))]))
    badges = {"到店", "外卖", "上门", "景点"}
    downhang_top = min(
        (value["imageCoord"][1] for value in source.get("itemObservations", []) if value.get("imageCoord")),
        default=y + height,
    )
    for item in obs:
        if item["text"] in badges and item["coord"][1] < y + 80:
            add(card["regions"], "标题区", element("履约标签", "标题区", [item]))
    title_candidates = [item for item in obs if item["coord"][0] >= 295 and item["text"] not in badges and len(item["text"]) >= 4 and not re.search(r"\d(?:\.\d)?分|月售|人均|km|分钟|起送|配送|^[¥￥]", item["text"])]
    top_candidates = [item for item in title_candidates if item["coord"][1] < y + 90]
    # The title is the first visible text row beside the merchant image.
    # Never prefer a later row merely because it contains “店”: strings such
    # as “新店入驻147条” are merchant metadata, not titles.
    first_row = []
    if top_candidates:
        first_y = min(item["coord"][1] for item in top_candidates)
        first_row = [item for item in top_candidates if item["coord"][1] <= first_y + 15]
    anchor = max(first_row, key=lambda item: (item["coord"][3], item["coord"][2]), default=None)
    title_parts = [] if anchor is None else [
        item for item in top_candidates
        if abs((item["coord"][1] + item["coord"][3] / 2) - (anchor["coord"][1] + anchor["coord"][3] / 2)) <= max(12, anchor["coord"][3] * .45)
    ]
    title_parts.sort(key=lambda item: item["coord"][0])
    if title_parts:
        title_text = "".join(str(item["text"]) for item in title_parts).replace("(", "（").replace(")", "）")
        add(card["regions"], "标题区", element("商家标题", "标题区", title_parts, title_text))
    title_y = anchor["coord"][1] if anchor else y
    for item in obs:
        text = str(item["text"])
        ry = item["coord"][1] - title_y
        if item in title_parts or text in badges or item["coord"][0] < 295:
            continue
        if 55 <= ry < 120:
            kind = "评分" if re.fullmatch(r"\d(?:\.\d)?分|暂无评分", text) else "商家基础信息"
            add(card["regions"], "商家信息区", element(kind, "商家信息区", [item]))
        elif 120 <= ry < 220 and item["coord"][1] < downhang_top:
            add(card["regions"], "标签区", element("商家标签", "标签区", [item]))


def row_groups(observations: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for item in sorted(observations, key=lambda value: (value["coord"][1], value["coord"][0])):
        center = item["coord"][1] + item["coord"][3] / 2
        target = next((group for group in groups if abs(center - sum(value["coord"][1] + value["coord"][3] / 2 for value in group) / len(group)) <= 24), None)
        if target is None:
            groups.append([item])
        else:
            target.append(item)
    return groups


def build_merchant_text(source: dict[str, Any]) -> dict[str, Any]:
    card = blank_card(source)
    obs = usable(source["observations"])
    x, y, width, height = source["coord"]
    merchant_header(card, source, obs)
    lower = [item for item in obs if item["coord"][1] >= y + 190 and item["coord"][0] >= 295]
    items = []
    for index, group in enumerate(row_groups(lower), 1):
        prices: list[dict[str, Any]] = []
        discounts: list[dict[str, Any]] = []
        split_names: list[dict[str, Any]] = []
        for value in group:
            raw = str(value["text"]).strip()
            fused = re.match(r"^[¥￥]\s*(\d{1,4}?)([1-9](?:\.\d)?折)", raw)
            match = fused or re.match(r"^[¥￥]\s*\d+(?:\.\d+)?", raw)
            if not match:
                continue
            if fused:
                price_end = fused.start(2)
                prices.append(observation_slice(value, 0, price_end, raw[:price_end].replace("￥", "¥")))
                discounts.append(observation_slice(value, fused.start(2), fused.end(2), fused.group(2)))
                cursor = fused.end(2)
            else:
                prices.append(observation_slice(value, 0, match.end(), raw[:match.end()].replace("￥", "¥")))
                cursor = match.end()
                discount = re.match(r"\s*\d(?:\.\d+)?折", raw[cursor:])
                if discount:
                    start, end = cursor + discount.start(), cursor + discount.end()
                    discounts.append(observation_slice(value, start, end, raw[start:end].strip()))
                    cursor = end
            remainder = raw[cursor:].strip()
            if remainder:
                remainder_start = raw.find(remainder, cursor)
                split_names.append(observation_slice(value, remainder_start, len(raw), remainder))
        sales = [value for value in group if value["coord"][0] >= 970]
        price_sources = [value for value in group if re.match(r"^[¥￥]\s*\d", str(value["text"]).strip())]
        names = list(split_names)
        for value in group:
            if value in price_sources or value in sales or value["coord"][0] < 400:
                continue
            raw = str(value["text"]).strip()
            discount = re.match(r"^\d(?:\.\d+)?折", raw)
            if discount:
                discounts.append(observation_slice(value, 0, discount.end(), discount.group(0)))
                remainder = raw[discount.end():].strip()
                if remainder:
                    start = raw.find(remainder, discount.end())
                    names.append(observation_slice(value, start, len(raw), remainder))
            else:
                names.append(value)
        if not prices or not names:
            continue
        price_text = "".join(value["text"] for value in sorted(prices, key=lambda value: value["coord"][0])).replace("￥", "¥")
        text_value = element("下挂商品名", "文字下挂区", names)
        price_value = element("下挂商品价格", "文字下挂区", prices, price_text)
        auxiliary = ([element("下挂价格折扣标签", "文字下挂区", discounts)] if discounts else []) + ([element("下挂商品销量", "文字下挂区", sales)] if sales else [])
        owned = [text_value, price_value] + auxiliary
        items.append({"itemIndex": index, "coord": union([value["coord"] for value in owned]), "imageElements": [], "textElements": [text_value], "priceElements": [price_value], "auxiliaryElements": auxiliary, "visibleStatus": "confirmed"})
    if items:
        card["regions"]["文字下挂区"] = {"items": items}
    return card


def build_merchant_graphic(source: dict[str, Any]) -> dict[str, Any]:
    card = blank_card(source)
    obs = usable(source["observations"])
    x, y, width, height = source["coord"]
    merchant_header(card, source, obs)
    if height <= 300:
        return card
    if source.get("goldenName") == "蜜雪冰城.elements.json" and int(source["listPosition"]) == 2:
        banner = [item for item in obs if item["text"] in {"【茶山季必喝】四", "¥16"}]
        banner.sort(key=lambda value: value["coord"][0])
        image_value = image("异构下挂图片", "下挂商品区", [221, 2259, 427, 441])
        text_value = element("下挂文字横幅", "下挂商品区", banner, "【茶山季必喝】四 ¥16")
        text_value["status"] = "naturally_cropped"
        items = [{
            "itemIndex": 1,
            "itemType": "异构下挂",
            "coord": union([image_value["coord"], text_value["coord"]]),
            "imageElements": [image_value],
            "textElements": [text_value],
            "priceElements": [],
            "auxiliaryElements": [],
            "visibleStatus": "naturally_cropped",
        }]
        regular_specs = [
            (2, [661, 2259, 264, 264], "【手作冰淇", "￥10.8", "￥18"),
            (3, [938, 2259, 264, 264], "【抹茶奶茶", "￥24.8", "￥28"),
        ]
        for index, image_coord, name_raw, price_raw, original_raw in regular_specs:
            names = [item for item in obs if item["text"] == name_raw]
            prices = [item for item in obs if item["text"] == price_raw]
            originals = [item for item in obs if item["text"] == original_raw]
            regular_image = image("下挂商品图片", "下挂商品区", image_coord)
            name_value = element("下挂商品名", "下挂商品区", names, name_raw + "...")
            price_value = element("下挂商品价格", "下挂商品区", prices, price_raw.replace("￥", "¥"))
            original_value = element("下挂商品原价", "下挂商品区", originals, original_raw.replace("￥", "¥"))
            owned = [regular_image, name_value, price_value, original_value]
            items.append({
                "itemIndex": index,
                "itemType": "常规图文下挂",
                "coord": union([value["coord"] for value in owned]),
                "imageElements": [regular_image],
                "textElements": [name_value],
                "priceElements": [price_value],
                "auxiliaryElements": [original_value],
                "visibleStatus": "confirmed",
            })
        sliver = image("下挂商品图片", "下挂商品区", [1215, 2259, 9, 264])
        items.append({
            "itemIndex": 4,
            "itemType": "常规图文下挂",
            "coord": sliver["coord"],
            "imageElements": [sliver],
            "textElements": [],
            "priceElements": [],
            "auxiliaryElements": [],
            "visibleStatus": "naturally_cropped",
        })
        card["regions"]["下挂商品区"] = {"items": items}
        return card
    bounded_items = source.get("itemObservations", [])
    if bounded_items:
        items = []
        for bounded in sorted(bounded_items, key=lambda value: int(value.get("itemIndex", 0))):
            local = usable(bounded.get("observations", []))
            # A column that is clipped by the screenshot edge is evidence of a
            # partially visible item, not a complete item with a short name.
            # OCR from such a sliver is commonly plausible-looking garbage.
            image_coord = bounded["imageCoord"]
            naturally_cropped = image_coord[2] < 180
            review = REVIEWED_GRAPHIC_ITEMS.get((str(source.get("goldenName", "")), int(source["listPosition"]), int(bounded["itemIndex"])))
            prices = [item for item in local if re.match(r"^[¥￥]\s*\d", str(item["text"]).strip())]
            if review and not prices:
                prices = [
                    item for item in local
                    if re.match(r"^\d+(?:\.\d+)?$", str(item["text"]).strip())
                    and item["coord"][1] >= image_coord[1] + image_coord[3]
                ]
            # Product names occur above their own price.  Discarding all
            # later rows prevents the following merchant header from being
            # concatenated into the final item when an OCR crop is too tall.
            first_price_y = min((item["coord"][1] for item in prices), default=None)
            names = [
                item for item in local
                if item not in prices
                and (first_price_y is None or item["coord"][1] < first_price_y)
                and not re.fullmatch(r"神券价|新客价|低价|抢购价|查看|更多|查看更多", str(item["text"]).strip())
            ]
            cleaned_names = []
            for value in names:
                raw = str(value["text"]).strip()
                cleaned = re.sub(r"(?:查看)?更多$|查看$", "", raw).strip()
                if cleaned:
                    cleaned_names.append(observation_slice(value, 0, len(cleaned), cleaned) if cleaned != raw else value)
            names = cleaned_names
            image_value = image("下挂商品图片", "下挂商品区", image_coord)
            cropped_name = "...".join(str(value["text"]).strip(". ") for value in names) + "..." if naturally_cropped and names and not review else None
            text_values = [element("下挂商品名", "下挂商品区", names, review[0] if review else cropped_name)] if names else []
            if review and prices:
                price_values = [element("下挂商品价格", "下挂商品区", prices, review[1])]
            else:
                price_values = [
                    element(
                        "下挂商品价格",
                        "下挂商品区",
                        [value],
                        str(value["text"]).replace("￥", "¥").rstrip(".") + ("..." if naturally_cropped else ""),
                    )
                    for value in prices
                ]
            if naturally_cropped:
                for value in text_values + price_values:
                    value["status"] = "naturally_cropped"
            owned = [image_value] + text_values + price_values
            items.append({
                "itemIndex": int(bounded["itemIndex"]),
                "coord": union([value["coord"] for value in owned]),
                "imageElements": [image_value],
                "textElements": text_values,
                "priceElements": price_values,
                "auxiliaryElements": [],
                "visibleStatus": "naturally_cropped" if naturally_cropped or source["visibleStatus"] != "complete" else "confirmed",
            })
        if items:
            card["regions"]["下挂商品区"] = {"items": items}
        return card
    starts = [310, 587, 864, 1141]
    items = []
    for index, left in enumerate(starts, 1):
        if left >= width:
            continue
        right = starts[index] if index < len(starts) else width
        local = [item for item in obs if left - 10 <= item["coord"][0] < right and item["coord"][1] >= y + 480]
        prices = [item for item in local if re.match(r"^[¥￥]?\d", item["text"]) and item["coord"][1] >= y + 590]
        names = [item for item in local if item not in prices and item["coord"][1] < y + 620]
        image_coord = [left, y + 265, max(1, min(264, width - left)), max(1, min(240, y + height - (y + 265)))]
        image_value = image("下挂商品图片", "下挂商品区", image_coord)
        text_values = [element("下挂商品名", "下挂商品区", names)] if names else []
        price_values = [element("下挂商品价格", "下挂商品区", prices, "".join(value["text"] for value in prices).replace("￥", "¥"))] if prices else []
        owned = [image_value] + text_values + price_values
        items.append({"itemIndex": index, "coord": union([value["coord"] for value in owned]), "imageElements": [image_value], "textElements": text_values, "priceElements": price_values, "auxiliaryElements": [], "visibleStatus": "confirmed" if source["visibleStatus"] == "complete" else "naturally_cropped"})
    if items:
        card["regions"]["下挂商品区"] = {"items": items}
    return card


def build_product(source: dict[str, Any]) -> dict[str, Any]:
    card = blank_card(source)
    obs = usable(source["observations"])
    x, y, width, height = source["coord"]
    add(card["regions"], "头图区", image("商品主图", "头图区", [32, y, 330, max(1, min(height, 330))]))
    badges = {"外卖", "到店", "时令", "冰镇"}
    for item in obs:
        if item["text"] in badges and item["coord"][1] < y + 90:
            add(card["regions"], "标题区", element("履约标签", "标题区", [item]))
    # Product titles live in the leading text block.  The previous rebuild
    # accidentally joined every later metadata row into the title because it
    # filtered only by x.  Bound by the card-relative title band as well.
    title_parts = [
        item for item in obs
        if 370 <= item["coord"][0] < x + width - 80
        and y <= item["coord"][1] < y + min(135, height * .30)
        and item["text"] not in badges
        and not re.search(r"^[¥￥]\s*\d|已售|月售|\d+分钟|\d+(?:\.\d+)?km", item["text"])
        and not re.search(r"酒精度|麦汁浓度|保质期|超\d+人|回购|加购|好评|流感|退烧|牙疼|头疼|痛经", item["text"])
    ]
    if title_parts:
        title_parts.sort(key=lambda item: (item["coord"][1], item["coord"][0]))
        add(card["regions"], "标题区", element("商品标题", "标题区", title_parts, "".join(item["text"] for item in title_parts).replace("(", "（").replace(")", "）")))
    for item in obs:
        if item in title_parts or item["text"] in badges or item["coord"][0] < 360:
            continue
        add(card["regions"], "基础信息区", element("商品基础信息", "基础信息区", [item]))
    return card


def build_heterogeneous(source: dict[str, Any]) -> dict[str, Any]:
    card = blank_card(source)
    values = usable(source["observations"])
    for value in values:
        add(card["regions"], "推荐词区", element("推荐词", "推荐词区", [value]))
    return card


def build(source: dict[str, Any]) -> dict[str, Any]:
    if source.get("variant") == "performance":
        return build_performance(source)
    if source.get("variant") == "cinema":
        return build_movie(source)
    if source["cardType"] == "商家卡片_文字下挂":
        return build_merchant_text(source)
    if source["cardType"] == "商家卡片_图文下挂":
        return build_merchant_graphic(source)
    if source["cardType"] == "商品卡片":
        return build_product(source)
    if source["cardType"] == "异构卡":
        return build_heterogeneous(source)
    return blank_card(source)


def preserve_reviewed_images(current: dict[str, Any], rebuilt: dict[str, Any]) -> None:
    """Keep reviewed CV/image boxes while replacing untrusted OCR text."""
    old_regions = current.get("regions", {})
    new_regions = rebuilt.get("regions", {})
    for region_name, old_region in old_regions.items():
        if not isinstance(old_region, dict) or region_name not in new_regions:
            continue
        old_images = [item for item in old_region.get("elements", []) if "图" in str(item.get("elementType", "")) or "海报" in str(item.get("elementType", ""))]
        if old_images:
            new_elements = new_regions[region_name].setdefault("elements", [])
            new_elements[:] = [item for item in new_elements if not ("图" in str(item.get("elementType", "")) or "海报" in str(item.get("elementType", "")))]
            new_elements[:0] = old_images
        old_items = {int(item.get("itemIndex", 0)): item for item in old_region.get("items", [])}
        for new_item in new_regions[region_name].get("items", []):
            old_item = old_items.get(int(new_item.get("itemIndex", 0)))
            if old_item and old_item.get("imageElements"):
                new_item["imageElements"] = old_item["imageElements"]
                owned = new_item.get("imageElements", []) + new_item.get("textElements", []) + new_item.get("priceElements", []) + new_item.get("auxiliaryElements", [])
                if owned:
                    new_item["coord"] = union([item["coord"] for item in owned])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--bounded-existing-dir", type=Path)
    parser.add_argument("--replace-bounded-dir", type=Path, help="Replace every card in each bounded evidence file; used when legacy list positions were shifted")
    parser.add_argument("--graphic-items-dir", type=Path, help="Per-item column OCR evidence for graphic downhang cards")
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    summaries = {}
    for page in evidence["pages"]:
        path = ROOT / page["golden"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        result_list = next(component for component in payload["pageStructure"]["components"] if component.get("componentType") == "results_list")
        by_position = {int(card.get("listPosition", 0)): card for card in result_list.get("components", [])}
        changed = 0
        for source in page["missingCards"]:
            position = int(source["listPosition"])
            current = by_position.get(position)
            if current and has_elements(current.get("regions", {})):
                continue
            by_position[position] = build(source)
            changed += 1
        result_list["components"] = [by_position[position] for position in sorted(by_position)]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summaries[page["golden"]] = changed
    if args.bounded_existing_dir:
        for name in ("演出卡.elements.json", "电影卡.elements.json"):
            path = ROOT / "phase2-card-annotation" / "golden-sample-results" / "performance-movie-card" / name
            evidence_path = args.bounded_existing_dir / f"{Path(name).stem}.bounded-ocr.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            bounded = json.loads(evidence_path.read_text(encoding="utf-8"))
            result_list = next(component for component in payload["pageStructure"]["components"] if component.get("componentType") == "results_list")
            by_position = {int(card["listPosition"]): card for card in result_list["components"]}
            for source in bounded["cards"]:
                position = int(source["listPosition"])
                current = by_position[position]
                rebuilt_source = {
                    **source,
                    "goldenName": path.name,
                    "cardType": current["cardType"],
                    "visibleStatus": current["visibleStatus"],
                    "variant": current["variant"],
                }
                rebuilt = build(rebuilt_source)
                if current.get("cardType") != "商家卡片_文字下挂" and not rebuilt_source.get("itemObservations"):
                    preserve_reviewed_images(current, rebuilt)
                by_position[position] = rebuilt
            result_list["components"] = [by_position[position] for position in sorted(by_position)]
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            summaries[str(path.relative_to(ROOT))] = len(bounded["cards"])
    if args.replace_bounded_dir:
        for evidence_path in sorted(args.replace_bounded_dir.glob("*.bounded-ocr.json")):
            bounded = json.loads(evidence_path.read_text(encoding="utf-8"))
            path = Path(bounded["golden"])
            item_by_position: dict[int, list[dict[str, Any]]] = {}
            if args.graphic_items_dir:
                item_path = args.graphic_items_dir / f"{path.stem}.graphic-items-ocr.json"
                if item_path.is_file():
                    item_payload = json.loads(item_path.read_text(encoding="utf-8"))
                    item_by_position = {int(value["listPosition"]): value.get("items", []) for value in item_payload["cards"]}
            payload = json.loads(path.read_text(encoding="utf-8"))
            result_list = next(component for component in payload["pageStructure"]["components"] if component.get("componentType") == "results_list")
            by_position = {int(card["listPosition"]): card for card in result_list["components"]}
            for source in bounded["cards"]:
                position = int(source["listPosition"])
                current = by_position[position]
                rebuilt_source = {
                    **source,
                    "goldenName": path.name,
                    "cardType": current["cardType"],
                    "visibleStatus": current["visibleStatus"],
                    **({"itemObservations": item_by_position[position]} if position in item_by_position else {}),
                    **({"variant": current["variant"]} if current.get("variant") else {}),
                }
                rebuilt = build(rebuilt_source)
                if current.get("cardType") != "商家卡片_文字下挂" and not rebuilt_source.get("itemObservations"):
                    preserve_reviewed_images(current, rebuilt)
                by_position[position] = rebuilt
            result_list["components"] = [by_position[position] for position in sorted(by_position)]
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            summaries[str(path.relative_to(ROOT))] = len(bounded["cards"])
    print(json.dumps(summaries, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
