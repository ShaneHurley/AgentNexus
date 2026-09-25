"""Runtime guardrails override learned routes (RF-W6-D-08)."""

from __future__ import annotations

from typing import Any

from research_forge.wave6.routing.offline import OfflineRouterModel


class RoutingGuardrails:
    def apply(
        self,
        proposed_route: str,
        *,
        features: dict[str, Any],
        policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        policy = policy or {}
        budget = features.get("budget_profile", "M")
        remaining = float(features.get("budget_remaining_usd", 1.0))
        if budget == "S" and proposed_route == "fan_out":
            return {"route": "single_agent", "overridden": True, "reason": "budget_profile_cap"}
        if remaining < float(policy.get("min_usd_for_fanout", 2.0)) and proposed_route == "fan_out":
            return {"route": "single_agent", "overridden": True, "reason": "budget_remaining"}
        if features.get("adversarial_probe"):
            return {"route": "single_agent", "overridden": True, "reason": "adversarial_denied"}
        return {"route": proposed_route, "overridden": False, "reason": None}

    def route_with_model(
        self, model: OfflineRouterModel, features: dict[str, Any], policy: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        proposed = model.predict(features)
        return self.apply(proposed, features=features, policy=policy)
