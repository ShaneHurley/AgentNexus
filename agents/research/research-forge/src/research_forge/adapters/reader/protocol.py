"""Reader protocol types (RF-W1-E-01)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContentChunk:
    chunk_id: str
    locator: str
    text: str
    access_level: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "locator": self.locator,
            "text": self.text,
            "access_level": self.access_level,
        }


@dataclass
class ReaderResponse:
    access_level: str
    chunks: list[ContentChunk] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_byte_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_level": self.access_level,
            "chunks": [c.to_dict() for c in self.chunks],
            "metadata": self.metadata,
            "raw_byte_ref": self.raw_byte_ref,
        }
