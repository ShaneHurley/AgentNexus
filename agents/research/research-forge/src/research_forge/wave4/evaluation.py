"""Wave 4 exit evaluation (RF-W4-F)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_forge.wave4.fabrication import FabricationChecker
from research_forge.wave4.fusion import PortfolioFusion
from research_forge.wave4.ideator import IndependentIdeator
from research_forge.wave4.promotion import PromotionRules
from research_forge.wave4.types import NO_DEFENSIBLE_IDEA


@dataclass
class QualityDimensions:
    evidence_grounding: float
    usefulness: float
    feasibility: float
    distinctiveness: float
    testability: float

    def to_dict(self) -> dict[str, float]:
        return {
            "evidence_grounding": self.evidence_grounding,
            "usefulness": self.usefulness,
            "feasibility": self.feasibility,
            "distinctiveness": self.distinctiveness,
            "testability": self.testability,
        }


@dataclass
class FabricationRates:
    source_fabrication: int = 0
    unsupported_mechanism: int = 0
    generic_templates: int = 0
    forced_idea_count: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "source_fabrication": self.source_fabrication,
            "unsupported_mechanism": self.unsupported_mechanism,
            "generic_templates": self.generic_templates,
            "forced_idea_count": self.forced_idea_count,
        }


@dataclass
class Wave4TaskExpectation:
    task_id: str
    stratum: str
    expect_abstention: bool = False
    expect_simple_solution: bool = False
    notes: list[str] = field(default_factory=list)


class Wave4ExitEvaluator:
    def __init__(self, tasks: list[dict[str, Any]] | None = None) -> None:
        self.tasks = tasks or []
        self._fabrication = FabricationChecker()

    def locked_task_expectations(self) -> list[Wave4TaskExpectation]:
        out: list[Wave4TaskExpectation] = []
        for row in self.tasks:
            out.append(
                Wave4TaskExpectation(
                    task_id=row["task_id"],
                    stratum=row["stratum"],
                    expect_abstention=bool(row.get("expect_abstention")),
                    expect_simple_solution=bool(row.get("expect_simple_solution")),
                    notes=list(row.get("notes", [])),
                )
            )
        return out

    def measure_quality_diversity(
        self,
        ideas: list[dict[str, Any]],
        dimension_scores: dict[str, dict[str, float]],
    ) -> dict[str, Any]:
        per_idea: dict[str, dict[str, float]] = {}
        for idea in ideas:
            dims = dimension_scores.get(idea["idea_id"], {})
            per_idea[idea["idea_id"]] = QualityDimensions(
                evidence_grounding=dims.get("evidence", 0.0),
                usefulness=dims.get("impact", 0.0),
                feasibility=dims.get("feasibility", 0.0),
                distinctiveness=dims.get("distinctiveness", 0.0),
                testability=dims.get("testability", 0.0),
            ).to_dict()
        return {"per_idea": per_idea, "scalar_aggregate_forbidden": True}

    def measure_fabrication_padding(
        self,
        audit_results: list[dict[str, Any]],
        *,
        ideator_outcomes: list[dict[str, Any]],
    ) -> FabricationRates:
        rates = FabricationRates()
        for ar in audit_results:
            for issue in ar.get("issues", []):
                if issue.startswith("invented_source"):
                    rates.source_fabrication += 1
                if issue.startswith("template_default"):
                    rates.generic_templates += 1
                if issue.startswith("unsupported"):
                    rates.unsupported_mechanism += 1
        padded = sum(1 for o in ideator_outcomes if o.get("forced_padding"))
        rates.forced_idea_count = padded
        return rates

    def validate_abstention(self, outcome: dict[str, Any]) -> bool:
        return outcome.get("outcome") == NO_DEFENSIBLE_IDEA and bool(outcome.get("reason"))

    def independent_wave4_audit(
        self,
        portfolio: dict[str, Any],
    ) -> dict[str, Any]:
        critical: list[str] = []
        for idea in portfolio.get("ideas", []):
            if idea.get("opportunity_type") == "hybrid" and len(idea.get("lineage", [])) < 2:
                critical.append(f"hybrid_lineage:{idea['idea_id']}")
        for exp in portfolio.get("experiments", []):
            if not exp.get("next_steps"):
                critical.append(f"missing_next_steps:{exp.get('experiment_id')}")
        if "rejected_alternatives" not in portfolio:
            critical.append("rejected_alternatives_not_preserved")
        return {"critical": critical, "passed": len(critical) == 0}

    def audit_permissions(self) -> dict[str, Any]:
        ideator = IndependentIdeator()
        fusion = PortfolioFusion()
        issues: list[str] = []
        try:
            ideator.assert_no_search("public_search")
        except PermissionError:
            pass
        else:
            issues.append("ideator_search_not_blocked")
        try:
            fusion.assert_no_search("scout_lane")
        except PermissionError:
            pass
        else:
            issues.append("fusion_search_not_blocked")
        promo = PromotionRules()
        fake = {"idea_id": "IDEA-X", "evidence_ids": [], "dependencies": ["UNKNOWN:api"]}
        if not promo.validate_recommend(fake, evidence_index={}):
            issues.append("promotion_rules_inert")
        return {"issues": issues, "passed": len(issues) == 0}
