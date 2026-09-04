#!/usr/bin/env python3
"""Publish one validated Phase2 attempt to the task's immutable final paths."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"not_object:{path}")
    return payload


def copy_once(source: Path, destination: Path) -> None:
    if destination.exists():
        raise ValueError(f"refuse_to_overwrite:{destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-audit", required=True, type=Path)
    parser.add_argument("--recognition-audit", required=True, type=Path)
    parser.add_argument("--output-manifest", required=True, type=Path)
    parser.add_argument("--output-audit", required=True, type=Path)
    parser.add_argument("--output-recognition-audit", required=True, type=Path)
    args = parser.parse_args()

    screenshot = args.screenshot.resolve()
    manifest = load(args.manifest)
    manifest_audit = load(args.manifest_audit)
    recognition_audit = load(args.recognition_audit)
    if Path(str(manifest.get("screenshot", ""))).resolve() != screenshot:
        raise ValueError("manifest_screenshot_mismatch")
    if manifest.get("recognition", {}).get("phase3Ready") is not True or manifest.get("recognition", {}).get("wholePageGate") is not True:
        raise ValueError("manifest_not_phase3_ready")
    if manifest_audit.get("valid") is not True or recognition_audit.get("valid") is not True:
        raise ValueError("attempt_audit_not_valid")

    publications = (
        (args.manifest, args.output_manifest),
        (args.manifest_audit, args.output_audit),
        (args.recognition_audit, args.output_recognition_audit),
    )
    existing = [str(destination) for _, destination in publications if destination.exists()]
    if existing:
        raise ValueError(f"refuse_to_overwrite:{','.join(existing)}")
    for source, destination in publications:
        copy_once(source, destination)
    print(json.dumps({
        "ok": True,
        "screenshot": str(screenshot),
        "manifest": str(args.output_manifest.resolve()),
        "audit": str(args.output_audit.resolve()),
        "recognitionAudit": str(args.output_recognition_audit.resolve()),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
