"""Mock search adapter — conformance scenarios (RF-W1-D-02)."""

from __future__ import annotations

from typing import Any

from research_forge.adapters.search.protocol import normalize_page


class MockSearchAdapterV1:
    adapter_id = "mock_search_v1"

    def __init__(self, fixtures: list[dict[str, Any]] | None = None) -> None:
        self._fixtures = fixtures or [
            {
                "result_id": "res-alpha",
                "title": "Alpha Paper",
                "url": "https://example.org/a",
                "snippet": "Alpha claims 42% improvement (n=100).",
                "source_type": "paper",
                "date": "2024-01-01",
                "authors": ["A. Author"],
            },
            {
                "result_id": "res-beta",
                "title": "Beta Paper",
                "url": "https://example.org/b",
                "snippet": "Beta contradicts alpha at 38%.",
                "source_type": "paper",
                "date": "2024-02-01",
                "authors": ["B. Author"],
            },
        ]
        self._timeout_query = "__timeout__"
        self._empty_query = "__empty__"

    def search(
        self,
        query: str,
        *,
        page_size: int = 10,
        cursor: str | int | None = 0,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if query == self._timeout_query:
            return {"query": query, "error": "timeout", "results": [], "cursor": cursor}
        if query == self._empty_query:
            return {
                "query": query,
                "results": [],
                "cursor": cursor,
                "next_cursor": None,
                "adapter_id": self.adapter_id,
            }
        start = int(cursor or 0)
        if start >= len(self._fixtures):
            return {
                "query": query,
                "results": [],
                "cursor": start,
                "next_cursor": None,
                "adapter_id": self.adapter_id,
            }
        end = min(start + page_size, len(self._fixtures))
        page = self._fixtures[start:end]
        next_cursor = end if end < len(self._fixtures) else None
        return {
            "query": query,
            "results": normalize_page(page),
            "cursor": start,
            "next_cursor": next_cursor,
            "adapter_id": self.adapter_id,
            "filters": filters or {},
        }
