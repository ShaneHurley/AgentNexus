"""Wave 3 exit evaluation (RF-W3-G)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_forge.wave3.auditor import ResearchAuditor
from research_forge.wave3.followup import FollowUpCoordinator
from research_forge.wave3.methods import MethodsReviewer
from research_forge.wave3.skeptic import AdversarialSkeptic


@dataclass
class ScrutinyMetrics:
    methods_flags: int = 0
    contradictions_found: int = 0
    audit_critical: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "methods_flags": self.methods_flags,
            "contradictions_found": self.contradictions_found,
            "audit_critical": self.audit_critical,
            "cost_usd": self.cost_usd,
        }


@dataclass
class ScrutinyComparison:
    task_id: str
    wave2: ScrutinyMetrics
    wave3: ScrutinyMetrics
    improved: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "wave2": self.wave2.to_dict(),
            "wave3": self.wave3.to_dict(),
            "improved": self.improved,
            "notes": self.notes,
        }


class Wave3ExitEvaluator:
    def __init__(self, calibration: dict[str, Any] | None = None) -> None:
        self.calibration = calibration or {}

    def run_locked_scrutiny_suite(
        self,
        task_id: str,
        packet: dict[str, Any],
        *,
        wave2_baseline: ScrutinyMetrics,
        wave3_result: dict[str, Any],
    ) -> ScrutinyComparison:
        w3 = ScrutinyMetrics(
            methods_flags=len(wave3_result.get("methods_flags", [])),
            contradictions_found=len(wave3_result.get("contradictions", [])),
            audit_critical=sum(
                1
                for f in wave3_result.get("audit", {}).get("findings", [])
                if f.get("severity") == "critical"
            ),
            cost_usd=float(wave3_result.get("cost_usd", 0.0)),
        )
        improved = (
            w3.methods_flags >= wave2_baseline.methods_flags
            and w3.contradictions_found >= wave2_baseline.contradictions_found
        ) or w3.audit_critical > wave2_baseline.audit_critical
        notes: list[str] = []
        if w3.cost_usd > wave2_baseline.cost_usd:
            notes.append("wave3_cost_higher_expected")
        return ScrutinyComparison(
            task_id=task_id,
            wave2=wave2_baseline,
            wave3=w3,
            improved=improved,
            notes=notes,
        )

    def calibrate_reviewer_noise(self, labeled: list[dict[str, Any]]) -> dict[str, Any]:
        tp = fp = fn = 0
        for row in labeled:
            pred = row.get("predicted_critical", False)
            actual = row.get("actual_critical", False)
            if pred and actual:
                tp += 1
            elif pred and not actual:
                fp += 1
            elif not pred and actual:
                fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / (tp + fn) if (tp + fn) else 1.0
        thresholds = self.calibration.get("severity_thresholds", {})
        return {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": precision,
            "recall": recall,
            "thresholds": thresholds,
        }

    def validate_bounded_followup(self, coordinator: FollowUpCoordinator, attempts: int) -> dict[str, Any]:
        max_rounds = coordinator.max_rounds
        uncontrolled = attempts > max_rounds * 3
        return {
            "max_rounds": max_rounds,
            "attempts_observed": attempts,
            "uncontrolled_recursive_search": uncontrolled,
            "passed": not uncontrolled,
        }

    def audit_wave3_permissions(self) -> dict[str, Any]:
        issues: list[str] = []
        skeptic = AdversarialSkeptic()
        methods = MethodsReviewer()
        auditor = ResearchAuditor()
        if methods.allowed_tools and "search" in " ".join(methods.allowed_tools):
            issues.append("methods_search_leak")
        try:
            skeptic.assert_no_search("public_search")
        except PermissionError:
            pass
        else:
            issues.append("skeptic_search_not_blocked")
        if not auditor.allowed_tools:
            issues.append("auditor_tools_empty_expected")
        critical = [i for i in issues if "search" in i or "injection" in i]
        return {
            "issues": issues,
            "critical": critical,
            "passed": len(critical) == 0,
        }
