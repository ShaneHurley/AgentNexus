"""GET /api/usage — events + normalized agent metrics."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from ..metrics_normalize import normalize_metrics
from . import common as c


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _bucket_key(ts: str, bucket: str) -> str:
    dt = _parse_ts(ts)
    if not dt:
        return "unknown"
    if bucket == "day":
        return dt.date().isoformat()
    if bucket == "hour":
        return dt.replace(minute=0, second=0, microsecond=0).isoformat()
    return ts


def handle_get(handler, path: str, query: dict, parts: list[str]) -> bool:
    if path != "/api/usage":
        return False
    ctx = c.ctx(handler)
    store = ctx["usage_store"]
    registry = ctx["registry"]
    from_ts = query.get("from", [None])[0]
    to_ts = query.get("to", [None])[0]
    agent_filter = query.get("agent_id", [None])[0]
    bucket = (query.get("bucket", [""])[0] or "").lower()

    events = store.list_events(from_ts=from_ts, to_ts=to_ts, agent_id=agent_filter)
    buckets: list[dict[str, Any]] = []
    if bucket in ("hour", "day"):
        grouped: dict[str, Counter] = defaultdict(Counter)
        for ev in events:
            key = _bucket_key(ev.get("ts") or "", bucket)
            grouped[key][ev.get("event") or "unknown"] += 1
        buckets = [
            {"bucket": k, "counts": dict(v), "total": sum(v.values())}
            for k, v in sorted(grouped.items())
        ]

    metrics: list[dict[str, Any]] = []
    for agent_id, adapter in registry.adapters.items():
        if agent_filter and agent_id != agent_filter:
            continue
        try:
            raw = adapter.metrics()
        except Exception as exc:  # noqa: BLE001
            raw = {"error": str(exc)}
        metrics.append(normalize_metrics(agent_id, raw if isinstance(raw, dict) else {}))

    c.send(handler, 200, {
        "events": events,
        "buckets": buckets,
        "bucket": bucket or None,
        "metrics": metrics,
        "event_total": len(events),
    })
    return True
