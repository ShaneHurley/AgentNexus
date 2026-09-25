"""Deprecation review (RF-W6-F-06)."""

from __future__ import annotations

from typing import Any


class DeprecationReviewer:
    def review(self, component: dict[str, Any]) -> dict[str, Any]:
        usage = int(component.get("usage_30d") or 0)
        dependents = list(component.get("dependents") or [])
        replay_ok = bool(component.get("replay_review_passed"))
        if usage == 0 and not dependents and replay_ok:
            return {"decision": "deprecate", "historical_packets_preserved": True}
        if dependents:
            return {"decision": "retain", "reason": "dependents"}
        return {"decision": "retain", "reason": "insufficient_review"}
