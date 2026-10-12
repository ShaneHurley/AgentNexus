"""GET /api/workshop/snapshot — cached workshop summary."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

from . import common as c


class WorkshopSnapshotCache:
    def __init__(self, ttl_seconds: float = 5.0):
        self._lock = threading.Lock()
        self._ttl = ttl_seconds
        self._cached: tuple[float, dict[str, Any]] | None = None

    def get(self, builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            if self._cached and now - self._cached[0] < self._ttl:
                return self._cached[1]
        payload = builder()
        with self._lock:
            now2 = time.monotonic()
            if self._cached and now2 - self._cached[0] < self._ttl:
                return self._cached[1]
            self._cached = (now2, payload)
            return payload


def _build_snapshot(ctx: dict[str, Any]) -> dict[str, Any]:
    registry = ctx["registry"]
    agents = registry.list_agents()
    quick_data: dict[str, dict[str, Any]] = {}
    for agent in agents:
        agent_id = agent.get("id")
        if not agent_id:
            continue
        adapter = registry.adapters.get(agent_id)
        latest_runs: list[dict[str, Any]] = []
        pending_approvals = 0
        if adapter is not None:
            try:
                latest_runs = adapter.list_runs(3)[:3]
            except Exception:  # noqa: BLE001
                latest_runs = []
            try:
                pending_approvals = len(adapter.pending_approvals())
            except Exception:  # noqa: BLE001
                pending_approvals = 0
        thread_counts = {"queued": 0, "applied": 0}
        try:
            for msg in registry.steer.list(agent_id, limit=500):
                status = msg.get("status")
                if status == "queued":
                    thread_counts["queued"] += 1
                elif status == "applied":
                    thread_counts["applied"] += 1
        except Exception:  # noqa: BLE001
            pass
        quick_data[agent_id] = {
            "latest_runs": latest_runs,
            "pending_approvals_count": pending_approvals,
            "thread_summary_counts": thread_counts,
        }
    return {
        "generated_at": time.time(),
        "auth_required": ctx["auth_required"],
        "agents": agents,
        "quick_data": quick_data,
    }


def handle_get(handler, path: str, query: dict, parts: list[str]) -> bool:
    if path != "/api/workshop/snapshot":
        return False
    ctx = c.ctx(handler)
    cache: WorkshopSnapshotCache = ctx["workshop_snapshot"]
    payload = cache.get(lambda: _build_snapshot(ctx))
    c.send(handler, 200, payload)
    return True
