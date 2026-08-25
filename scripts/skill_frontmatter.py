"""Small dependency-free readers for eval Skill frontmatter."""
from __future__ import annotations

import json
import re
from pathlib import Path


FRONTMATTER_PATTERN = re.compile(r"\A---\n(.*?)\n---(?:\n|\Z)", re.DOTALL)
INLINE_WEIGHT_PATTERN = re.compile(r"^weight:\s*(\{[^\n]+\})\s*$")
BLOCK_WEIGHT_ITEM_PATTERN = re.compile(
    r"^\s+['\"]?([^:'\"]+)['\"]?\s*:\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*$"
)


def parse_weight(text: str) -> dict[str, float] | None:
    """Return an eval rating map from JSON-inline or YAML-block frontmatter.

    Eval Skills deliberately use a small frontmatter schema.  Supporting both
    common YAML spellings prevents a valid future Skill from becoming invisible
    to scoring solely because its mapping spans multiple lines.
    """
    frontmatter = FRONTMATTER_PATTERN.match(text)
    if not frontmatter:
        return None
    lines = frontmatter.group(1).splitlines()
    for index, line in enumerate(lines):
        inline = INLINE_WEIGHT_PATTERN.match(line)
        if inline:
            try:
                raw = json.loads(inline.group(1))
            except json.JSONDecodeError:
                return None
            return _normalise_weight(raw)
        if line.strip() != "weight:":
            continue
        raw: dict[str, float] = {}
        for child in lines[index + 1:]:
            if not child.strip():
                continue
            if not child[0].isspace():
                break
            item = BLOCK_WEIGHT_ITEM_PATTERN.match(child)
            if not item:
                return None
            raw[item.group(1).strip()] = float(item.group(2))
        return raw or None
    return None


def load_weight(path: Path) -> dict[str, float] | None:
    try:
        return parse_weight(path.read_text(encoding="utf-8"))
    except OSError:
        return None


def _normalise_weight(raw: object) -> dict[str, float] | None:
    if not isinstance(raw, dict) or not raw:
        return None
    try:
        return {str(rating): float(score) for rating, score in raw.items()}
    except (TypeError, ValueError):
        return None
