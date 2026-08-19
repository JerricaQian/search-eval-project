#!/usr/bin/env python3
"""Build 34 normalized/evidence golden pairs without touching legacy JSON."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from compile_golden_phase3_manifest import normalize_golden, validate_normalized_bundle, write_json


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "phase2-card-annotation" / "golden-sample-results"
DEFAULT_OUTPUT = ROOT / ".artifacts" / "phase3-golden-architecture" / "golden-34"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source_root: Path, output_root: Path, force: bool = False) -> dict:
    sources = sorted(source_root.rglob("*.elements.json"))
    if len(sources) != 34:
        raise ValueError(f"expected 34 legacy goldens, found {len(sources)}")
    source_hashes = {path: file_sha256(path) for path in sources}
    pairs: list[dict[str, str]] = []

    for source in sources:
        relative_parent = source.relative_to(source_root).parent
        basename = source.name.removesuffix(".elements.json")
        target_dir = output_root / relative_parent
        normalized_path = target_dir / f"{basename}.normalized.json"
        evidence_path = target_dir / f"{basename}.evidence.json"
        if not force and (normalized_path.exists() or evidence_path.exists()):
            raise FileExistsError(f"refusing to overwrite new bundle: {normalized_path}")

        payload = json.loads(source.read_text(encoding="utf-8"))
        normalized, evidence = normalize_golden(
            payload,
            source.resolve(),
            evidence_name=evidence_path.name,
        )
        errors = validate_normalized_bundle(normalized, evidence, evidence_path)
        # The evidence file does not exist until the pair is written; filename,
        # hashes and ID indexes are still validated here.
        errors = [error for error in errors if error != "evidence_sidecar_filename_mismatch"]
        if errors:
            raise ValueError(f"{source}: {','.join(errors)}")
        write_json(normalized_path, normalized, pretty=False)
        write_json(evidence_path, evidence, pretty=False)
        post_errors = validate_normalized_bundle(normalized, evidence, evidence_path)
        if post_errors:
            raise ValueError(f"{source}: {','.join(post_errors)}")
        pairs.append({
            "source": str(source.relative_to(ROOT)),
            "normalized": str(normalized_path.relative_to(ROOT)),
            "evidence": str(evidence_path.relative_to(ROOT)),
        })

    changed_sources = [str(path.relative_to(ROOT)) for path, digest in source_hashes.items() if file_sha256(path) != digest]
    return {
        "valid": not changed_sources,
        "images": len(pairs),
        "jsonFiles": len(pairs) * 2,
        "outputRoot": str(output_root.relative_to(ROOT)),
        "legacyFilesChanged": changed_sources,
        "pairs": pairs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build normalized/evidence pairs for all 34 golden screenshots")
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true", help="Replace only files under output-root")
    args = parser.parse_args()
    result = build(args.source_root.resolve(), args.output_root.resolve(), args.force)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
