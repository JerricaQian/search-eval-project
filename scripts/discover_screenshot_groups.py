#!/usr/bin/env python3
"""Discover reusable search screenshots without changing any files.

Expected filenames are ``<query>_<tab>_<screen>.png``; a preserved external
copy may additionally end in ``_副本`` or ``_副本N``.  Parsing from the
right keeps search terms containing underscores usable.  The JSON output is
intended for the Screenshot Agent and can be safely shown to a user before an
evaluation run is created.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from screenshot_naming import parse_screenshot_name


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def inspect_image(path: Path, min_bytes: int) -> str:
    if path.stat().st_size < min_bytes:
        return f"file_too_small(<{min_bytes}_bytes)"
    try:
        with Image.open(path) as image:
            image.verify()
    except (OSError, ValueError) as exc:
        return f"unreadable_image:{exc.__class__.__name__}"
    return ""


def parse_name(path: Path) -> tuple[str, str, str, str] | None:
    """Return query/tab/screen plus a distinct copy instance.

    A copy suffix belongs to screenshot identity, not to the query.  It must
    therefore be discoverable while remaining in its own group instead of
    being silently merged into an unsuffixed screenshot of the same screen.
    """
    parsed = parse_screenshot_name(path)
    if parsed is None:
        return None
    return parsed.query, parsed.tab, parsed.screen, parsed.instance


def discover(directory: Path, min_bytes: int = 5001) -> dict[str, Any]:
    grouped: dict[tuple[str, str], dict[str, list[dict[str, str]]]] = defaultdict(lambda: defaultdict(list))
    invalid: list[dict[str, str]] = []
    unparseable: list[str] = []

    if not directory.exists():
        return {"screenshotDir": str(directory), "groups": [], "invalidFiles": [], "unparseableFiles": [], "error": "directory_not_found"}

    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        parsed = parse_name(path)
        if parsed is None:
            unparseable.append(str(path.resolve()))
            continue
        issue = inspect_image(path, min_bytes)
        if issue:
            invalid.append({"path": str(path.resolve()), "reason": issue})
            continue
        query, tab, screen, instance = parsed
        grouped[(query, instance)][tab].append({"screen": screen, "path": str(path.resolve())})

    groups = []
    for query, instance in sorted(grouped):
        tabs = []
        files: list[str] = []
        for tab in sorted(grouped[(query, instance)]):
            entries = sorted(grouped[(query, instance)][tab], key=lambda item: (int(item["screen"]), item["path"]))
            tabs.append({"tab": tab, "screens": [item["screen"] for item in entries], "files": [item["path"] for item in entries]})
            files.extend(item["path"] for item in entries)
        groups.append({"query": query, "instance": instance, "tabs": tabs, "files": files, "count": len(files)})

    return {
        "screenshotDir": str(directory.resolve()),
        "groups": groups,
        "invalidFiles": invalid,
        "unparseableFiles": unparseable,
        "error": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover valid reusable search screenshots.")
    parser.add_argument("--screenshot-dir", required=True, type=Path)
    parser.add_argument("--min-bytes", type=int, default=5001)
    args = parser.parse_args()
    print(json.dumps(discover(args.screenshot_dir, args.min_bytes), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
