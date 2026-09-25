"""Post-run improvement proposal schema (RF-W6-E-01)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REQUIRED = (
    "proposal_id",
    "observed_failure",
    "evidence_refs",
    "affected_component",
    "proposed_change",
    "expected_benefit",
    "risks",
    "test_cases",
    "rollback_plan",
)

VALID_COMPONENTS = frozenset(
    {
        "model",
        "prompt",
        "orchestrator",
        "tool",
        "adapter",
        "source_policy",
        "context",
        "verifier",
        "judge",
        "budget",
    }
)


@dataclass
class ImprovementProposal:
    proposal_id: str
    observed_failure: str
    evidence_refs: list[str]
    affected_component: str
    proposed_change: dict[str, Any]
    expected_benefit: str
    risks: list[str]
    test_cases: list[str]
    rollback_plan: str
    failure_ids: list[str] = field(default_factory=list)

    def validate(self) -> list[str]:
        errors: list[str] = []
        for key in REQUIRED:
            val = getattr(self, key, None)
            if val is None or val == "" or val == [] or val == {}:
                errors.append(f"missing:{key}")
        if self.affected_component not in VALID_COMPONENTS:
            errors.append("invalid_component")
        if self.proposed_change.get("kind") == "vague_prompt_tweak":
            errors.append("vague_improve_prompt_invalid")
        if not self.failure_ids:
            errors.append("missing_failure_ids")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "observed_failure": self.observed_failure,
            "evidence_refs": self.evidence_refs,
            "affected_component": self.affected_component,
            "proposed_change": self.proposed_change,
            "expected_benefit": self.expected_benefit,
            "risks": self.risks,
            "test_cases": self.test_cases,
            "rollback_plan": self.rollback_plan,
            "failure_ids": self.failure_ids,
        }
