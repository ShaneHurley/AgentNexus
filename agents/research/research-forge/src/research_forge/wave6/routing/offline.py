"""Offline routing optimizer — no live tools (RF-W6-D-04/05)."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Callable


LiveToolFn = Callable[..., Any]


@dataclass
class OfflineRouterModel:
    version: str
    weights: dict[str, float] = field(default_factory=dict)
    trained_on: int = 0

    def predict(self, features: dict[str, Any]) -> str:
        score_fan = self.weights.get("lane_count", 0) * float(features.get("lane_count") or 0)
        score_fan += self.weights.get("complexity_high", 0) if features.get("complexity") == "high" else 0
        return "fan_out" if score_fan >= self.weights.get("threshold", 2.0) else "single_agent"


class OfflineTrainer:
    def __init__(self, *, live_tool_guard: LiveToolFn | None = None) -> None:
        self._live_tool_guard = live_tool_guard

    def train(self, events: list[dict[str, Any]]) -> OfflineRouterModel:
        if self._live_tool_guard is not None:
            raise RuntimeError("training_cannot_call_live_research_tools")
        fan = [e for e in events if e.get("route") == "fan_out" and e.get("expert_verdict") == "good"]
        single = [e for e in events if e.get("route") == "single_agent" and e.get("expert_verdict") == "good"]
        threshold = 2.0
        if fan and single:
            threshold = statistics.mean([float(e["request_features"].get("lane_count") or 1) for e in fan])
        return OfflineRouterModel(
            version="offline-v1",
            weights={"lane_count": 0.5, "complexity_high": 1.5, "threshold": threshold},
            trained_on=len(events),
        )

    def evaluate_held_out(self, model: OfflineRouterModel, held_out: list[dict[str, Any]]) -> dict[str, Any]:
        correct = 0
        costs: list[float] = []
        for ev in held_out:
            pred = model.predict(ev.get("request_features") or {})
            if pred == ev.get("route"):
                correct += 1
            costs.append(float(ev.get("outcome_metrics", {}).get("cost_usd", 0)))
        n = len(held_out) or 1
        return {
            "accuracy": correct / n,
            "cost_mean": statistics.mean(costs) if costs else 0.0,
            "cost_stdev": statistics.pstdev(costs) if len(costs) > 1 else 0.0,
            "n": len(held_out),
        }
