"""Wave 4 ideation orchestrator (integrates W4-A..F)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from research_forge.wave3.orchestrator import ScrutinyOrchestrator
from research_forge.wave4.dimensions import PortfolioDimensions
from research_forge.wave4.experiment import ExperimentArchitect
from research_forge.wave4.fabrication import FabricationChecker
from research_forge.wave4.fusion import PortfolioFusion
from research_forge.wave4.ideator import IndependentIdeator
from research_forge.wave4.lineage import LineageGraph
from research_forge.wave4.promotion import PromotionRules, RepairQueue
from research_forge.wave4.registry import IdeaRegistry


def load_wave4_config(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "config" / "wave4.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class IdeationOrchestrator:
    """Runs portfolio ideation on scrutiny-cleared packets (mock-by-default)."""

    def __init__(self, repo_root: Path, cfg: dict[str, Any] | None = None) -> None:
        self.repo_root = repo_root
        self.cfg = cfg or load_wave4_config(repo_root)
        self.scrutiny = ScrutinyOrchestrator(repo_root)
        self.ideator = IndependentIdeator()
        self.registry = IdeaRegistry()
        self.fusion = PortfolioFusion()
        self.experiment = ExperimentArchitect()
        self.fabrication = FabricationChecker()
        self.dimensions = PortfolioDimensions()
        self.promotion = PromotionRules()
        self.graph = LineageGraph()
        repair_cfg = self.cfg.get("repair", {})
        self.repair_queue = RepairQueue(max_attempts=int(repair_cfg.get("max_attempts", 2)))

    def _gate_scrutiny(self, packet: dict[str, Any]) -> dict[str, Any] | None:
        if packet.get("skip_scrutiny"):
            return packet.get("scrutiny_result")
        result = self.scrutiny.run(packet, sample_seed=int(self.cfg.get("audit_sample_seed", 42)))
        if result.get("acceptance_blocked") and not packet.get("human_override"):
            return result
        return result

    def run(
        self,
        packet: dict[str, Any],
        *,
        ideator_drafts: list[dict[str, Any]] | None = None,
        fusion_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scrutiny = self._gate_scrutiny(packet)
        if scrutiny and scrutiny.get("acceptance_blocked") and not packet.get("human_override"):
            return {
                "status": "blocked",
                "reason": "scrutiny_not_cleared",
                "scrutiny": scrutiny,
            }

        evidence = packet.get("evidence", {})
        downgraded = set(packet.get("downgraded_sources") or [])
        ideator_drafts = ideator_drafts or packet.get("ideator_drafts") or []
        ideator_outputs: list[dict[str, Any]] = []
        all_candidates: list[dict[str, Any]] = []

        if not ideator_drafts:
            for idx in range(int(self.cfg.get("parallel_ideators", 3))):
                ideator_outputs.append(self.ideator.run(packet, ideator_index=idx))
                all_candidates.extend(ideator_outputs[-1].get("candidates", []))
        else:
            for idx, draft in enumerate(ideator_drafts):
                out = self.ideator.run(packet, ideator_index=idx, draft=draft)
                ideator_outputs.append(out)
                if out.get("outcome"):
                    continue
                all_candidates.extend(out.get("candidates", []))

        abstentions = [o for o in ideator_outputs if o.get("outcome")]
        for idea in all_candidates:
            self.registry.add(idea)

        fab_audits = [self.fabrication.audit_idea(i, evidence) for i in all_candidates]
        dim_scores = self.dimensions.score_batch(all_candidates)

        experiments: list[dict[str, Any]] = []
        for idea in all_candidates:
            if any(a["idea_id"] == idea["idea_id"] and a["blocks_promotion"] for a in fab_audits):
                self.registry.reject(idea["idea_id"], "fabrication_check_failed")
                continue
            promo = self.promotion.try_promote(
                idea,
                evidence_index=evidence,
                repair_queue=self.repair_queue,
                downgraded_sources=downgraded,
            )
            if promo.get("ok"):
                self.registry.recommend(idea["idea_id"], "promotion_rules_passed")
            exp = self.experiment.design_for_idea(
                idea,
                seed_tests=(scrutiny or {}).get("falsification", {}).get("tests"),
            )
            experiments.append(exp)

        hybrid: dict[str, Any] | None = None
        interaction_review: dict[str, Any] | None = None
        compatibility_matrix: dict[str, dict[str, Any]] = {}
        if len(all_candidates) >= 2:
            compatibility_matrix = self.fusion.build_compatibility_matrix(all_candidates)
        if fusion_request and len(all_candidates) >= 2:
            parents = [c for c in all_candidates if c["idea_id"] in fusion_request.get("parent_ids", [])]
            if len(parents) >= 2:
                hybrid = self.fusion.create_hybrid(
                    run_id=packet.get("run_id", "run-w4"),
                    parents=parents,
                    selections=fusion_request.get("selections", []),
                    baseline_idea_id=fusion_request.get("baseline_idea_id", parents[0]["idea_id"]),
                    evidence=evidence,
                    graph=self.graph,
                )
                self.registry.add(hybrid)
                interaction_review = self.fusion.interaction_risk_review(hybrid, evidence)
                experiments.append(self.experiment.design_for_idea(hybrid))

        rejected = [i for i in self.registry.query(include_rejected=True) if i.get("status") == "rejected"]

        return {
            "status": "completed",
            "scrutiny": scrutiny,
            "ideator_outputs": ideator_outputs,
            "abstentions": abstentions,
            "ideas": self.registry.query(include_rejected=True),
            "dimension_scores": dim_scores,
            "fabrication_audits": fab_audits,
            "compatibility_matrix": compatibility_matrix,
            "hybrid": hybrid,
            "interaction_review": interaction_review,
            "experiments": experiments,
            "repair_log": self.repair_queue.log,
            "registry_events": self.registry.events,
            "rejected_alternatives": rejected,
            "lineage_components": {
                k: self.graph.trace_components(k) for k in self.graph.component_edges
            },
        }
