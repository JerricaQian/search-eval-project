"""Shared colour taxonomy for Phase3 screenshot evaluation.

Only this module defines the seven-colour hue boundary.  Each dimension may
use a different measurement scope and threshold, but must not redefine the
seven-colour mapping.
"""
from __future__ import annotations

from collections import OrderedDict


# A low-saturation tint is not the only way a rendered neutral appears in a
# screenshot.  Near-black and low absolute RGB-chroma pixels can carry a noisy
# hue after anti-aliasing/compression while still reading as black or grey.
# All three colour evals share this perceptual-neutral gate.
ACHROMATIC_S_THRESHOLD = 15.0
ACHROMATIC_V_THRESHOLD = 20.0
ACHROMATIC_RGB_CHROMA_THRESHOLD = 20.0


# Hue degrees in [0, 360).  Red deliberately crosses the 0/360 boundary.
HUE7_BINS: tuple[tuple[str, float, float], ...] = (
    ("red", 0.0, 15.0),
    ("orange", 15.0, 45.0),
    ("yellow", 45.0, 68.0),
    ("green", 68.0, 150.0),       # yellow-green merges into green
    ("cyan", 150.0, 195.0),
    ("blue", 195.0, 250.0),
    ("purple", 250.0, 330.0),     # magenta / purple-red merge into purple
    ("red", 330.0, 360.0),
)

HUE7_ZH = {
    "red": "红", "orange": "橙", "yellow": "黄", "green": "绿",
    "cyan": "青", "blue": "蓝", "purple": "紫",
}


def hue7_family(hue_deg: float) -> str:
    """Return the canonical seven-colour family for a hue in degrees."""
    hue = float(hue_deg) % 360.0
    for family, lower, upper in HUE7_BINS:
        if lower <= hue < upper:
            return family
    return "red"  # defensive only; modulo guarantees a matching interval


def hue7_ranges() -> list[tuple[str, list[tuple[float, float]]]]:
    """Return grouped ranges for vectorised callers such as page analysis."""
    grouped: OrderedDict[str, list[tuple[float, float]]] = OrderedDict()
    for family, lower, upper in HUE7_BINS:
        grouped.setdefault(family, []).append((lower, upper))
    return list(grouped.items())


def is_chromatic_hsv(saturation_pct: float, value_pct: float) -> bool:
    """Return whether HSV values represent a perceptibly chromatic colour."""
    saturation = float(saturation_pct)
    value = float(value_pct)
    rgb_chroma = 255.0 * saturation / 100.0 * value / 100.0
    return (
        saturation >= ACHROMATIC_S_THRESHOLD
        and value >= ACHROMATIC_V_THRESHOLD
        and rgb_chroma >= ACHROMATIC_RGB_CHROMA_THRESHOLD
    )


def is_chromatic_rgb(red: int, green: int, blue: int) -> bool:
    """RGB companion to :func:`is_chromatic_hsv` for JSON style colours."""
    maximum = max(red, green, blue)
    minimum = min(red, green, blue)
    if maximum == 0:
        return False
    saturation = (maximum - minimum) / maximum * 100.0
    value = maximum / 255.0 * 100.0
    return is_chromatic_hsv(saturation, value)
