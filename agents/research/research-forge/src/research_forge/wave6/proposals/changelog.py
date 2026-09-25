"""Proposal changelog and provenance (RF-W6-E-08)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ChangelogEntry:
    proposal_id: str
    action: str
    actor: str
    reason: str
    tests: list[str]
    version: str
    outcome: str | None = None
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "action": self.action,
            "actor": self.actor,
            "reason": self.reason,
            "tests": self.tests,
            "version": self.version,
            "outcome": self.outcome,
            "at": self.at,
        }


class ProposalChangelog:
    def __init__(self) -> None:
        self.entries: list[ChangelogEntry] = []

    def record(self, entry: ChangelogEntry) -> None:
        self.entries.append(entry)

    def reconstruct(self, proposal_id: str) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self.entries if e.proposal_id == proposal_id]
