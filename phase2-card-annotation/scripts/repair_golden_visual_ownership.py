#!/usr/bin/env python3
"""Remove legacy cross-region copies while preserving the canonical owner."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from golden_visual_identity import canonical_owner, duplicate_visual_atoms


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "phase2-card-annotation" / "golden-sample-results"


def result_cards(payload: dict[str, Any]):
    for component in payload["pageStructure"]["components"]:
        if component.get("componentType") != "results_list":
            continue
        for card in component.get("components", []):
            if card.get("componentType") in {"result_card", "heterogeneous_card"}:
                yield card


def remove_at_path(regions: dict[str, Any], path: tuple[Any, ...]) -> None:
    parent: Any = regions
    for segment in path[:-1]:
        parent = parent[segment]
    del parent[path[-1]]


def repair(path: Path, *, write: bool) -> tuple[int, list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    removed = 0
    unresolved: list[str] = []
    for card in result_cards(payload):
        regions = card.get("regions", {})
        duplicates = duplicate_visual_atoms(regions)
        removals: list[tuple[Any, ...]] = []
        for duplicate in duplicates:
            keeper = canonical_owner(duplicate["owners"])
            if keeper is None:
                owners = ",".join(owner["region"] for owner in duplicate["owners"])
                unresolved.append(
                    f"card{card.get('listPosition')}:{duplicate['normalizedText']}:{owners}"
                )
                continue
            removals.extend(
                owner["path"] for owner in duplicate["owners"] if owner is not keeper
            )
        # Delete list members from right to left so indexes remain stable.
        for element_path in sorted(removals, key=lambda item: tuple(str(x) for x in item), reverse=True):
            remove_at_path(regions, element_path)
            removed += 1
    if write and removed:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return removed, unresolved


def main() -> int:
    files = sorted(RESULTS.rglob("*.elements.json"))
    total = 0
    unresolved: list[str] = []
    changed_files = 0
    for path in files:
        removed, current_unresolved = repair(path, write=True)
        total += removed
        changed_files += int(removed > 0)
        unresolved.extend(f"{path.name}:{item}" for item in current_unresolved)
    print(json.dumps({
        "files": len(files),
        "changedFiles": changed_files,
        "removedDuplicateOwners": total,
        "unresolved": unresolved,
    }, ensure_ascii=False))
    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
