"""Wave 2 fan-out orchestrator (integrates W2-A..E)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from research_forge.adapters.search.mock import MockSearchAdapterV1
from research_forge.wave2.curator import SourceCurator
from research_forge.wave2.landscape import LandscapeMapper
from research_forge.wave2.saturation import ExpansionCoordinator, SaturationConfig, SaturationEngine
from research_forge.wave2.scheduler import FanOutScheduler
from research_forge.wave2.scout import SourceScout
from research_forge.wave2.types import ResearchLane, SchedulerLimits


def load_wave2_config(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "config" / "wave2.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class FanOutOrchestrator:
    """Difficulty-gated fan-out path layered on Wave 1 charter."""

    def __init__(self, repo_root: Path, *, search_fixtures: list[dict[str, Any]] | None = None) -> None:
        self.repo_root = repo_root
        self.cfg = load_wave2_config(repo_root)
        scout = SourceScout(MockSearchAdapterV1(search_fixtures))
        limits = SchedulerLimits.from_config(self.cfg.get("scheduler", {}))
        self.mapper = LandscapeMapper()
        self.scout = scout
        self.scheduler = FanOutScheduler(limits, scout)
        self.curator = SourceCurator(
            class_floors=self.cfg.get("curator", {}).get("source_class_floors")
        )
        sat_cfg = self.cfg.get("saturation", {})
        self.saturation = SaturationEngine(
            SaturationConfig(
                duplicate_window_rounds=int(sat_cfg.get("duplicate_window_rounds", 2)),
                min_new_sources_per_round=int(sat_cfg.get("min_new_sources_per_round", 1)),
                max_rounds_without_gain=int(sat_cfg.get("max_rounds_without_gain", 2)),
            )
        )
        self.expansion = ExpansionCoordinator(self.saturation)

    def should_fan_out(self, charter: dict[str, Any]) -> bool:
        routing = self.cfg.get("routing", {})
        questions = charter.get("research_questions") or []
        depth = charter.get("depth", "standard")
        min_depth = routing.get("fanout_min_depth", "standard")
        depth_rank = {"quick": 0, "standard": 1, "deep": 2, "thesis": 3}
        if depth_rank.get(depth, 1) < depth_rank.get(min_depth, 1):
            return False
        return len(questions) >= int(routing.get("fanout_min_questions", 2))

    def run(
        self,
        charter: dict[str, Any],
        *,
        run_id: str,
        seed_sources: list[dict[str, Any]] | None = None,
        max_lanes: int | None = None,
    ) -> dict[str, Any]:
        landscape = self.mapper.map_landscape(charter, seed_sources)
        lane_dicts = landscape["lanes"]
        lanes = [
            ResearchLane(
                lane_id=ln["lane_id"],
                angle=ln["angle"],
                purpose=ln["purpose"],
                source_classes=ln["source_classes"],
                query_concepts=ln["query_concepts"],
                unique_queries=ln["unique_queries"],
                expected_evidence=ln["expected_evidence"],
                stop_rule=ln["stop_rule"],
                overlap_score=ln.get("overlap_score", 0.0),
                decision_value=ln.get("decision_value", ""),
            )
            for ln in lane_dicts
        ]
        if max_lanes:
            lanes = lanes[:max_lanes]
        self.scheduler.load_lanes(lanes)
        lane_ids = [ln.lane_id for ln in lanes]
        scout_results = self.scheduler.dispatch_batch(run_id, lane_ids)

        all_candidates: list[dict[str, Any]] = []
        for sr in scout_results:
            all_candidates.extend(sr.get("candidates", []))

        triage = self.curator.triage(all_candidates, lane_id="aggregate")
        by_class: dict[str, list[dict[str, Any]]] = {}
        for c in all_candidates:
            by_class.setdefault(c.get("source_type", "unknown"), []).append(c)
        class_report = self.curator.enforce_class_floors(by_class)

        for idx, sr in enumerate(scout_results):
            self.saturation.record_round(
                sr["lane_id"],
                round_index=idx,
                new_canonical=len(sr.get("candidates", [])),
                new_independent=len(sr.get("candidates", [])),
                new_contradictions=0,
                new_claims=0,
                cost_usd=float(sr.get("spent_usd", 0)),
            )

        fan_in = self.scheduler.deterministic_fan_in()
        return {
            "run_id": run_id,
            "landscape": landscape,
            "scout_runs": scout_results,
            "triage": [d.to_dict() for d in triage],
            "class_floor_report": class_report,
            "fan_in": fan_in.to_dict(),
            "ledger_events": self.scheduler.events,
        }
