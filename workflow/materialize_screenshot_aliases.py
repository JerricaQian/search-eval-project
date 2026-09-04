#!/usr/bin/env python3
"""Create canonical screenshot aliases after evaluation without changing originals."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def safe_part(value: str) -> str:
    return value.strip().replace("/", "_").replace("\\", "_").replace(":", "_")


def available_path(directory: Path, stem: str, suffix: str, source_hash: str) -> tuple[Path, str]:
    candidate = directory / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate, "created"
    if candidate.is_file() and digest(candidate) == source_hash:
        return candidate, "already_present"
    index = 2
    while True:
        candidate = directory / f"{stem}_副本{index}{suffix}"
        if not candidate.exists():
            return candidate, "created_with_copy_suffix"
        if candidate.is_file() and digest(candidate) == source_hash:
            return candidate, "already_present"
        index += 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity-map", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path, help="Completed Phase2-4 receipt required before aliases are created.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--mapping-output", required=True, type=Path)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict) or receipt.get("protocol") != "MEITUAN_EVAL_TASK" or receipt.get("status") != "completed":
        raise ValueError("completed_evaluation_receipt_required")
    payload = json.loads(args.identity_map.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("contract") != "screenshot.identity-map":
        raise ValueError("identity_map_contract_invalid")
    receipt_query = str(receipt.get("query", "")).strip()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for entry in payload.get("entries", []):
        source = Path(str(entry.get("sourcePath", ""))).resolve()
        expected_hash = str(entry.get("sha256", "")).lower()
        if not source.is_file() or digest(source) != expected_hash:
            raise ValueError(f"identity_source_missing_or_changed:{source}")
        query, tab, screen = (safe_part(str(entry.get(key, ""))) for key in ("query", "tab", "screen"))
        if receipt_query and query != safe_part(receipt_query):
            raise ValueError(f"identity_query_receipt_mismatch:{query}")
        if not query or not tab or not screen:
            records.append({"sourcePath": str(source), "status": "skipped", "reason": "query_tab_or_screen_unresolved"})
            continue
        target, status = available_path(args.output_dir, f"{query}_{tab}_{screen}", source.suffix, expected_hash)
        if not target.exists():
            shutil.copy2(source, target)
        records.append({"sourcePath": str(source), "aliasPath": str(target.resolve()), "sha256": expected_hash, "status": status})
    result = {
        "contract": "screenshot.canonical-alias-map",
        "identityMap": str(args.identity_map.resolve()),
        "receipt": str(args.receipt.resolve()),
        "records": records,
        "sourceFilesPreserved": True,
    }
    args.mapping_output.parent.mkdir(parents=True, exist_ok=True)
    if args.mapping_output.exists():
        raise ValueError(f"refuse_to_overwrite:{args.mapping_output}")
    args.mapping_output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
