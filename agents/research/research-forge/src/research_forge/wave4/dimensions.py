"""Portfolio dimension scoring (RF-W4-B-04)."""

from __future__ import annotations

from typing import Any

from research_forge.wave4.types import PORTFOLIO_DIMENSIONS


class PortfolioDimensions:
    def score(self, idea: dict[str, Any], *, compatibility: float = 0.5) -> dict[str, float]:
        evidence_ids = idea.get("evidence_ids") or []
        assumptions = idea.get("assumptions") or []
        has_fals = bool(idea.get("falsification_test"))
        raw: dict[str, float] = {
            "evidence": min(1.0, len(evidence_ids) * 0.25),
            "root_cause_fit": 0.7 if idea.get("root_cause_model") else 0.2,
            "impact": 0.6,
            "feasibility": 0.55 if not assumptions else 0.45,
            "testability": 0.9 if has_fals else 0.1,
            "risk": 0.4,
            "cost": 0.5,
            "reversibility": 0.65 if "rollback" in " ".join(idea.get("failure_modes") or []) else 0.4,
            "robustness": 0.5,
            "distinctiveness": 0.7 if idea.get("distinctiveness") else 0.3,
            "compatibility": compatibility,
        }
        for key in PORTFOLIO_DIMENSIONS:
            raw.setdefault(key, 0.0)
        return raw

    def score_batch(self, ideas: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
        return {i["idea_id"]: self.score(i) for i in ideas}
