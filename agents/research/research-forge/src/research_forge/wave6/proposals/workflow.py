"""Human merge workflow — no automatic merge (RF-W6-E-06)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_forge.wave6.proposals.schema import ImprovementProposal


@dataclass
class MergeApproval:
    proposal_id: str
    reviewer: str
    diff_inspected: bool
    evidence_reviewed: bool
    tests_reviewed: bool
    rollback_reviewed: bool
    signature: str

    def valid(self) -> bool:
        return all(
            [
                self.reviewer,
                self.diff_inspected,
                self.evidence_reviewed,
                self.tests_reviewed,
                self.rollback_reviewed,
                self.signature,
            ]
        )


class ProposalWorkflow:
    def __init__(self) -> None:
        self._merged: set[str] = set()
        self._log: list[dict[str, Any]] = []

    def attempt_auto_merge(self, proposal: ImprovementProposal) -> dict[str, Any]:
        entry = {"proposal_id": proposal.proposal_id, "merged": False, "reason": "automatic_merge_forbidden"}
        self._log.append(entry)
        return entry

    def human_merge(self, proposal: ImprovementProposal, approval: MergeApproval) -> dict[str, Any]:
        if proposal.validate():
            return {"merged": False, "reason": "invalid_proposal", "errors": proposal.validate()}
        if not approval.valid():
            return {"merged": False, "reason": "incomplete_review"}
        self._merged.add(proposal.proposal_id)
        entry = {"proposal_id": proposal.proposal_id, "merged": True, "reviewer": approval.reviewer}
        self._log.append(entry)
        return entry
