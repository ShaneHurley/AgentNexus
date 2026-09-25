"""Mock search adapter — deterministic pagination."""

from __future__ import annotations

from typing import Any


class MockSearchAdapter:
    adapter_id = "mock_search_v1"

    def __init__(self, fixtures: list[dict[str, Any]] | None = None) -> None:
        self._fixtures = fixtures or [
            {
                "title": "Alpha Paper",
                "url": "https://example.org/a",
                "snippet": "First result",
                "source_type": "web",
            },
            {
                "title": "Beta Paper",
                "url": "https://example.org/b",
                "snippet": "Second result",
                "source_type": "web",
            },
        ]

    def search(self, query: str, *, page_size: int = 1, cursor: int = 0) -> dict[str, Any]:
        start = cursor
        end = min(start + page_size, len(self._fixtures))
        results = self._fixtures[start:end]
        next_cursor = end if end < len(self._fixtures) else None
        return {
            "query": query,
            "results": results,
            "cursor": cursor,
            "next_cursor": next_cursor,
            "adapter_id": self.adapter_id,
        }
