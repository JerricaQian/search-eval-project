#!/usr/bin/env python3
"""Extract auditable, non-semantic facts from a search-result screenshot.

This is deliberately a *candidate* generator. It does not decide whether a
row is a title, price, tag, or whether a card is good/bad; those are domain
rules evaluated after extraction. It combines pixel detectors with local OCR
and retains independent-layout consensus for deterministic gating. OCR
uncertainty triggers bounded local reprocessing, never vision-model reading.

The output is stable JSON and is safe to retain as a Phase2 process artifact.
It is not itself the Phase2 element manifest.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

from detect_photo_region import detect_photos


VERSION = "phase2.cv-facts.v1"

# The server models are expensive to initialise.  Keep one instance alive for
# a single annotation process, then run it only on semantic field crops.
_PADDLE_OCR: Any | None = None


@dataclass
class Box:
    x: int
    y: int
    w: int
    h: int

    def as_list(self) -> list[int]:
        return [self.x, self.y, self.w, self.h]


def _clamp_box(x: int, y: int, w: int, h: int, width: int, height: int) -> Box | None:
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(width, x + w), min(height, y + h)
    if x1 <= x0 or y1 <= y0:
        return None
    return Box(x0, y0, x1 - x0, y1 - y0)


def _content_rows(rgb: np.ndarray) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The reusable scan_rows heuristic, returned as JSON rather than stdout."""
    height, width, _ = rgb.shape
    flattened = rgb.astype(np.int16).reshape(height, -1)
    whitespace = (flattened.std(axis=1) < 6) & (flattened.mean(axis=1) > 240)
    bands: list[dict[str, Any]] = []
    cursor = 0
    while cursor < height:
        if not whitespace[cursor]:
            cursor += 1
            continue
        end = cursor + 1
        while end < height and whitespace[end]:
            end += 1
        if end - cursor >= 4:
            bands.append({"y0": int(cursor), "y1": int(end), "height": int(end - cursor)})
        cursor = end

    rows: list[dict[str, Any]] = []
    start = 0
    for band in bands:
        if band["y0"] - start >= 4:
            rows.append({"y0": start, "y1": band["y0"], "height": band["y0"] - start})
        start = band["y1"]
    if height - start >= 4:
        rows.append({"y0": start, "y1": height, "height": height - start})
    return bands, rows


def _ocr_with_paddle(image_path: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Run PaddleOCR when installed, supporting its public v2/v3 result shapes.

    Keeping this optional lets the rest of the CV pipeline run before the OCR
    dependency is installed.  A missing backend is an explicit uncertainty,
    never interpreted as missing page text.
    """
    # Paddle model initialisation can download/cache large assets. Enable it
    # explicitly in production after the local model cache is provisioned;
    # until then the deterministic Tesseract path remains available.
    if os.environ.get("PHASE2_ENABLE_PADDLEOCR") != "1":
        return [], "paddleocr_not_enabled"
    if importlib.util.find_spec("paddleocr") is None:
        return [], "paddleocr_not_installed"
    try:
        # Keep model/cache files inside this project rather than relying on a
        # user-home directory, which may be sandboxed in local-agent runs.
        cache_dir = Path(__file__).resolve().parents[2] / ".artifacts" / "paddlex-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(cache_dir))
        os.environ.setdefault("MPLCONFIGDIR", str(cache_dir / "matplotlib"))
        # PaddleOCR defaults to HuggingFace. BOS is the official alternative
        # and is generally the more reachable model source on mainland CN networks.
        os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")
        global _PADDLE_OCR
        if _PADDLE_OCR is None:
            from paddleocr import PaddleOCR  # type: ignore[import-not-found]
            # These two model directories are intentionally local runtime
            # assets. Orientation/unwarping is unnecessary for upright mobile
            # screenshots and would trigger unrelated model downloads.
            model_root = Path(__file__).resolve().parents[1] / "models" / "paddleocr"
            det_model_dir = model_root / "PP-OCRv5_server_det_infer"
            rec_model_dir = model_root / "PP-OCRv5_server_rec_infer"
            if not (det_model_dir / "inference.yml").is_file() or not (rec_model_dir / "inference.yml").is_file():
                return [], "paddleocr_local_models_not_found"
            _PADDLE_OCR = PaddleOCR(
                text_detection_model_name="PP-OCRv5_server_det",
                text_detection_model_dir=str(det_model_dir),
                text_recognition_model_name="PP-OCRv5_server_rec",
                text_recognition_model_dir=str(rec_model_dir),
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        raw = list(_PADDLE_OCR.predict(str(image_path))) if hasattr(_PADDLE_OCR, "predict") else _PADDLE_OCR.ocr(str(image_path), cls=True)
    except Exception as exc:  # backend errors are represented in the artifact
        return [], f"paddleocr_error:{type(exc).__name__}:{exc}"[:240]

    entries: list[dict[str, Any]] = []
    # PaddleOCR v2: [[[quad], (text, confidence)], ...]
    if isinstance(raw, list) and raw and isinstance(raw[0], list):
        candidates = raw[0] if len(raw) == 1 else raw
        for item in candidates:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            quad, result = item[0], item[1]
            if not isinstance(quad, (list, tuple)) or not isinstance(result, (list, tuple)) or len(result) < 2:
                continue
            try:
                xs = [float(point[0]) for point in quad]
                ys = [float(point[1]) for point in quad]
                text, confidence = str(result[0]), float(result[1])
            except (TypeError, ValueError, IndexError):
                continue
            entries.append({
                "text": text,
                "coord": [int(min(xs)), int(min(ys)), int(max(xs) - min(xs)), int(max(ys) - min(ys))],
                "ocrConfidence": round(confidence, 4),
            })
    # PaddleOCR v3 yields dict-like OCRResult instances.  Keep each detected
    # text box separate; later domain rules decide which field owns it.
    if isinstance(raw, list):
        for result in raw:
            if not hasattr(result, "get"):
                continue
            try:
                texts = list(result.get("rec_texts", []))
                scores = list(result.get("rec_scores", []))
                boxes = list(result.get("rec_boxes", []))
            except (TypeError, ValueError):
                continue
            for text, confidence, box in zip(texts, scores, boxes):
                try:
                    x0, y0, x1, y1 = [float(value) for value in box]
                    entries.append({
                        "text": str(text),
                        "coord": [int(x0), int(y0), int(x1 - x0), int(y1 - y0)],
                        "ocrConfidence": round(float(confidence), 4),
                    })
                except (TypeError, ValueError):
                    continue
    if not entries:
        return [], "paddleocr_result_shape_not_supported"
    return entries, None


def ocr_region(image_path: Path, coord: list[int], tesseract_psm: int | None = None) -> tuple[list[dict[str, Any]], str, str | None]:
    """OCR one bounded semantic region and return page-relative boxes.

    PaddleOCR is deliberately never sent an entire long result page by this
    helper.  The caller must provide a region established by layout CV.
    """
    with Image.open(image_path) as source:
        width, height = source.size
        x, y, w, h = coord
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(width, x + w), min(height, y + h)
        if x1 <= x0 or y1 <= y0:
            return [], "unavailable", "invalid_region"
        crop = source.crop((x0, y0, x1, y1))
        # Upscaling improves tiny crops, but full-width card crops already have
        # 35-50 px glyphs.  Golden calibration may opt into scale=1 to avoid a
        # 4x pixel-cost penalty without changing the bounded source region.
        scale = max(1, min(2, int(os.environ.get("PHASE2_BOUNDED_OCR_SCALE", "2"))))
        if scale != 1:
            crop = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.LANCZOS)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png") as handle:
            crop.save(handle.name)
            entries, paddle_error = _ocr_with_paddle(Path(handle.name))
            error = paddle_error
            backend = "paddleocr"
            if paddle_error:
                entries, fallback_error = _run_tesseract(Path(handle.name), tesseract_psm) if tesseract_psm else _ocr_with_tesseract(Path(handle.name))
                backend = "tesseract" if not fallback_error else "unavailable"
                error = paddle_error if not fallback_error else f"{paddle_error};{fallback_error}"
            if (backend == "unavailable" or not entries) and tesseract_psm:
                # Low-contrast gray metadata often disappears in a tight crop.
                # Retry the same bounded pixels with deterministic grayscale
                # autocontrast; this is not a new semantic or model source.
                enhanced = ImageOps.autocontrast(crop.convert("L"))
                enhanced = enhanced.point(lambda value: 0 if value < 220 else 255)
                with tempfile.NamedTemporaryFile(suffix=".png") as enhanced_handle:
                    enhanced.save(enhanced_handle.name)
                    entries, threshold_error = _run_tesseract(Path(enhanced_handle.name), tesseract_psm)
                if entries and not threshold_error:
                    backend = "tesseract_threshold"
                    error = paddle_error
                else:
                    backend = "unavailable"
                    error = ";".join(value for value in (paddle_error, threshold_error) if value)
    # Undo the bounded-crop scale and translate coordinates to the source page.
    for item in entries:
        cx, cy, cw, ch = item["coord"]
        item["coord"] = [x0 + round(cx / scale), y0 + round(cy / scale), round(cw / scale), round(ch / scale)]
    return entries, backend, error


def _run_tesseract(image_path: Path, psm: int) -> tuple[list[dict[str, Any]], str | None]:
    binary = shutil.which("tesseract")
    if not binary:
        return [], "tesseract_not_installed"
    try:
        completed = subprocess.run(
            [binary, str(image_path), "stdout", "-l", "chi_sim+eng", "--psm", str(psm), "tsv"],
            check=False, capture_output=True, text=True, timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], f"tesseract_error:{type(exc).__name__}:{exc}"[:240]
    if completed.returncode != 0:
        return [], f"tesseract_error:{completed.stderr.strip()}"[:240]
    lines = completed.stdout.splitlines()
    if not lines:
        return [], "tesseract_empty_tsv"
    words: list[dict[str, Any]] = []
    for row in lines[1:]:
        values = row.split("\t", 11)
        if len(values) != 12:
            continue
        try:
            level = int(values[0])
            line_key = tuple(int(value) for value in values[1:5])
            left, top, width, height, confidence = int(values[6]), int(values[7]), int(values[8]), int(values[9]), float(values[10])
        except ValueError:
            continue
        text = values[11].strip()
        if level != 5 or not text or confidence < 0:
            continue
        words.append({
            "text": text, "coord": [left, top, width, height],
            "lineKey": line_key,
        })
    # Tesseract TSV is word-level. Chinese mobile UI frequently becomes many
    # one/two-glyph words, which previously inflated the rejection ratio and
    # destroyed titles. Merge only spatially adjacent words on the same OCR
    # line; large gaps still preserve independent price/tag fields.
    entries: list[dict[str, Any]] = []
    for line_key in dict.fromkeys(item["lineKey"] for item in words):
        line_words = sorted((item for item in words if item["lineKey"] == line_key), key=lambda item: item["coord"][0])
        groups: list[list[dict[str, Any]]] = []
        for word in line_words:
            if not groups:
                groups.append([word])
                continue
            previous = groups[-1][-1]
            px, py, pw, ph = previous["coord"]
            x, y, w, h = word["coord"]
            gap = x - (px + pw)
            if gap <= max(10, round(max(ph, h) * 1.25)):
                groups[-1].append(word)
            else:
                groups.append([word])
        for group in groups:
            x0 = min(item["coord"][0] for item in group)
            y0 = min(item["coord"][1] for item in group)
            x1 = max(item["coord"][0] + item["coord"][2] for item in group)
            y1 = max(item["coord"][1] + item["coord"][3] for item in group)
            text_parts: list[str] = []
            for word in group:
                value = str(word["text"])
                separator = " " if text_parts and text_parts[-1][-1:].isascii() and text_parts[-1][-1:].isalnum() and value[:1].isascii() and value[:1].isalpha() else ""
                text_parts.append(separator + value)
            entries.append({"text": "".join(text_parts), "coord": [x0, y0, x1 - x0, y1 - y0]})
    return entries, None


def _run_tesseract_plain(image_path: Path, psm: int) -> tuple[list[dict[str, Any]], str | None]:
    """Read bounded lines without consuming or filtering by OCR confidence."""
    binary = shutil.which("tesseract")
    if not binary:
        return [], "tesseract_not_installed"
    try:
        completed = subprocess.run(
            [binary, str(image_path), "stdout", "-l", "chi_sim+eng", "--psm", str(psm)],
            check=False, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], f"tesseract_error:{type(exc).__name__}:{exc}"[:240]
    if completed.returncode != 0:
        return [], f"tesseract_error:{completed.stderr.strip()}"[:240]
    entries = [{"text": line.strip()} for line in completed.stdout.splitlines() if line.strip()]
    return (entries, None) if entries else ([], "tesseract_empty_text")


def _normal_ocr_text(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "", value).lower()


def _box_match(left: list[int], right: list[int]) -> float:
    lx, ly, lw, lh = left; rx, ry, rw, rh = right
    iw = max(0, min(lx + lw, rx + rw) - max(lx, rx))
    ih = max(0, min(ly + lh, ry + rh) - max(ly, ry))
    intersection = iw * ih
    union = lw * lh + rw * rh - intersection
    return intersection / union if union else 0.0


def _annotate_ocr_consensus(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> None:
    for item in primary:
        ranked = sorted(secondary, key=lambda other: _box_match(item["coord"], other["coord"]), reverse=True)
        match = ranked[0] if ranked and _box_match(item["coord"], ranked[0]["coord"]) >= 0.18 else None
        left = _normal_ocr_text(str(item.get("text", "")))
        right = _normal_ocr_text(str(match.get("text", ""))) if match else ""
        item["ocrConsensus"] = {"status": "confirmed" if left and left == right else "disagreed" if match else "unmatched",
                                "primaryText": item.get("text", ""), "secondaryText": match.get("text", "") if match else ""}


def _structured_text_quality(value: str) -> int:
    chinese = sum("\u4e00" <= char <= "\u9fff" for char in value)
    stripped = re.sub(r"(?:ml|kg|vol|cm|mm|km|SPA|KTV|Plus|Pro)", "", value, flags=re.I)
    latin = sum(char.isascii() and char.isalpha() for char in stripped)
    return chinese * 2 - latin


def _prefer_independent_structured_text(entries: list[dict[str, Any]]) -> int:
    """Select a clearly cleaner independent layout without language correction.

    Prices still require the same numeric anchor.  Natural-language rows may
    switch only when the alternate layout has substantially stronger Chinese
    script coherence, which recovers titles whose primary layout is mostly
    Latin-shaped OCR debris.
    """
    changed = 0
    for item in entries:
        consensus = item.get("ocrConsensus", {})
        if consensus.get("status") != "disagreed":
            continue
        primary = str(item.get("text", ""))
        secondary = str(consensus.get("secondaryText", ""))
        primary_price = re.search(r"[¥￥]\s*(\d+(?:\.\d+)?)", primary)
        secondary_price = re.search(r"[¥￥]\s*(\d+(?:\.\d+)?)", secondary)
        if primary_price or secondary_price:
            if not primary_price or not secondary_price:
                continue
            if _numeric_signature(primary_price.group(1)) != _numeric_signature(secondary_price.group(1)):
                continue
            if len(secondary) < len(primary) * 0.55 or _structured_text_quality(secondary) < _structured_text_quality(primary) + 2:
                continue
            acceptance = "same_price_numeric_signature_and_higher_script_coherence"
        else:
            secondary_chinese = sum("\u4e00" <= char <= "\u9fff" for char in secondary)
            if secondary_chinese < 4 or _structured_text_quality(secondary) < _structured_text_quality(primary) + 4:
                continue
            acceptance = "substantially_higher_chinese_script_coherence"
        item["text"] = secondary
        item["ocrRefinement"] = {
            "applied": True, "originalText": primary, "refinedText": secondary,
            "backend": "tesseract_independent_layout", "acceptance": acceptance,
            "originalConsensus": dict(consensus),
        }
        item["ocrConsensus"] = {
            "status": "confirmed", "primaryText": secondary, "secondaryText": primary,
            "method": "independent_layout_structured_field_selection",
        }
        changed += 1
    return changed


def _ocr_with_tesseract(image_path: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Chinese OCR with an independent layout-mode consensus signal."""
    primary, error = _run_tesseract(image_path, 6)
    if error:
        return primary, error
    # PSM 11 is not used as replacement text. It is an independent hook input
    # that helps detect plausible-looking but unstable PSM 6 strings.
    secondary, secondary_error = _run_tesseract(image_path, 11)
    if not secondary_error:
        _annotate_ocr_consensus(primary, secondary)
        _prefer_independent_structured_text(primary)
    else:
        for item in primary:
            item["ocrConsensus"] = {"status": "unavailable", "primaryText": item.get("text", ""), "secondaryText": ""}
    return primary, None


def _ocr(image_path: Path) -> tuple[list[dict[str, Any]], str, str | None]:
    # Whole-page PaddleOCR is too costly on long result screenshots. It is
    # reserved for `ocr_region`, after CV identifies a tight semantic crop.
    if os.environ.get("PHASE2_ENABLE_PADDLEOCR") == "1" and os.environ.get("PHASE2_ALLOW_FULL_PAGE_PADDLEOCR") != "1":
        return [], "deferred_region_ocr", None
    if os.environ.get("PHASE2_ALLOW_FULL_PAGE_PADDLEOCR") != "1":
        entries, error = _ocr_with_tesseract(image_path)
        return entries, "tesseract" if not error else "unavailable", error
    entries, error = _ocr_with_paddle(image_path)
    if not error:
        return entries, "paddleocr", None
    fallback_entries, fallback_error = _ocr_with_tesseract(image_path)
    if not fallback_error:
        return fallback_entries, "tesseract", None
    return [], "unavailable", f"{error};{fallback_error}"


def _near_row(box: Box, row: dict[str, Any]) -> bool:
    return box.y < row["y1"] and box.y + box.h > row["y0"]


def _color_role_from_rgb(value: np.ndarray) -> str:
    r, g, b = (int(channel) for channel in value)
    if r > g * 1.25 and r > b * 1.25:
        return "red" if g < r * 0.72 else "orange"
    if b > r * 1.18 and b > g * 1.05:
        return "blue"
    if g > r * 1.15 and g > b * 1.08:
        return "green"
    if max(r, g, b) - min(r, g, b) < 38:
        return "neutral"
    return "multicolor"


def _horizontal_foreground_segments(crop: np.ndarray, mask: np.ndarray) -> list[dict[str, Any]]:
    """Measure independent horizontal visual groups inside one OCR line.

    Small glyph gaps remain in one group. A UI-sized blank gap separates
    sibling tags even when OCR flattened them into one text candidate.
    """
    if crop.size == 0 or mask.size == 0:
        return []
    height = crop.shape[0]
    active = np.flatnonzero(mask.sum(axis=0) >= max(2, round(height * 0.08)))
    if len(active) == 0:
        return []
    max_glyph_gap = max(10, round(height * 0.22))
    groups: list[tuple[int, int]] = []
    start = previous = int(active[0])
    for column in active[1:]:
        column = int(column)
        if column - previous > max_glyph_gap:
            groups.append((start, previous + 1))
            start = column
        previous = column
    groups.append((start, previous + 1))
    minimum_width = max(8, round(height * 0.32))
    output = []
    for start, end in groups:
        if end - start < minimum_width:
            continue
        pixels = crop[:, start:end][mask[:, start:end]]
        if len(pixels) < 3:
            continue
        median = np.median(pixels, axis=0)
        output.append({"xOffset": start, "width": end - start, "medianRgb": [int(value) for value in median], "colorRole": _color_role_from_rgb(median)})
    return output


def _text_color_hint(rgb: np.ndarray, box: Box) -> dict[str, Any]:
    crop = rgb[box.y:box.y + box.h, box.x:box.x + box.w]
    if crop.size == 0:
        return {"colorRole": "unknown", "evidence": "empty_crop"}
    values = crop.reshape(-1, 3)
    surface_rgb = [int(value) for value in np.median(values, axis=0)]
    spread = values.max(axis=1) - values.min(axis=1)
    brightness = values.mean(axis=1)
    foreground_mask = ((brightness < 185) | ((spread > 45) & (brightness < 235))).reshape(crop.shape[:2])
    foreground = values[foreground_mask.reshape(-1)]
    if len(foreground) < max(3, len(values) // 120):
        return {"colorRole": "unknown", "surfaceMedianRgb": surface_rgb, "evidence": "insufficient_foreground_pixels"}
    median = np.median(foreground, axis=0)
    r, g, b = (int(value) for value in median)
    return {
        "colorRole": _color_role_from_rgb(median),
        "medianRgb": [r, g, b],
        "surfaceMedianRgb": surface_rgb,
        "horizontalForegroundSegments": _horizontal_foreground_segments(crop, foreground_mask),
        "evidence": "foreground_surface_and_horizontal_segment_pixels",
    }


def _hex_rgb(value: Any) -> str:
    if not isinstance(value, list) or len(value) != 3 or not all(isinstance(channel, int) and 0 <= channel <= 255 for channel in value):
        return ""
    return "#" + "".join(f"{channel:02X}" for channel in value)


def _text_size_bucket(height: int) -> str:
    """A geometry fact, not a claim about the design-system token."""
    if height <= 24:
        return "small"
    if height <= 44:
        return "medium"
    return "large"


def _direct_text_phase3_facts(text: str, box: Box, hint: dict[str, Any], accepted: bool) -> dict[str, Any]:
    """Emit Phase3-shaped CV facts before later card/semantic assignment."""
    color = hint.get("colorRole", "unknown")
    visible = "confirmed" if accepted else "uncertain"
    return {
        "render": {"visibleStatus": visible, "renderState": "normal" if accepted else "uncertain", "isPhoto": False, "isSystemUi": True},
        "textFacts": {"rawText": text, "textStatus": "complete" if accepted else "uncertain", "semanticRole": "other",
                      "emphasisLevel": "secondary", "fontSizeBucket": _text_size_bucket(box.h), "fontWeightBucket": "unknown", "textColorRole": color},
        "visual": {"entityKind": "text", "visualStatus": visible, "isColored": color not in {"neutral", "unknown"}, "isShaped": False,
                   "colorRole": color, "backgroundColor": "", "textColor": _hex_rgb(hint.get("medianRgb")), "borderColor": "",
                   "hasGraphicAssist": False, "graphicType": "无", "styleKey": f"text|{color}|other|无容器|无",
                   "colorEvidence": hint.get("evidence", "not_measured")},
    }


def _text_hygiene_reasons(text: str, box: Box, row_hits: int) -> list[str]:
    """Reject OCR debris deterministically; never escalate it to model reading."""
    compact = text.strip()
    meaningful = [char for char in compact if char.isalnum() or "\u4e00" <= char <= "\u9fff"]
    if not meaningful:
        return ["ocr_punctuation_only"]
    reasons: list[str] = []
    if box.h < 10 or box.w < 8:
        reasons.append("ocr_box_too_small")
    if len(meaningful) == 1 and not meaningful[0].isdigit():
        reasons.append("ocr_single_glyph_fragment")
    if row_hits != 1:
        reasons.append("text_box_row_alignment_ambiguous")
    return reasons


def _text_candidates(ocr: list[dict[str, Any]], rows: list[dict[str, Any]], rgb: np.ndarray, width: int, height: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(ocr, start=1):
        x, y, w, h = (int(value) for value in item["coord"])
        box = _clamp_box(x, y, w, h, width, height)
        if not box:
            continue
        overlaps = sum(1 for row in rows if _near_row(box, row))
        reasons = _text_hygiene_reasons(str(item["text"]), box, overlaps)
        hint = _text_color_hint(rgb, box)
        accepted = not reasons
        candidates.append({
            "id": f"T{index}", "kind": "text", "text": item["text"], "coord": box.as_list(),
            # Independent Tesseract layout modes are kept as gate evidence.
            # They never replace the primary OCR string or trigger model OCR.
            "ocrConsensus": item.get("ocrConsensus", {
                "status": "unavailable", "primaryText": item.get("text", ""), "secondaryText": "",
            }),
            "geometry": {"rowAlignment": "single_row" if overlaps == 1 else "ambiguous"},
            "visualHint": hint,
            # These direct CV facts use the Phase3 names. Later stages only
            # add ownership, region and semantic role; they must not replace
            # the colour/pixel evidence with a guess.
            "phase3Facts": _direct_text_phase3_facts(item["text"], box, hint, accepted),
            **({"ocrRefinement": item["ocrRefinement"]} if item.get("ocrRefinement") else {}),
            "route": "accepted" if accepted else "rejected", "rejectionReasons": reasons,
        })
    return candidates


def _numeric_signature(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


def _select_bounded_price_refinement(primary_text: str, entries: list[dict[str, Any]]) -> str:
    """Choose only a local OCR price whose digits are anchored in full-page OCR."""
    primary_digits = _numeric_signature(primary_text)
    matches: list[tuple[int, str]] = []
    for entry in entries:
        value = str(entry.get("text", "")).strip()
        match = re.search(r"[¥￥]\s*(\d+(?:[./]\d+)?)", value)
        if not match:
            continue
        digits = _numeric_signature(match.group(1))
        if len(digits) < 2:
            continue
        if digits in primary_digits or primary_digits in digits:
            context = 2 if re.search(r"到手价|神价|低价|特价|券后|月售|起|[-–]", value) else 0
            matches.append((len(digits) + context, value))
    return max(matches, default=(0, ""))[1]


def _bounded_price_refinements(rgb: np.ndarray, candidates: list[dict[str, Any]], maximum: int = 8) -> int:
    """Re-read a few likely price lines with a red/dark foreground mask.

    The local result replaces raw OCR only when it restores a real currency
    glyph and its numeric signature agrees with the original full-page OCR.
    No language correction or inferred value is introduced.
    """
    height, width, _ = rgb.shape
    selected = []
    for item in candidates:
        text = str(item.get("text", ""))
        x, y, w, h = item.get("coord", [0, 0, 0, 0])
        role = item.get("visualHint", {}).get("colorRole")
        contextual = bool(re.search(r"到手价|到手从|神价|低价|特价|券后|票价|价格|\d+(?:\.\d+)?\s*起|\d{2,4}\s*[-–]\s*\d{2,4}", text))
        obvious_non_price = bool(re.search(r"分钟|公里|\bkm\b|\d+(?:\.\d+)?万?条|起送|配送费|20\d{2}[-/.年]", text, re.I)) and not contextual
        if item.get("route") != "accepted" or role not in {"red", "orange"} or sum(char.isdigit() for char in text) < 2:
            continue
        if not contextual and not width * 0.18 <= x <= width * 0.88:
            continue
        if obvious_non_price or re.search(r"[¥￥]\s*\d", text):
            continue
        selected.append(item)
    refined = 0
    for item in selected[:maximum]:
        x, y, w, h = item["coord"]
        pad_x, pad_y = min(20, x), min(12, y)
        x0, y0 = x - pad_x, y - pad_y
        x1, y1 = min(width, x + w + 20), min(height, y + h + 12)
        crop = rgb[y0:y1, x0:x1]
        if crop.size == 0:
            continue
        red = (crop[:, :, 0] > crop[:, :, 1] * 1.12) & (crop[:, :, 0] > crop[:, :, 2] * 1.12) & (crop[:, :, 0] > 90)
        dark = crop.mean(axis=2) < 130
        mask = np.full(red.shape, 255, dtype=np.uint8)
        mask[red | dark] = 0
        image = Image.fromarray(mask).resize((mask.shape[1] * 4, mask.shape[0] * 4), Image.Resampling.NEAREST)
        with tempfile.NamedTemporaryFile(suffix=".png") as handle:
            image.save(handle.name)
            entries, error = _run_tesseract_plain(Path(handle.name), 11)
        if error:
            continue
        recovered = _select_bounded_price_refinement(str(item["text"]), entries)
        if not recovered:
            continue
        original = str(item["text"])
        original_consensus = item.get("ocrConsensus", {})
        item["text"] = recovered
        item["ocrConsensus"] = {
            "status": "confirmed", "primaryText": recovered, "secondaryText": original,
            "method": "bounded_price_mask_psm11_numeric_anchor",
        }
        item["ocrRefinement"] = {
            "applied": True, "originalText": original, "refinedText": recovered,
            "backend": "tesseract_psm11", "crop": [x0, y0, x1 - x0, y1 - y0],
            "acceptance": "currency_glyph_restored_and_numeric_signature_anchored",
            "originalConsensus": original_consensus,
        }
        item.get("phase3Facts", {}).get("textFacts", {})["rawText"] = recovered
        refined += 1
    return refined


def _photo_candidates(image_path: Path, rows: list[dict[str, Any]], width: int, height: int) -> list[dict[str, Any]]:
    photos, _ = detect_photos(str(image_path))
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(photos, start=1):
        box = _clamp_box(item["x"], item["y"], item["w"], item["h"], width, height)
        if not box:
            continue
        # Existing detector's rules are deliberately weak evidence.  A large or
        # colourful region and one stable content row is enough to propose a
        # photo, never enough to assign its semantic role.
        row_hits = sum(1 for row in rows if _near_row(box, row))
        detector_confidence = 0.86 if item["rule"] == "paired_grid_texture" else 0.82 if item["rule"] == "large" else 0.8 if item["rule"] == "low_hue_textured" else 0.72 if item["rule"] == "colorful" else 0.62
        geometry_confidence = 0.9 if row_hits <= 3 else 0.65
        confidence = min(detector_confidence, geometry_confidence)
        reasons = []
        if confidence < 0.75:
            reasons.append("photo_detector_weak_or_icon_like")
        if row_hits > 3:
            reasons.append("photo_spans_multiple_content_rows")
        accepted = not reasons
        candidates.append({
            "id": f"P{index}", "kind": "photo_candidate", "coord": box.as_list(),
            "detectorRule": item["rule"], "confidence": round(confidence, 4),
            "confidenceParts": {"detector": detector_confidence, "rowGeometry": geometry_confidence},
            "phase3Facts": {
                "render": {"visibleStatus": "confirmed" if accepted else "uncertain", "renderState": "normal" if accepted else "uncertain", "isPhoto": True, "isSystemUi": False},
                "visual": {"entityKind": "image", "visualStatus": "confirmed" if accepted else "uncertain", "isColored": False, "isShaped": False,
                           "colorRole": "unknown", "backgroundColor": "", "textColor": "", "borderColor": "", "hasGraphicAssist": False,
                           "graphicType": "无", "styleKey": "image|unknown|photo|无容器|无", "colorEvidence": "Phase3_pixel_measurement_required"},
            },
            "route": "accepted" if accepted else "rejected", "rejectionReasons": reasons,
        })
    return candidates


def extract(image_path: Path) -> dict[str, Any]:
    with Image.open(image_path) as image:
        rgb = np.asarray(image.convert("RGB"))
    height, width, _ = rgb.shape
    whitespace, rows = _content_rows(rgb)
    ocr, ocr_backend, backend_error = _ocr(image_path)
    independent_layout_refinements = sum(bool(item.get("ocrRefinement", {}).get("applied")) for item in ocr)
    text = _text_candidates(ocr, rows, rgb, width, height)
    bounded_price_refinements = _bounded_price_refinements(rgb, text)
    photos = _photo_candidates(image_path, rows, width, height)
    unresolved = [item["id"] for item in text + photos if item["route"] != "accepted"]
    missing_capabilities: list[str] = []
    if backend_error:
        # A missing OCR runtime means text has not been observed, not that the
        # screen contains no text.  Make the gap explicit for the orchestrator.
        missing_capabilities.append("local_chinese_ocr")
    return {
        "contractVersion": VERSION,
        "screenshot": str(image_path.resolve()),
        "viewport": {"width": width, "height": height},
        "backends": {"pixel": "opencv+numpy", "ocr": ocr_backend, "ocrStatus": backend_error or "ok", "independentLayoutRefinements": independent_layout_refinements, "boundedPriceRefinements": bounded_price_refinements},
        "whitespaceBands": whitespace,
        "contentRows": rows,
        "candidates": {"text": text, "photos": photos},
        "routing": {
            "policy": "cv_only_gated_v1", "unresolvedCandidateIds": unresolved,
            "missingCapabilities": missing_capabilities,
            "rule": "Rejected OCR/CV candidates are not sent to a model. They are evidence that the page-level recognition gate must reprocess or block this manifest; they cannot establish absence, defects, or excellence.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract CV/OCR facts from a search-result screenshot")
    parser.add_argument("image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"image not found: {args.image}")
    result = extract(args.image)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "unresolved": len(result["routing"]["unresolvedCandidateIds"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
