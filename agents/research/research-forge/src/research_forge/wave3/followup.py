"""Targeted follow-up loop (RF-W3-E)."""

from __future__ import annotations

from typing import Any

from research_forge.errors import ErrorCode, forge_error
from research_forge.wave3.types import DEFAULT_FOLLOWUP_MAX_ROUNDS


class FollowUpPolicyError(PermissionError):
    pass


class FollowUpCoordinator:
    role_id = "followup_coordinator"
    allowed_tools: tuple[str, ...] = ("scout_lane", "curator_triage")

    def __init__(self, *, max_rounds: int = DEFAULT_FOLLOWUP_MAX_ROUNDS) -> None:
        self.max_rounds = max_rounds
        self._rounds_by_gap: dict[str, int] = {}
        self._history: list[dict[str, Any]] = []

    def validate_request(self, req: dict[str, Any]) -> list[str]:
        required = (
            "gap_id",
            "decision_relevance",
            "inspected_evidence_ids",
            "desired_source_type",
            "query",
            "budget_usd",
            "stop_condition",
        )
        errors: list[str] = []
        for field in required:
            if not req.get(field):
                errors.append(f"missing:{field}")
        if req.get("query", "").strip().lower() in ("research more", "find more sources"):
            errors.append("generic_query_forbidden")
        return errors

    def authorize(
        self,
        req: dict[str, Any],
        *,
        orchestrator_approved: bool,
        budget_approved: bool,
        self_spawn: bool = False,
    ) -> dict[str, Any]:
        if self_spawn:
            raise FollowUpPolicyError("Follow-up cannot self-spawn")
        errors = self.validate_request(req)
        if errors:
            return {"authorized": False, "errors": errors}
        if not orchestrator_approved or not budget_approved:
            return {"authorized": False, "errors": ["authorization_denied"]}
        gap_id = req["gap_id"]
        rounds = self._rounds_by_gap.get(gap_id, 0)
        if rounds >= self.max_rounds and not req.get("high_stakes_override"):
            return {"authorized": False, "errors": ["max_rounds_exceeded"]}
        return {"authorized": True, "errors": [], "round_index": rounds + 1}

    def execute_lane(
        self,
        req: dict[str, Any],
        *,
        scout_run: dict[str, Any],
        curator_decisions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        auth = self.authorize(
            req,
            orchestrator_approved=True,
            budget_approved=True,
        )
        if not auth["authorized"]:
            return {"status": "denied", **auth}
        gap_id = req["gap_id"]
        self._rounds_by_gap[gap_id] = self._rounds_by_gap.get(gap_id, 0) + 1
        gain = self._measure_information_gain(req, scout_run, curator_decisions)
        record = {
            "gap_id": gap_id,
            "lane": req.get("lane_id", "followup"),
            "round": self._rounds_by_gap[gap_id],
            "information_gain": gain,
            "scout_candidates": len(scout_run.get("candidates", [])),
        }
        self._history.append(record)
        if gain == "none" and self._rounds_by_gap[gap_id] >= self.max_rounds:
            record["gap_resolution"] = "UNKNOWN"
        return {"status": "completed", **record}

    def _measure_information_gain(
        self,
        req: dict[str, Any],
        scout_run: dict[str, Any],
        curator_decisions: list[dict[str, Any]],
    ) -> str:
        if scout_run.get("forced_no_gain"):
            return "none"
        deep = [d for d in curator_decisions if d.get("status") in ("DEEP_READ", "FOLLOW_CITATIONS")]
        if not deep:
            return "none"
        if req.get("expected_resolution") == "narrow":
            return "narrowed"
        return "resolved"

    def enforce_budget_exhaustion(self, available_usd: float, req_budget: float) -> Any:
        if req_budget > available_usd:
            return forge_error(ErrorCode.BUDGET_EXCEEDED, "Follow-up budget exceeds available")
        return None

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)

    def assert_no_bypass(self, workflow_id: str) -> None:
        if workflow_id not in ("scout", "curator", "extractor", "verifier", "followup_coordinator"):
            raise FollowUpPolicyError("No new workflow bypass allowed")
