import json
from pathlib import Path
import pytest

from agent_core.context_runtime import context_pin, preview, bound_role_evidence
from agent_core.replay import replay, replay_fixture


CORPUS = Path(__file__).parent / "fixtures/codex-replay-v1.json"


def protected():
    return {"intent": "Keep user scope", "constraints": {"acceptance_criteria": ["No writes"]},
            "permissions": {"write": False}, "approval_hash": None, "plan_hash": "plan-id",
            "budget": {"tokens": 32000}, "pending_calls": []}


def test_complete_offline_corpus_never_invokes_a_provider_or_tool(monkeypatch):
    from agent_core.providers.codex_cli import CodexCLIProvider
    monkeypatch.setattr(CodexCLIProvider, "invoke", lambda *a: pytest.fail("live invocation in replay"))
    report = replay(CORPUS)
    assert report["ok"]
    assert len(report["results"]) == 12
    assert report["model_calls"] == report["tool_executions"] == 0
    assert report["evidence_kind"] == "transport_contract"


def test_wrong_expectation_fails_not_silently_accepted():
    fixture = json.loads(CORPUS.read_text())[0]
    fixture["expected"]["output"] = {"ok": False}
    assert not replay_fixture(fixture)["passed"]


def test_preview_bounds_entire_request_and_preserves_protected_fields():
    facts = protected()
    report = preview(facts, [{"id": str(i), "body": "x" * 1000} for i in range(20)],
                     prompt="instructions", tools=[{"name": "read"}], output_schema={"type": "object"},
                     provider_overhead_tokens=8192, max_output_tokens=1000)
    assert report["protected"] == facts
    assert len(report["evidence"]) <= 8
    assert report["evidence_tokens"] <= 4000
    assert report["request_estimated_tokens"] <= 32000
    assert report["expansion_refs"]
    with pytest.raises(ValueError):
        preview(facts, [], provider_overhead_tokens=32000)


def test_bound_evidence_leaves_role_inputs_and_authority_unchanged():
    packet = {"ORIGINAL_REQUEST": "original", "permissions": {"write": False},
              "plan": {"file_allowlist": ["a.py"]}, "acceptance_criteria": ["No scope expansion"],
              "research_digest": [{"claim": "x" * 2500} for _ in range(12)]}
    reduced = bound_role_evidence(packet)
    assert reduced["plan"] == packet["plan"]
    assert reduced["permissions"] == packet["permissions"]
    assert reduced["acceptance_criteria"] == packet["acceptance_criteria"]
    assert len(reduced["research_digest"]) < 12
    assert len(packet["research_digest"]) == 12
    assert reduced["evidence_estimated_tokens"] <= 4000


def test_context_variant_pins_are_stable_and_distinct():
    assert context_pin() == context_pin("baseline")
    assert context_pin()["context_policy_hash"] != context_pin("bounded-context-v1")["context_policy_hash"]
    with pytest.raises(ValueError): context_pin("invented")


def test_public_replay_and_preview(tmp_path, capsys):
    from agent_core.nexus_cli import main
    assert main(["eval", "--mode", "replay", "--input", str(CORPUS)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"]
    packet = tmp_path / "packet.json"
    packet.write_text(json.dumps({"protected": protected(), "evidence": [], "provider_overhead_tokens": 8192}))
    assert main(["tools", "context-preview", "--input", str(packet)]) == 0
    assert json.loads(capsys.readouterr().out)["request_estimated_tokens"] > 8192


def test_supervised_eval_rejects_api_provider_before_dispatch(tmp_path):
    from agent_core.supervised_evaluation import run_suite
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps({"version": 1, "id": "bad", "cases": [{"provider": "openai"}]}))
    with pytest.raises(ValueError): run_suite(tmp_path, suite)


def test_supervised_approval_pauses_without_repetition_or_automatic_approval(tmp_path, monkeypatch):
    from agent_core import supervised_evaluation as module
    import hashlib
    request = tmp_path / "request.txt"
    request.write_text("Implement the scoped fixture after plan approval.")
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps({"version": 1, "id": "fixture", "cases": [{
        "id": "code", "profile": "Code", "workspace": str(tmp_path), "request_file": str(request),
        "request_sha256": hashlib.sha256(request.read_bytes()).hexdigest(), "token_limit": 80000,
        "expected_status": "WAITING_HUMAN"}]}))
    calls = []
    class Process:
        returncode = 0
        def __init__(self, arguments, **kwargs): calls.append(arguments)
        def communicate(self, timeout=None):
            result = {"session_id": "session"} if len(calls) == 1 else {
                "status": "WAITING_HUMAN", "run_id": "run", "pending_approvals": [{"kind": "plan"}], "request": "Implement the scoped fixture after plan approval."}
            return json.dumps(result).encode(), b""
    monkeypatch.setattr(module.subprocess, "Popen", Process)
    monkeypatch.setattr(module, "native_metrics", lambda *a: {})
    report = module.run_suite(tmp_path, suite, repetitions=3)
    assert report["paused_for_approval"] and report["ok"]
    assert report["qualification"] == "not_evaluated"
    assert not report["results"][0]["task_complete"]
    assert len(calls) == 2
    assert "codex_cli" in calls[-1] and "--budget-usd" in calls[-1]
    assert not any("approve" in command or "--deadline-seconds" in command for command in calls)


def test_candidate_cannot_activate_through_a_normal_run(tmp_path):
    from agent_core.supervisor import Supervisor
    from agent_core.contracts import ContractDenied
    class Adapter:
        def snapshot(self, *args): return {"provider": "mock"}
    supervisor = Supervisor(tmp_path / "state", adapters={"daily-coder": Adapter()})
    session = supervisor.new_session(project=str(tmp_path))
    with pytest.raises(ContractDenied):
        supervisor.create_run(session["session_id"], "daily-coder", "inspect", tmp_path,
                              context_variant="bounded-context-v1")


@pytest.mark.parametrize("counts", [(None, None), (5, None), (None, 2)])
def test_receipt_with_missing_usage_never_becomes_reported_zero(tmp_path, counts):
    from agent_core.supervised_evaluation import native_metrics
    from daily_coder.state_store import StateStore
    from daily_coder.artifacts import ArtifactStore
    import uuid
    runtime = tmp_path / "agents/coding/daily-coder-ecosystem/.daily-coder"
    state = StateStore(runtime / "state.sqlite")
    run = str(uuid.uuid4())
    state.create(run, "fixture", str(tmp_path), "pin", "create")
    ArtifactStore(runtime / "artifacts", state).put(run, "provider_usage", "runtime",
        {"input_tokens": counts[0], "output_tokens": counts[1], "cached_tokens": None})
    metrics = native_metrics(tmp_path, run)
    assert metrics["reported_tokens"] is None
    assert metrics["known_reported_tokens"] == sum(value for value in counts if value is not None)
    assert metrics["cached_tokens"] is None


def test_request_mutation_after_session_creation_cannot_change_dispatch(tmp_path, monkeypatch):
    from agent_core import supervised_evaluation as module
    import hashlib
    request = tmp_path / "request.txt"
    request.write_text("Original approved scope")
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps({"version": 1, "id": "fixture", "cases": [{
        "id": "code", "profile": "Code", "workspace": str(tmp_path), "request_file": str(request),
        "request_sha256": hashlib.sha256(request.read_bytes()).hexdigest(), "token_limit": 80000,
        "expected_status": "WAITING_HUMAN"}]}))
    calls = []
    class Process:
        returncode = 0
        def __init__(self, arguments, **kwargs): calls.append(arguments)
        def communicate(self, timeout=None):
            if len(calls) == 1:
                request.write_text("Changed unapproved scope")
                result = {"session_id": "session"}
            else:
                frozen = Path(calls[-1][calls[-1].index("--request-file") + 1])
                assert frozen != request
                assert frozen.read_text() == "Original approved scope"
                result = {"status": "WAITING_HUMAN", "run_id": "run", "request": frozen.read_text()}
            return json.dumps(result).encode(), b""
    monkeypatch.setattr(module.subprocess, "Popen", Process)
    monkeypatch.setattr(module, "native_metrics", lambda *a: {})
    report = module.run_suite(tmp_path, suite, repetitions=1)
    assert report["ok"] and report["results"][0]["request_pin_matches"]


def test_two_profiles_can_share_an_immutable_request(tmp_path):
    from agent_core.supervised_evaluation import run_suite
    import hashlib
    request = tmp_path / "request.txt"
    request.write_text("Same public investigation")
    case = {"id": "first", "profile": "Research", "workspace": str(tmp_path), "request_file": str(request),
            "request_sha256": hashlib.sha256(request.read_bytes()).hexdigest(), "token_limit": 80000,
            "expected_status": "COMPLETE"}
    suite = tmp_path / "suite.json"
    suite.write_text(json.dumps({"version": 1, "id": "same-request", "cases": [case, {**case, "id": "second"}]}))
    report = run_suite(tmp_path, suite, repetitions=1)
    assert len(report["results"]) == 2
    assert all(row["status"] == "BLOCKED" and row["model_calls"] == 0 for row in report["results"])
