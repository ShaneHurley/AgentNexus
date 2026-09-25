"""Proposal generator — verified failures only (RF-W6-E-02/03)."""

from __future__ import annotations

from typing import Any

from research_forge.wave6.proposals.schema import ImprovementProposal


class ProposalGenerator:
    def from_failures(self, failures: list[dict[str, Any]]) -> list[ImprovementProposal]:
        proposals: list[ImprovementProposal] = []
        for f in failures:
            if not f.get("verified"):
                continue
            if f.get("source") == "unaudited_feedback":
                continue
            component = f.get("component") or "orchestrator"
            prop = ImprovementProposal(
                proposal_id=f"prop-{f['failure_id']}",
                observed_failure=f.get("description") or "unknown",
                evidence_refs=list(f.get("evidence_refs") or []),
                affected_component=component,
                proposed_change=f.get("proposed_change") or {"kind": "config_patch", "target": component},
                expected_benefit=f.get("expected_benefit") or "reduce recurrence",
                risks=list(f.get("risks") or ["regression"]),
                test_cases=list(f.get("test_cases") or [f"replay-{f['failure_id']}"]),
                rollback_plan=f.get("rollback_plan") or "revert to prior version",
                failure_ids=[f["failure_id"]],
            )
            if not prop.validate():
                proposals.append(prop)
        return proposals
