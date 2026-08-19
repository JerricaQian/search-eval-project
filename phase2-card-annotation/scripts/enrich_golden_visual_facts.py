#!/usr/bin/env python3
"""Attach measured Phase3-facing render, text, and color facts to all goldens.

This is an offline golden-only pass.  It reads each already calibrated element
box and measures that exact screenshot crop; it never changes text or geometry.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "phase2-card-annotation" / "golden-sample-results"


def hex_rgb(value: np.ndarray | list[int]) -> str:
    return "#" + "".join(f"{int(channel):02X}" for channel in value)


def color_role(rgb: np.ndarray) -> str:
    r, g, b = (int(value) for value in rgb)
    if max(r, g, b) - min(r, g, b) < 34:
        return "neutral"
    if r > g * 1.22 and r > b * 1.22:
        return "orange" if g >= r * 0.34 else "red"
    if g > r * 1.12 and g > b * 1.06:
        return "green"
    if b > r * 1.14 and b > g * 1.04:
        return "blue"
    if r > 105 and b > 105 and g < min(r, b) * 0.82:
        return "purple"
    if r > 150 and g > 115 and b < min(r, g) * 0.62:
        return "yellow"
    return "multicolor"


def measure_crop(rgb: np.ndarray, coord: list[int]) -> dict[str, str]:
    height, width = rgb.shape[:2]
    x, y, w, h = (int(value) for value in coord)
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(width, x + w), min(height, y + h)
    crop = rgb[y0:y1, x0:x1]
    if crop.size == 0:
        return {"colorRole": "unknown", "textColor": "", "backgroundColor": "", "colorEvidence": "empty_element_crop"}

    border = np.concatenate((crop[0].reshape(-1, 3), crop[-1].reshape(-1, 3), crop[:, 0].reshape(-1, 3), crop[:, -1].reshape(-1, 3)))
    background = np.median(border, axis=0)
    pixels = crop.reshape(-1, 3).astype(np.int16)
    distance = np.linalg.norm(pixels - background.astype(np.int16), axis=1)
    brightness = pixels.mean(axis=1)
    foreground = pixels[(distance >= 30) & (brightness <= 248)]
    if len(foreground) < max(6, len(pixels) // 350):
        spread = pixels.max(axis=1) - pixels.min(axis=1)
        foreground = pixels[(brightness < 190) | ((spread > 42) & (brightness < 238))]
    if len(foreground) < 3:
        return {
            "colorRole": "unknown",
            "textColor": "",
            "backgroundColor": hex_rgb(background),
            "colorEvidence": "element_crop_insufficient_foreground_pixels",
        }
    foreground_median = np.median(foreground, axis=0)
    return {
        "colorRole": color_role(foreground_median),
        "textColor": hex_rgb(foreground_median),
        "backgroundColor": hex_rgb(background),
        "colorEvidence": "element_crop_border_and_foreground_pixel_median",
    }


def entity_kind(element_type: str, region: str) -> str:
    if any(token in element_type for token in ("图片", "头图", "海报", "视频", "横幅/轮播")):
        return "image"
    if "icon" in element_type.lower():
        return "icon"
    if region == "标签区" or any(token in element_type for token in ("标签", "履约", "折扣", "状态", "榜单", "图筛项")):
        return "tag"
    return "text"


def semantic_role(element_type: str, text: str) -> str:
    if "标题" in element_type or element_type in {"影院名", "酒店名称", "电影名"}:
        return "title"
    if "价格" in element_type or element_type in {"起价", "价格区间", "价格与交易信息"} or re.match(r"^[¥￥]", text):
        return "price"
    if "评分" in element_type or "好评率" in element_type:
        return "rating"
    if "销量" in element_type or "观看人数" in element_type or "计数" in element_type:
        return "sales"
    if element_type in {"距离", "地址", "城市", "位置信息", "AOI"}:
        return "location"
    if "履约" in element_type or "配送" in element_type:
        return "fulfillment"
    if any(token in element_type for token in ("折扣", "券", "推荐", "榜单")):
        return "promotion"
    if "图筛" in element_type:
        return "filter"
    return "other"


def tag_semantic_role(element_type: str, text: str) -> str:
    if re.search(r"券|折|减|膨", text) or "折扣" in element_type:
        return "券标"
    if "履约" in element_type or re.search(r"外卖|到店|配送|上门", text):
        return "履约标"
    if "榜" in text or "榜单" in element_type:
        return "榜单标"
    if "图筛" in element_type:
        return "筛选项"
    return "业务标签"


def size_bucket(height: int) -> str:
    if height <= 28:
        return "small"
    if height <= 48:
        return "medium"
    return "large"


def enrich_element(element: dict[str, Any], rgb: np.ndarray) -> None:
    coord = element.get("coord")
    if not isinstance(coord, list) or len(coord) != 4:
        return
    element_type = str(element.get("elementType", ""))
    region = str(element.get("sourceRegion", ""))
    text = str(element.get("visibleText", ""))
    kind = entity_kind(element_type, region)
    confirmed = element.get("status") == "confirmed"
    visible_status = "confirmed" if confirmed else "uncertain"
    naturally_cropped = "..." in text or "…" in text
    element["render"] = {
        "visibleStatus": visible_status,
        "renderState": "naturally_cropped" if naturally_cropped else ("normal" if confirmed else "uncertain"),
        "sourceRegion": region,
        "isPhoto": kind == "image",
        "isSystemUi": kind != "image",
    }

    if kind == "image":
        element["visual"] = {
            "entityKind": "image",
            "visualStatus": visible_status,
            "isColored": False,
            "isShaped": False,
            "colorRole": "unknown",
            "backgroundColor": "",
            "textColor": "",
            "borderColor": "",
            "hasGraphicAssist": False,
            "graphicType": "无",
            "styleKey": f"image|unknown|photo|{region}|无",
            "sourceRegion": region,
            "colorEvidence": "photo_excluded_phase3_pixel_measurement_required",
        }
        element.pop("textFacts", None)
        return

    measured = measure_crop(rgb, coord)
    role = semantic_role(element_type, text)
    element["textFacts"] = {
        "rawText": text,
        "textStatus": "naturally_ellipsized" if naturally_cropped else ("complete" if confirmed else "uncertain"),
        "semanticRole": role,
        "emphasisLevel": "primary" if role in {"title", "price"} else "secondary",
        "fontSizeBucket": size_bucket(int(coord[3])),
        "fontWeightBucket": "unknown",
        "textColorRole": measured["colorRole"],
    }
    tag_role = tag_semantic_role(element_type, text) if kind in {"tag", "icon"} else role
    visual: dict[str, Any] = {
        "entityKind": kind,
        "visualStatus": "confirmed" if confirmed and measured["colorRole"] != "unknown" else "uncertain",
        "isColored": measured["colorRole"] not in {"neutral", "unknown"},
        "isShaped": False,
        "colorRole": measured["colorRole"],
        "backgroundColor": measured["backgroundColor"],
        "textColor": measured["textColor"],
        "borderColor": "",
        "hasGraphicAssist": False,
        "graphicType": "无",
        "styleKey": f"{kind}|{measured['colorRole']}|{tag_role}|unknown|无",
        "sourceRegion": region,
        "colorEvidence": measured["colorEvidence"],
    }
    if kind in {"tag", "icon"}:
        visual.update({
            "semanticRole": tag_role,
            "containerShape": "unknown",
            "graphicAssistRole": "无",
            "countedInComplexity": True,
            "countDecision": "独立元素框及当前截图像素确认",
            "dedupDecision": "未与其他可见实体合并",
            "dedupWithElementIds": [],
        })
    element["visual"] = visual


def enrich(path: Path) -> tuple[int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    screenshot = ROOT / payload["verification"]["rawScreenshot"]
    rgb = np.asarray(Image.open(screenshot).convert("RGB"))
    element_count = measured_count = 0

    def visit(value: Any) -> None:
        nonlocal element_count, measured_count
        if isinstance(value, dict):
            if "elementType" in value:
                element_count += 1
                enrich_element(value, rgb)
                measured_count += int(value.get("visual", {}).get("colorEvidence") == "element_crop_border_and_foreground_pixel_median")
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload["pageStructure"])
    verification = payload.setdefault("verification", {})
    verification["claimScope"] = sorted(set(verification.get("claimScope", []) + ["element_render_facts", "element_text_facts", "element_visual_color_facts"]))
    verification["visualCalibration"] = {
        "status": "measured_from_current_element_boxes",
        "method": "element_crop_border_and_foreground_pixel_median",
        "photoPolicy": "photos retain geometry and are measured by Phase3 after exclusion masking",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return element_count, measured_count


def main() -> int:
    files = sorted(RESULTS.rglob("*.elements.json"))
    if len(files) != 34:
        raise RuntimeError(f"expected 34 golden JSON files, found {len(files)}")
    elements = measured = 0
    for path in files:
        current_elements, current_measured = enrich(path)
        elements += current_elements
        measured += current_measured
    print(json.dumps({"files": len(files), "elements": elements, "pixelMeasuredElements": measured}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
