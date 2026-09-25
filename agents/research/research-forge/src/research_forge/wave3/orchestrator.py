"""Wave 3 scrutiny orchestrator (integrates W3-A..F)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from research_forge.wave3.auditor import ResearchAuditor
from research_forge.wave3.contradiction import ContradictionMapper
from research_forge.wave3.falsify import FalsificationDesigner
from research_forge.wave3.followup import FollowUpCoordinator
from research_forge.wave3.methods import MethodsReviewer
from research_forge.wave3.skeptic import AdversarialSkeptic


def load_wave3_config(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "config" / "wave3.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class ScrutinyOrchestrator:
    """Runs frozen-evidence scrutiny on fan-in packets (mock-by-default)."""

    def __init__(self, repo_root: Path, cfg: dict[str, Any] | None = None) -> None:
        self.repo_root = repo_root
        self.cfg = cfg or load_wave3_config(repo_root)
        self.methods = MethodsReviewer()
        self.mapper = ContradictionMapper()
        self.skeptic = AdversarialSkeptic(
            max_rounds=int(self.cfg.get("skeptic", {}).get("max_rounds", 3))
        )
        self.falsify = FalsificationDesigner()
        fu_cfg = self.cfg.get("followup", {})
        self.followup = FollowUpCoordinator(
            max_rounds=int(fu_cfg.get("max_rounds", 1)),
        )
        aud_cfg = self.cfg.get("auditor", {})
        self.auditor = ResearchAuditor(sample_rate=float(aud_cfg.get("sample_rate", 0.25)))

    def run(
        self,
        packet: dict[str, Any],
        *,
        sample_seed: int = 42,
        followup_request: dict[str, Any] | None = None,
        scout_run: dict[str, Any] | None = None,
        curator_decisions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        sources: dict[str, dict[str, Any]] = packet.get("sources", {})
        evidence: dict[str, dict[str, Any]] = packet.get("evidence", {})
        high_risk = bool(packet.get("high_risk_domain"))

        methods_reviews: list[dict[str, Any]] = []
        methods_flags: list[str] = []
        for sid, src in sources.items():
            cards = [evidence[eid] for eid in evidence if evidence[eid].get("source_id") == sid]
            review = self.methods.review(src, cards, high_risk_domain=high_risk)
            methods_reviews.append(review)
            methods_flags.extend(f["kind"] for f in review.get("flags", []))

        matrix = self.mapper.build_matrix(sources, evidence, packet.get("matrix_cells", []))
        conflicts = self.mapper.detect_conflicts(matrix)
        contradictions = self.mapper.to_contradiction_records(conflicts)
        gaps = self.mapper.generate_gaps(conflicts, missing_evidence=packet.get("missing_evidence"))

        skeptic_out = self.skeptic.run_review(
            leading_conclusions=packet.get("leading_conclusions", []),
            evidence=evidence,
            objections=packet.get("objections", []),
            responses=packet.get("skeptic_responses"),
            charter_frozen=packet.get("charter"),
        )

        falsify_out = self.falsify.design_tests(
            propositions=packet.get("propositions", []),
            hypotheses=packet.get("hypotheses", []),
            proposed_tests=packet.get("proposed_tests", []),
        )

        followup_out: dict[str, Any] | None = None
        if followup_request and scout_run is not None:
            followup_out = self.followup.execute_lane(
                followup_request,
                scout_run=scout_run,
                curator_decisions=curator_decisions or [],
            )

        adversarial = packet.get("adversarial_signals", [])
        audit = self.auditor.audit(
            packet,
            sample_seed=sample_seed,
            adversarial_signals=adversarial,
        )

        cost_usd = float(self.cfg.get("cost_estimate_usd", 0.35))

        return {
            "run_id": packet.get("run_id", "w3-scrutiny"),
            "methods_reviews": methods_reviews,
            "methods_flags": sorted(set(methods_flags)),
            "evidence_matrix": matrix,
            "contradictions": contradictions,
            "gaps": gaps,
            "skeptic": skeptic_out,
            "falsification": falsify_out,
            "followup": followup_out,
            "audit": audit,
            "cost_usd": cost_usd,
            "acceptance_blocked": audit.get("blocked", False),
        }
