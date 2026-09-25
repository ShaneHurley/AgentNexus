"""Shadow mode routing (RF-W6-D-06)."""

from __future__ import annotations

from typing import Any

from research_forge.wave6.routing.baseline import StaticRoutingBaseline
from research_forge.wave6.routing.offline import OfflineRouterModel


class ShadowRouter:
    def __init__(self, model: OfflineRouterModel, baseline: StaticRoutingBaseline | None = None) -> None:
        self.model = model
        self.baseline = baseline or StaticRoutingBaseline()
        self.shadow_log: list[dict[str, Any]] = []

    def execute(self, features: dict[str, Any]) -> dict[str, Any]:
        active_route = self.baseline.decide(features)
        proposed = self.model.predict(features)
        entry = {
            "features": features,
            "active_route": active_route,
            "proposed_route": proposed,
            "match": active_route == proposed,
        }
        self.shadow_log.append(entry)
        return {"route": active_route, "shadow_proposed": proposed, "executed": active_route}

    def agreement_rate(self) -> float:
        if not self.shadow_log:
            return 0.0
        matches = sum(1 for e in self.shadow_log if e["match"])
        return matches / len(self.shadow_log)
