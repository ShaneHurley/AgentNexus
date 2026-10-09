"""Live search adapter with Brave Search API integration."""

from __future__ import annotations

import logging
import os
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from agent_core.providers.http import get_json

logger = logging.getLogger(__name__)


class LiveSearchAdapter:
    """Fetch real search results; unavailable retrieval never creates evidence."""

    def __init__(
        self,
        *,
        adapter_id: str = "public_search_v1",
        api_key: str | None = None,
        model: Any | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.adapter_id = adapter_id
        self.api_key = api_key or os.environ.get("BRAVE_SEARCH_API_KEY", "")
        self.timeout = timeout
        # Retained for constructor compatibility. Models must never invent search evidence.
        self._model = model

    def search(
        self,
        query: str,
        *,
        page_size: int = 10,
        cursor: int | str | None = 0,
        filters: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Return provider results or an explicit empty/unavailable result."""
        int_cursor = int(cursor or 0)
        results: list[dict[str, Any]] = []
        brave_key = self.api_key or os.environ.get("BRAVE_SEARCH_API_KEY", "")
        retrieval_status = "unavailable"
        if brave_key:
            try:
                results = self._search_brave(query, brave_key, page_size=page_size, cursor=int_cursor)
                retrieval_status = "retrieved" if results else "empty"
            except Exception as exc:  # Provider details may contain sensitive request data.
                logger.warning("Brave search API call failed (%s)", type(exc).__name__)
                retrieval_status = "failed"

        return {
            "query": query,
            "results": results,
            "cursor": int_cursor,
            "next_cursor": None,
            "adapter_id": self.adapter_id,
            "metadata": {"retrieval_status": retrieval_status, "synthetic": False},
        }

    def _search_brave(
        self,
        query: str,
        api_key: str,
        *,
        page_size: int = 10,
        cursor: int = 0,
    ) -> list[dict[str, Any]]:
        encoded_query = urllib.parse.quote(query)
        url = f"https://api.search.brave.com/res/v1/web/search?q={encoded_query}&count={page_size}&offset={cursor}"
        data = get_json(
            url,
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            timeout=self.timeout,
        )
        web_items = (data.get("web") or {}).get("results") or []
        now = datetime.now(timezone.utc).isoformat()
        results: list[dict[str, Any]] = []
        for idx, item in enumerate(web_items, start=1):
            title = str(item.get("title") or "Untitled")
            item_url = str(item.get("url") or "")
            results.append({
                "result_id": f"res-{idx}",
                "title": title,
                "canonical_title": title,
                "url": item_url,
                "canonical_url": item_url,
                "snippet": str(item.get("description") or item.get("snippet") or ""),
                "source_type": "web",
                "authors_or_owner": [item.get("profile", {}).get("name") or "web"],
                "date": item.get("page_age") or now[:10],
                "provider_rank": idx,
                "retrieved_at": now,
                "source_authenticity": "unverified",
            })
        return results
