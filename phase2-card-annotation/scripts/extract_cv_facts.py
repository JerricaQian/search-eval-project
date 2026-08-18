#!/usr/bin/env python3
"""Extract auditable, non-semantic facts from a search-result screenshot.

This is deliberately a *candidate* generator.  It does not decide whether a
row is a title, price, tag, or whether a card is good/bad; those are domain
rules evaluated after Phase2.  It combines the repository's existing pixel
detectors with optional local PaddleOCR and records confidence by source so a
caller can route only unresolved crops to a vision model.

The output is stable JSON and is safe to retain as a Phase2 process artifact.
It is not itself the Phase2 element manifest.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

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


def ocr_region(image_path: Path, coord: list[int]) -> tuple[list[dict[str, Any]], str, str | None]:
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
        # Upscaling improves dense, small mobile UI glyphs before detection.
        crop = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png") as handle:
            crop.save(handle.name)
            entries, error = _ocr_with_paddle(Path(handle.name))
            backend = "paddleocr"
            if error:
                entries, error = _ocr_with_tesseract(Path(handle.name))
                backend = "tesseract" if not error else "unavailable"
    # Undo the 2x scale and translate coordinates to the source page.
    for item in entries:
        cx, cy, cw, ch = item["coord"]
        item["coord"] = [x0 + round(cx / 2), y0 + round(cy / 2), round(cw / 2), round(ch / 2)]
    return entries, backend, error


def _ocr_with_tesseract(image_path: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Fallback local Chinese OCR using the system Tesseract installation."""
    binary = shutil.which("tesseract")
    if not binary:
        return [], "tesseract_not_installed"
    try:
        completed = subprocess.run(
            # Search-result screenshots are dense, horizontally aligned UI.
            # PSM 6 preserves Chinese phrases/lines far better than sparse-text
            # PSM 11, whose character fragments made card-level rules unusable.
            [binary, str(image_path), "stdout", "-l", "chi_sim+eng", "--psm", "6", "tsv"],
            check=False, capture_output=True, text=True, timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], f"tesseract_error:{type(exc).__name__}:{exc}"[:240]
    if completed.returncode != 0:
        return [], f"tesseract_error:{completed.stderr.strip()}"[:240]
    lines = completed.stdout.splitlines()
    if not lines:
        return [], "tesseract_empty_tsv"
    entries: list[dict[str, Any]] = []
    for row in lines[1:]:
        values = row.split("\t", 11)
        if len(values) != 12:
            continue
        try:
            level, left, top, width, height, confidence = int(values[0]), int(values[6]), int(values[7]), int(values[8]), int(values[9]), float(values[10])
        except ValueError:
            continue
        text = values[11].strip()
        if level != 5 or not text or confidence < 0:
            continue
        entries.append({
            "text": text, "coord": [left, top, width, height],
            "ocrConfidence": round(confidence / 100.0, 4),
        })
    return entries, None


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


def _text_color_hint(rgb: np.ndarray, box: Box) -> dict[str, Any]:
    crop = rgb[box.y:box.y + box.h, box.x:box.x + box.w]
    if crop.size == 0:
        return {"colorRole": "unknown", "evidence": "empty_crop"}
    values = crop.reshape(-1, 3)
    spread = values.max(axis=1) - values.min(axis=1)
    brightness = values.mean(axis=1)
    foreground = values[(brightness < 185) | ((spread > 45) & (brightness < 235))]
    if len(foreground) < max(3, len(values) // 120):
        return {"colorRole": "unknown", "evidence": "insufficient_foreground_pixels"}
    r, g, b = (int(value) for value in np.median(foreground, axis=0))
    if r > g * 1.25 and r > b * 1.25:
        role = "red" if g < r * 0.72 else "orange"
    elif b > r * 1.18 and b > g * 1.05:
        role = "blue"
    elif g > r * 1.15 and g > b * 1.08:
        role = "green"
    elif max(r, g, b) - min(r, g, b) < 38:
        role = "neutral"
    else:
        role = "multicolor"
    return {"colorRole": role, "medianRgb": [r, g, b], "evidence": "foreground_pixel_median"}


def _text_candidates(ocr: list[dict[str, Any]], rows: list[dict[str, Any]], rgb: np.ndarray, width: int, height: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(ocr, start=1):
        x, y, w, h = (int(value) for value in item["coord"])
        box = _clamp_box(x, y, w, h, width, height)
        if not box:
            continue
        overlaps = sum(1 for row in rows if _near_row(box, row))
        ocr_confidence = float(item["ocrConfidence"])
        geometry_confidence = 1.0 if overlaps == 1 else 0.65 if overlaps else 0.4
        confidence = min(ocr_confidence, geometry_confidence)
        reasons: list[str] = []
        if ocr_confidence < 0.92:
            reasons.append("ocr_below_initial_key_text_threshold")
        if overlaps != 1:
            reasons.append("text_box_row_alignment_ambiguous")
        candidates.append({
            "id": f"T{index}", "kind": "text", "text": item["text"], "coord": box.as_list(),
            "confidence": round(confidence, 4), "confidenceParts": {
                "ocr": round(ocr_confidence, 4), "rowGeometry": geometry_confidence,
            },
            "visualHint": _text_color_hint(rgb, box),
            "route": "local_vision" if reasons else "accepted",
            "routeReasons": reasons,
        })
    return candidates


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
        detector_confidence = 0.82 if item["rule"] == "large" else 0.72 if item["rule"] == "colorful" else 0.62
        geometry_confidence = 0.9 if row_hits <= 3 else 0.65
        confidence = min(detector_confidence, geometry_confidence)
        reasons = []
        if confidence < 0.75:
            reasons.append("photo_detector_weak_or_icon_like")
        if row_hits > 3:
            reasons.append("photo_spans_multiple_content_rows")
        candidates.append({
            "id": f"P{index}", "kind": "photo_candidate", "coord": box.as_list(),
            "detectorRule": item["rule"], "confidence": round(confidence, 4),
            "confidenceParts": {"detector": detector_confidence, "rowGeometry": geometry_confidence},
            "route": "local_vision" if reasons else "accepted", "routeReasons": reasons,
        })
    return candidates


def extract(image_path: Path) -> dict[str, Any]:
    with Image.open(image_path) as image:
        rgb = np.asarray(image.convert("RGB"))
    height, width, _ = rgb.shape
    whitespace, rows = _content_rows(rgb)
    ocr, ocr_backend, backend_error = _ocr(image_path)
    text = _text_candidates(ocr, rows, rgb, width, height)
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
        "backends": {"pixel": "opencv+numpy", "ocr": ocr_backend, "ocrStatus": backend_error or "ok"},
        "whitespaceBands": whitespace,
        "contentRows": rows,
        "candidates": {"text": text, "photos": photos},
        "routing": {
            "policy": "conservative-v1", "unresolvedCandidateIds": unresolved,
            "missingCapabilities": missing_capabilities,
            "rule": "Only candidate-local crops may be sent to a vision model; unresolved facts cannot establish absence, defects, or excellence.",
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
