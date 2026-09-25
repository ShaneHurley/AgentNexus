"""Canary activation and rollback (RF-W6-E-07)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CanaryState:
    proposal_id: str
    version: str
    traffic_pct: float
    stop_threshold: float
    active: bool = False
    metrics: list[float] = field(default_factory=list)

    def record_metric(self, value: float) -> None:
        self.metrics.append(value)

    def should_stop(self) -> bool:
        if not self.metrics:
            return False
        return self.metrics[-1] >= self.stop_threshold


class CanaryController:
    def __init__(self) -> None:
        self._states: dict[str, CanaryState] = {}

    def activate(self, proposal_id: str, version: str, *, traffic_pct: float = 5.0) -> CanaryState:
        state = CanaryState(
            proposal_id=proposal_id,
            version=version,
            traffic_pct=traffic_pct,
            stop_threshold=0.15,
            active=True,
        )
        self._states[proposal_id] = state
        return state

    def rollback(self, proposal_id: str, to_version: str) -> dict[str, Any]:
        state = self._states.get(proposal_id)
        if not state:
            return {"ok": False, "reason": "not_found"}
        state.active = False
        return {"ok": True, "rolled_back_to": to_version, "command": f"rf rollback --proposal {proposal_id} --version {to_version}"}
