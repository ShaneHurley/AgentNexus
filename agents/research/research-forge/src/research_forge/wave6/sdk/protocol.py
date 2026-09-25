"""Provider-neutral adapter protocol v1 (RF-W6-A-01)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

PROTOCOL_VERSION = "1.0.0"


@dataclass
class AdapterLocator:
    kind: str
    value: str
    access_level: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value, "access_level": self.access_level}


@dataclass
class CanonicalSourceRecord:
    """Normalized source from any adapter — no guessed metadata."""

    source_id: str
    title: str
    identifiers: list[dict[str, str]]
    source_type: str
    publication_status: str
    retrieved_at: str
    provider: str
    access_disclosure: str
    content_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "identifiers": self.identifiers,
            "source_type": self.source_type,
            "publication_status": self.publication_status,
            "retrieved_at": self.retrieved_at,
            "provider": self.provider,
            "access_disclosure": self.access_disclosure,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
        }


@dataclass
class SearchPage:
    results: list[dict[str, Any]]
    next_cursor: str | int | None
    total_hint: int | None = None
    rate_limit_remaining: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": self.results,
            "next_cursor": self.next_cursor,
            "total_hint": self.total_hint,
            "rate_limit_remaining": self.rate_limit_remaining,
        }


@runtime_checkable
class SearchAdapter(Protocol):
    adapter_id: str
    protocol_version: str

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]: ...

    def supported_operations(self) -> frozenset[str]: ...


@runtime_checkable
class ReaderAdapter(Protocol):
    adapter_id: str
    protocol_version: str

    def read(self, locator: dict[str, Any], **kwargs: Any) -> dict[str, Any]: ...

    def supported_operations(self) -> frozenset[str]: ...
