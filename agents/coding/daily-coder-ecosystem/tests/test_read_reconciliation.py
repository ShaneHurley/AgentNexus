import json
import pytest
from agent_core.contracts import ContractDenied
from daily_coder.state_store import StateStore
from daily_coder.read_reconciliation import reconcile_read


def seed(tmp_path, tool="filesystem.read", expected=None, path=None):
    state = StateStore(tmp_path / "state.sqlite")
    state.create("run", "task", str(tmp_path), "pinned", "run:create")
    state.begin_tool_operation("op", "run", "researcher", "RESEARCH", tool, {"path": "missing"}, path=path, expected_output_hash=expected)
    state.set_status("run", "RECONCILIATION_REQUIRED")
    return state


def test_read_recovery_retains_pins_and_is_idempotent(tmp_path):
    state = seed(tmp_path)
    before = state.get("run")
    result = reconcile_read(state, "run", "op", actor="operator", acknowledge_unavailable=True)
    assert result["read_failed"] and result["reconciled_read"]
    assert state.get("run") == before
    assert reconcile_read(state, "run", "op", actor="operator", acknowledge_unavailable=True) == result
    assert state.pending_tool_operations("run") == []
    assert sum(event["kind"] == "read_result_unavailable" for event in state.events("run")) == 1


@pytest.mark.parametrize("tool,expected,path", [
    ("filesystem.write", "a"*64, "/target"),
    ("tests.run", None, None),
    ("network.fetch", None, None),
    ("filesystem.read", "a"*64, None),
    ("filesystem.list", None, "/target"),
])
def test_effectful_or_inconsistent_receipts_remain_pending(tmp_path,tool,expected,path):
    state = seed(tmp_path,tool,expected,path)
    with pytest.raises(ContractDenied):
        reconcile_read(state, "run", "op", actor="operator", acknowledge_unavailable=True)
    assert state.tool_operation("op")["state"] == "pending"


def test_acknowledgment_and_run_identity_required(tmp_path):
    state = seed(tmp_path)
    with pytest.raises(ContractDenied):
        reconcile_read(state, "run", "op", actor="operator")
    with pytest.raises(ContractDenied):
        reconcile_read(state, "different", "op", actor="operator", acknowledge_unavailable=True)
    assert state.tool_operation("op")["state"] == "pending"


def test_unknown_model_reservation_blocks_recovery(tmp_path):
    state = seed(tmp_path)
    with state._connect() as connection:
        connection.execute("INSERT INTO budget_reservations VALUES(?,?,?,?,?,NULL,NULL,'reserved',?,?)",
                           ("model","run","today",100,0.0,1.0,1.0))
    with pytest.raises(ContractDenied,match="unknown"):
        reconcile_read(state,"run","op",actor="operator",acknowledge_unavailable=True)
    assert state.tool_operation("op")["state"] == "pending"
