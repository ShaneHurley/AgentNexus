"""Source registry — writes only via ledger projection."""

from __future__ import annotations

from typing import Any

from research_forge.ledger.reconstruct import reconstruct_run_state
from research_forge.registries.normalize import canonical_key


class SourceRegistry:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._state = reconstruct_run_state(events)
        self._sources: dict[str, dict[str, Any]] = dict(self._state.get("sources", {}))
        self._aliases: dict[str, str] = {}
        for sid, src in self._sources.items():
            for ident in src.get("identifiers", []):
                key = canonical_key(ident["type"], ident["value"])
                self._aliases[key] = sid

    @classmethod
    def from_events(cls, events: list[dict[str, Any]]) -> SourceRegistry:
        return cls(events)

    def find_canonical(self, identifier_type: str, value: str) -> str | None:
        return self._aliases.get(canonical_key(identifier_type, value))

    def get(self, source_id: str) -> dict[str, Any] | None:
        return self._sources.get(source_id)

    def query_by_hash(self, content_hash: str) -> list[str]:
        return [
            sid for sid, s in self._sources.items() if s.get("content_hash") == content_hash
        ]

    def dedupe_candidates(self, a: dict[str, Any], b: dict[str, Any]) -> str:
        for ident_a in a.get("identifiers", []):
            key = canonical_key(ident_a["type"], ident_a["value"])
            if key in self._aliases:
                return "duplicate"
        title_a = (a.get("title") or "").lower()
        title_b = (b.get("title") or "").lower()
        if title_a and title_a == title_b:
            return "uncertain"
        return "distinct"

    def independent_roots(self, source_ids: list[str]) -> set[str]:
        roots: set[str] = set()
        for sid in source_ids:
            src = self._sources.get(sid, {})
            parents = src.get("provenance_parent_ids") or []
            roots.add(parents[0] if parents else sid)
        return roots
