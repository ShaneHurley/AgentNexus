from __future__ import annotations

from pathlib import Path

from research_forge.wave1.orchestrator import RunState, Wave1Orchestrator


def test_e2e_mock_hashes_stable(repo_root: Path) -> None:
    orch = Wave1Orchestrator(repo_root, live=False)
    req = {
        "topic": "Alpha vs Beta efficacy",
        "objective": "Compare reported improvements",
        "intended_decision_or_use": "internal planning",
        "required_output": "brief",
        "desired_depth": "standard",
    }
    out1 = orch.run(req)
    assert out1["ok"]
    assert out1["report_hash"]
    assert out1["packet_hash"]

    orch2 = Wave1Orchestrator(repo_root, live=False)
    out2 = orch2.run(req)
    assert out2["report_hash"] == out1["report_hash"]
    assert out2["packet_hash"] == out1["packet_hash"]


def test_pause_resume_no_duplicate_search(repo_root: Path) -> None:
    orch = Wave1Orchestrator(repo_root, live=False)
    req = {"topic": "Redis vs Memcached for sessions"}
    paused = orch.run(req)
    assert paused.get("paused")
    sd = paused["state"]
    state = RunState(
        run_id=sd["run_id"],
        phase=sd["phase"],
        request=sd["request"],
        clarification=sd.get("clarification"),
        paused=sd.get("paused", True),
        resume_token=sd.get("resume_token"),
    )
    resumed = orch.resume(
        state,
        {"CLQ-001": "product decision", "CLQ-002": "brief", "CLQ-003": "cost"},
    )
    assert resumed["ok"]
    assert len(resumed["state"]["search_log"]) == 1
