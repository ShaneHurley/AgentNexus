from __future__ import annotations

from pathlib import Path

import pytest

from research_forge.schemas_pkg.registry import get_registry
from research_forge.wave1.charter import CharterPlanner


@pytest.fixture
def planner(repo_root: Path) -> CharterPlanner:
    return CharterPlanner(get_registry(repo_root))


def test_charter_immutable_hash(planner: CharterPlanner) -> None:
    req = {
        "topic": "Topic",
        "objective": "Obj",
        "intended_decision_or_use": "use",
        "required_output": "brief",
    }
    plan = planner.build_plan(req)
    charter = planner.freeze_charter(planner.draft_charter(req, plan))
    h1 = charter["charter_hash"]
    charter2 = dict(charter)
    charter2["objective"] = "Changed"
    h2 = planner._charter_hash(charter2)
    assert h1 != h2


def test_missing_negative_lane_fails(planner: CharterPlanner) -> None:
    bad_plan = {
        "plan_id": "p1",
        "charter_question_map": {"RQ-001": ["q"]},
        "source_classes": ["scholarly"],
        "inclusion_rules": [],
        "exclusion_rules": [],
        "recency": "5y",
        "initial_queries": ["q"],
        "negative_evidence_lane": {"lane_id": "NEG", "query_templates": []},
    }
    with pytest.raises(ValueError):
        planner._validate_plan_coherence(bad_plan, ["RQ-001"])
