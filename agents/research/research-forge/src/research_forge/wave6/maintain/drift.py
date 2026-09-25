"""Operational drift monitoring (RF-W6-F-03)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DriftThresholds:
    citation_quality_min: float = 0.85
    unsupported_claim_rate_max: float = 0.05
    cost_usd_daily_max: float = 500.0
    lane_yield_min: float = 0.3

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation_quality_min": self.citation_quality_min,
            "unsupported_claim_rate_max": self.unsupported_claim_rate_max,
            "cost_usd_daily_max": self.cost_usd_daily_max,
            "lane_yield_min": self.lane_yield_min,
        }


class DriftMonitor:
    def __init__(self, thresholds: DriftThresholds | None = None) -> None:
        self.thresholds = thresholds or DriftThresholds()
        self.alerts: list[dict[str, Any]] = []

    def evaluate(self, metrics: dict[str, Any]) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        t = self.thresholds
        if metrics.get("citation_quality", 1.0) < t.citation_quality_min:
            alerts.append({"metric": "citation_quality", "level": "warning"})
        if metrics.get("unsupported_claim_rate", 0) > t.unsupported_claim_rate_max:
            alerts.append({"metric": "unsupported_claim_rate", "level": "critical"})
        if metrics.get("cost_usd_daily", 0) > t.cost_usd_daily_max:
            alerts.append({"metric": "cost_usd_daily", "level": "warning"})
        if metrics.get("lane_yield", 1.0) < t.lane_yield_min:
            alerts.append({"metric": "lane_yield", "level": "warning"})
        self.alerts.extend(alerts)
        return alerts
