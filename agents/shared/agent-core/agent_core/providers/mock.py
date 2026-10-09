"""Offline mock provider for testing and dry-runs."""
from __future__ import annotations

from typing import Any

from agent_core.providers.base import Invocation, InvocationResult, Provider, TokenUsage


class MockProvider(Provider):
    """Offline contract exercise provider. Never requires external network or API keys."""
    name: str = "mock"

    def __init__(self, canned_responses: dict[str, Any] | None = None) -> None:
        self.canned_responses = canned_responses or {}
        self.invocations: list[Invocation] = []

    def invoke(self, request: Invocation) -> InvocationResult:
        self.invocations.append(request)
        if request.role in self.canned_responses:
            out = self.canned_responses[request.role]
            return InvocationResult(
                output=out if isinstance(out, dict) else {"content": str(out)},
                input_tokens=10,
                output_tokens=10,
                model="mock",
                usage=TokenUsage(input_tokens=10, output_tokens=10, total_tokens=20),
            )

        q = request.input_packet.get("request") or request.input_packet.get("ORIGINAL_REQUEST", "")
        outputs: dict[str, Any] = {
            "sizer": {"profile": request.input_packet.get("profile", "S"), "score": 0, "reasons": ["mock sizing"]},
            "researcher": {
                "question": "bounded repository reconnaissance",
                "scope": "read-only mock",
                "observations": [{"label": "UNKNOWN", "claim": "Mock observation", "locator": "mock:0"}],
                "unknowns": ["implementation ground truth"],
            },
            "brainstormer": {"options": [{"name": "conventional", "hypothesis": "Follow smallest verified change path."}], "no_better_angle_found": True},
            "master": {
                "intent": str(q),
                "non_goals": ["Unrequested refactors"],
                "invariants": ["Preserve user intent"],
                "chosen_approach": "Mock dry-run only",
                "rejected_alternatives": [],
                "scope": [],
                "risk": "unknown",
                "acceptance_criteria": ["Replace mock provider before modifying code"],
                "unresolved_questions": [],
            },
            "test_designer": {"criteria": [{"id": "AC-1", "behavior": "Configured provider is required for real edits", "proof": "provider conformance test"}], "test_required": False, "reason": "Mock run performs no code change."},
            "planner": {"change_units": [], "file_allowlist": [], "verification_commands": [], "rollback": "No changes to roll back.", "unresolved_questions": []},
            "plan_reviewer": {"verdict": "pass", "findings": [], "checked": ["No unresolved questions", "No write scope"]},
            "implementer": {"changed_files": [], "commands": [], "observations": ["Mock provider made no edits."]},
            "test_author": {"changed_test_files": [], "criterion_mapping": [], "negative_control": "not_applicable"},
            "test_executor": {"verdict": "pass", "commands": [], "evidence": ["Mock orchestration contract only"], "limitations": ["No repository tests executed"]},
            "code_reviewer": {"verdict": "pass", "findings": [], "reviewed_diff_first": True, "limitations": ["No diff"]},
            "documenter": {"changed_docs": [], "summary": "No code change to document."},
            "alignment_checker": {"verdict": "pass", "checks": {"intent_to_decision": True, "decision_to_plan": True, "plan_to_diff": True, "diff_to_tests": True, "diff_to_docs": True}, "findings": []},
            "skill_curator": {"verdict": "no_candidate", "reason": "No verified reusable procedure emerged."},
            "failure_diagnostician": {"failure_class": "orchestration", "first_failing_signal": "mock", "evidence": [], "recommended_action": "stop", "rationale": "Mock runs cannot diagnose real failures."},
            "frontier_advisor": {"decision": "No frontier decision is available in mock mode.", "rationale": "Mock provider", "confidence": "low", "missing_evidence": ["live provider"]},
        }
        out = outputs.get(request.role, {"status": "ok", "verdict": "pass"})
        return InvocationResult(
            output=out,
            input_tokens=50,
            output_tokens=50,
            model="mock",
            usage=TokenUsage(input_tokens=50, output_tokens=50, total_tokens=100),
        )
