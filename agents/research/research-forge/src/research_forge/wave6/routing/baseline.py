"""Static routing baseline — frozen (RF-W6-D-03)."""

from __future__ import annotations

from typing import Any

BASELINE_VERSION = "wave2-static-v1"


class StaticRoutingBaseline:
    """Deterministic rules from Wave 2 fan-out evaluation."""

    FROZEN = True

    def decide(self, features: dict[str, Any]) -> str:
        lanes = int(features.get("lane_count") or 1)
        complexity = features.get("complexity", "medium")
        if lanes >= 4 or complexity == "high":
            return "fan_out"
        if features.get("budget_profile") == "S":
            return "single_agent"
        return "single_agent"

    def metadata(self) -> dict[str, Any]:
        return {"baseline_version": BASELINE_VERSION, "frozen": self.FROZEN}
