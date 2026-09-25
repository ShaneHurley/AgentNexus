"""Adapter contract — one class per orchestrator agent.

Replace or add adapters without touching the UI. The server only calls these methods.
"""
from __future__ import annotations
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AgentAdapter(Protocol):
    id: str
    name: str
    description: str

    def capabilities(self) -> list[str]:
        """Declared features: health, runs, start, approve, resume, cancel, activity, metrics, steer."""

    def health(self) -> dict[str, Any]:
        ...

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        ...

    def get_run(self, run_id: str) -> dict[str, Any]:
        ...

    def start_run(self, request: str, **kwargs: Any) -> dict[str, Any]:
        ...

    def approve(self, run_id: str, *, reject: bool = False, note: str | None = None, kind: str = "plan") -> dict[str, Any]:
        ...

    def resume(self, run_id: str) -> dict[str, Any]:
        ...

    def cancel(self, run_id: str) -> dict[str, Any]:
        ...

    def pending_approvals(self) -> list[dict[str, Any]]:
        ...

    def activity(self, run_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        ...

    def metrics(self) -> dict[str, Any]:
        ...
