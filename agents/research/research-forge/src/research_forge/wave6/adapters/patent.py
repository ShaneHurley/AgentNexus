"""Patent adapter — normalized legal metadata (RF-W6-B-07)."""

from __future__ import annotations

from typing import Any

from research_forge.wave6.sdk.protocol import PROTOCOL_VERSION


class MockPatentAdapter:
    adapter_id = "mock_patent"
    protocol_version = PROTOCOL_VERSION

    _PATENTS: list[dict[str, Any]] = [
        {
            "publication_number": "US20240001234A1",
            "jurisdiction": "US",
            "family_id": "FAM-100",
            "status": "pending",
            "status_certainty": "official",
            "assignee": "Example Corp",
            "claims_access": "abstract_only",
            "filing_date": "2023-01-01",
        },
        {
            "publication_number": "EP3000000A1",
            "jurisdiction": "EP",
            "family_id": "FAM-100",
            "status": "unknown",
            "status_certainty": "uncertain",
            "assignee": "Example Corp",
            "claims_access": "none",
            "filing_date": "2023-02-01",
        },
    ]

    def supported_operations(self) -> frozenset[str]:
        return frozenset({"search", "read"})

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        hits = [p for p in self._PATENTS if query.lower() in p["assignee"].lower()]
        return {
            "results": [
                {
                    "result_id": p["publication_number"],
                    "canonical_title": p["publication_number"],
                    "source_type": "patent",
                    "jurisdiction": p["jurisdiction"],
                    "family_id": p["family_id"],
                    "legal_status": p["status"],
                    "status_certainty": p["status_certainty"],
                }
                for p in hits
            ],
            "next_cursor": None,
        }

    def read(self, locator: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        pub = locator.get("publication_number")
        for p in self._PATENTS:
            if p["publication_number"] == pub:
                return {
                    "access_level": "abstract" if p["claims_access"] == "abstract_only" else "none",
                    "access_disclosure": f"claims_access={p['claims_access']}",
                    "locator": {"kind": "patent", "value": pub},
                    "legal_status": p["status"],
                    "status_certainty": p["status_certainty"],
                    "family_id": p["family_id"],
                }
        return {"error": "not_found"}
