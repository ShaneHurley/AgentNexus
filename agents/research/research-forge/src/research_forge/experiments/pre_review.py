"""Deterministic gate pre-review — required before any run."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_forge.experiments.config import data_allowlist_roots, load_experiment_config
from research_forge.experiments.store import ExperimentStore
from research_forge.schemas_pkg.registry import get_experiment_registry


def _norm_outcome(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


class ExperimentPreReviewer:
    role_id = "experiment_pre_reviewer"

    def __init__(
        self,
        package_root: Path,
        workspace_root: Path | None = None,
        store: ExperimentStore | None = None,
    ) -> None:
        self.package_root = package_root
        self.workspace_root = (workspace_root or package_root).resolve()
        self.store = store or ExperimentStore(
            self.workspace_root, package_root=self.package_root
        )
        self.cfg = load_experiment_config(self.package_root)
        self.registry = get_experiment_registry(self.package_root)

    def _resolve_data(self, data_path: str) -> Path:
        p = Path(data_path)
        if not p.is_absolute():
            p = (self.workspace_root / p).resolve()
        else:
            p = p.resolve()
        return p

    def _outside_allowlist(self, data_path: Path) -> bool:
        roots = data_allowlist_roots(self.workspace_root, self.cfg)
        for root in roots:
            try:
                data_path.relative_to(root)
                return False
            except ValueError:
                continue
        # also allow under experiments workspace itself
        try:
            data_path.relative_to(self.store.root)
            return False
        except ValueError:
            return True

    def review(self, experiment_id: str) -> dict[str, Any]:
        proposal = self.store.read_json(experiment_id, "proposal.json")
        if not proposal:
            raise FileNotFoundError(f"No proposal for {experiment_id}")

        thresholds = self.cfg.get("pre_review_thresholds", {})
        reasons: list[str] = []
        scores = {
            "actionable": 3,
            "usable_data": 3,
            "information_gain": 3,
            "time_cost": 2,
            "safety": 4,
        }

        impact = (proposal.get("decision_impact") or "").strip()
        if len(impact) < 20:
            scores["actionable"] = 1
            reasons.append("decision_impact_too_weak")
        else:
            scores["actionable"] = 4

        for field in (
            "expected_support",
            "expected_reject",
            "expected_inconclusive",
            "hypothesis",
            "why_run",
            "question",
        ):
            if not (proposal.get(field) or "").strip():
                scores["information_gain"] = 1
                reasons.append(f"missing_{field}")

        outcomes = [
            _norm_outcome(proposal.get("expected_support") or ""),
            _norm_outcome(proposal.get("expected_reject") or ""),
            _norm_outcome(proposal.get("expected_inconclusive") or ""),
        ]
        if all(outcomes) and len(set(outcomes)) < 3:
            scores["information_gain"] = 1
            reasons.append("expected_outcomes_not_discriminating")

        data_path = self._resolve_data(proposal["inputs"]["data_path"])
        kind = proposal["kind"]
        if kind == "python_unittest_benchmark":
            start_rel = proposal["inputs"].get("unittest_start") or proposal["inputs"]["data_path"]
            start_path = self._resolve_data(start_rel)
            if not start_path.exists():
                scores["usable_data"] = 1
                reasons.append("data_path_missing")
            elif start_path.is_dir() or start_path.is_file():
                scores["usable_data"] = 4
            else:
                scores["usable_data"] = 1
                reasons.append("data_path_missing")
            data_path = start_path
        elif not data_path.is_file():
            scores["usable_data"] = 1
            reasons.append("data_path_missing")
        else:
            size = data_path.stat().st_size
            if size == 0:
                scores["usable_data"] = 1
                reasons.append("data_file_empty")
            else:
                scores["usable_data"] = 4

        outside = self._outside_allowlist(data_path) if data_path.exists() else True
        requires_external = outside

        est = int(proposal.get("estimated_runtime_seconds", 30))
        reps = int(proposal.get("repetitions", 1))
        long_s = int(self.cfg.get("long_runtime_seconds", 300))
        long_r = int(self.cfg.get("long_repetitions", 5))
        requires_long = est > long_s or reps > long_r
        if requires_long:
            scores["time_cost"] = 5
        elif est > 60:
            scores["time_cost"] = 3
        else:
            scores["time_cost"] = 2

        requires_code = kind == "python_unittest_benchmark"
        if requires_code:
            scores["safety"] = 2
            # Code is allowed only with later approval; do not auto-reject solely for being code
        else:
            scores["safety"] = 4

        # Hard rejects
        if scores["actionable"] < int(thresholds.get("actionable", 3)):
            reasons.append("actionable_below_threshold")
        if scores["usable_data"] < int(thresholds.get("usable_data", 3)):
            reasons.append("usable_data_below_threshold")
        if scores["information_gain"] < int(thresholds.get("information_gain", 3)):
            reasons.append("information_gain_below_threshold")

        verdict = "REJECT" if reasons else "PASS"
        if verdict == "PASS":
            rationale = (
                "Proposal passed the structural gate checklist (distinct expected "
                "outcomes, usable local inputs, actionable decision impact); "
                "run still requires explicit approvals."
            )
        else:
            rationale = "Rejected: " + "; ".join(reasons)

        review: dict[str, Any] = {
            "experiment_id": experiment_id,
            "scores": scores,
            "verdict": verdict,
            "rationale": rationale,
            "rejection_reasons": reasons,
            "requires_long_approval": requires_long,
            "requires_code_approval": requires_code,
            "requires_external_data_approval": requires_external,
            "token_budget": 0,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
        self.registry.validate("experiment_pre_review", review)
        self.store.write_json(experiment_id, "pre-review.json", review)
        status = "rejected" if verdict == "REJECT" else "pre_reviewed"
        self.store.set_status(experiment_id, status, verdict=verdict)
        return review
