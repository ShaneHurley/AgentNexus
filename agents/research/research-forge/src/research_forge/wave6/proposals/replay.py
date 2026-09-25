"""Frozen regression replay for proposals (RF-W6-E-04/05)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

RunFn = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


@dataclass
class ReplayBundle:
    proposal_id: str
    baseline_results: list[dict[str, Any]] = field(default_factory=list)
    proposed_results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "baseline_results": self.baseline_results,
            "proposed_results": self.proposed_results,
        }


class ProposalReplay:
    def __init__(self, run_fn: RunFn) -> None:
        self.run_fn = run_fn

    def replay(
        self,
        proposal_id: str,
        cases: list[dict[str, Any]],
        *,
        baseline_config: dict[str, Any],
        proposed_config: dict[str, Any],
    ) -> ReplayBundle:
        bundle = ReplayBundle(proposal_id=proposal_id)
        for case in cases:
            bundle.baseline_results.append(self.run_fn(case, baseline_config))
            bundle.proposed_results.append(self.run_fn(case, proposed_config))
        return bundle

    def evaluate_held_out(
        self, bundle: ReplayBundle, held_out: list[dict[str, Any]], *, proposed_config: dict[str, Any]
    ) -> dict[str, Any]:
        gains = 0
        regressions = 0
        for case in held_out:
            out = self.run_fn(case, proposed_config)
            if out.get("passed"):
                gains += 1
            elif out.get("regression"):
                regressions += 1
        threshold_met = gains > regressions and regressions == 0
        return {"gains": gains, "regressions": regressions, "promotion_threshold_met": threshold_met}
