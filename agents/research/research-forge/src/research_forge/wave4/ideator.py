"""Independent Ideator (RF-W4-A)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from research_forge.hashing.content import hash_normalized_text
from research_forge.wave4.diversity import DiversityChecker
from research_forge.wave4.types import (
    IDEATOR_MAX_CANDIDATES,
    IDEATOR_MAX_FIELD_LEN,
    IDEATOR_MAX_TOTAL_CHARS,
    NO_DEFENSIBLE_IDEA,
    OPPORTUNITY_TO_SCHEMA,
    TACTICAL_OPPORTUNITY_TYPES,
)


class IdeatorPolicyError(PermissionError):
    pass


class IdeatorIsolationError(ValueError):
    pass


class IndependentIdeator:
    role_id = "ideator"
    allowed_tools: tuple[str, ...] = ()

    def __init__(self) -> None:
        self._diversity = DiversityChecker()

    def assert_no_search(self, tool: str) -> None:
        if "search" in tool.lower() or "scout" in tool.lower():
            raise IdeatorPolicyError(f"ideator cannot use {tool}")

    def validate_input(self, packet: dict[str, Any]) -> None:
        forbidden = packet.get("peer_ideas") or packet.get("other_ideas") or packet.get("portfolio")
        if forbidden:
            raise IdeatorIsolationError("ideator input must not include other ideas")
        if packet.get("audit", {}).get("veto"):
            raise IdeatorIsolationError("audit veto blocks ideation")

    def assign_opportunity_type(self, ideator_index: int) -> str:
        return TACTICAL_OPPORTUNITY_TYPES[ideator_index % len(TACTICAL_OPPORTUNITY_TYPES)]

    def _lineage_hash(self, lineage: list[str]) -> str:
        body = "|".join(sorted(lineage))
        return hash_normalized_text(body)

    def _next_idea_id(self, run_id: str, tactical: str, seq: int) -> str:
        digest = hashlib.sha256(f"{run_id}:{tactical}:{seq}".encode()).hexdigest()[:8]
        return f"IDEA-{digest.upper()}"

    def build_candidate_card(
        self,
        *,
        run_id: str,
        tactical_type: str,
        seq: int,
        root_cause: str,
        proposal: str,
        evidence_ids: list[str],
        verified_evidence: dict[str, dict[str, Any]],
        assumptions: list[str] | None = None,
        components: list[str] | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        assumptions = list(assumptions or [])
        for eid in evidence_ids:
            if eid not in verified_evidence:
                assumptions.append(f"Evidence {eid} unavailable; treat claim as assumption")
        card: dict[str, Any] = {
            "idea_id": self._next_idea_id(run_id, tactical_type, seq),
            "title": (title or proposal[:80])[:IDEATOR_MAX_FIELD_LEN],
            "lineage": [],
            "root_cause_model": root_cause[:IDEATOR_MAX_FIELD_LEN],
            "proposal": proposal[:IDEATOR_MAX_FIELD_LEN],
            "components": (components or [])[:20],
            "evidence_ids": evidence_ids,
            "assumptions": assumptions[:30],
            "expected_benefits": ["Reduced failure rate if mechanism holds"],
            "failure_modes": ["Mechanism wrong; rollback via baseline restore"],
            "dependencies": [],
            "costs": ["Engineering time bounded by charter"],
            "risks": ["Unverified dependency on production traffic shape"],
            "falsification_test": "Held-out trace shows no improvement versus baseline",
            "minimum_experiment": "A/B on 5% traffic for one week",
            "status": "active",
            "opportunity_type": OPPORTUNITY_TO_SCHEMA.get(tactical_type, "incremental"),
            "tactical_opportunity_type": tactical_type,
            "baseline": "Current production configuration",
            "distinctiveness": f"Distinct via {tactical_type} mechanism",
            "lineage_hash": self._lineage_hash([]),
        }
        return card

    def no_defensible_idea(self, tactical_type: str, reason: str) -> dict[str, Any]:
        return {
            "outcome": NO_DEFENSIBLE_IDEA,
            "tactical_opportunity_type": tactical_type,
            "reason": reason[:IDEATOR_MAX_FIELD_LEN],
            "candidates": [],
        }

    def enforce_bounds(self, candidates: list[dict[str, Any]]) -> None:
        if len(candidates) > IDEATOR_MAX_CANDIDATES:
            raise ValueError("ideator candidate count exceeds bound")
        total = 0
        for c in candidates:
            for key in ("proposal", "root_cause_model", "falsification_test"):
                total += len(str(c.get(key, "")))
        if total > IDEATOR_MAX_TOTAL_CHARS:
            raise ValueError("ideator output exceeds character bound")

    def run(
        self,
        packet: dict[str, Any],
        *,
        ideator_index: int = 0,
        draft: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.validate_input(packet)
        tactical = self.assign_opportunity_type(ideator_index)
        evidence = packet.get("evidence", {})
        charter = packet.get("charter", {})
        gaps = packet.get("gaps") or []
        run_id = packet.get("run_id", "run-w4")

        if draft and draft.get("outcome") == NO_DEFENSIBLE_IDEA:
            return self.no_defensible_idea(tactical, draft.get("reason", "insufficient evidence"))

        unresolved_high = [
            g for g in gaps if g.get("decision_relevance") == "high" and g.get("status") != "resolved"
        ]
        if draft is None and unresolved_high and tactical in ("combine", "replace"):
            return self.no_defensible_idea(
                tactical,
                "Unresolved high-relevance gaps block defensible architectural change",
            )

        if draft and draft.get("candidates"):
            candidates = list(draft["candidates"])
        elif draft and draft.get("proposal"):
            candidates = [
                self.build_candidate_card(
                    run_id=run_id,
                    tactical_type=tactical,
                    seq=0,
                    root_cause=draft.get("root_cause", charter.get("objective", "Unknown")),
                    proposal=draft["proposal"],
                    evidence_ids=list(draft.get("evidence_ids") or []),
                    verified_evidence=evidence,
                    components=list(draft.get("components") or []),
                    assumptions=list(draft.get("assumptions") or []),
                    title=draft.get("title"),
                )
            ]
        else:
            eids = [
                eid
                for eid, ev in evidence.items()
                if ev.get("verifier_status") == "passed" and ev.get("claim_status") in ("FACT", "INFERENCE")
            ][:3]
            candidates = [
                self.build_candidate_card(
                    run_id=run_id,
                    tactical_type=tactical,
                    seq=0,
                    root_cause=charter.get("objective", "Unknown root cause"),
                    proposal=f"Apply {tactical} lever on verified evidence",
                    evidence_ids=eids,
                    verified_evidence=evidence,
                    components=[f"{tactical}-component"],
                )
            ]

        self.enforce_bounds(candidates)
        flags = self._diversity.check_batch(candidates)
        return {
            "ideator_index": ideator_index,
            "tactical_opportunity_type": tactical,
            "candidates": candidates,
            "diversity_flags": flags,
            "external_search": False,
        }
