#!/usr/bin/env python3
"""Build a read-only Phase3 fact pack from a publication-ready Atomic v3 manifest."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from phase2_bundle_loader import load_phase2_facts


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    payload: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != "phase2.atomic-manifest.v3":
        raise SystemExit("atomic_v3_manifest_required")
    # Loader is the integrity authority: schema, publication state and source hash.
    facts = load_phase2_facts(manifest_path=manifest_path)
    cards = facts["cards"]
    # `coord` is retained as a compatibility alias for validators and reports;
    # `坐标` remains the canonical Phase2 fact field.
    active = [
        {**element, "coord": list(element["坐标"])}
        for card in cards for region in card["regions"] for element in region["elements"]
    ]
    element_by_id = {element["id"]: element for element in active}
    card_structures = []
    alignment_groups: dict[str, list[str]] = {}
    for card in cards:
        signature = card["structure"]["layoutSignature"]
        key = f'{card["cardTypeCode"]}|{card.get("variant", "")}|{signature}'
        alignment_groups.setdefault(key, []).append(card["cardId"])
        anchors = []
        for region in card["regions"]:
            for element in region["elements"]:
                x, y, w, h = element["坐标"]
                anchors.append({"elementId": element["id"], "region": region["name"], "left": x, "top": y, "right": x + w, "bottom": y + h})
        card_structures.append({"cardId": card["cardId"], "cardType": card["cardTypeCode"], "bounds": card["coord"], "regions": card["structure"]["regions"], "layoutSignature": signature, "anchors": anchors})
    screenshot = Path(facts["screenshot"])
    pack = {
        "contractVersion": "phase3.atomic-fact-pack.v1",
        "valid": True,
        "query": facts["query"],
        "total": len(active),
        "activeElements": active,
        "source": {"manifest": str(manifest_path), "manifestSha256": sha256(manifest_path), "screenshot": str(screenshot), "screenshotSha256": sha256(screenshot)},
        "integrity": {"atomicSchemaValid": True, "publicationReady": True, "sourceHashValid": True},
        # This compatibility-shaped audit is consumed by validate_eval_results only; it is not a Phase2 manifest.
        "manifestAudit": {"valid": True, "query": facts["query"], "total": len(active), "activeElements": active},
        "inventory": {"sourceManifestTotal": len(active), "pageModules": facts["pageFacts"]["modules"], "cardIds": [card["cardId"] for card in cards], "atomicElementIds": list(element_by_id)},
        "structureFacts": {"cards": card_structures},
        "hierarchyFacts": {"candidateElementIds": list(element_by_id), "measurementRequired": True},
        "alignmentFacts": {"comparisonGroups": [{"comparisonGroupKey": key, "cardIds": ids} for key, ids in alignment_groups.items()]},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"valid": True, "output": str(args.output), "total": len(active)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
