#!/usr/bin/env python3
"""Compile every golden and require all Phase3 fact dependency gates."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from compile_golden_phase3_manifest import canonical_json_sha256, compile_phase3, normalize_golden


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "phase2-card-annotation" / "golden-sample-results"
VALIDATOR = ROOT / "scripts" / "validate_element_manifest.py"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(SCRIPTS))
from phase2_bundle_loader import load_phase2_facts
from extract_phase3_comparability import derive_comparability
from extract_phase3_relation_candidates import derive_relation_candidates


def audit() -> dict:
    files = sorted(RESULTS.rglob("*.elements.json"))
    failures: list[dict] = []
    source_bytes = normalized_bytes = evidence_bytes = in_memory_phase3_bytes = 0
    cards = canonical_elements = page_elements = phase3_elements = direct_compile_files = phase3_comparisons = phase3_relation_pairs = 0
    with tempfile.TemporaryDirectory(prefix="golden-phase3-") as temp_dir:
        temp = Path(temp_dir)
        for index, path in enumerate(files):
            payload = json.loads(path.read_text(encoding="utf-8"))
            try:
                evidence_name = f"{index}.evidence.json"
                normalized, evidence = normalize_golden(payload, path.resolve(), evidence_name=evidence_name)
                manifest = compile_phase3(normalized)
            except Exception as exc:
                failures.append({"golden": str(path.relative_to(ROOT)), "stage": "compile", "errors": [str(exc)]})
                continue
            if normalized["provenance"]["evidenceCanonicalSha256"] != canonical_json_sha256(evidence):
                failures.append({"golden": str(path.relative_to(ROOT)), "stage": "evidence", "errors": ["evidence hash mismatch"]})
            if set(normalized["elementsById"]) != set(evidence["elementsById"]):
                failures.append({"golden": str(path.relative_to(ROOT)), "stage": "evidence", "errors": ["card element ID index mismatch"]})
            normalized_path = temp / f"{index}.normalized.json"
            evidence_path = temp / evidence_name
            normalized_path.write_text(json.dumps(normalized, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
            evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
            try:
                direct_manifest = load_phase2_facts(normalized_path=normalized_path, evidence_path=evidence_path)
            except Exception as exc:
                failures.append({"golden": str(path.relative_to(ROOT)), "stage": "direct_bundle", "errors": [str(exc)]})
                continue
            if direct_manifest != manifest:
                failures.append({"golden": str(path.relative_to(ROOT)), "stage": "direct_bundle", "errors": ["in-memory view differs from migration view"]})
                continue
            direct_compile_files += 1
            manifest_text = json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n"
            command = [
                "python3", str(VALIDATOR),
                "--normalized-input", str(normalized_path),
                "--evidence-input", str(evidence_path),
                "--require-hierarchy-facts", "--require-alignment-facts",
                "--require-alignment-anchors",
            ]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            result = json.loads(completed.stdout)
            if completed.returncode:
                failures.append({
                    "golden": str(path.relative_to(ROOT)),
                    "stage": "validate",
                    "errors": result.get("errors", []),
                })
            try:
                phase3_comparisons += len(derive_comparability(manifest)["comparisons"])
                relation_candidates = derive_relation_candidates(manifest)
                phase3_relation_pairs += sum(
                    len(card["candidatePairs"])
                    for key in ("authenticityCandidates", "redundancyCandidates")
                    for card in relation_candidates[key]
                )
            except Exception as exc:
                failures.append({"golden": str(path.relative_to(ROOT)), "stage": "phase3_derivation", "errors": [str(exc)]})
            source_bytes += path.stat().st_size
            normalized_bytes += len(json.dumps(normalized, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            evidence_bytes += len(json.dumps(evidence, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            in_memory_phase3_bytes += len(manifest_text.encode("utf-8"))
            cards += len(normalized["cards"])
            canonical_elements += len(normalized["elementsById"])
            page_elements += len(normalized.get("pageElementsById", {}))
            phase3_elements += int(result.get("total", 0))
    return {
        "valid": not failures and len(files) == 34,
        "goldenFiles": len(files),
        "cards": cards,
        "canonicalCardElements": canonical_elements,
        "canonicalPageElements": page_elements,
        "phase3Elements": phase3_elements,
        "phase3DerivedComparisons": phase3_comparisons,
        "phase3DerivedRelationPairs": phase3_relation_pairs,
        "directCompileFiles": direct_compile_files,
        "bytes": {
            "prettyLegacy": source_bytes,
            "compactNormalized": normalized_bytes,
            "compactEvidence": evidence_bytes,
            "inMemoryPhase3View": in_memory_phase3_bytes,
        },
        "failures": failures,
    }


def main() -> int:
    result = audit()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
