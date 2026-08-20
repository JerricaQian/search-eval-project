#!/usr/bin/env python3
"""Deterministic per-component visual measurement for phase3 eval-1..7.

Reads the phase2 element manifest (card coords + regions + elements) plus the
original screenshot, and measures REAL pixels with OpenCV/numpy. No rating is
decided here; ratings are derived from these numbers by
apply_component_ratings.py, so every grade stays traceable to a measurement.

Geometry facts established by probing the four scenes (and handled below):
  * A card's 头图区 may be a LEFT COLUMN beside the text column (生日蛋糕/盒马/
    生理盐水) or a TOP BAND above the text (电竞房 2-column grid). Region pairs
    are therefore classified as vertical / horizontal / nested before any
    boundary test runs.
  * Some manifests carry a full-card wrapper region with 0 elements
    (电竞房 card-*): these are containers, not content partitions, and are
    excluded from adjacent-pair boundary testing.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from phase2_bundle_loader import load_phase2_facts

ROOT: Path
MANIFEST_DIR: Path
METRIC_DIR: Path


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
    c = el.get("内容简述") or el.get("content") or ""
    return re.sub(r"^原文[:：]\s*", "", c).strip()


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

HUE_FAMILIES = [
    ("red", 0, 12), ("orange", 12, 40), ("yellow", 40, 68),
    ("yellow-green", 68, 88), ("green", 88, 150), ("cyan", 150, 195),
    ("blue", 195, 250), ("purple", 250, 290), ("magenta", 290, 335),
    ("red", 335, 361),
]


def hue_family(hue_deg: float) -> str:
    for name, lo, hi in HUE_FAMILIES:
        if lo <= hue_deg < hi:
            return name
    return "red"


def measure_colors(bgr: np.ndarray, card_box, photo_mask: np.ndarray, ui_mask: np.ndarray) -> dict:
    """eval-3: 36-colour HSV binning over UI pixels only.

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
        ratio = cnt / max(chroma_count, 1)
        fams.append({"family": name, "pixels": cnt, "ratioOfChroma": round(ratio, 4),
                     "kept": ratio >= 0.01})
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


def ink_rows(bgr: np.ndarray, box) -> tuple[int, int] | None:
    """First/last ink row (absolute y) inside a box, or None when empty."""
    h_img, w_img = bgr.shape[:2]
    x0, y0, x1, y1 = clamp_box(box, w_img, h_img)
    patch = bgr[y0:y1, x0:x1]
    if patch.size == 0:
        return None
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    ink, _ = ink_mask(gray)
    rows = np.where(ink.any(axis=1))[0]
    if not rows.size:
        return None
    return int(y0 + rows[0]), int(y0 + rows[-1])


def ink_cols(bgr: np.ndarray, box) -> tuple[int, int] | None:
    """First/last ink column (absolute x) inside a box, or None when empty."""
    h_img, w_img = bgr.shape[:2]
    x0, y0, x1, y1 = clamp_box(box, w_img, h_img)
    patch = bgr[y0:y1, x0:x1]
    if patch.size == 0:
        return None
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    ink, _ = ink_mask(gray)
    cols = np.where(ink.any(axis=0))[0]
    if not cols.size:
        return None
    return int(x0 + cols[0]), int(x0 + cols[-1])


def pair_relation(a: list, b: list) -> str:
    """vertical | horizontal | nested, from measured region geometry."""
    ax0, ay0, aw, ah = [int(v) for v in a]
    bx0, by0, bw, bh = [int(v) for v in b]
    ax1, ay1, bx1, by1 = ax0 + aw, ay0 + ah, bx0 + bw, by0 + bh
    xo = overlap(ax0, ax1, bx0, bx1)
    yo = overlap(ay0, ay1, by0, by1)
    a_in_b = ax0 >= bx0 - 2 and ay0 >= by0 - 2 and ax1 <= bx1 + 2 and ay1 <= by1 + 2
    b_in_a = bx0 >= ax0 - 2 and by0 >= ay0 - 2 and bx1 <= ax1 + 2 and by1 <= ay1 + 2
    if a_in_b or b_in_a:
        return "nested"
    if xo >= 0.5 * min(aw, bw) and yo < 0.5 * min(ah, bh):
        return "vertical"
    if yo >= 0.5 * min(ah, bh) and xo < 0.5 * min(aw, bw):
        return "horizontal"
    return "vertical" if yo <= xo else "horizontal"


def region_content_extent(bgr: np.ndarray, region: dict, axis: str):
    """Ink extent of a region's ELEMENTS along one axis.

    Phase2 region rectangles are loose bounding boxes that often overlap
    (生日蛋糕 C1: 标签区 ends y=1765 while 下挂区 starts y=1740), even though the
    rendered content does not. Measuring the union of the member elements'
    ink extents gives the true content band and therefore the true separation.
    """
    fn = ink_rows if axis == "y" else ink_cols
    lo, hi = None, None
    for el in region.get("elements", []):
        box = ebox(el)
        if not box:
            continue
        ext = fn(bgr, box)
        if not ext:
            continue
        lo = ext[0] if lo is None else min(lo, ext[0])
        hi = ext[1] if hi is None else max(hi, ext[1])
    if lo is None:
        return fn(bgr, region["coord"])
    return lo, hi


def boundary_test(bgr: np.ndarray, ra: dict, rb: dict, inner_gaps: list,
                  relation: str) -> dict:
    """eval-6: physical / spatial / visual boundary between two regions.

    Separation is measured between the two regions' CONTENT ink extents (union
    of member elements), not their declared rectangles, because phase2 region
    boxes overlap while the rendered content does not. The three tests are
    OR-ed per SKILL: any one clear boundary means the pair is fine.
    """
    h_img, w_img = bgr.shape[:2]
    a, b = ra["coord"], rb["coord"]

    if relation == "horizontal":
        (lo_r, hi_r) = (ra, rb) if a[0] <= b[0] else (rb, ra)
        e_lo = region_content_extent(bgr, lo_r, "x")
        e_hi = region_content_extent(bgr, hi_r, "x")
        gap = int(e_hi[0] - e_lo[1]) if (e_lo and e_hi) else int(
            hi_r["coord"][0] - (lo_r["coord"][0] + lo_r["coord"][2]))
        y_lo = max(int(a[1]), int(b[1]))
        y_hi = min(int(a[1] + a[3]), int(b[1] + b[3]))
        bx0 = max(0, e_lo[1] if e_lo else 0)
        bx1 = min(w_img, e_hi[0] if e_hi else 0)
        band = bgr[max(0, y_lo):min(h_img, y_hi), bx0:bx1] if bx1 > bx0 else None
        axis = "x"
    else:
        (lo_r, hi_r) = (ra, rb) if a[1] <= b[1] else (rb, ra)
        e_lo = region_content_extent(bgr, lo_r, "y")
        e_hi = region_content_extent(bgr, hi_r, "y")
        gap = int(e_hi[0] - e_lo[1]) if (e_lo and e_hi) else int(
            hi_r["coord"][1] - (lo_r["coord"][1] + lo_r["coord"][3]))
        x_lo = max(int(a[0]), int(b[0]))
        x_hi = min(int(a[0] + a[2]), int(b[0] + b[2]))
        by0 = max(0, e_lo[1] if e_lo else 0)
        by1 = min(h_img, e_hi[0] if e_hi else 0)
        band = bgr[by0:by1, max(0, x_lo):min(w_img, x_hi)] if by1 > by0 else None
        axis = "y"

    # physical: a drawn divider / rule inside the separating band
    physical = False
    if band is not None and band.size:
        g = cv2.cvtColor(band, cv2.COLOR_BGR2GRAY).astype(np.float32)
        prof = g.mean(axis=1) if axis == "y" else g.mean(axis=0)
        if prof.size >= 2:
            physical = bool(prof.min() < float(np.median(prof)) - 10)

    # spatial: outer gap clearly exceeds typical inner element gap (内紧外松)
    median_inner = float(np.median(inner_gaps)) if inner_gaps else 0.0
    spatial = bool(gap >= median_inner * 1.5) if median_inner > 0 else bool(gap >= 16)

    # visual: either a different fill or a stable foreground/typographic
    # hierarchy (for example black merchant text followed by gray fulfillment).
    pa = region_profile(bgr, a)
    pb = region_profile(bgr, b)
    background_delta = sum(abs(x - y) for x, y in zip(pa["bgRGB"], pb["bgRGB"]))
    foreground_delta = sum(abs(x - y) for x, y in zip(pa["inkRGB"], pb["inkRGB"]))
    background_visual = background_delta > 24
    typographic_visual = foreground_delta >= 60
    visual = bool(background_visual or typographic_visual)

    return {
        "relation": relation,
        "gapPx": gap,
        "gapBasis": "inkExtent" if (e_lo and e_hi) else "declaredBox",
        "medianInnerGapPx": round(median_inner, 1),
        "physical": physical,
        "spatial": spatial,
        "visual": visual,
        "backgroundVisual": background_visual,
        "typographicVisual": typographic_visual,
        "backgroundDelta": int(background_delta),
        "foregroundDelta": int(foreground_delta),
        "clear": bool(physical or spatial or visual),
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
    tag_styles: dict[str, list[str]] = defaultdict(list)
    excluded_tags: list[dict] = []
    region_scan: dict[str, dict] = defaultdict(lambda: {"included": [], "excluded": []})
    for e in elems:
        if e.get("isExcluded"):
            continue
        if not (etype(e) == "标签" or classify(e) == "tag"):
            continue
        st = measure_tag_style(bgr, ebox(e))
        rn = e.get("_region") or "-"
        visual = e.get("visual") if isinstance(e.get("visual"), dict) else {}
        if visual.get("visualStatus") != "confirmed":
            excluded_tags.append({"id": e.get("id"), "reason": "Phase2 原子类型或边界未确认，不进入 Phase3 测量"})
            region_scan[rn]["excluded"].append(f"{e.get('id')}(未确认)")
            continue
        # The formal style is measured by Phase3 from current pixels.  A
        # Phase2 styleKey may be retained for traceability but never controls
        # inclusion, deduplication or the count.
        phase3_style_key = st["pixelStyle"]
        if st["chromatic"]:
            tag_styles[phase3_style_key].append(e.get("id"))
            region_scan[rn]["included"].append(f"{e.get('id')}({phase3_style_key})")
        else:
            excluded_tags.append({"id": e.get("id"), "pixelStyle": st["pixelStyle"],
                                  "reason": "中性色纯文字标签，无彩色底/描边/图形辅助",
                                  "chromaRatio": st["chromaRatio"]})
            region_scan[rn]["excluded"].append(f"{e.get('id')}(中性色)")

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

    # ---------- eval-6: adjacent region boundaries (skip wrapper containers)
    real_regions = []
    for r in regions:
        if not r.get("coord"):
            continue
        if len(r.get("elements", [])) == 0:
            continue          # full-card wrapper, not a content partition
        real_regions.append(r)

    # Baseline for "内紧外松": vertical gaps between successive element ROWS
    # inside a region, measured on ink extents so it is comparable with the
    # outer gaps computed in boundary_test().
    inner_gaps: list[int] = []
    for r in real_regions:
        els = [e for e in r.get("elements", []) if ebox(e)]
        rows: list[tuple[int, int]] = []
        for e in sorted(els, key=lambda e: ebox(e)[1]):
            ext = ink_rows(bgr, ebox(e))
            if not ext:
                continue
            if rows and ext[0] <= rows[-1][1]:      # same visual row: merge
                rows[-1] = (rows[-1][0], max(rows[-1][1], ext[1]))
            else:
                rows.append(ext)
        for (_, prev_end), (next_start, _) in zip(rows, rows[1:]):
            g = next_start - prev_end
            if g > 0:
                inner_gaps.append(int(g))

    # order regions by real content position, not by loose declared boxes
    def order_key(r: dict):
        ry = region_content_extent(bgr, r, "y")
        rx = region_content_extent(bgr, r, "x")
        return (ry[0] if ry else r["coord"][1], rx[0] if rx else r["coord"][0])

    ordered = sorted(real_regions, key=order_key)
    boundaries = []
    for a, b in zip(ordered, ordered[1:]):
        rel = pair_relation(a["coord"], b["coord"])
        res = boundary_test(bgr, a, b, inner_gaps, rel)
        res["pair"] = f"{a.get('name')}→{b.get('name')}"
        boundaries.append(res)

    # ---------- eval-2: layout signature
    img_els = [e for e in elems if etype(e) == "图片"]
    head = None
    for e in img_els:
        b = ebox(e)
        if head is None or (b[1], b[0]) < (head[1], head[0]):
            head = b
    text_els = [e for e in active if etype(e) != "图片"]
    text_xs = [ebox(e)[0] for e in text_els]
    text_ys = [ebox(e)[1] for e in text_els]
    image_pos = "none"
    if head and text_xs and text_ys:
        hx_c = head[0] + head[2] / 2
        tx_min = min(text_xs)
        if head[0] + head[2] <= tx_min + 8:
            image_pos = "left"
        elif head[0] >= max(ebox(e)[0] + ebox(e)[2] for e in text_els) - 8:
            image_pos = "right"
        elif head[1] + head[3] <= min(text_ys) + 8:
            image_pos = "top"
        else:
            image_pos = "overlap"
    layout = {
        "cardType": card.get("卡片类型"),
        "imagePosition": image_pos,
        "regionOrder": [r.get("name") for r in ordered],
        "textLeftEdge": int(min(text_xs)) if text_xs else None,
        "textLeftEdgeSpreadPx": int(max(text_xs) - min(text_xs)) if text_xs else 0,
        "headImageBox": head,
    }

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
        "tagStyleCount": len(tag_styles),
        "excludedTags": excluded_tags,
        "regionScan": {k: v for k, v in region_scan.items()},
        "icons": icons,
        "weightBlocks": blocks,
        "boundaries": boundaries,
        "wrapperRegions": [r.get("name") for r in regions
                           if r.get("coord") and not r.get("elements")],
        "layout": layout,
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
        "manifestTotal": manifest_total,
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
    args = ap.parse_args()
    if bool(args.normalized_input) != bool(args.evidence_input):
        ap.error("--normalized-input and --evidence-input must be provided together")
    if args.manifest_input and args.normalized_input:
        ap.error("--manifest-input cannot be combined with --normalized-input")
    if args.manifest_input and len(args.scenes) != 1:
        ap.error("--manifest-input currently accepts exactly one scene")
    if args.normalized_input and len(args.scenes) != 1:
        ap.error("direct golden bundle mode currently accepts exactly one scene")
    configure_paths(args.project_dir)
    METRIC_DIR.mkdir(parents=True, exist_ok=True)
    for scene in args.scenes:
        data = run_scene(scene, args.suffix, args.normalized_input, args.evidence_input, args.manifest_input)
        out = METRIC_DIR / f"metrics_{scene}_{args.skill}.json"
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{scene}: components={data['componentCount']} "
              f"manifestTotal={data['manifestTotal']} -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
