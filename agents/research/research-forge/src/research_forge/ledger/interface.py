"""Append-only ledger interface — no update/delete."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LedgerReader(Protocol):
    def read_by_run(self, run_id: str) -> list[dict[str, Any]]: ...

    def read_by_sequence(self, run_id: str, sequence: int) -> dict[str, Any] | None: ...

    def latest_sequence(self, run_id: str) -> int: ...

    def verify_chain(self, run_id: str | None = None) -> tuple[bool, list[str]]: ...


@runtime_checkable
class LedgerWriter(Protocol):
    def append(
        self,
        event: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]: ...

    def export_bundle(self, run_id: str, redact_keys: frozenset[str] | None = None) -> dict[str, Any]: ...


class AbstractLedger(ABC):
    """Inspection helper: mutation methods must not exist on concrete ledgers."""

    @abstractmethod
    def append(self, event: dict[str, Any], *, idempotency_key: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def update(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - must not be used
        raise AttributeError("Ledger is append-only")

    def delete(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        raise AttributeError("Ledger is append-only")
