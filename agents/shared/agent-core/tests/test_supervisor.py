import importlib.util
import pytest


class Engine:
    def __init__(self): self.version=1; self.calls=0; self.result={}; self.interrupt=False; self.running=False
    def snapshot(self, workspace, live, provider): return {"version":self.version,"live":live,"provider":provider}
    def create(self, row): return "native-"+row["run_id"]
    def execute(self, row, answers=None):
        self.calls += 1
        if self.interrupt: self.running=True; raise KeyboardInterrupt("crash")
        self.result={"status":"SIMULATED","phase":"done","usage":{"tokens":10,"usd":.01,"usage_status":"estimated"},"artifacts":[]}
        return self.result
    def inspect(self, row):
        return {"status":"RUNNING","phase":"inflight","usage":{"unknown":True}} if self.running else self.result or {"status":"QUEUED","phase":"new"}
    def cancel(self,row):
        if not self.running: self.result={"status":"CANCELLED","phase":"cancelled","usage":{"tokens":0,"usd":0,"usage_status":"estimated"}}


def supervisor(path, engine):
    assert importlib.util.find_spec("agent_core.supervisor") is not None, "supervisor missing"
    from agent_core.supervisor import Supervisor
    return Supervisor(path, adapters={"daily-coder":engine})


def test_engine_completion_checkpoint_and_duplicate_resume(tmp_path):
    engine=Engine(); sup=supervisor(tmp_path,engine)
    session=sup.new_session(project=str(tmp_path))
    run=sup.create_run(session["session_id"],"daily-coder","fix",tmp_path)
    out=sup.execute(run["run_id"])
    assert out["status"] == "SIMULATED" and out["execution_started"]
    assert out["legacy_id"].startswith("native-")
    assert sup.execute(run["run_id"])["status"] == "SIMULATED"
    assert engine.calls == 1
    assert sup.store.latest_checkpoint(run["run_id"])["phase"] == "done"
    assert sup.status(out["legacy_id"])["accounting"]["estimated_usd"] == .01


def test_crash_cannot_replay_and_reservation_survives(tmp_path):
    engine=Engine(); sup=supervisor(tmp_path,engine)
    run=sup.create_run(sup.new_session()["session_id"],"daily-coder","fix",tmp_path)
    engine.interrupt=True
    with pytest.raises(KeyboardInterrupt): sup.execute(run["run_id"])
    restarted=supervisor(tmp_path,engine)
    out=restarted.execute(run["run_id"])
    assert out["status"] == "RECONCILIATION_REQUIRED"
    assert engine.calls == 1
    assert out["accounting"]["reserved_usd"] > 0
    cancelled=restarted.cancel(run["run_id"])
    assert not cancelled["cancelled"]
    assert cancelled["status"] in ("CANCEL_REQUESTED","RECONCILIATION_REQUIRED")


def test_changed_configuration_before_dispatch_is_denied(tmp_path):
    engine=Engine(); sup=supervisor(tmp_path,engine)
    run=sup.create_run(sup.new_session()["session_id"],"daily-coder","fix",tmp_path)
    engine.version=2
    out=sup.execute(run["run_id"])
    assert out["status"] == "BLOCKED" and not out["execution_started"]
    assert engine.calls == 0


def test_queued_cancel_is_acknowledged_without_engine_execution(tmp_path):
    engine=Engine(); sup=supervisor(tmp_path,engine)
    run=sup.create_run(sup.new_session()["session_id"],"daily-coder","fix",tmp_path)
    out=sup.cancel(run["run_id"])
    assert out["cancelled"] and out["acknowledged"]
    assert out["status"] == "CANCELLED"
    assert engine.calls == 0


def test_zero_resource_ceiling_denies_before_engine_dispatch(tmp_path):
    engine=Engine(); sup=supervisor(tmp_path,engine)
    run=sup.create_run(sup.new_session()["session_id"],"daily-coder","fix",tmp_path,limit_usd=0,limit_tokens=0)
    out=sup.execute(run["run_id"])
    assert out["status"] == "BLOCKED" and engine.calls == 0


def test_actual_overrun_is_visible_and_blocks_completion(tmp_path):
    engine=Engine(); sup=supervisor(tmp_path,engine)
    run=sup.create_run(sup.new_session()["session_id"],"daily-coder","fix",tmp_path,limit_usd=.001)
    out=sup.execute(run["run_id"])
    assert out["status"] == "BLOCKED"
    assert out["accounting"]["estimated_usd"] == .01


def test_crash_after_root_settlement_recovers_without_engine_replay(tmp_path):
    engine=Engine(); sup=supervisor(tmp_path,engine)
    run=sup.create_run(sup.new_session()["session_id"],"daily-coder","fix",tmp_path)
    original=sup.store.checkpoint
    def crash(key,state,*args):
        if state.get("phase")=="done": raise KeyboardInterrupt("after settlement")
        return original(key,state,*args)
    sup.store.checkpoint=crash
    with pytest.raises(KeyboardInterrupt): sup.execute(run["run_id"])
    restarted=supervisor(tmp_path,engine)
    assert restarted.execute(run["run_id"])["status"]=="SIMULATED"
    assert engine.calls==1
    assert len(restarted.store.events(run["run_id"])) > 0


def test_partial_headroom_does_not_grant_full_native_budget(tmp_path):
    engine=Engine();sup=supervisor(tmp_path,engine);session=sup.new_session()
    parent=sup.create_run(session["session_id"],"daily-coder","parent",tmp_path,limit_usd=.025)
    for number in range(3):
        child=sup.create_run(session["session_id"],"daily-coder","child",tmp_path,parent_id=parent["run_id"],limit_usd=.02)
        out=sup.execute(child["run_id"])
        if number:
            assert out["status"]=="BLOCKED"
    assert engine.calls==1


def test_legacy_import_preserves_known_and_unknown_exposure(tmp_path):
    engine=Engine();sup=supervisor(tmp_path,engine);session=sup.new_session()
    engine.result={"status":"SIMULATED","usage":{"tokens":20,"usd":.25,"usage_status":"estimated"}}
    row=sup.import_legacy(session["session_id"],"daily-coder","old-one",tmp_path)
    assert row["accounting"]["estimated_usd"]==.25
    engine.result={"status":"RUNNING","usage":{"unknown":True}}
    row=sup.import_legacy(session["session_id"],"daily-coder","old-two",tmp_path)
    assert row["accounting"]["usage_status"]=="unknown"
    assert row["accounting"]["reserved_usd"]>0
    assert engine.calls==0
