from __future__ import annotations

from pathlib import Path

import pytest

from research_forge.schemas_pkg.registry import get_registry
from research_forge.wave1.clarifier import IntakeClarifier


@pytest.fixture
def clarifier(repo_root: Path) -> IntakeClarifier:
    return IntakeClarifier(get_registry(repo_root))


def test_invalid_request_never_clarifies(clarifier: IntakeClarifier) -> None:
    with pytest.raises(Exception):
        clarifier.clarify({"topic": ""})


def test_complete_request_no_questions(clarifier: IntakeClarifier) -> None:
    req = {
        "topic": "Stable topic on caching",
        "objective": "Summarize cache eviction policies",
        "intended_decision_or_use": "architecture decision",
        "required_output": "brief",
        "desired_depth": "standard",
    }
    out = clarifier.clarify(req)
    assert out["result_type"] == "ready"


def test_ambiguous_compare_asks(clarifier: IntakeClarifier) -> None:
    out = clarifier.clarify({"topic": "Redis vs Memcached for session store"})
    assert out["result_type"] == "questions"
    assert len(out["questions"]) <= 3


def test_merge_preserves_original(clarifier: IntakeClarifier) -> None:
    original = {"topic": "Redis vs Memcached"}
    merged = clarifier.merge_clarification(
        original,
        {"CLQ-001": "product decision", "CLQ-002": "decision_report"},
    )
    assert merged["_clarification_provenance"]["original_request"]["topic"] == original["topic"]
    assert merged["required_output"] == "decision_report"
