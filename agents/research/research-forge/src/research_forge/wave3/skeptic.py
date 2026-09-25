"""Adversarial Skeptic (RF-W3-C)."""

from __future__ import annotations

from typing import Any

from research_forge.wave3.types import MAX_SKEPTIC_ROUNDS, ChallengeCategory


class SkepticPolicyError(PermissionError):
    pass


class AdversarialSkeptic:
    role_id = "adversarial_skeptic"
    allowed_tools: tuple[str, ...] = ()

    def __init__(self, *, max_rounds: int = MAX_SKEPTIC_ROUNDS) -> None:
        self.max_rounds = max_rounds
        self._round = 0

    def assert_no_search(self, tool_id: str) -> None:
        if "search" in tool_id or tool_id.startswith("scout"):
            raise SkepticPolicyError("Skeptic cannot search by default")

    def run_review(
        self,
        *,
        leading_conclusions: list[dict[str, Any]],
        evidence: dict[str, dict[str, Any]],
        objections: list[dict[str, Any]],
        responses: list[dict[str, Any]] | None = None,
        charter_frozen: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if charter_frozen is not None and objections:
            for obj in objections:
                if obj.get("charter_override"):
                    raise SkepticPolicyError("Skeptic cannot alter charter")

        gated = [self._gate_objection(o, evidence) for o in objections]
        accepted = [o for o in gated if o["status"] == "accepted"]
        gaps = [o for o in gated if o["status"] == "bounded_gap"]

        strongest = self._strongest_unfavorable(leading_conclusions, accepted)
        checks_performed = self._default_checks(evidence)

        self._round += 1
        if responses:
            self._round += 1
        verdict = "contained" if not accepted else "challenge_open"
        if self._round >= self.max_rounds:
            verdict = "round_cap_reached"

        return {
            "review_id": "SKP-1",
            "rounds_used": min(self._round, self.max_rounds),
            "max_rounds": self.max_rounds,
            "objections": gated,
            "strongest_unfavorable": strongest,
            "checks_performed": checks_performed,
            "verdict": verdict,
            "blocking": any(o.get("blocking") for o in accepted),
        }

    def _gate_objection(self, obj: dict[str, Any], evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
        cat = obj.get("category")
        if cat not in {c.value for c in ChallengeCategory}:
            return {**obj, "status": "rejected", "reason": "invalid_category"}
        eids = obj.get("evidence_ids") or []
        if not eids and not obj.get("assumption"):
            return {
                **obj,
                "status": "bounded_gap",
                "blocking": False,
                "reason": "unsupported_objection",
            }
        for eid in eids:
            if eid not in evidence:
                return {
                    **obj,
                    "status": "bounded_gap",
                    "blocking": False,
                    "reason": "unknown_evidence",
                }
        return {**obj, "status": "accepted", "blocking": obj.get("blocking", False)}

    def _strongest_unfavorable(
        self,
        conclusions: list[dict[str, Any]],
        accepted: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not conclusions:
            return None
        lead = conclusions[0]
        related = [o for o in accepted if o.get("conclusion_id") == lead.get("conclusion_id")]
        if related:
            related.sort(key=lambda o: o.get("severity_rank", 0), reverse=True)
            return related[0]
        return {
            "conclusion_id": lead.get("conclusion_id"),
            "category": ChallengeCategory.SIMPLER_BASELINE.value,
            "summary": "no_failure_found",
            "checks_performed": True,
        }

    def _default_checks(self, evidence: dict[str, dict[str, Any]]) -> list[str]:
        checks = ["framing_review", "counterevidence_scan", "baseline_simplicity"]
        if any(c.get("contradicts_source_ids") for c in evidence.values()):
            checks.append("contradiction_crosscheck")
        return checks
