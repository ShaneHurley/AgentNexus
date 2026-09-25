"""Routing event dataset schema (RF-W6-D-01)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REQUIRED_EVENT_FIELDS = (
    "event_id",
    "request_features",
    "route",
    "models",
    "tools",
    "budget_profile",
    "outcome_metrics",
    "audit_ref",
    "expert_verdict",
)


@dataclass
class RoutingEvent:
    event_id: str
    request_features: dict[str, Any]
    route: str
    models: list[str]
    tools: list[str]
    budget_profile: str
    outcome_metrics: dict[str, Any]
    audit_ref: str
    expert_verdict: str
    provider_specific: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        data = self.to_dict()
        for key in REQUIRED_EVENT_FIELDS:
            if not data.get(key):
                errors.append(f"missing:{key}")
        if self.provider_specific:
            errors.append("hidden_provider_feature")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "request_features": self.request_features,
            "route": self.route,
            "models": self.models,
            "tools": self.tools,
            "budget_profile": self.budget_profile,
            "outcome_metrics": self.outcome_metrics,
            "audit_ref": self.audit_ref,
            "expert_verdict": self.expert_verdict,
        }
