"""Promotion rules and repair queue (RF-W4-B-05/06)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class PromotionError(ValueError):
    pass


@dataclass
class RepairQueue:
    max_attempts: int = 2
    attempts: dict[str, int] = field(default_factory=dict)
    log: list[dict[str, Any]] = field(default_factory=list)

    def enqueue(self, idea_id: str, missing: list[str]) -> dict[str, Any]:
        n = self.attempts.get(idea_id, 0)
        if n >= self.max_attempts:
            entry = {"idea_id": idea_id, "status": "cap_exceeded", "missing": missing}
            self.log.append(entry)
            return entry
        self.attempts[idea_id] = n + 1
        entry = {"idea_id": idea_id, "status": "repair_requested", "missing": missing, "attempt": n + 1}
        self.log.append(entry)
        return entry


class PromotionRules:
    def validate_recommend(
        self,
        idea: dict[str, Any],
        *,
        evidence_index: dict[str, dict[str, Any]],
        downgraded_sources: set[str] | None = None,
    ) -> list[str]:
        errors: list[str] = []
        downgraded = downgraded_sources or set()
        for eid in idea.get("evidence_ids") or []:
            card = evidence_index.get(eid)
            if not card:
                errors.append(f"missing_evidence:{eid}")
                continue
            if card.get("verifier_status") == "failed":
                errors.append(f"failed_citation:{eid}")
            sid = card.get("source_id")
            if sid and sid in downgraded:
                errors.append(f"downgraded_source:{sid}")
        for dep in idea.get("dependencies") or []:
            if dep.startswith("UNKNOWN:"):
                errors.append(f"critical_unknown_dependency:{dep}")
        if not idea.get("falsification_test"):
            errors.append("no_falsification_test")
        return errors

    def try_promote(
        self,
        idea: dict[str, Any],
        *,
        evidence_index: dict[str, dict[str, Any]],
        repair_queue: RepairQueue,
        downgraded_sources: set[str] | None = None,
    ) -> dict[str, Any]:
        errors = self.validate_recommend(idea, evidence_index=evidence_index, downgraded_sources=downgraded_sources)
        if not errors:
            return {"ok": True, "status": "recommended"}
        repairable = [
            e
            for e in errors
            if e.startswith(("missing_evidence", "no_falsification", "critical_unknown_dependency"))
        ]
        if repairable:
            repair_queue.enqueue(idea["idea_id"], repairable)
        return {"ok": False, "errors": errors}
