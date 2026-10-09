from pathlib import Path
import pytest
from agent_core.contracts import ContractDenied
from research_forge.wave1.orchestrator import RunState, Wave1Orchestrator
from research_forge.wave1.lifecycle import LifecycleJournal

REQUEST = {"topic":"Alpha vs Beta efficacy", "objective":"Compare reported improvements",
           "intended_decision_or_use":"internal planning", "required_output":"brief", "desired_depth":"standard"}

class Crash(BaseException):
    pass

def state_for(orch,run_id):
    return RunState.from_dict(orch.lifecycle(run_id)["checkpoint"]["state"])

def test_completed_call_before_checkpoint_is_not_replayed(repo_root,tmp_path,monkeypatch):
    orch=Wave1Orchestrator(repo_root,workspace=tmp_path)
    complete=LifecycleJournal.complete
    run_id=[]
    def crash(self,row,result,budget):
        complete(self,row,result,budget)
        run_id.append(self.directory.name)
        if row["auth"]["phase"] == "search":
            raise Crash()
    monkeypatch.setattr(LifecycleJournal,"complete",crash)
    with pytest.raises(Crash):
        orch.run(REQUEST)
    monkeypatch.setattr(LifecycleJournal,"complete",complete)
    restarted=Wave1Orchestrator(repo_root,workspace=tmp_path)
    def forbidden(*args,**kwargs):
        pytest.fail("completed search dispatched twice")
    monkeypatch.setattr(restarted.search,"search",forbidden)
    output=restarted.resume(state_for(restarted,run_id[0]))
    assert output["ok"]
    view=restarted.lifecycle(run_id[0])
    assert len(view["calls"]) == 3
    assert view["budget"]["spent_usd"] == pytest.approx(.05)
    assert all(c["accounting"] == "estimated" and c["reported_usd"] is None for c in view["calls"])
    assert restarted.resume(state_for(restarted,run_id[0])) == output

def test_incomplete_provider_call_retains_budget_and_never_replays(repo_root,tmp_path,monkeypatch):
    orch=Wave1Orchestrator(repo_root,workspace=tmp_path)
    def crash(*args,**kwargs):
        raise Crash()
    monkeypatch.setattr(orch.search,"search",crash)
    with pytest.raises(Crash):
        orch.run(REQUEST)
    run_id=next((tmp_path / "runs" / "wave1").iterdir()).name
    restarted=Wave1Orchestrator(repo_root,workspace=tmp_path)
    view=restarted.lifecycle(run_id)
    assert view["reconciliation_required"]
    assert view["budget"]["reserved_usd"] == pytest.approx(.01)
    with pytest.raises(ContractDenied,match="RECONCILIATION_REQUIRED"):
        restarted.resume(state_for(restarted,run_id))
    cancelled=restarted.cancel(run_id)
    assert cancelled["budget"]["reserved_usd"] == pytest.approx(.01)
    with pytest.raises(ContractDenied,match="RECONCILIATION_REQUIRED"):
        restarted.resume(state_for(restarted,run_id))
    assert not any(e["kind"] == "cancel_acknowledged" for e in restarted.lifecycle(run_id)["events"])

def test_configuration_change_and_legacy_state_fail_closed(repo_root,tmp_path):
    orch=Wave1Orchestrator(repo_root,workspace=tmp_path)
    paused=orch.run({"topic":"Alpha"})
    state=RunState.from_dict(paused["state"])
    changed=Wave1Orchestrator(repo_root,workspace=tmp_path)
    changed.max_sources=3
    with pytest.raises(ContractDenied,match="configuration"):
        changed.resume(state,{"CLQ-001":"planning"})
    state.run_id="legacy"
    with pytest.raises(ContractDenied,match="legacy"):
        orch.resume(state)

def test_cancel_idle_acknowledges_and_blocks_dispatch(repo_root,tmp_path):
    orch=Wave1Orchestrator(repo_root,workspace=tmp_path)
    paused=orch.run({"topic":"Alpha"})
    state=RunState.from_dict(paused["state"])
    assert orch.cancel(state.run_id)["cancel_requested"]
    with pytest.raises(ContractDenied,match="CANCELLED"):
        orch.resume(state)
    assert any(e["kind"] == "cancel_acknowledged" for e in orch.lifecycle(state.run_id)["events"])

def test_process_lock_rejects_second_executor(repo_root,tmp_path):
    orch=Wave1Orchestrator(repo_root,workspace=tmp_path)
    paused=orch.run({"topic":"Alpha"})
    state=RunState.from_dict(paused["state"])
    with LifecycleJournal(tmp_path,state.run_id).lock():
        with pytest.raises(ContractDenied,match="already executing"):
            Wave1Orchestrator(repo_root,workspace=tmp_path).resume(state)


def test_crash_before_call_start_restarts_safely(repo_root,tmp_path,monkeypatch):
    orch=Wave1Orchestrator(repo_root,workspace=tmp_path)
    prepare=LifecycleJournal.prepare
    def crash(*args,**kwargs):
        raise Crash()
    monkeypatch.setattr(LifecycleJournal,"prepare",crash)
    with pytest.raises(Crash):
        orch.run(REQUEST)
    run_id=next((tmp_path / "runs" / "wave1").iterdir()).name
    assert not orch.lifecycle(run_id)["calls"]
    monkeypatch.setattr(LifecycleJournal,"prepare",prepare)
    restarted=Wave1Orchestrator(repo_root,workspace=tmp_path)
    assert restarted.resume(state_for(restarted,run_id))["ok"]
    assert restarted.lifecycle(run_id)["budget"]["reserved_usd"] == 0


def test_load_state_prefers_committed_journal_over_projection(repo_root,tmp_path):
    from research_forge.wave1.persistence import load_run_state,state_path
    orch=Wave1Orchestrator(repo_root,workspace=tmp_path)
    paused=orch.run({"topic":"Alpha"})
    run_id=paused["state"]["run_id"]
    state_path(tmp_path,run_id).write_text("incomplete projection")
    state,meta=load_run_state(tmp_path,run_id)
    assert state.paused
    assert meta["live"] is False


def test_active_call_completion_then_cancel_blocks_next_provider(repo_root,tmp_path,monkeypatch):
    orch=Wave1Orchestrator(repo_root,workspace=tmp_path)
    search=orch.search.search
    def cancel_then_return(*args,**kwargs):
        run_id=next((tmp_path / "runs" / "wave1").iterdir()).name
        pending=orch.cancel(run_id)
        assert pending["reconciliation_required"]
        assert pending["budget"]["reserved_usd"] == pytest.approx(.01)
        return search(*args,**kwargs)
    monkeypatch.setattr(orch.search,"search",cancel_then_return)
    with pytest.raises(ContractDenied,match="CANCELLED"):
        orch.run(REQUEST)
    run_id=next((tmp_path / "runs" / "wave1").iterdir()).name
    view=orch.lifecycle(run_id)
    assert len(view["calls"]) == 1
    assert not view["reconciliation_required"]
    assert view["budget"]["reserved_usd"] == 0
    assert view["budget"]["spent_usd"] == pytest.approx(.01)
    assert any(e["kind"] == "cancel_acknowledged" for e in view["events"])


def test_preallocated_run_identity_and_backup(repo_root,tmp_path):
    alias="run-preallocated"
    orch=Wave1Orchestrator(repo_root,workspace=tmp_path)
    output=orch.run(REQUEST,run_id=alias)
    assert output["run_id"] == alias
    assert orch.run(REQUEST,run_id=alias) == output
    journal=LifecycleJournal(tmp_path,alias)
    backup=journal.backup()
    import sqlite3
    with sqlite3.connect(backup) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM calls").fetchone()[0] == 3
    with pytest.raises(ValueError):
        orch.run(REQUEST,run_id="..")
    with pytest.raises(ContractDenied,match="new RF run"):
        orch.run(REQUEST,state=state_for(orch,alias),run_id=alias)


def test_newer_or_unversioned_journal_is_never_rewritten(tmp_path):
    import sqlite3
    journal=LifecycleJournal(tmp_path,"run-newer")
    with journal.connect() as db:
        db.execute("PRAGMA user_version=9")
    with pytest.raises(ContractDenied,match="unsupported RF journal schema"):
        LifecycleJournal(tmp_path,"run-newer")
    with sqlite3.connect(journal.path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 9


@pytest.mark.parametrize("usd",[0,.001,.03])
def test_native_cost_ceiling_blocks_before_provider_exceeds_limit(repo_root,tmp_path,monkeypatch,usd):
    from research_forge.errors import ForgeException,ErrorCode
    orch=Wave1Orchestrator(repo_root,workspace=tmp_path,resource_limits={"tokens":100,"usd":usd,"deadline":None})
    with pytest.raises(ForgeException) as exc:
        orch.run(REQUEST,run_id="run-limited")
    assert exc.value.error.code == ErrorCode.BUDGET_EXCEEDED
    view=orch.lifecycle("run-limited")
    spent=(view["budget"] or {}).get("spent_usd",0)
    assert spent <= usd
    assert not view["reconciliation_required"]
    assert all(call["status"] == "completed" for call in view["calls"])
    if usd < .01:
        assert not view["calls"]


def test_native_token_and_deadline_ceiling_and_pin(repo_root,tmp_path):
    import time
    from research_forge.errors import ForgeException
    for alias,limits in [("zero-tokens",{"tokens":0,"usd":1,"deadline":None}),
                         ("expired",{"tokens":100,"usd":1,"deadline":time.time()-1})]:
        orch=Wave1Orchestrator(repo_root,workspace=tmp_path,resource_limits=limits)
        with pytest.raises(ForgeException):
            orch.run(REQUEST,run_id=alias)
        assert not orch.lifecycle(alias)["calls"]
    orch=Wave1Orchestrator(repo_root,workspace=tmp_path,resource_limits={"tokens":100,"usd":1,"deadline":None})
    paused=orch.run({"topic":"Alpha"})
    changed=Wave1Orchestrator(repo_root,workspace=tmp_path,resource_limits={"tokens":100,"usd":2,"deadline":None})
    with pytest.raises(ContractDenied,match="configuration"):
        changed.resume(RunState.from_dict(paused["state"]))


def test_cancel_during_local_composition_is_acknowledged_before_return(repo_root,tmp_path,monkeypatch):
    orch=Wave1Orchestrator(repo_root,workspace=tmp_path)
    compose=orch.composer.compose_report
    def cancel_then_compose(*args,**kwargs):
        orch.cancel("run-compose-cancel")
        return compose(*args,**kwargs)
    monkeypatch.setattr(orch.composer,"compose_report",cancel_then_compose)
    with pytest.raises(ContractDenied,match="CANCELLED"):
        orch.run(REQUEST,run_id="run-compose-cancel")
    view=orch.lifecycle("run-compose-cancel")
    assert view["cancel_requested"]
    assert not view["reconciliation_required"]
    assert any(e["kind"] == "cancel_acknowledged" for e in view["events"])
    # Completed local output remains durable, but STOP controls cached replay.
    assert view["checkpoint"]["state"]["phase"] == "done"
    with pytest.raises(ContractDenied,match="CANCELLED"):
        orch.resume(state_for(orch,"run-compose-cancel"))
