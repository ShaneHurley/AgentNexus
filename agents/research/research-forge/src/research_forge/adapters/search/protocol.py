"""Provider-neutral search protocol (RF-W1-D-01)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class SearchRequest:
    query: str
    page_size: int = 10
    cursor: str | int | None = None
    filters: dict[str, Any] = field(default_factory=dict)
    date_bounds: tuple[str | None, str | None] | None = None
    language: str | None = None
    source_type: str | None = None


@dataclass
class NormalizedSearchResult:
    result_id: str
    canonical_title: str
    canonical_url: str
    authors_or_owner: list[str]
    date: str
    source_type: str
    snippet: str
    provider_rank: int
    retrieved_at: str

    @classmethod
    def from_raw(cls, raw: dict[str, Any], *, rank: int) -> NormalizedSearchResult:
        return cls(
            result_id=raw.get("result_id") or f"res-{rank}",
            canonical_title=raw.get("title") or "UNKNOWN",
            canonical_url=raw.get("url") or "UNKNOWN",
            authors_or_owner=list(raw.get("authors") or raw.get("authors_or_owner") or ["UNKNOWN"]),
            date=raw.get("date") or "UNKNOWN",
            source_type=raw.get("source_type") or "UNKNOWN",
            snippet=raw.get("snippet") or "UNKNOWN",
            provider_rank=rank,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "canonical_title": self.canonical_title,
            "canonical_url": self.canonical_url,
            "authors_or_owner": self.authors_or_owner,
            "date": self.date,
            "source_type": self.source_type,
            "snippet": self.snippet,
            "provider_rank": self.provider_rank,
            "retrieved_at": self.retrieved_at,
        }


def normalize_page(raw_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [NormalizedSearchResult.from_raw(r, rank=i).to_dict() for i, r in enumerate(raw_results)]
