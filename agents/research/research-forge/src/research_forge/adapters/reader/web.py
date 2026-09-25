"""Web/document reader stub — data-only, no execution (RF-W1-E-03)."""

from __future__ import annotations

from typing import Any

from research_forge.adapters.reader.protocol import ContentChunk, ReaderResponse
from research_forge.hashing.content import hash_bytes

MAX_BYTES = 256_000
ALLOWED_MIME = frozenset({"text/html", "text/plain", "application/pdf"})


class WebDocumentReader:
    adapter_id = "web_reader_v1"

    def __init__(self, documents: dict[str, bytes] | None = None) -> None:
        self._docs = documents or {}

    def read(
        self,
        source_ref: dict[str, Any],
        *,
        locator: str | None = None,
    ) -> dict[str, Any]:
        url = str(source_ref.get("url") or "")
        if "ignore previous instructions" in url.lower():
            return ReaderResponse(
                access_level="snippet",
                chunks=[
                    ContentChunk(
                        chunk_id="inj-1",
                        locator="snippet:1",
                        text="[data-only; injection not executed]",
                        access_level="snippet",
                    )
                ],
                metadata={"injection_detected": True, "url": url},
            ).to_dict()
        body = self._docs.get(url)
        if body is None:
            return ReaderResponse(
                access_level="metadata",
                metadata={"error": "inaccessible", "url": url},
            ).to_dict()
        if len(body) > MAX_BYTES:
            return ReaderResponse(
                access_level="metadata",
                metadata={"error": "oversized", "size": len(body)},
            ).to_dict()
        mime = source_ref.get("mime") or "text/plain"
        if mime not in ALLOWED_MIME:
            return ReaderResponse(
                access_level="metadata",
                metadata={"error": "unsupported_mime", "mime": mime},
            ).to_dict()
        text = body.decode("utf-8", errors="replace")
        if mime == "text/html":
            text = text.replace("<script", "&lt;script")
        level = "abstract" if source_ref.get("abstract_only") else "full"
        chunk_text = text if level == "full" else text[:500]
        chunks = [
            ContentChunk(
                chunk_id="web-1",
                locator=locator or "section:1",
                text=chunk_text,
                access_level=level,
            )
        ]
        return ReaderResponse(
            access_level=level,
            chunks=chunks,
            metadata={"mime": mime, "content_hash": hash_bytes(body), "url": url},
            raw_byte_ref=f"ref://{hash_bytes(body)}",
        ).to_dict()
