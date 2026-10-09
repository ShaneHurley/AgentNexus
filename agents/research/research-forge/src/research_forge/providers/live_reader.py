"""Live web reader adapter with explicit fixture and retrieval provenance."""

from __future__ import annotations

import logging
import hashlib
import re
from typing import Any
from urllib.parse import urlparse

from agent_core.providers.http import ProviderError, get_public_text as get_text

logger = logging.getLogger(__name__)

MOCK_OR_EXAMPLE_HOSTS = frozenset({
    "example.com",
    "example.org",
    "example.net",
    "localhost",
    "127.0.0.1",
})


class LiveReaderAdapter:
    """Live web reader adapter for research-forge.
    
    Fetches real web content using agent_core.providers.http.get_text. Explicit
    fixtures are marked synthetic; missing or failed retrieval returns no content.
    """

    def __init__(
        self,
        *,
        adapter_id: str = "web_reader_v1",
        timeout: float = 5.0,
        custom_fixtures: dict[str, str] | None = None,
    ) -> None:
        self.adapter_id = adapter_id
        self.timeout = timeout
        self.fixtures = dict(custom_fixtures or {})

    def read(
        self,
        canonical_url: str | dict[str, Any],
        *,
        level: str | None = None,
        locator: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Fetch or synthesize content for a given canonical URL."""
        if isinstance(canonical_url, dict):
            url = str(canonical_url.get("url") or canonical_url.get("canonical_url") or "")
            if level is None and canonical_url.get("abstract_only"):
                level = "abstract"
            if locator is None:
                locator = canonical_url.get("locator")
        else:
            url = str(canonical_url)

        access_level = level or "full"
        text = ""
        retrieval_status = "unavailable"
        synthetic = False
        if url in self.fixtures:
            text = self.fixtures[url]
            retrieval_status = "fixture"
            synthetic = True
        elif self._is_mock_or_example(url):
            retrieval_status = "unavailable"
        elif url.startswith(("http://", "https://")):
            try:
                raw_text = get_text(url, timeout=self.timeout)
                text = self._clean_content(raw_text)
                retrieval_status = "retrieved" if text else "empty"
            except Exception as exc:
                logger.warning("Failed to fetch live URL (%s)", type(exc).__name__)
                retrieval_status = "failed"
        else:
            retrieval_status = "unavailable"

        # Slice text if requested access level is abstract or snippet
        if access_level == "abstract":
            text = text[:800]
        elif access_level == "snippet":
            text = text[:300]

        chunk_loc = locator or "section:1"
        chunks = [
            {
                "chunk_id": "chunk-1",
                "locator": chunk_loc,
                "text": text,
                "access_level": access_level,
            }
        ] if text else []

        return {
            "canonical_url": url,
            "content": text,
            "access_level": access_level,
            "adapter_id": self.adapter_id,
            "chunks": chunks,
            "locator": chunk_loc,
            "metadata": {
                "content_hash": "sha256:"+hashlib.sha256(text.encode()).hexdigest(),
                "retrieval_status": retrieval_status,
                "synthetic": synthetic,
                "source_authenticity": "synthetic_fixture" if synthetic else "unverified",
            },
        }

    def _is_mock_or_example(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
            return host in MOCK_OR_EXAMPLE_HOSTS or not host
        except Exception:
            return True

    def _clean_content(self, raw: str) -> str:
        # Strip script and style tags
        cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.DOTALL | re.IGNORECASE)
        # Strip general HTML tags
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        # Normalize whitespace
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:32000]
