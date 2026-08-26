"""Single parser for project screenshot filenames.

Canonical identity is ``<query>_<tab>_<screen>``.  External files are never
renamed on intake, so recognised copy suffixes are carried as a distinct
``instance`` instead of becoming part of the query or screen number.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


COPY_SUFFIX = re.compile(
    r"_(?P<label>副本|copy)(?:(?:[（(](?P<bracket>\d+)[）)])|[ _-]?(?P<number>\d+))?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ScreenshotName:
    query: str
    tab: str
    screen: str
    instance: str

    @property
    def canonical_stem(self) -> str:
        return f"{self.query}_{self.tab}_{self.screen}"


def parse_screenshot_name(value: str | Path) -> ScreenshotName | None:
    """Parse canonical screenshot identity and recognised preserved copies.

    Accepted examples: ``漂流_全部_1.png``、``漂流_全部_1_副本.png``、
    ``漂流_全部_1_副本2.png``、``漂流_全部_1_copy(2).png``.  Query text may
    itself contain underscores because the three identity segments are read
    from the right after an optional copy suffix is removed.
    """
    stem = Path(value).stem
    instance = "original"
    suffix = COPY_SUFFIX.search(stem)
    if suffix:
        label = suffix.group("label")
        number = suffix.group("bracket") or suffix.group("number") or ""
        instance = f"副本{number}" if label.lower() in {"副本", "copy"} else f"副本{number}"
        stem = stem[:suffix.start()]
    parts = [item.strip() for item in stem.rsplit("_", 2)]
    if len(parts) != 3 or not all(parts) or not parts[2].isdigit():
        return None
    return ScreenshotName(query=parts[0], tab=parts[1], screen=parts[2], instance=instance)
