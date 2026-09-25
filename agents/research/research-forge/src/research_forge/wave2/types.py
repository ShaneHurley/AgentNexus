"""Shared Wave 2 types and enums."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TriageStatus(str, Enum):
    SCREEN = "SCREEN"
    DEEP_READ = "DEEP_READ"
    REFERENCE_ONLY = "REFERENCE_ONLY"
    REJECT = "REJECT"
    FOLLOW_CITATIONS = "FOLLOW_CITATIONS"


class LaneState(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SATURATED = "saturated"
    CANCELED = "canceled"
    COMPLETE = "complete"


DEFAULT_ANGLE_TAXONOMY: tuple[str, ...] = (
    "foundations",
    "current_research",
    "alternatives",
    "standards",
    "implementation",
    "failures",
    "economics",
    "safety",
    "human_factors",
    "analogies",
)

REQUIRED_SPECIAL_LANES: tuple[str, ...] = ("disconfirmation", "real_world_implementation")

MAX_SCOUT_PROSE_CHARS = 280
MAX_SCOUT_REFINEMENTS = 1
MAX_SCOUT_RETRIES = 2


@dataclass
class TermEntry:
    term: str
    kind: str
    maps_to: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"term": self.term, "kind": self.kind, "maps_to": self.maps_to, "note": self.note}


@dataclass
class ResearchLane:
    lane_id: str
    angle: str
    purpose: str
    source_classes: list[str]
    query_concepts: list[str]
    unique_queries: list[str]
    expected_evidence: str
    stop_rule: dict[str, Any]
    overlap_score: float = 0.0
    decision_value: str = ""
    state: LaneState = LaneState.PENDING
    owner: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane_id": self.lane_id,
            "angle": self.angle,
            "purpose": self.purpose,
            "source_classes": self.source_classes,
            "query_concepts": self.query_concepts,
            "unique_queries": self.unique_queries,
            "expected_evidence": self.expected_evidence,
            "stop_rule": self.stop_rule,
            "overlap_score": self.overlap_score,
            "decision_value": self.decision_value,
            "state": self.state.value,
            "owner": self.owner,
        }


@dataclass
class ScoutCandidate:
    candidate_id: str
    lane_id: str
    url: str
    title: str
    relevance_reason: str
    source_type: str
    access: str
    uniqueness_hypothesis: str
    follow_citations: bool
    query_event_id: str

    def to_dict(self) -> dict[str, Any]:
        reason = self.relevance_reason[:MAX_SCOUT_PROSE_CHARS]
        return {
            "candidate_id": self.candidate_id,
            "lane_id": self.lane_id,
            "url": self.url,
            "title": self.title,
            "relevance_reason": reason,
            "source_type": self.source_type,
            "access": self.access,
            "uniqueness_hypothesis": self.uniqueness_hypothesis[:MAX_SCOUT_PROSE_CHARS],
            "follow_citations": self.follow_citations,
            "query_event_id": self.query_event_id,
        }


@dataclass
class CuratorDecision:
    candidate_id: str
    status: TriageStatus
    reason: str
    scores: dict[str, float]
    cluster_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "status": self.status.value,
            "reason": self.reason,
            "scores": self.scores,
            "cluster_id": self.cluster_id,
        }


@dataclass
class SaturationRound:
    lane_id: str
    round_index: int
    new_canonical_sources: int
    new_independent_evidence: int
    new_contradictions: int
    new_decision_claims: int
    cost_usd: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane_id": self.lane_id,
            "round_index": self.round_index,
            "new_canonical_sources": self.new_canonical_sources,
            "new_independent_evidence": self.new_independent_evidence,
            "new_contradictions": self.new_contradictions,
            "new_decision_claims": self.new_decision_claims,
            "cost_usd": self.cost_usd,
        }


@dataclass
class SchedulerLimits:
    max_active_scouts: int = 4
    max_adapter_calls_per_lane: int = 6
    max_calls_per_domain: int = 20
    overlap_merge_threshold: float = 0.65

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> SchedulerLimits:
        return cls(
            max_active_scouts=int(cfg.get("max_active_scouts", 4)),
            max_adapter_calls_per_lane=int(cfg.get("max_adapter_calls_per_lane", 6)),
            max_calls_per_domain=int(cfg.get("max_calls_per_domain", 20)),
            overlap_merge_threshold=float(cfg.get("overlap_merge_threshold", 0.65)),
        )


@dataclass
class FanInSnapshot:
    canonical_source_ids: list[str]
    lane_contributions: dict[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_source_ids": sorted(self.canonical_source_ids),
            "lane_contributions": {
                lane: sorted(ids) for lane, ids in sorted(self.lane_contributions.items())
            },
        }
