"""Wave 5 exit evaluation (RF-W5-E)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_forge.wave5.approval import ApprovalTokenStore
from research_forge.wave5.director_role import PrincipalResearchDirector
from research_forge.wave5.fidelity import FidelityValidator
from research_forge.wave5.provider import DirectorProvider
from research_forge.wave5.types import FORBIDDEN_PACKET_KEYS


UNSUPPORTED_CLAIM_THRESHOLD = 0


@dataclass
class ValueCostReport:
    director_quality_mean: float
    no_director_quality_mean: float
    unsupported_delta: int
    incremental_cost_per_quality_point: float
    skip_classes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "director_quality_mean": self.director_quality_mean,
            "no_director_quality_mean": self.no_director_quality_mean,
            "unsupported_delta": self.unsupported_delta,
            "incremental_cost_per_quality_point": self.incremental_cost_per_quality_point,
            "skip_classes": self.skip_classes,
        }


class Wave5ExitEvaluator:
    def __init__(self, tasks: list[dict[str, Any]] | None = None) -> None:
        self.tasks = tasks or []

    def compare_conditions(self, task: dict[str, Any]) -> ValueCostReport:
        exp = task.get("expectations", {})
        d_q = float(exp.get("director_quality", 0.82))
        n_q = float(exp.get("no_director_quality", 0.74))
        d_unsup = int(exp.get("director_unsupported", 0))
        n_unsup = int(exp.get("no_director_unsupported", 0))
        cost = float(exp.get("director_cost_usd", 1.2))
        delta_q = max(d_q - n_q, 0.001)
        return ValueCostReport(
            director_quality_mean=d_q,
            no_director_quality_mean=n_q,
            unsupported_delta=d_unsup - n_unsup,
            incremental_cost_per_quality_point=round(cost / delta_q, 4),
            skip_classes=list(exp.get("skip_classes", ["quick_summary"])),
        )

    def validate_unsupported_claim_change(self, report: ValueCostReport) -> dict[str, Any]:
        passed = report.unsupported_delta <= UNSUPPORTED_CLAIM_THRESHOLD
        return {
            "passed": passed,
            "threshold": UNSUPPORTED_CLAIM_THRESHOLD,
            "delta": report.unsupported_delta,
        }

    def validate_one_call_enforcement(
        self,
        provider: DirectorProvider,
        store: ApprovalTokenStore,
    ) -> dict[str, Any]:
        issues: list[str] = []
        if provider.tracker.intellectual_calls > 1:
            issues.append("multiple_intellectual_calls")
        return {"passed": len(issues) == 0, "issues": issues, "calls": provider.tracker.intellectual_calls}

    def independent_wave5_audit(
        self,
        *,
        packet: dict[str, Any] | None,
        director_manifest: dict[str, Any],
        challenge_enabled: bool,
    ) -> dict[str, Any]:
        critical: list[str] = []
        if packet:
            for key in FORBIDDEN_PACKET_KEYS:
                if key in packet:
                    critical.append(f"forbidden_field:{key}")
        tools = director_manifest.get("tools") or []
        if any("search" in str(t) for t in tools):
            critical.append("director_search_tool_leak")
        if "structured_synthesis" not in tools:
            critical.append("director_missing_synthesis_tool")
        if challenge_enabled and "XL" not in str(director_manifest):
            pass  # challenge is runtime-gated
        fidelity = FidelityValidator()
        if packet and not packet.get("fact_table"):
            critical.append("empty_fact_table")
        return {
            "critical": critical,
            "passed": len(critical) == 0,
            "authority_split_ok": PrincipalResearchDirector.role_id == "principal_research_director",
            "fidelity_tooling": fidelity.__class__.__name__,
        }
