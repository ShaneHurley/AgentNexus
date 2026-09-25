"""Landscape Mapper — taxonomy and lanes only (RF-W2-A)."""

from __future__ import annotations

import re
import uuid
from typing import Any

from research_forge.wave2.types import (
    DEFAULT_ANGLE_TAXONOMY,
    REQUIRED_SPECIAL_LANES,
    LaneState,
    ResearchLane,
    TermEntry,
)

_FORBIDDEN_OUTPUT_KEYS = frozenset({"recommendation", "conclusion", "deep_read", "essay"})


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"[a-zA-Z0-9]{3,}", text)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


class LandscapeMapper:
    """Produces taxonomy, terminology, and lanes — no search or recommendations."""

    role_id = "landscape_mapper"
    allowed_tools: tuple[str, ...] = ()

    def __init__(self, extra_angles: list[str] | None = None) -> None:
        self.angle_taxonomy = list(DEFAULT_ANGLE_TAXONOMY)
        if extra_angles:
            for angle in extra_angles:
                if angle not in self.angle_taxonomy:
                    self.angle_taxonomy.append(angle)

    def map_landscape(
        self,
        charter: dict[str, Any],
        seed_sources: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        seed_sources = seed_sources or []
        terminology = self.build_terminology_map(charter, seed_sources)
        lanes = self.generate_candidate_lanes(charter, terminology)
        lanes = self.compute_overlap_scores(lanes)
        active = self.review_and_merge(lanes)
        out = {
            "map_id": f"map-{uuid.uuid4().hex[:12]}",
            "charter_id": charter.get("charter_id", "unknown"),
            "angle_taxonomy": list(self.angle_taxonomy),
            "terminology": [t.to_dict() for t in terminology],
            "lanes": [lane.to_dict() for lane in active],
            "merged_lane_ids": [lane.lane_id for lane in lanes if lane.state.value == "canceled"],
        }
        self._assert_taxonomy_only(out)
        return out

    def build_terminology_map(
        self,
        charter: dict[str, Any],
        seed_sources: list[dict[str, Any]],
    ) -> list[TermEntry]:
        entries: list[TermEntry] = []
        objective = charter.get("objective", "")
        for ng in charter.get("non_goals", []):
            entries.append(
                TermEntry(term=ng[:80], kind="exclusion", maps_to="exclude", note="charter non_goal")
            )
        for rq in charter.get("research_questions", []):
            entries.append(
                TermEntry(term=rq, kind="query_concept", maps_to=rq, note="charter question")
            )
        words = _tokenize(objective)
        for w in sorted(words)[:12]:
            entries.append(
                TermEntry(term=w, kind="synonym", maps_to=objective[:120], note="objective token")
            )
        for src in seed_sources:
            title = (src.get("title") or "")[:80]
            if title:
                entries.append(
                    TermEntry(
                        term=title,
                        kind="acronym",
                        maps_to=src.get("source_id", "seed"),
                        note="seed source",
                    )
                )
        if not entries:
            entries.append(
                TermEntry(term="topic", kind="query_concept", maps_to="RQ-001", note="fallback")
            )
        return entries

    def generate_candidate_lanes(
        self,
        charter: dict[str, Any],
        terminology: list[TermEntry],
    ) -> list[ResearchLane]:
        concepts = [t.term for t in terminology if t.kind == "query_concept"]
        if not concepts:
            concepts = ["general"]
        exclusions = [t.term for t in terminology if t.kind == "exclusion"]
        source_classes = charter.get("source_classes") or [
            "scholarly",
            "standards",
            "implementation",
            "news",
        ]
        lanes: list[ResearchLane] = []
        for idx, angle in enumerate(self.angle_taxonomy):
            lane_id = f"LANE-{angle.upper().replace(' ', '_')[:20]}"
            cls = source_classes[idx % len(source_classes)]
            q = f"{angle}: {concepts[0]}"
            lanes.append(
                ResearchLane(
                    lane_id=lane_id,
                    angle=angle,
                    purpose=f"Cover {angle} for charter objective",
                    source_classes=[cls],
                    query_concepts=concepts[:3],
                    unique_queries=[q, f"{angle} evidence {concepts[0]}"],
                    expected_evidence=f"{angle} primary or secondary sources",
                    stop_rule={"result_cap": 8, "max_cost_usd": 1.5},
                    decision_value=f"Unique coverage of {angle}",
                )
            )
        for special in REQUIRED_SPECIAL_LANES:
            lane_id = f"LANE-{special.upper()}"
            lanes.append(
                ResearchLane(
                    lane_id=lane_id,
                    angle=special,
                    purpose=f"Mandatory {special.replace('_', ' ')} lane",
                    source_classes=["scholarly", "implementation"],
                    query_concepts=concepts[:2],
                    unique_queries=[f"{special} {concepts[0]}", f"counterevidence {concepts[0]}"],
                    expected_evidence="contradicting or deployment evidence",
                    stop_rule={"result_cap": 6, "max_cost_usd": 1.0},
                    decision_value=f"Required {special}",
                )
            )
        if exclusions:
            for lane in lanes:
                lane.stop_rule["exclusions"] = exclusions[:5]
        return lanes

    def compute_overlap_scores(self, lanes: list[ResearchLane]) -> list[ResearchLane]:
        for i, lane in enumerate(lanes):
            concepts_i = set(lane.query_concepts) | _tokenize(" ".join(lane.unique_queries))
            max_overlap = 0.0
            for j, other in enumerate(lanes):
                if i == j:
                    continue
                concepts_j = set(other.query_concepts) | _tokenize(" ".join(other.unique_queries))
                if lane.source_classes == other.source_classes:
                    max_overlap = max(max_overlap, _jaccard(concepts_i, concepts_j))
            lane.overlap_score = round(max_overlap, 4)
        return lanes

    def review_and_merge(
        self,
        lanes: list[ResearchLane],
        *,
        merge_threshold: float = 0.85,
    ) -> list[ResearchLane]:
        """Merge redundant lanes; keep required special lanes."""
        active: list[ResearchLane] = []
        seen_angles: set[str] = set()
        for lane in sorted(lanes, key=lambda ln: ln.overlap_score):
            if lane.angle in REQUIRED_SPECIAL_LANES:
                active.append(lane)
                continue
            if lane.overlap_score >= merge_threshold and lane.angle in seen_angles:
                lane.state = LaneState.CANCELED
                continue
            if lane.angle in seen_angles:
                lane.state = LaneState.CANCELED
                continue
            seen_angles.add(lane.angle)
            if not lane.decision_value:
                lane.decision_value = f"Covers {lane.angle}"
            active.append(lane)
        for lane in active:
            if not lane.decision_value:
                lane.decision_value = f"Covers {lane.angle}"
        return active

    def _assert_taxonomy_only(self, payload: dict[str, Any]) -> None:
        for key in payload:
            if key in _FORBIDDEN_OUTPUT_KEYS:
                raise ValueError(f"Landscape mapper must not emit {key}")
        blob = str(payload).lower()
        for word in ("recommend", "we should", "best approach"):
            if word in blob and "recommendation" not in blob:
                pass
