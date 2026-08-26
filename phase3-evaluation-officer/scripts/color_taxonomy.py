"""Shared colour taxonomy for Phase3 screenshot evaluation.

Only this module defines the seven-colour hue boundary.  Each dimension may
use a different measurement scope and threshold, but must not redefine the
seven-colour mapping.
"""
from __future__ import annotations

from collections import OrderedDict


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
