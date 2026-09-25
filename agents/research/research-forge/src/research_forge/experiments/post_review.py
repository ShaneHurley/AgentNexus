"""Post-run reviewer — descriptive LOCAL_OBSERVATION only."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_forge.experiments.store import ExperimentStore
from research_forge.schemas_pkg.registry import get_experiment_registry

_HIGHER_RE = re.compile(r"\b(higher|greater|larger|above)\b", re.IGNORECASE)


class ExperimentPostReviewer:
    role_id = "experiment_post_reviewer"

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
        self.registry = get_experiment_registry(self.package_root)

    def review(self, experiment_id: str) -> dict[str, Any]:
        proposal = self.store.read_json(experiment_id, "proposal.json")
        result = self.store.read_json(experiment_id, "result.json")
        if not proposal or not result:
            raise FileNotFoundError("proposal.json and result.json required for post-review")

        status = self.store.read_json(experiment_id, "status.json") or {}
        if status.get("status") == "running":
            raise RuntimeError("experiment still running; check status later")

        observed = self._classify(proposal, result)
        limitations = [
            "Local descriptive result only; not a controlled causal estimate.",
            "Sample limited to the provided local file or test suite.",
            "Transfer to the broader research question requires human or auditor judgment.",
        ]
        if result.get("exit_code", 1) != 0:
            limitations.append("Nonzero exit code; treat metrics as incomplete.")
            observed = "inconclusive"
        metrics = result.get("metrics") or {}
        if metrics.get("inconclusive"):
            observed = "inconclusive"
            limitations.append("Insufficient usable groups or rows for a discriminating comparison.")

        usability = "usable_descriptive"
        if observed == "inconclusive" or result.get("exit_code", 0) != 0:
            usability = "weak"

        summary = (
            f"Observed class={observed} for kind={proposal['kind']}. "
            f"Hypothesis under test: {proposal['hypothesis']}"
        )
        post: dict[str, Any] = {
            "experiment_id": experiment_id,
            "observed_class": observed,
            "summary": summary,
            "limitations": limitations,
            "evidence_usability": usability,
            "transfer_boundary": (
                "Do not treat this local observation as a general research conclusion "
                "or causal claim about the charter question."
            ),
            "status": "LOCAL_OBSERVATION",
            "not_a_causal_conclusion": True,
            "token_budget": 0,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
        self.registry.validate("experiment_post_review", post)
        self.store.write_json(experiment_id, "post-review.json", post)
        return post

    def _classify(self, proposal: dict[str, Any], result: dict[str, Any]) -> str:
        kind = proposal["kind"]
        metrics = result.get("metrics") or {}
        if kind == "group_comparison":
            return self._classify_group_comparison(proposal, metrics)
        if kind == "dataset_profile":
            if (
                result.get("exit_code", 1) == 0
                and int(metrics.get("row_count", 0)) > 0
                and bool(metrics.get("columns"))
            ):
                return "support"
            return "inconclusive"
        if kind == "python_unittest_benchmark":
            if result.get("exit_code", 1) == 0:
                return "support"
            return "reject"
        return "inconclusive"

    def _classify_group_comparison(
        self, proposal: dict[str, Any], metrics: dict[str, Any]
    ) -> str:
        if metrics.get("inconclusive"):
            return "inconclusive"
        means = metrics.get("group_means") or {}
        if not means:
            return "inconclusive"
        means_l = {str(k).lower(): float(v) for k, v in means.items()}
        hyp = (proposal.get("hypothesis") or "").lower()

        # (i) Word-boundary group A / group B path
        if re.search(r"\bgroup\s+a\b", hyp) and re.search(r"\bgroup\s+b\b", hyp):
            if "a" in means_l and "b" in means_l:
                if means_l["b"] > means_l["a"]:
                    return "support"
                if means_l["b"] < means_l["a"]:
                    return "reject"
                return "inconclusive"
            return "inconclusive"

        # (ii) Exactly two groups, both named as whole words, with a higher/greater claim
        if len(means_l) == 2 and _HIGHER_RE.search(hyp):
            labels = list(means_l.keys())
            if all(re.search(rf"\b{re.escape(label)}\b", hyp) for label in labels):
                positions = {
                    label: hyp.find(label) for label in labels if hyp.find(label) >= 0
                }
                if len(positions) == 2:
                    claimed_higher = min(positions, key=positions.get)
                    other = next(label for label in labels if label != claimed_higher)
                    if means_l[claimed_higher] > means_l[other]:
                        return "support"
                    if means_l[claimed_higher] < means_l[other]:
                        return "reject"
                    return "inconclusive"

        return "inconclusive"
