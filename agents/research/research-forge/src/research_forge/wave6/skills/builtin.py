"""Built-in method skills (RF-W6-C-02..06)."""

from __future__ import annotations

from typing import Any

from research_forge.wave6.skills.manifest import SkillManifest


def _base(name: str, request_types: list[str], phases: list[str], schema: str) -> SkillManifest:
    return SkillManifest(
        name=name,
        version="1.0.0",
        request_types=request_types,
        required_inputs=["research_charter"],
        phases=phases,
        output_schemas=[schema],
        tool_budgets={"search_calls": 50, "read_pages": 100},
        acceptance_criteria=["reproducible_log", "explicit_boundaries"],
        prohibited_behaviors=["hidden_synthesis", "skip_screening_log"],
    )


SYSTEMATIC_REVIEW = _base(
    "systematic_review",
    ["literature_review", "evidence_synthesis"],
    ["search_log", "screening", "quality_appraisal", "synthesis"],
    "systematic_review.schema.json",
)

ARCHITECTURE_RESEARCH = _base(
    "architecture_research",
    ["architecture", "design_tradeoff"],
    ["requirements", "alternatives", "tradeoffs", "failure_modes", "decision_record"],
    "architecture_decision.schema.json",
)

FEASIBILITY_STUDY = _base(
    "feasibility_study",
    ["feasibility", "go_no_go"],
    ["technical", "economic", "operational", "regulatory", "schedule", "organization"],
    "feasibility_report.schema.json",
)

STATISTICAL_REVIEW = _base(
    "statistical_review",
    ["methods_audit", "stats_check"],
    ["study_type_check", "recompute_inputs", "uncertainty", "overclaim_scan"],
    "statistical_review.schema.json",
)

EXPERIMENT_DESIGN = _base(
    "experiment_design",
    ["experiment_plan"],
    ["hypothesis", "controls", "measurements", "thresholds", "safety", "rollback"],
    "experiment.schema.json",
)

ALL_SKILLS: dict[str, SkillManifest] = {
    s.name: s
    for s in (
        SYSTEMATIC_REVIEW,
        ARCHITECTURE_RESEARCH,
        FEASIBILITY_STUDY,
        STATISTICAL_REVIEW,
        EXPERIMENT_DESIGN,
    )
}


class SkillRunner:
    """Mock skill execution producing structured phase outputs."""

    def run(self, skill: SkillManifest, inputs: dict[str, Any]) -> dict[str, Any]:
        missing = [k for k in skill.required_inputs if k not in inputs]
        if missing:
            return {"error": "missing_inputs", "missing": missing}
        outputs = {phase: {"status": "completed", "log_ref": f"log-{phase}"} for phase in skill.phases}
        if skill.name == "feasibility_study":
            outputs["go_no_go"] = {"conditions": ["budget_confirmed", "regulatory_clear"], "decision": "conditional_go"}
        if skill.name == "experiment_design":
            hyp = inputs.get("hypothesis", "")
            if not hyp or hyp.lower().startswith("always true"):
                return {"error": "unfalsifiable_plan"}
        if skill.name == "architecture_research":
            outputs["decision_record"] = {
                "baseline": inputs.get("baseline", "status_quo"),
                "experiment": inputs.get("experiment_proposal", "pilot"),
            }
        return {"skill": skill.name, "version": skill.version, "phases": outputs}
