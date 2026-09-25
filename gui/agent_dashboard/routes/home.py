"""GET /api/home/snapshot — cached dashboard summary."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

from . import common as c


class SnapshotCache:
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
    usage = ctx["usage_store"]
    agents = registry.list_agents()
    recent_events = usage.list_events()[-20:]
    runs_preview: list[dict[str, Any]] = []
    for agent_id, adapter in registry.adapters.items():
        try:
            runs = adapter.list_runs(3)
        except Exception:  # noqa: BLE001
            continue
        for run in runs[:3]:
            runs_preview.append({
                "agent_id": agent_id,
                "run_id": run.get("run_id"),
                "status": run.get("status"),
                "updated_at": run.get("updated_at"),
            })
    runs_preview.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
    return {
        "generated_at": time.time(),
        "agents": agents,
        "recent_runs": runs_preview[:12],
        "recent_usage_events": recent_events,
        "auth_required": ctx["auth_required"],
    }


def handle_get(handler, path: str, query: dict, parts: list[str]) -> bool:
    if path != "/api/home/snapshot":
        return False
    ctx = c.ctx(handler)
    cache: SnapshotCache = ctx["home_snapshot"]
    payload = cache.get(lambda: _build_snapshot(ctx))
    c.send(handler, 200, payload)
    return True
