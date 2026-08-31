#!/usr/bin/env python3
"""Deterministic per-component visual measurement for pixel-dependent evals.

Reads the phase2 element manifest (card coords + regions + elements) plus the
original screenshot, and measures REAL pixels with OpenCV/numpy. No rating is
decided here; ratings are derived from these numbers by
apply_component_ratings.py, so every grade stays traceable to a measurement.

Eval-2 visual order and eval-6 information partitioning are intentionally not
measured here: both consume the validated Phase2 JSON structure and coordinates
directly, without OpenCV or screenshot-derived layout facts.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[6]
PHASE3_COMMON_SCRIPTS_DIR = PROJECT_ROOT / "phase3-evaluation" / "common" / "scripts"
SHARED_SCRIPTS_DIR = PROJECT_ROOT / "scripts"
for module_dir in (PHASE3_COMMON_SCRIPTS_DIR, SHARED_SCRIPTS_DIR):
    if str(module_dir) not in sys.path:
        sys.path.insert(0, str(module_dir))

from phase2_bundle_loader import load_phase2_facts
from color_taxonomy import HUE7_BINS, hue7_family
from phase3_color_scope import excluded_page_modules

ROOT: Path
MANIFEST_DIR: Path
METRIC_DIR: Path

HIERARCHY_CALIBRATION_PROFILE = "phase3.hierarchy-glyph.v1"
HIERARCHY_REFERENCE_WIDTH_PX = 1224
HIERARCHY_REFERENCE_GAP_PX = 6


def hierarchy_glyph_gap_threshold(image_width_px: int) -> int:
    """Scale the calibrated 2pt-equivalent glyph gap to the screenshot width.

    The current golden corpus is rendered at roughly 3 physical pixels per
    typographic point (1224px viewport), so a 2pt perceptual step maps to a
    6px glyph-ink-height gap.  Smaller screenshots keep a 3px floor so
    anti-aliasing noise cannot create extra tiers.
    """
    return max(3, int(round(HIERARCHY_REFERENCE_GAP_PX * image_width_px / HIERARCHY_REFERENCE_WIDTH_PX)))


def configure_paths(project_dir: str) -> None:
    global ROOT, MANIFEST_DIR, METRIC_DIR
    ROOT = Path(project_dir)
    MANIFEST_DIR = ROOT / "screenshots-out"
    METRIC_DIR = ROOT / ".artifacts" / "过程文件-指标测量"


# ---------------------------------------------------------------- utilities

def clamp_box(box, w: int, h: int) -> tuple[int, int, int, int]:
    x, y, bw, bh = [int(round(float(v))) for v in box]
    x0 = max(0, min(x, w - 1))
    y0 = max(0, min(y, h - 1))
    x1 = max(x0 + 1, min(x + bw, w))
    y1 = max(y0 + 1, min(y + bh, h))
    return x0, y0, x1, y1


def crop(img: np.ndarray, box) -> np.ndarray:
    h, w = img.shape[:2]
    x0, y0, x1, y1 = clamp_box(box, w, h)
    return img[y0:y1, x0:x1]


def ebox(el: dict) -> list:
    return el.get("坐标") or el.get("coord")


def etype(el: dict) -> str:
    return el.get("元素类型") or el.get("elementType") or ""


def etext(el: dict) -> str:
    facts = el.get("textFacts") if isinstance(el.get("textFacts"), dict) else {}
    c = facts.get("rawText") or el.get("内容简述") or el.get("content") or ""
    return re.sub(r"^原文[:：]\s*", "", c).strip()


def semantic_role(el: dict) -> str:
    facts = el.get("textFacts") if isinstance(el.get("textFacts"), dict) else {}
    return str(facts.get("semanticRole") or "other").strip() or "other"


def overlap(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, min(a1, b1) - max(a0, b0))


# ------------------------------------------------------- photo / ui masking

def build_photo_mask(bgr: np.ndarray, excluded_boxes: list, overlay_boxes: list) -> np.ndarray:
    """Exclude Phase2-confirmed photo pixels and retain only confirmed system-UI overlays.

    Image texture must never be reclassified as UI merely because it contains a
    compact saturated patch. Overlay retention is therefore driven exclusively
    by Phase2 `render.isSystemUi` facts and their exact element bounds.
    """
    h, w = bgr.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    for box in excluded_boxes:
        x0, y0, x1, y1 = clamp_box(box, w, h)
        mask[y0:y1, x0:x1] = 255
    for box in overlay_boxes:
        x0, y0, x1, y1 = clamp_box(box, w, h)
        mask[y0:y1, x0:x1] = 0
    return mask


# --------------------------------------------------------------- colour bins

HUE_FAMILIES = list(HUE7_BINS)


def hue_family(hue_deg: float) -> str:
    return hue7_family(hue_deg)


def measure_colors(bgr: np.ndarray, card_box, photo_mask: np.ndarray, ui_mask: np.ndarray) -> dict:
    """eval-3: seven-colour HSV binning over UI pixels only.

    Photo pixels are excluded; near-white background and low-coverage families
    (<1% of chromatic pixels, per SKILL) are dropped before counting families.
    """
    h, w = bgr.shape[:2]
    x0, y0, x1, y1 = clamp_box(card_box, w, h)
    sub = bgr[y0:y1, x0:x1]
    sub_photo = photo_mask[y0:y1, x0:x1]

    hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
    H = hsv[:, :, 0].astype(np.float32) * 2.0
    S = hsv[:, :, 1].astype(np.float32) / 255.0 * 100.0
    V = hsv[:, :, 2].astype(np.float32) / 255.0 * 100.0

    valid = (sub_photo == 0) & (ui_mask[y0:y1, x0:x1] > 0)
    valid &= ~((S < 12) & (V > 92))      # drop white page background
    chromatic = valid & (S >= 12) & (V >= 20)
    chroma_count = int(chromatic.sum())

    counts: Counter[str] = Counter()
    if chroma_count:
        hf = H[chromatic]
        for name, lo, hi in HUE_FAMILIES:
            counts[name] += int(((hf >= lo) & (hf < hi)).sum())

    fams = []
    for name, cnt in counts.items():
        if not cnt:
            continue
        ratio = cnt / max(int(valid.sum()), 1)
        chroma_ratio = cnt / max(chroma_count, 1)
        fams.append({"family": name, "pixels": cnt, "ratioOfChroma": round(chroma_ratio, 4),
                     "ratioOfValidUi": round(ratio, 4),
                     "diagnosticRatioOfChroma": round(chroma_ratio, 4), "kept": ratio >= 0.01})
    kept = sorted([f for f in fams if f["kept"]], key=lambda f: -f["pixels"])
    dropped = sorted([f for f in fams if not f["kept"]], key=lambda f: -f["pixels"])
    return {
        "validPixels": int(valid.sum()),
        "photoExcludedPixels": int((sub_photo > 0).sum()),
        "chromaticPixels": chroma_count,
        "families": kept,
        "droppedFamilies": dropped,
        "familyCount": len(kept),
    }


# ------------------------------------------------------------ text measuring

INK_DELTA = 14      # grey-on-white UI text can be as faint as ~20 levels


def ink_mask(gray: np.ndarray) -> tuple[np.ndarray, int]:
    """Ink = pixels differing from the local background by >= INK_DELTA.

    The threshold is deliberately low: 电竞房 channel tabs are light grey
    (min 220 / max 250) on white, and a 40-level threshold wrongly reported
    them as blank/missing.
    """
    bg = int(np.median(gray))
    return np.abs(gray.astype(np.int32) - bg) >= INK_DELTA, bg


def measure_text(bgr: np.ndarray, box) -> dict:
    """Per-line glyph height + ink colour of a text element, from real pixels.

    Multi-line blocks are split into ink row-runs so the reported glyph height
    is one text line, not the whole paragraph span (which produced bogus
    338px/396px values).
    """
    patch = crop(bgr, box)
    if patch.size == 0:
        return {"glyphHeightPx": 0, "lineCount": 0, "inkRatio": 0.0,
                "meanColor": [0, 0, 0], "chromatic": False}
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    ink, bg = ink_mask(gray)

    rows = ink.any(axis=1)
    runs: list[int] = []
    start = None
    for i, on in enumerate(rows):
        if on and start is None:
            start = i
        elif not on and start is not None:
            runs.append(i - start)
            start = None
    if start is not None:
        runs.append(len(rows) - start)
    runs = [r for r in runs if r >= 4]           # ignore 1-2px separators
    gh = int(round(float(np.median(runs)))) if runs else 0

    if ink.any():
        mc = patch[ink].mean(axis=0)
        mean_color = [int(mc[2]), int(mc[1]), int(mc[0])]
    else:
        mean_color = [bg, bg, bg]
    mx, mn = max(mean_color), min(mean_color)
    sat = (mx - mn) / mx if mx else 0.0
    return {
        "glyphHeightPx": gh,
        "lineCount": len(runs),
        "inkRatio": round(float(ink.mean()), 4),
        "meanColor": mean_color,
        "chromatic": bool(sat >= 0.25 and mx >= 60),
    }


def json_color_is_chromatic(value: Any) -> bool:
    """Return whether a Phase2 JSON colour is non-neutral (HSV saturation >= 12)."""
    if not isinstance(value, str):
        return False
    token = value.strip().lstrip("#")
    if len(token) == 3:
        token = "".join(character * 2 for character in token)
    if len(token) not in {6, 8}:
        return False
    try:
        red, green, blue = (int(token[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return False
    maximum = max(red, green, blue)
    saturation = 0.0 if maximum == 0 else (maximum - min(red, green, blue)) / maximum * 100
    return saturation >= 12.0


def element_json_chromatic(element: dict[str, Any]) -> bool:
    """Use declared JSON styles for emphasis; pixel work is glyph height only."""
    visual = element.get("visual") if isinstance(element.get("visual"), dict) else {}
    return any(
        json_color_is_chromatic(visual.get(field))
        for field in ("textColor", "backgroundColor", "borderColor")
    )


def analyse_hierarchy_card(bgr: np.ndarray, card: dict[str, Any]) -> dict[str, Any]:
    """Measure only eval-5 glyph facts, avoiding unrelated colour/complexity scans."""
    image_width_px = int(bgr.shape[1])
    threshold = hierarchy_glyph_gap_threshold(image_width_px)
    blocks: list[dict[str, Any]] = []
    for region in card.get("regions", []):
        region_name = str(region.get("name") or "-")
        for element in region.get("elements", []):
            if element.get("isExcluded") or etype(element) == "图片" or not ebox(element):
                continue
            measured = measure_text(bgr, ebox(element))
            blocks.append({
                "id": str(element.get("id") or ""),
                "text": etext(element),
                "region": region_name,
                "semanticRole": semantic_role(element),
                "glyphHeightPx": measured["glyphHeightPx"],
                "lineCount": measured["lineCount"],
                "inkRatio": measured["inkRatio"],
                "chromatic": element_json_chromatic(element),
                "colorEvidenceSource": "phase2_json_visual_colors",
            })
    return {
        "cardId": card.get("cardId"),
        "cardType": card.get("卡片类型"),
        "coord": card.get("coord"),
        "hierarchyMeasurement": {
            "calibrationProfile": HIERARCHY_CALIBRATION_PROFILE,
            "referenceWidthPx": HIERARCHY_REFERENCE_WIDTH_PX,
            "referenceGapPx": HIERARCHY_REFERENCE_GAP_PX,
            "imageWidthPx": image_width_px,
            "glyphHeightGapThresholdPx": threshold,
            "weightBlocks": blocks,
        },
    }


# --------------------------------------------------------------- tag / icon

def measure_tag_style(bgr: np.ndarray, box) -> dict:
    """Measure Phase3 colour/container evidence for one Phase2 atomic box."""
    patch = crop(bgr, box)
    if patch.size == 0:
        return {"pixelStyle": "empty", "chromatic": False, "chromaRatio": 0.0,
                "ringChromaRatio": 0.0, "family": "neutral"}
    h, w = patch.shape[:2]
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    S = hsv[:, :, 1].astype(np.float32) / 255 * 100
    V = hsv[:, :, 2].astype(np.float32) / 255 * 100
    Hd = hsv[:, :, 0].astype(np.float32) * 2

    ring = np.zeros((h, w), dtype=bool)
    t = max(1, min(h, w) // 6)
    ring[:t, :] = True
    ring[-t:, :] = True
    ring[:, :t] = True
    ring[:, -t:] = True

    chroma = (S >= 18) & (V >= 25)
    chroma_ratio = float(chroma.mean())
    ring_chroma = float((chroma & ring).mean())
    ink_chroma = float((chroma & (V < 92)).mean())

    chromatic = chroma_ratio >= 0.12 or ring_chroma >= 0.10 or ink_chroma >= 0.08
    fam = hue_family(float(np.median(Hd[chroma]))) if (chromatic and chroma.any()) else "neutral"
    if chroma_ratio >= 0.45:
        shape = "filled"
    elif ring_chroma >= 0.10:
        shape = "outlined"
    else:
        shape = "text"
    return {
        "pixelStyle": f"{fam}-{shape}" if chromatic else "neutral-plain",
        "family": fam,
        "shape": shape,
        "chromatic": bool(chromatic),
        "chromaRatio": round(chroma_ratio, 3),
        "ringChromaRatio": round(ring_chroma, 3),
    }


PROMOTION_TEXT_RE = re.compile(
    r"特价|特惠|立减|折|优惠|券|补贴|返|赠|可抵|仅剩|低价|限时|秒杀|抢购|权益|会员"
)
PRIMARY_PRICE_RE = re.compile(
    r"^\s*[¥￥]\s*\d+(?:\.\d+)?(?:\s*(?:元|起|/\S+))?\s*$|"
    r"^\s*\d+(?:\.\d+)?\s*(?:元|起)\s*$"
)


def primary_field_exclusion(el: dict) -> str | None:
    """Return the explicit core-field exclusion required by eval-4.

    Coloured auxiliary copy is a tag candidate, but a coloured title, rating
    value or main transaction price is still the underlying core field.  The
    distinction is semantic and must be made before style-key generation.
    """
    role = semantic_role(el)
    text = etext(el)
    if role == "title":
        return "主标题不是标签"
    if role == "rating" or re.fullmatch(r"\s*[0-5](?:\.\d+)?\s*分\s*", text):
        return "核心评分值不是标签"
    if role == "price" and not PROMOTION_TEXT_RE.search(text) and PRIMARY_PRICE_RE.fullmatch(text):
        return "主价格不是标签"
    return None


def five_part_tag_style_key(el: dict, measured: dict) -> str:
    """Build the deterministic five-segment key used for style-kind counts."""
    visual = el.get("visual") if isinstance(el.get("visual"), dict) else {}
    measured_shape = str(measured.get("shape") or "text")
    declared_container = str(visual.get("containerShape") or "none").strip().lower()
    if declared_container not in {"", "none", "无", "无容器"}:
        container = declared_container
    else:
        container = {"filled": "filled", "outlined": "outlined"}.get(measured_shape, "none")
    graphic = str(visual.get("graphicAssistRole") or "none").strip() or "none"
    if graphic in {"无", "none", "None"}:
        graphic = "none"
    return "|".join([
        "tag",
        str(measured.get("family") or "neutral"),
        semantic_role(el),
        container,
        graphic,
    ])


def detect_media_overlay_candidates(
    bgr: np.ndarray,
    media_elements: list[dict],
    covered_boxes: list[list],
) -> list[dict]:
    """Find compact solid chromatic overlays near the top edge of photos.

    These are anomaly cues only. They never enter the formal count without a
    Phase2 atom; a hit therefore requests Phase2 review instead of fabricating
    an element in Phase3.
    """
    image_h, image_w = bgr.shape[:2]
    hits: list[dict] = []
    for media in media_elements:
        box = ebox(media)
        if not box:
            continue
        x0, y0, x1, y1 = clamp_box(box, image_w, image_h)
        patch = bgr[y0:y1, x0:x1]
        if patch.size == 0:
            continue
        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1].astype(np.float32) / 255 * 100
        val = hsv[:, :, 2].astype(np.float32) / 255 * 100
        mask = ((sat >= 55) & (val >= 45)).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        for component_index in range(1, count):
            lx, ly, width, height, area = [int(value) for value in stats[component_index]]
            max_overlay_width = min(105, max(10, int((x1 - x0) * 0.32)))
            if not (10 <= width <= max_overlay_width):
                continue
            if not (8 <= height <= min(72, max(8, (y1 - y0) // 3))):
                continue
            if ly > (y1 - y0) * 0.35:
                continue
            if lx > (x1 - x0) * 0.35 and lx + width < (x1 - x0) * 0.65:
                continue
            fill = area / float(max(width * height, 1))
            if fill < 0.58:
                continue
            absolute = [x0 + lx, y0 + ly, width, height]
            ax0, ay0, aw, ah = absolute
            overlaps_known = False
            for known in covered_boxes:
                kx, ky, kw, kh = [int(value) for value in known]
                intersection = overlap(ax0, ax0 + aw, kx, kx + kw) * overlap(ay0, ay0 + ah, ky, ky + kh)
                if intersection >= 0.5 * max(1, aw * ah):
                    overlaps_known = True
                    break
            if overlaps_known:
                continue
            component_mask = labels[ly:ly + height, lx:lx + width] == component_index
            hue_values = hsv[ly:ly + height, lx:lx + width, 0][component_mask].astype(np.float32) * 2
            family = hue_family(float(np.median(hue_values))) if hue_values.size else "unknown"
            hits.append({
                "mediaElementId": str(media.get("id") or ""),
                "coord": absolute,
                "colorFamily": family,
                "fillRatio": round(fill, 3),
                "decision": "phase2_review_required",
                "reason": "头图顶部发现未被活动原子覆盖的紧凑彩色 UI 角标候选",
            })
    return hits


def detect_icon_candidates(bgr: np.ndarray, boxes: list, photo_mask: np.ndarray) -> dict:
    """Measure compact icon-style candidates inside caller-selected boxes.

    Phase3 supplies confirmed atomic icon boxes for formal measurement. A
    broader scan is retained only as an anomaly cue; blobs outside a Phase2
    atom request base-recognition review and never enter the formal count.
    """
    h_img, w_img = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    styles: list[str] = []
    hits: list[dict] = []
    for box in boxes:
        x0, y0, x1, y1 = clamp_box(box, w_img, h_img)
        sub = bgr[y0:y1, x0:x1]
        sp = photo_mask[y0:y1, x0:x1]
        if sub.size == 0:
            continue
        S = hsv[y0:y1, x0:x1, 1].astype(np.float32) / 255 * 100
        V = hsv[y0:y1, x0:x1, 2].astype(np.float32) / 255 * 100
        cand = ((S >= 35) & (V >= 45) & (sp == 0)).astype(np.uint8) * 255
        cand = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        num, labels, stats, _ = cv2.connectedComponentsWithStats(cand, 8)
        for i in range(1, num):
            x, y, w, h, area = stats[i]
            if area < 90 or w < 12 or h < 12 or w > 64 or h > 64:
                continue
            ar = w / h
            if not (0.65 <= ar <= 1.55):
                continue
            fill = area / float(w * h)
            if fill < 0.35:
                continue
            comp = labels == i
            fam = hue_family(float(np.median(hsv[y0:y1, x0:x1, 0].astype(np.float32)[comp] * 2)))
            key = f"{fam}-{'solid' if fill > 0.6 else 'outline'}-{int(round(h / 12)) * 12}"
            styles.append(key)
            hits.append({"styleKey": key, "at": [int(x0 + x), int(y0 + y), int(w), int(h)]})
    uniq = sorted(set(styles))
    return {"candidateCount": len(uniq), "candidateStyles": uniq, "candidateHits": hits[:40]}


def derive_icon_styles(bgr: np.ndarray, elems: list[dict], photo_mask: np.ndarray) -> dict:
    """Phase3 measures icon styles inside Phase2-confirmed atomic icon boxes."""
    icons = [
        element for element in elems
        if not element.get("isExcluded")
        and isinstance(element.get("visual"), dict)
        and element["visual"].get("entityKind") == "icon"
        and element["visual"].get("visualStatus") == "confirmed"
        and ebox(element)
    ]
    measured = detect_icon_candidates(bgr, [ebox(element) for element in icons], photo_mask)
    included = [
        {"id": str(element.get("id", "")), "coord": ebox(element)}
        for element in icons
    ]
    return {
        "iconCount": measured["candidateCount"],
        "iconStyles": measured["candidateStyles"],
        "iconEntities": included,
        "pixelHits": measured["candidateHits"],
        "measurementComplete": not icons or measured["candidateCount"] > 0,
        "unmeasuredAtomicIconIds": [] if (not icons or measured["candidateCount"] > 0) else [item["id"] for item in included],
        "countSource": "phase3.pixel_measurement_within_phase2_icon_atoms",
    }


# --------------------------------------------------------- region utilities

def region_profile(bgr: np.ndarray, box) -> dict:
    patch = crop(bgr, box)
    if patch.size == 0:
        return {"inkRatio": 0.0, "blank": True, "bgRGB": [255, 255, 255],
                "inkRGB": [255, 255, 255], "stdev": 0.0, "grayMin": 255, "grayMax": 255}
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    ink, _ = ink_mask(gray)
    modal = Counter(tuple(v) for v in (patch.reshape(-1, 3) // 16 * 16)).most_common(1)[0][0]
    ink_pixels = patch[ink]
    if ink_pixels.size:
        ink_bgr = np.median(ink_pixels, axis=0)
        ink_rgb = [int(ink_bgr[2]), int(ink_bgr[1]), int(ink_bgr[0])]
    else:
        ink_rgb = [255, 255, 255]
    return {
        "inkRatio": round(float(ink.mean()), 4),
        # truly empty = no ink AND no tonal range at all (flat fill)
        "blank": bool(ink.mean() < 0.001 and float(gray.max() - gray.min()) < 6),
        "bgRGB": [int(modal[2]), int(modal[1]), int(modal[0])],
        "inkRGB": ink_rgb,
        "stdev": round(float(gray.std()), 2),
        "grayMin": int(gray.min()),
        "grayMax": int(gray.max()),
    }


# --------------------------------------------------------- element taxonomy

KIND_PATTERNS = [
    ("title", ["title", "name"]),
    ("price", ["price", "minimum", "percapita", "pay"]),
    ("rating", ["rating", "score", "star"]),
    ("sales", ["sales", "reviews", "sold", "month"]),
    ("location", ["location", "distance", "address", "area", "poi"]),
    ("image", ["image", "img", "photo", "pic"]),
    ("tag", ["tag", "badge", "label", "discount", "coupon", "reduction",
             "ranking", "flash", "promo", "hot", "free", "delivery"]),
]


def classify(el: dict) -> str:
    eid = (el.get("id") or "").lower()
    for kind, keys in KIND_PATTERNS:
        if any(k in eid for k in keys):
            return kind
    t = etype(el)
    if t == "标签":
        return "tag"
    if t == "图片":
        return "image"
    return "other"


# ------------------------------------------------------------- card analysis

def analyse_card(bgr: np.ndarray, card: dict, photo_mask: np.ndarray, ui_mask: np.ndarray) -> dict:
    card_box = card["coord"]
    regions = card.get("regions", [])
    image_width_px = int(bgr.shape[1])
    hierarchy_gap_px = hierarchy_glyph_gap_threshold(image_width_px)

    elems: list[dict] = []
    for reg in regions:
        for el in reg.get("elements", []):
            e = dict(el)
            e["_region"] = reg.get("name")
            elems.append(e)
    active = [e for e in elems if not e.get("isExcluded")]

    # ---------- eval-1: presence / blankness of every declared element
    presence = []
    for e in elems:
        prof = region_profile(bgr, ebox(e))
        presence.append({
            "id": e.get("id"), "region": e.get("_region"), "kind": classify(e),
            "excluded": bool(e.get("isExcluded")), "coord": ebox(e),
            "text": etext(e), "inkRatio": prof["inkRatio"], "blank": prof["blank"],
        })
    blank = [p for p in presence if p["blank"]]
    kinds_present = sorted({p["kind"] for p in presence if not p["blank"]})

    # ---------- eval-3: colour families
    colors = measure_colors(bgr, card_box, photo_mask, ui_mask)

    # ---------- eval-4: tag styles + icons (whole-card sweep across ALL regions)
    expected_regions = [str(region.get("name") or "-") for region in regions]
    scanned_regions: list[str] = []
    scanned_element_ids: list[str] = []
    tag_styles: dict[str, list[str]] = defaultdict(list)
    tag_contents: dict[str, list[str]] = defaultdict(list)
    excluded_tags: list[dict] = []
    candidate_ledger: list[dict] = []
    region_scan: dict[str, dict] = {
        region_name: {"scannedElementIds": [], "included": [], "excluded": []}
        for region_name in expected_regions
    }

    for region in regions:
        region_name = str(region.get("name") or "-")
        scanned_regions.append(region_name)
        for original in region.get("elements", []):
            if original.get("isExcluded"):
                continue
            e = next(
                item for item in active
                if item.get("id") == original.get("id") and item.get("_region") == region_name
            )
            element_id = str(e.get("id") or "")
            scanned_element_ids.append(element_id)
            region_scan[region_name]["scannedElementIds"].append(element_id)
            visual = e.get("visual") if isinstance(e.get("visual"), dict) else {}
            ledger = {
                "elementId": element_id,
                "region": region_name,
                "content": etext(e) or "[图片]",
                "sourceKind": str(visual.get("entityKind") or classify(e) or "other"),
                "semanticRole": semantic_role(e),
            }

            if visual.get("visualStatus") != "confirmed":
                ledger.update({
                    "decision": "phase2_review_required",
                    "reason": "Phase2 原子类型或边界未确认",
                })
                candidate_ledger.append(ledger)
                excluded_tags.append({"id": element_id, "reason": ledger["reason"]})
                region_scan[region_name]["excluded"].append(f"{element_id}(未确认)")
                continue

            if visual.get("entityKind") == "icon":
                ledger.update({"decision": "included_icon", "reason": "Phase2 已确认独立 icon 原子"})
                candidate_ledger.append(ledger)
                region_scan[region_name]["included"].append(f"{element_id}(独立 icon)")
                continue

            if etype(e) == "图片" or visual.get("entityKind") == "image":
                ledger.update({"decision": "excluded", "reason": "主体图片不是标签或独立 icon"})
                candidate_ledger.append(ledger)
                region_scan[region_name]["excluded"].append(f"{element_id}(主体图片)")
                continue

            core_reason = primary_field_exclusion(e)
            if core_reason:
                ledger.update({"decision": "excluded", "reason": core_reason})
                candidate_ledger.append(ledger)
                excluded_tags.append({"id": element_id, "reason": core_reason})
                region_scan[region_name]["excluded"].append(f"{element_id}({core_reason})")
                continue

            measured = measure_tag_style(bgr, ebox(e))
            declared_container = str(visual.get("containerShape") or "none").strip().lower()
            graphic = str(visual.get("graphicAssistRole") or "none").strip()
            shaped = declared_container not in {"", "none", "无", "无容器"}
            has_graphic = graphic not in {"", "none", "None", "无"}
            typed_tag = etype(e) == "标签" or classify(e) == "tag"
            include_as_tag = bool(measured["chromatic"] or shaped or has_graphic)

            if include_as_tag:
                style_key = five_part_tag_style_key(e, measured)
                tag_styles[style_key].append(element_id)
                tag_contents[style_key].append(etext(e))
                basis = "Phase2 标签原子" if typed_tag else "无容器彩色辅助文字"
                ledger.update({
                    "decision": "included_tag",
                    "reason": basis,
                    "styleKey": style_key,
                    "pixelStyle": measured["pixelStyle"],
                    "colorEvidence": {
                        "chromatic": measured["chromatic"],
                        "family": measured["family"],
                        "chromaRatio": measured["chromaRatio"],
                        "ringChromaRatio": measured["ringChromaRatio"],
                    },
                })
                region_scan[region_name]["included"].append(f"{element_id}({style_key})")
            else:
                reason = "中性色普通文字，无异形、异色或图形辅助"
                ledger.update({
                    "decision": "excluded",
                    "reason": reason,
                    "pixelStyle": measured["pixelStyle"],
                })
                excluded_tags.append({
                    "id": element_id,
                    "pixelStyle": measured["pixelStyle"],
                    "reason": reason,
                    "chromaRatio": measured["chromaRatio"],
                })
                region_scan[region_name]["excluded"].append(f"{element_id}(中性色普通文字)")
            candidate_ledger.append(ledger)

    media_elements = [element for element in active if etype(element) == "图片"]
    known_ui_boxes = [ebox(element) for element in active if etype(element) != "图片" and ebox(element)]
    overlay_review_candidates = detect_media_overlay_candidates(bgr, media_elements, known_ui_boxes)
    tag_style_groups = [
        {
            "styleKey": style_key,
            "elementIds": element_ids,
            "contents": tag_contents[style_key],
        }
        for style_key, element_ids in sorted(tag_styles.items())
    ]

    icon_boxes = [ebox(e) for e in elems
                  if etype(e) != "文本" and not e.get("isExcluded")]
    icon_boxes += [ebox(e) for e in elems if etype(e) == "图片" and e.get("isExcluded")]
    icons = derive_icon_styles(bgr, elems, photo_mask)
    icons["cvCandidatesForPhase2Review"] = detect_icon_candidates(bgr, icon_boxes, photo_mask)

    # ---------- eval-5: visual weight tiers from measured glyph height
    # A text element whose box also spans a declared image (盒马 下挂区 stacks the
    # product title box over the shared product strip image) would otherwise
    # report the photo's full height as a glyph height; those are marked so the
    # tier logic can treat them as composite blocks rather than type specimens.
    image_boxes = [ebox(e) for e in elems if etype(e) == "图片" and ebox(e)]

    def over_image(box) -> bool:
        bx0, by0, bx1, by1 = box[0], box[1], box[0] + box[2], box[1] + box[3]
        for ib in image_boxes:
            ix0, iy0, ix1, iy1 = ib[0], ib[1], ib[0] + ib[2], ib[1] + ib[3]
            ox = overlap(bx0, bx1, ix0, ix1)
            oy = overlap(by0, by1, iy0, iy1)
            if ox * oy >= 0.6 * max(1, (bx1 - bx0) * (by1 - by0)):
                return True
        return False

    blocks = []
    for e in elems:
        box = ebox(e)
        area = int(box[2]) * int(box[3])
        if etype(e) == "图片":
            blocks.append({"id": e.get("id"), "type": "image", "area": area,
                           "glyphHeightPx": 0, "chromatic": False,
                           "region": e.get("_region")})
        else:
            m = measure_text(bgr, box)
            blocks.append({"id": e.get("id"), "type": "text", "area": area,
                           "glyphHeightPx": m["glyphHeightPx"],
                           "lineCount": m["lineCount"],
                           "overImage": over_image(box),
                           "chromatic": m["chromatic"], "meanColor": m["meanColor"],
                           "region": e.get("_region")})

    texts = [{"id": e.get("id"), "region": e.get("_region"), "kind": classify(e),
              "text": etext(e)} for e in active]

    return {
        "cardId": card.get("cardId"),
        "cardType": card.get("卡片类型"),
        "coord": card_box,
        "elementCount": len(elems),
        "activeElementCount": len(active),
        "presence": presence,
        "kindsPresent": kinds_present,
        "blankElements": [b["id"] for b in blank],
        "colors": colors,
        "tagStyles": dict(tag_styles),
        "tagStyleGroups": tag_style_groups,
        "tagStyleCount": len(tag_styles),
        "excludedTags": excluded_tags,
        "regionScan": {k: v for k, v in region_scan.items()},
        "expectedRegions": expected_regions,
        "scannedRegions": scanned_regions,
        "unscannedRegions": sorted(set(expected_regions) - set(scanned_regions)),
        "scannedElementIds": scanned_element_ids,
        "candidateLedger": candidate_ledger,
        "coverageStatus": "completed",
        "styleKeyContract": [
            "entityCategory", "colorRole", "semanticRole", "containerShape", "graphicAssist"
        ],
        "phase2ReviewCandidates": [
            item for item in candidate_ledger if item.get("decision") == "phase2_review_required"
        ] + overlay_review_candidates,
        "phase2ReviewRequired": bool(
            overlay_review_candidates
            or any(item.get("decision") == "phase2_review_required" for item in candidate_ledger)
        ),
        "icons": icons,
        "weightBlocks": blocks,
        "hierarchyMeasurement": {
            "calibrationProfile": HIERARCHY_CALIBRATION_PROFILE,
            "referenceWidthPx": HIERARCHY_REFERENCE_WIDTH_PX,
            "referenceGapPx": HIERARCHY_REFERENCE_GAP_PX,
            "imageWidthPx": image_width_px,
            "glyphHeightGapThresholdPx": hierarchy_gap_px,
            "weightBlocks": blocks,
        },
        "texts": texts,
    }


def _resolve_manifest_and_audit(scene: str, suffix: str) -> tuple[Path, Path | None]:
    """Support both the suffixed convention (elements_{scene}_{suffix}.json)
    and this project's plain convention (elements_{scene}.json +
    elements_{scene}.recognition-audit.json)."""
    suffixed = MANIFEST_DIR / f"elements_{scene}_{suffix}.json"
    if suffixed.exists():
        audit = MANIFEST_DIR / f"elements_{scene}_{suffix}.audit.json"
        return suffixed, (audit if audit.exists() else None)
    plain = MANIFEST_DIR / f"elements_{scene}.json"
    audit = MANIFEST_DIR / f"elements_{scene}.recognition-audit.json"
    return plain, (audit if audit.exists() else None)


def run_scene(
    scene: str,
    suffix: str,
    normalized_path: Path | None = None,
    evidence_path: Path | None = None,
    manifest_path: Path | None = None,
    skill: str | None = None,
) -> dict:
    if manifest_path is not None:
        manifest = load_phase2_facts(manifest_path=manifest_path)
        audit_path = None
    elif normalized_path is not None:
        manifest = load_phase2_facts(normalized_path=normalized_path, evidence_path=evidence_path)
        audit_path = None
    else:
        manifest_path, audit_path = _resolve_manifest_and_audit(scene, suffix)
        manifest = load_phase2_facts(manifest_path=manifest_path)
    manifest_total = None
    if audit_path is not None:
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        manifest_total = audit.get("total")
    if manifest_total is None:
        manifest_total = sum(
            1
            for card in manifest.get("cards", [])
            for reg in card.get("regions", [])
            for el in reg.get("elements", [])
            if not el.get("isExcluded")
        )
    shot = Path(manifest["screenshot"])
    bgr = cv2.imread(str(shot))
    if bgr is None:
        raise SystemExit(f"cannot read image: {shot}")
    h, w = bgr.shape[:2]

    if skill == "eval-5-info-hierarchy":
        comps = [analyse_hierarchy_card(bgr, card) for card in manifest.get("cards", [])]
        return {
            "scene": scene,
            "suffix": suffix,
            "query": manifest.get("query"),
            "screenshot": str(shot),
            "imageSize": [w, h],
            "measurementScope": "hierarchy_only",
            "hierarchyCalibration": {
                "profile": HIERARCHY_CALIBRATION_PROFILE,
                "referenceWidthPx": HIERARCHY_REFERENCE_WIDTH_PX,
                "referenceGapPx": HIERARCHY_REFERENCE_GAP_PX,
                "imageWidthPx": w,
                "glyphHeightGapThresholdPx": hierarchy_glyph_gap_threshold(w),
            },
            "manifestTotal": manifest_total,
            "componentCount": len(comps),
            "components": comps,
        }

    excluded_boxes = []
    overlay_boxes = []
    ui_boxes = []
    for card in manifest.get("cards", []):
        for reg in card.get("regions", []):
            for el in reg.get("elements", []):
                box = ebox(el)
                if not box:
                    continue
                if el.get("isExcluded") or etype(el) == "图片":
                    excluded_boxes.append((el.get("render") or {}).get("photoMaskCoord") or box)
                else:
                    ui_boxes.append(box)
                    if (el.get("render") or {}).get("isSystemUi") is True:
                        overlay_boxes.append(box)
    photo_mask = build_photo_mask(bgr, excluded_boxes, overlay_boxes)
    ui_mask = np.zeros((h, w), dtype=np.uint8)
    for box in ui_boxes:
        x0, y0, x1, y1 = clamp_box(box, w, h)
        ui_mask[y0:y1, x0:x1] = 255

    comps = [analyse_card(bgr, c, photo_mask, ui_mask) for c in manifest.get("cards", [])]
    return {
        "scene": scene, "suffix": suffix, "query": manifest.get("query"),
        "screenshot": str(shot), "imageSize": [w, h],
        "hierarchyCalibration": {
            "profile": HIERARCHY_CALIBRATION_PROFILE,
            "referenceWidthPx": HIERARCHY_REFERENCE_WIDTH_PX,
            "referenceGapPx": HIERARCHY_REFERENCE_GAP_PX,
            "imageWidthPx": w,
            "glyphHeightGapThresholdPx": hierarchy_glyph_gap_threshold(w),
        },
        "manifestTotal": manifest_total,
        "colorScope": {
            "componentSource": "cards_only",
            "excludedPageModules": excluded_page_modules(manifest),
            "rule": "Tab、图筛、业务图筛与筛选器不属于组件/卡片色彩统计范围。",
        },
        "componentCount": len(comps), "components": comps,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-dir", required=True, help="项目根目录，与 workflow projectDir 一致")
    ap.add_argument("--scenes", nargs="+", required=True)
    ap.add_argument("--suffix", default="首评-单一元素-5")
    ap.add_argument("--skill", required=True, help="调用方 skill 名，用于隔离输出文件避免并行写冲突")
    ap.add_argument("--normalized-input", type=Path, help="紧凑黄金真值；Phase3 直接读取，不生成展开清单")
    ap.add_argument("--evidence-input", type=Path, help="与 --normalized-input 配套的校验证据")
    ap.add_argument("--manifest-input", type=Path, help="直接读取单份 atomic/legacy Phase2 manifest")
    ap.add_argument("--output", type=Path,
                    help="单场景测量的隔离输出路径；省略时保留历史默认路径")
    args = ap.parse_args()
    if bool(args.normalized_input) != bool(args.evidence_input):
        ap.error("--normalized-input and --evidence-input must be provided together")
    if args.manifest_input and args.normalized_input:
        ap.error("--manifest-input cannot be combined with --normalized-input")
    if args.manifest_input and len(args.scenes) != 1:
        ap.error("--manifest-input currently accepts exactly one scene")
    if args.normalized_input and len(args.scenes) != 1:
        ap.error("direct golden bundle mode currently accepts exactly one scene")
    if args.output and len(args.scenes) != 1:
        ap.error("--output currently accepts exactly one scene")
    configure_paths(args.project_dir)
    METRIC_DIR.mkdir(parents=True, exist_ok=True)
    for scene in args.scenes:
        data = run_scene(
            scene,
            args.suffix,
            args.normalized_input,
            args.evidence_input,
            args.manifest_input,
            args.skill,
        )
        scene_key = Path(scene).stem
        out = args.output if args.output else METRIC_DIR / f"metrics_{scene_key}_{args.skill}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{scene}: components={data['componentCount']} "
              f"manifestTotal={data['manifestTotal']} -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
