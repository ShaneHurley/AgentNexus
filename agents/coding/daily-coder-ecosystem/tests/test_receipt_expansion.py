import uuid
import pytest
from daily_coder.tool_broker import ToolBroker, ToolDenied
from daily_coder.policy import PolicyGateway
from daily_coder.state_store import StateStore


def gateway(tmp_path):
    state = StateStore(tmp_path / "state.sqlite")
    run = str(uuid.uuid4())
    state.create(run, "inspect", str(tmp_path), "config", "created")
    tools = {"role_allowlists": {"researcher": ["filesystem.read"], "planner": ["filesystem.read"]},
             "disabled_until_adapter_configured": []}
    broker = ToolBroker(tmp_path, tools, {"path_policy": {"deny": [], "write_requires_plan_allowlist": True}})
    return PolicyGateway(broker, state, {}, True), run


def test_receipt_expansion_reauthorizes_run_role_and_current_tools(tmp_path):
    service, run = gateway(tmp_path)
    (tmp_path / "note.txt").write_text("public evidence\n")
    service.execute(run, "researcher", "RESEARCH", "filesystem.read", {"path": "note.txt"}, operation_id="read-1")
    result = service.execute(run, "researcher", "RESEARCH", "filesystem.read", {"operation_ref": "read-1", "limit": 30})
    assert result["historical_receipt"] and len(result["content"]) <= 30
    assert result["operation_ref"] == "read-1"
    with pytest.raises(ToolDenied):
        service.execute(run, "planner", "PLAN", "filesystem.read", {"operation_ref": "read-1"})
    service.broker.tools["role_allowlists"]["researcher"] = []
    with pytest.raises(ToolDenied):
        service.execute(run, "researcher", "RESEARCH", "filesystem.read", {"operation_ref": "read-1"})


def test_outline_is_gateway_owned_and_does_not_import_source(tmp_path):
    service, run = gateway(tmp_path)
    (tmp_path / "source.py").write_text("raise RuntimeError('must not run')\ndef sample(x:int): return x\n")
    result = service.execute(run, "researcher", "RESEARCH", "filesystem.read", {"path": "source.py", "view": "outline"})
    assert result["symbols"][0]["name"] == "sample"
    assert result["source_hash"]


def test_receipt_from_another_run_is_denied(tmp_path):
    service, run = gateway(tmp_path)
    (tmp_path / "note.txt").write_text("public evidence\n")
    service.execute(run, "researcher", "RESEARCH", "filesystem.read", {"path": "note.txt"}, operation_id="read-1")
    other = str(uuid.uuid4())
    service.state.create(other, "other", str(tmp_path), "config", "other-created")
    with pytest.raises(ToolDenied):
        service.execute(other, "researcher", "RESEARCH", "filesystem.read", {"operation_ref": "read-1"})


def test_last_role_turn_removes_tools_and_requests_an_honest_final_output(tmp_path):
    from daily_coder.orchestrator import Orchestrator
    from daily_coder.providers.mock import MockProvider
    from agent_core.providers.base import InvocationResult, ToolCall
    import shutil
    source = __import__("pathlib").Path(__file__).resolve().parents[1]
    package = tmp_path / "package"
    for folder in ("agents", "schemas", "skills", "config"):
        shutil.copytree(source / folder, package / folder)
    calls = []
    class Provider(MockProvider):
        def invoke(self, request):
            calls.append(request)
            if request.turn == 0:
                return InvocationResult(model="mock", input_tokens=10, output_tokens=10,
                                        tool_calls=[ToolCall("filesystem.read", {"path": "note.txt"}, "read")])
            assert not request.tools
            assert request.input_packet["TOOL_TURN_BUDGET"]["remaining_tool_rounds"] == 0
            return super().invoke(request)
    state = StateStore(tmp_path / "native.sqlite")
    engine = Orchestrator(package, state, Provider(), live=True)
    engine.config["role_tool_turns"]["researcher"] = 1
    run = engine.create("Inspect without writing", tmp_path)
    (tmp_path / "note.txt").write_text("public evidence")
    broker = ToolBroker(tmp_path, engine.tools_config, engine.policies)
    service = PolicyGateway(broker, state, engine.policies, True)
    result = engine._invoke(run, "researcher", "RESEARCH", {"ORIGINAL_REQUEST": "Inspect without writing"}, 0, "S", service)
    assert result["unknowns"] and len(calls) == 2
