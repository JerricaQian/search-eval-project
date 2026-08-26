"""Shared, versioned result-card identifiers for Phase2 and the evaluation officer."""
from __future__ import annotations

import json
from pathlib import Path


REGISTRY_PATH = Path(__file__).resolve().parents[2] / "card-type-registry.v1.json"


def load_registry() -> dict:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    entries = payload.get("resultCardTypes")
    if not isinstance(entries, list) or not entries:
        raise ValueError("card type registry has no resultCardTypes")
    ids = [item.get("id") for item in entries if isinstance(item, dict)]
    if len(ids) != len(set(ids)) or any(not isinstance(value, str) or not value for value in ids):
        raise ValueError("card type registry ids must be unique non-empty strings")
    return payload


def display_names() -> dict[str, str]:
    return {item["id"]: item["displayName"] for item in load_registry()["resultCardTypes"]}


def known_result_types() -> set[str]:
    return {item["id"] for item in load_registry()["resultCardTypes"] if item.get("formal") and item.get("resultList", True)}


def validate_phase2_taxonomy(taxonomy: dict) -> None:
    """Fail fast if the recognition taxonomy drifts from the shared registry."""
    taxonomy_ids = {item.get("id") for item in taxonomy.get("cardTypes", []) if isinstance(item, dict)}
    registry_ids = {item["id"] for item in load_registry()["resultCardTypes"]}
    if taxonomy_ids != registry_ids:
        missing, extra = sorted(registry_ids - taxonomy_ids), sorted(taxonomy_ids - registry_ids)
        raise ValueError(f"Phase2 taxonomy/registry mismatch: missing={missing}; extra={extra}")
