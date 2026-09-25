"""Routing training data quality filter (RF-W6-D-02)."""

from __future__ import annotations

from typing import Any

from research_forge.wave6.routing.dataset import RoutingEvent


class RoutingDataQualityFilter:
    def filter(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for raw in events:
            ev = RoutingEvent(
                event_id=raw["event_id"],
                request_features=raw.get("request_features") or {},
                route=raw.get("route") or "",
                models=list(raw.get("models") or []),
                tools=list(raw.get("tools") or []),
                budget_profile=raw.get("budget_profile") or "",
                outcome_metrics=raw.get("outcome_metrics") or {},
                audit_ref=raw.get("audit_ref") or "",
                expert_verdict=raw.get("expert_verdict") or "",
                provider_specific=dict(raw.get("provider_specific") or {}),
            )
            if ev.validate():
                continue
            if raw.get("outcome_verified") is False:
                continue
            if ev.expert_verdict in ("unknown", "failed"):
                continue
            if ev.event_id in seen:
                continue
            seen.add(ev.event_id)
            out.append(ev.to_dict())
        return out
