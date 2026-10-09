import pytest
from agent_core.contracts import ContractDenied
from research_forge.wave1.orchestrator import RunState, Wave1Orchestrator


def test_identical_research_requests_have_unique_runs(repo_root):
    req = {"topic": "Redis vs Memcached"}
    first = Wave1Orchestrator(repo_root).run(req)
    second = Wave1Orchestrator(repo_root).run(req)
    assert first["state"]["run_id"] != second["state"]["run_id"]


@pytest.mark.parametrize("phase", ["search", "read", "extract", "compose", "done"])
def test_nonpaused_resume_is_denied_without_phase_rewind(repo_root, phase):
    o = Wave1Orchestrator(repo_root)
    state = RunState(run_id="legacy", phase=phase, charter={"x": 1}, paused=False)
    with pytest.raises(ContractDenied, match="durable checkpoint"):
        o.resume(state, {})
    assert state.phase == phase
    assert not o.gateway.audit_log
