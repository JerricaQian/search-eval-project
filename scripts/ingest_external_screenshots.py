#!/usr/bin/env python3
"""Copy external search screenshots into the project without changing sources.

This is deliberately a light transport step: source images are copied directly
to the project-level ``screenshots/`` directory with their original filenames.
Filename validation and grouping are performed afterwards by
``discover_screenshot_groups.py``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
PROTOCOL = "EXTERNAL_SCREENSHOT_COPY_V1"
COPY_SUFFIX = re.compile(r"_(?:副本(?:[（(]\d+[）)]|\d+)?|copy(?:[ _-]?\d+)?)$", re.IGNORECASE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source] if source.suffix.lower() in IMAGE_SUFFIXES else []
    if source.is_dir():
        return sorted(path for path in source.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
    return []


def destination_for(source: Path, screenshot_dir: Path, source_hash: str) -> tuple[Path, bool]:
    """Return a non-overwriting destination and whether its name was changed."""
    primary = screenshot_dir / source.name
    if not primary.exists() or sha256(primary) == source_hash:
        return primary, False

    base_stem = source.stem
    previous = ""
    while base_stem != previous:
        previous = base_stem
        base_stem = COPY_SUFFIX.sub("", base_stem)
    sequence = 2
    while True:
        candidate = screenshot_dir / f"{base_stem}_副本{sequence}{source.suffix}"
        if not candidate.exists() or sha256(candidate) == source_hash:
            return candidate, True
        sequence += 1


def ingest(
    source_dir: Path,
    screenshot_dir: Path,
    *,
    min_bytes: int = 5001,
    batch_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Copy one image or all images in a directory, preserving their names.

    ``min_bytes`` and ``batch_id`` remain accepted for CLI compatibility but
    are intentionally not used by this copy-only step. Discovery owns image
    validation, parseability, and grouping.
    """
    source_dir = source_dir.resolve()
    screenshot_dir = screenshot_dir.resolve()
    result: dict[str, Any] = {
        "protocol": PROTOCOL,
        "sourcePath": str(source_dir),
        "screenshotDir": str(screenshot_dir),
        "dryRun": dry_run,
        "copied": [],
        "alreadyPresent": [],
        "renamed": [],
        "error": "",
    }
    if not source_dir.exists():
        result["error"] = "source_path_not_found"
        return result
    if source_dir.is_file() and source_dir.suffix.lower() not in IMAGE_SUFFIXES:
        result["error"] = "source_file_not_supported"
        return result

    for source in source_files(source_dir):
        source_hash = sha256(source)
        destination, was_renamed = destination_for(source, screenshot_dir, source_hash)
        record = {
            "sourcePath": str(source),
            "destinationPath": str(destination),
            "sha256": source_hash,
        }
        if destination.exists():
            result["alreadyPresent"].append(record)
            continue
        if dry_run:
            result["copied"].append({**record, "status": "would_copy", "renamed": was_renamed})
            if was_renamed:
                result["renamed"].append(record)
            continue

        screenshot_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if sha256(destination) != source_hash:
            raise RuntimeError(f"copy_hash_mismatch:{destination}")
        result["copied"].append({**record, "status": "copied", "renamed": was_renamed})
        if was_renamed:
            result["renamed"].append(record)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy external screenshots into the project screenshots directory.")
    parser.add_argument("--source-dir", required=True, type=Path, help="External screenshot directory or a single screenshot file.")
    parser.add_argument("--screenshot-dir", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = ingest(args.source_dir, args.screenshot_dir, dry_run=args.dry_run)
    except RuntimeError as exc:
        result = {"protocol": PROTOCOL, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result.get("error") else 2


if __name__ == "__main__":
    raise SystemExit(main())
