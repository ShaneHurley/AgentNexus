"""Internal knowledge adapter with ACL (RF-W6-B-06)."""

from __future__ import annotations

import hashlib
from typing import Any

from research_forge.wave6.sdk.protocol import PROTOCOL_VERSION


class MockInternalKnowledgeAdapter:
    adapter_id = "mock_internal"
    protocol_version = PROTOCOL_VERSION

    _DOCS: dict[str, dict[str, Any]] = {
        "doc-alice-1": {
            "title": "Alice roadmap",
            "owner": "alice",
            "confidentiality": "internal",
            "allowed_users": ["alice"],
            "citation_handle": "internal://alice/roadmap",
            "body": "Roadmap details for Alice team.",
        },
        "doc-bob-1": {
            "title": "Bob secret",
            "owner": "bob",
            "confidentiality": "restricted",
            "allowed_users": ["bob"],
            "citation_handle": "internal://bob/secret",
            "body": "Bob-only content.",
        },
    }

    def __init__(self, *, acting_user: str = "alice") -> None:
        self.acting_user = acting_user

    def supported_operations(self) -> frozenset[str]:
        return frozenset({"search", "read"})

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        user = kwargs.get("user") or self.acting_user
        hits = []
        for doc_id, doc in self._DOCS.items():
            if user not in doc["allowed_users"]:
                continue
            if query.lower() in doc["title"].lower():
                hits.append(
                    {
                        "result_id": doc_id,
                        "canonical_title": doc["title"],
                        "source_type": "internal",
                        "confidentiality": doc["confidentiality"],
                        "citation_handle": doc["citation_handle"],
                    }
                )
        return {"results": hits, "next_cursor": None}

    def read(self, locator: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        user = kwargs.get("user") or self.acting_user
        doc_id = locator.get("doc_id")
        doc = self._DOCS.get(doc_id or "")
        if not doc:
            return {"error": "not_found", "access_level": "none"}
        if user not in doc["allowed_users"]:
            return {"error": "permission_denied", "access_level": "none"}
        body = doc["body"]
        return {
            "access_level": "full",
            "access_disclosure": f"confidentiality={doc['confidentiality']}",
            "locator": {"kind": "internal_doc", "value": doc_id},
            "content_hash": hashlib.sha256(body.encode()).hexdigest(),
            "citation_handle": doc["citation_handle"],
            "text": body,
        }
