"""Lane saturation, snowball rules, early stop (RF-W2-E)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_forge.wave2.types import SaturationRound


@dataclass
class SaturationConfig:
    duplicate_window_rounds: int = 2
    min_new_sources_per_round: int = 1
    max_rounds_without_gain: int = 2
    min_lane_obligations: int = 1


@dataclass
class LaneSaturationTracker:
    lane_id: str
    rounds: list[SaturationRound] = field(default_factory=list)
    stopped: bool = False
    stop_reason: str | None = None

    def log_round(self, round_metrics: SaturationRound) -> None:
        self.rounds.append(round_metrics)

    def yield_per_cost(self) -> float:
        total_new = sum(r.new_canonical_sources for r in self.rounds)
        total_cost = sum(r.cost_usd for r in self.rounds) or 1e-9
        return total_new / total_cost


class SaturationEngine:
    def __init__(self, config: SaturationConfig) -> None:
        self.config = config
        self.trackers: dict[str, LaneSaturationTracker] = {}

    def tracker(self, lane_id: str) -> LaneSaturationTracker:
        if lane_id not in self.trackers:
            self.trackers[lane_id] = LaneSaturationTracker(lane_id=lane_id)
        return self.trackers[lane_id]

    def record_round(
        self,
        lane_id: str,
        *,
        round_index: int,
        new_canonical: int,
        new_independent: int,
        new_contradictions: int,
        new_claims: int,
        cost_usd: float,
    ) -> SaturationRound:
        row = SaturationRound(
            lane_id=lane_id,
            round_index=round_index,
            new_canonical_sources=new_canonical,
            new_independent_evidence=new_independent,
            new_contradictions=new_contradictions,
            new_decision_claims=new_claims,
            cost_usd=cost_usd,
        )
        self.tracker(lane_id).log_round(row)
        return row

    def should_stop_lane(self, lane_id: str) -> tuple[bool, str | None]:
        tr = self.tracker(lane_id)
        if tr.stopped:
            return True, tr.stop_reason
        if len(tr.rounds) < self.config.duplicate_window_rounds:
            return False, None
        window = tr.rounds[-self.config.duplicate_window_rounds :]
        if all(r.new_canonical_sources < self.config.min_new_sources_per_round for r in window):
            tr.stopped = True
            tr.stop_reason = "repeated_duplicates"
            return True, tr.stop_reason
        stale = 0
        for r in reversed(tr.rounds):
            if r.new_canonical_sources < self.config.min_new_sources_per_round:
                stale += 1
            else:
                break
        if stale >= self.config.max_rounds_without_gain:
            tr.stopped = True
            tr.stop_reason = "no_gain_window"
            return True, tr.stop_reason
        return False, None

    def citation_snowball_allowed(self, source: dict[str, Any]) -> bool:
        tags = set(source.get("tags") or [])
        if "generic_survey" in tags:
            return False
        if source.get("load_bearing"):
            return True
        if source.get("contradictory"):
            return True
        if source.get("uniquely_relevant"):
            return True
        return False

    def missing_class_followup(
        self,
        missing_class: str,
        attempts: int,
    ) -> dict[str, Any]:
        if attempts >= 1:
            return {
                "action": "record_gap",
                "source_class": missing_class,
                "attempts": attempts,
                "stop": True,
            }
        return {
            "action": "bounded_followup",
            "source_class": missing_class,
            "attempts": attempts + 1,
            "stop": False,
            "budget_usd_cap": 0.5,
        }

    def early_success_stop(
        self,
        proposition_coverage: dict[str, dict[str, Any]],
    ) -> tuple[bool, str | None]:
        if not proposition_coverage:
            return False, None
        for prop, status in proposition_coverage.items():
            if not status.get("adequate_evidence"):
                return False, None
            if not status.get("counterevidence_attempted"):
                return False, None
        return True, "decision_critical_satisfied"


class ExpansionCoordinator:
    """Combines saturation stop with scheduler hints."""

    def __init__(self, engine: SaturationEngine) -> None:
        self.engine = engine

    def apply_stop_to_lane(self, lane_id: str, stop_rule: dict[str, Any]) -> dict[str, Any]:
        stop, reason = self.engine.should_stop_lane(lane_id)
        if stop:
            stop_rule = dict(stop_rule)
            stop_rule["lane_saturated"] = True
            stop_rule["saturation_reason"] = reason
        return stop_rule
