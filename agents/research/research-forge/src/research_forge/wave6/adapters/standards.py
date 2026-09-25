"""Standards metadata adapter (RF-W6-B-05)."""

from __future__ import annotations

import hashlib
from typing import Any

from research_forge.wave6.sdk.protocol import PROTOCOL_VERSION


class MockStandardsAdapter:
    adapter_id = "mock_standards"
    protocol_version = PROTOCOL_VERSION

    _STANDARDS: list[dict[str, Any]] = [
        {
            "id": "RFC9110",
            "title": "HTTP Semantics",
            "edition": "2022",
            "status": "current",
            "access": "free",
        },
        {
            "id": "RFC2616",
            "title": "HTTP/1.1",
            "edition": "1999",
            "status": "superseded",
            "superseded_by": "RFC9110",
            "access": "free",
        },
    ]

    def supported_operations(self) -> frozenset[str]:
        return frozenset({"search", "read"})

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        cursor = int(kwargs.get("cursor") or 0)
        page_size = int(kwargs.get("page_size", 10))
        hits = [s for s in self._STANDARDS if query.lower() in s["title"].lower() or query in s["id"]]
        page = hits[cursor : cursor + page_size]
        results = [
            {
                "result_id": s["id"],
                "canonical_title": s["title"],
                "source_type": "standard",
                "edition": s["edition"],
                "status": s["status"],
                "access_disclosure": s["access"],
                "superseded": s["status"] == "superseded",
            }
            for s in page
        ]
        next_c = cursor + page_size if cursor + page_size < len(hits) else None
        return {"results": results, "next_cursor": next_c}

    def read(self, locator: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        std_id = locator.get("standard_id")
        for s in self._STANDARDS:
            if s["id"] == std_id:
                text = f"{s['title']} edition {s['edition']} status {s['status']}"
                return {
                    "access_level": "full" if s["access"] == "free" else "restricted",
                    "access_disclosure": f"edition={s['edition']}; access={s['access']}",
                    "locator": {"kind": "standard", "value": std_id},
                    "content_hash": hashlib.sha256(text.encode()).hexdigest(),
                    "superseded": s["status"] == "superseded",
                    "superseded_by": s.get("superseded_by"),
                    "text": text,
                }
        return {"error": "not_found"}
