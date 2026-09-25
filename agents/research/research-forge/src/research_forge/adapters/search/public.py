"""Public read-only search adapter — live-only, gateway-wrapped (RF-W1-D-03)."""

from __future__ import annotations

from typing import Any, Callable

from research_forge.adapters.search.protocol import normalize_page


class PublicSearchAdapter:
    adapter_id = "public_search_v1"
    user_agent = "ResearchForge/1.0 (+read-only)"

    def __init__(
        self,
        *,
        fetch_json: Callable[[str], dict[str, Any]] | None = None,
        forbidden_domains: frozenset[str] | None = None,
    ) -> None:
        self._fetch = fetch_json
        self._forbidden = forbidden_domains or frozenset()

    def search(
        self,
        query: str,
        *,
        page_size: int = 10,
        cursor: str | int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if "://" in query and ("@" in query.split("://", 1)[0] or "user:pass" in query):
            return {"query": query, "error": "credential_url", "results": []}
        domain = (filters or {}).get("domain")
        if domain and domain in self._forbidden:
            return {"query": query, "error": "forbidden_domain", "results": []}
        if self._fetch is None:
            return {"query": query, "error": "live_fetch_disabled", "results": []}
        raw = self._fetch(query)
        items = raw.get("results", [])[:page_size]
        return {
            "query": query,
            "results": normalize_page(items),
            "cursor": cursor,
            "next_cursor": raw.get("next_cursor"),
            "adapter_id": self.adapter_id,
        }
