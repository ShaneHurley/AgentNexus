"""Scholarly search adapter — mock read-only (RF-W6-B-01..03)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from research_forge.registries.normalize import normalize_arxiv, normalize_doi
from research_forge.wave6.sdk.protocol import PROTOCOL_VERSION


class MockScholarlySearchAdapter:
    adapter_id = "mock_scholarly"
    protocol_version = PROTOCOL_VERSION

    _CORPUS: list[dict[str, Any]] = [
        {
            "doi": "10.1000/preprint.1",
            "arxiv": "2301.00001v1",
            "title": "Example Study Alpha",
            "date": "2023-01-15",
            "type": "preprint",
            "status": "preprint",
        },
        {
            "doi": "10.1000/published.1",
            "arxiv": "2301.00001",
            "title": "Example Study Alpha",
            "date": "2023-06-01",
            "type": "article",
            "status": "published",
            "corrects": "10.1000/preprint.1",
        },
        {
            "doi": "10.1000/other.2",
            "title": "Unrelated Paper",
            "date": "2022-01-01",
            "type": "article",
            "status": "published",
        },
    ]

    def supported_operations(self) -> frozenset[str]:
        return frozenset({"search", "read", "metadata"})

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        page_size = int(kwargs.get("page_size", 10))
        cursor = int(kwargs.get("cursor") or 0)
        filters = kwargs.get("filters") or {}
        date_bounds = kwargs.get("date_bounds")

        hits = [r for r in self._CORPUS if query.lower() in r["title"].lower()]
        if filters.get("type"):
            hits = [r for r in hits if r["type"] == filters["type"]]
        if date_bounds:
            lo, hi = date_bounds
            if lo:
                hits = [r for r in hits if r["date"] >= lo]
            if hi:
                hits = [r for r in hits if r["date"] <= hi]

        if cursor >= len(hits):
            return {"results": [], "next_cursor": None, "rate_limit_remaining": 100}

        page = hits[cursor : cursor + page_size]
        results = [self._map_result(r, rank=cursor + i) for i, r in enumerate(page)]
        next_c = cursor + page_size if cursor + page_size < len(hits) else None
        return {"results": results, "next_cursor": next_c, "rate_limit_remaining": 100}

    def read(self, locator: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        doi = locator.get("doi")
        for r in self._CORPUS:
            if doi and normalize_doi(doi) == normalize_doi(r["doi"]):
                return self._read_record(r)
        return {"error": "not_found", "access_level": "none"}

    def _map_result(self, raw: dict[str, Any], *, rank: int) -> dict[str, Any]:
        ids: list[dict[str, str]] = [{"type": "doi", "value": raw["doi"]}]
        if raw.get("arxiv"):
            ids.append({"type": "arxiv", "value": raw["arxiv"]})
        canonical_doi = normalize_doi(raw["doi"])
        canonical_arxiv = normalize_arxiv(raw["arxiv"]) if raw.get("arxiv") else None
        return {
            "result_id": f"sch-{rank}",
            "canonical_title": raw["title"],
            "source_type": "scholarly",
            "publication_status": raw["status"],
            "date": raw["date"],
            "identifiers": ids,
            "canonical_doi": canonical_doi,
            "canonical_arxiv": canonical_arxiv,
            "alias_group": canonical_arxiv or canonical_doi,
            "metadata_provenance": "provider_mapped",
            "guessed_fields": [],
        }

    def _read_record(self, raw: dict[str, Any]) -> dict[str, Any]:
        body = f"Title: {raw['title']}\nStatus: {raw['status']}\n"
        h = hashlib.sha256(body.encode()).hexdigest()
        return {
            "access_level": "abstract",
            "access_disclosure": "mock_fulltext_unavailable",
            "locator": {"kind": "doi", "value": raw["doi"]},
            "content_hash": h,
            "publication_status": raw["status"],
            "correction_of": raw.get("corrects"),
        }

    def health_probe(self) -> dict[str, Any]:
        return {"available": True, "auth_ok": True, "rate_limit_ok": True, "issues": []}
