"""Versioned workflow definitions.

A workflow maps a sizing profile to an ordered, resumable phase list. Definitions are
data, not code, so new routes can be added without touching the orchestrator.
"""
from __future__ import annotations

WORKFLOW_VERSION = "2.1"

_TAIL_FULL = ["IMPLEMENT", "TEST_AUTHOR", "TEST_EXECUTE", "CODE_REVIEW", "DOCUMENT", "ALIGNMENT", "ACCEPTANCE", "COMPLETE"]
_TAIL_TRIVIAL = ["IMPLEMENT", "TEST_EXECUTE", "CODE_REVIEW", "ALIGNMENT", "ACCEPTANCE", "COMPLETE"]

WORKFLOWS: dict[str, list[str]] = {
    # Contained S work: no research fan-out, no brainstorm; full build/review tail.
    "S": ["INTAKE", "SIZE", "DECIDE", "PLAN", "PLAN_REVIEW", "READY_TO_BUILD"] + _TAIL_FULL,
    # Trivial S work: skip test_author + documenter; keep ALIGNMENT for acceptance.
    "S_TRIVIAL": ["INTAKE", "SIZE", "DECIDE", "PLAN", "PLAN_REVIEW", "READY_TO_BUILD"] + _TAIL_TRIVIAL,
    "M": ["INTAKE", "SIZE", "RESEARCH", "DECIDE", "TEST_DESIGN", "PLAN", "PLAN_REVIEW", "READY_TO_BUILD"] + _TAIL_FULL,
    "L": ["INTAKE", "SIZE", "RESEARCH", "BRAINSTORM", "DECIDE", "TEST_DESIGN", "PLAN", "PLAN_REVIEW", "READY_TO_BUILD"] + _TAIL_FULL,
    "XL": ["INTAKE", "SIZE", "RESEARCH", "BRAINSTORM", "DECIDE", "TEST_DESIGN", "PLAN", "PLAN_REVIEW", "READY_TO_BUILD"] + _TAIL_FULL,
}

PHASE_ROLE: dict[str, str] = {
    "RESEARCH": "researcher", "BRAINSTORM": "brainstormer", "DECIDE": "master",
    "TEST_DESIGN": "test_designer", "PLAN": "planner", "PLAN_REVIEW": "plan_reviewer",
    "IMPLEMENT": "implementer", "TEST_AUTHOR": "test_author", "TEST_EXECUTE": "test_executor",
    "CODE_REVIEW": "code_reviewer", "DOCUMENT": "documenter", "ALIGNMENT": "alignment_checker",
    "DIAGNOSE": "failure_diagnostician",
}

# Phases the orchestrator handles itself rather than delegating to a role.
CONTROL_PHASES = {"INTAKE", "SIZE", "READY_TO_BUILD", "ACCEPTANCE", "COMPLETE"}

def workflow_for(key: str) -> list[str]:
    return list(WORKFLOWS.get(key, WORKFLOWS["M"]))

def role_for(phase: str) -> str | None:
    return PHASE_ROLE.get(phase)
