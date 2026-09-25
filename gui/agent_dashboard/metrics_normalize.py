"""Normalize heterogeneous adapter metrics() payloads for usage API."""
from __future__ import annotations

from typing import Any


_TOTAL_KEYS = (
    "runs",
    "active",
    "queued",
    "waiting_human",
    "waiting_job",
    "complete",
    "failed",
)


def normalize_metrics(agent_id: str, raw: dict[str, Any] | None) -> dict[str, Any]:
    """Return a stable shape; missing fields are null (not omitted)."""
    raw = raw if isinstance(raw, dict) else {}
    totals_in = raw.get("totals") if isinstance(raw.get("totals"), dict) else {}
    totals: dict[str, Any] = {k: _coerce_count(totals_in.get(k)) for k in _TOTAL_KEYS}
    if totals["runs"] is None and totals_in:
        # Research Forge uses a subset; fill runs if present at top level only in totals_in
        pass
    if totals["runs"] is None and "runs" in raw and not totals_in:
        totals["runs"] = _coerce_count(raw.get("runs"))

    spend = raw.get("today")
    if isinstance(spend, dict):
        spend_usd = spend.get("usd")
    else:
        spend_usd = raw.get("spend_usd") or raw.get("est_usd")
    try:
        spend_f = float(spend_usd) if spend_usd is not None else None
    except (TypeError, ValueError):
        spend_f = None

    roles = raw.get("roles") if isinstance(raw.get("roles"), dict) else None
    accuracy = raw.get("accuracy") if isinstance(raw.get("accuracy"), dict) else None

    return {
        "agent_id": agent_id,
        "totals": totals,
        "spend_usd": spend_f,
        "roles": roles,
        "accuracy": accuracy,
        "tool_denials": raw.get("tool_denials"),
        "jobs_active": raw.get("jobs_active"),
        "limits": raw.get("limits"),
    }


def _coerce_count(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
