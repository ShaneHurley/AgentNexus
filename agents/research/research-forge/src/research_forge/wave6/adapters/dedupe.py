"""Cross-adapter source deduplication (RF-W6-B-09)."""

from __future__ import annotations

from typing import Any

from research_forge.registries.normalize import canonical_key


def merge_retrieval_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Map same document from several providers to one canonical source."""
    if not records:
        return {"canonical_source_id": None, "retrievals": []}

    canonical_id: str | None = None
    alias_keys: set[str] = set()
    retrievals: list[dict[str, Any]] = []

    for rec in records:
        ids = rec.get("identifiers") or []
        keys = [canonical_key(i["type"], i["value"]) for i in ids if i.get("type") and i.get("value")]
        alias_keys.update(keys)
        group = rec.get("alias_group")
        if group:
            alias_keys.add(str(group))
        retrievals.append(
            {
                "provider": rec.get("provider") or rec.get("adapter_id"),
                "retrieved_at": rec.get("retrieved_at"),
                "locator": rec.get("locator"),
            }
        )
        if canonical_id is None and rec.get("canonical_source_id"):
            canonical_id = rec["canonical_source_id"]

    if canonical_id is None:
        canonical_id = f"src-merged-{hash(tuple(sorted(alias_keys))) & 0xFFFFFFFF:08x}"

    return {
        "canonical_source_id": canonical_id,
        "identifier_keys": sorted(alias_keys),
        "retrievals": retrievals,
        "independence_count": 1,
    }
