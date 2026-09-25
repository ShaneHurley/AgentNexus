"""Intentionally non-conformant adapter for suite tests."""

from __future__ import annotations

from typing import Any


class BadAdapter:
    adapter_id = "bad_adapter"
    protocol_version = "0.0.1"

    def supported_operations(self) -> frozenset[str]:
        return frozenset({"search", "write"})

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        return {"oops": True}
