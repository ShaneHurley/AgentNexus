from pathlib import Path
import threading
import pytest
from daily_coder.orchestrator import Orchestrator
from daily_coder.providers.mock import MockProvider
from daily_coder.state_store import StateStore
from daily_coder.policy import PolicyGateway
from agent_core.lifecycle import ReconciliationRequired

DC = Path(__file__).resolve().parents[1]

def make(tmp_path, provider=None):
    state=StateStore(tmp_path / "state.sqlite")
    engine=Orchestrator(DC,state,provider or MockProvider())
    return engine,state,engine.create("fix typo",tmp_path)

def test_cancel_requires_engine_acknowledgment(tmp_path):
    engine,state,run=make(tmp_path)
    assert engine.request_cancel(run)["status"] == "CANCEL_REQUESTED"
    assert engine.run(run)["status"] == "CANCELLED"
    assert engine.artifacts.load(run,"checkpoint")["status"] == "CANCELLED"

def test_cancel_unknown_provider_retains_exposure(tmp_path):
    engine,state,run=make(tmp_path)
    engine.budget.reserve(run,"S",10,reservation_id="unknown")
    engine.request_cancel(run)
    assert engine.run(run)["status"] == "CANCEL_REQUESTED"
    assert state.active_budget_reservations(run)["calls"] == 1

def test_cancel_stops_dispatch_after_provider_returns(tmp_path):
    entered=threading.Event(); release=threading.Event()
    class Slow(MockProvider):
        def invoke(self,request):
            entered.set(); release.wait(5)
            return super().invoke(request)
    engine,state,run=make(tmp_path,Slow())
    worker=threading.Thread(target=engine.run,args=(run,)); worker.start()
    assert entered.wait(5)
    assert engine.request_cancel(run)["status"] == "CANCEL_REQUESTED"
    release.set(); worker.join(10)
    assert not worker.is_alive()
    assert state.get(run)["status"] == "CANCELLED"
    assert len(state.invocations(run)) == 1

class CrashBroker:
    def __init__(self): self.calls=0
    def authorize(self,*args): pass
    def execute(self,*args,**kw):
        self.calls+=1
        raise KeyboardInterrupt("crash after side effect")

def test_unknown_tool_receipt_blocks_replay(tmp_path):
    engine,state,run=make(tmp_path); broker=CrashBroker()
    gateway=PolicyGateway(broker,state,{},False)
    with pytest.raises(KeyboardInterrupt): gateway.execute(run,"researcher","RESEARCH","web.fetch",{"url":"https://example.invalid"})
    assert state.pending_tool_operations(run)
    assert engine.run(run)["status"] == "RECONCILIATION_REQUIRED"
    assert broker.calls == 1

def test_cancel_blocks_new_tools(tmp_path):
    engine,state,run=make(tmp_path); broker=CrashBroker()
    engine.request_cancel(run)
    with pytest.raises(ReconciliationRequired): PolicyGateway(broker,state,{},False).execute(run,"researcher","RESEARCH","web.fetch",{})
    assert broker.calls == 0


def test_approved_write_crash_reconciles_without_duplicate(tmp_path):
    from daily_coder.tool_broker import ToolBroker,file_sha
    from daily_coder.util import sha256_text
    engine,state,run=make(tmp_path)
    path=tmp_path/"a.txt"; path.write_text("old")
    tools={"role_allowlists":{"implementer":["filesystem.write"]}}
    policy={"path_policy":{"write_requires_plan_allowlist":True}}
    broker=ToolBroker(tmp_path,tools,policy)
    original=broker.execute
    def crash(*a,**kw):
        original(*a,**kw)
        raise KeyboardInterrupt("after write")
    broker.execute=crash
    plan={"file_allowlist":["a.txt"]}; plan_hash="plan-approved"
    engine.artifacts.put(run,"plan","planner",plan)
    state.set_field(run,"plan_hash",plan_hash)
    state.request_approval(run,"plan",plan_hash)
    state.decide_approval(run,"plan",plan_hash,"approved","test")
    args={"path":"a.txt","content":"new","expected_sha256":file_sha(path)}
    gateway=PolicyGateway(broker,state,policy,True)
    with pytest.raises(KeyboardInterrupt):
        gateway.execute(run,"implementer","IMPLEMENT","filesystem.write",args,["a.txt"],plan_hash,operation_id="write-1")
    assert path.read_text()=="new"
    assert state.pending_tool_operations(run)
    assert engine.run(run)["status"]=="RECONCILIATION_REQUIRED"
    broker.execute=original
    assert gateway.reconcile(run)
    assert not state.pending_tool_operations(run)
    state.set_status(run,"ACTIVE")
    result=gateway.execute(run,"implementer","IMPLEMENT","filesystem.write",args,["a.txt"],plan_hash,operation_id="write-1")
    assert result["reconciled"]
    assert path.read_text()=="new"

def test_job_cancel_does_not_claim_confirmation_on_permission_failure(tmp_path,monkeypatch):
    from daily_coder.jobs import JobManager
    import daily_coder.jobs as jobs
    engine,state,run=make(tmp_path)
    state.create_job("job",run,"tests",["python"],tmp_path,tmp_path/"log","fp",0)
    state.start_job("job",123456)
    monkeypatch.setattr(jobs.os,"killpg",lambda *a: (_ for _ in ()).throw(PermissionError()))
    monkeypatch.setattr(jobs.time,"sleep",lambda *a: None)
    assert engine.jobs.cancel("job")["state"] == "running"
    engine.request_cancel(run)
    assert engine.run(run)["status"] == "CANCEL_REQUESTED"


@pytest.mark.parametrize("confirmed",[True,False])
def test_isolated_tool_cancel_checks_persisted_status_and_keeps_unknown_receipt(tmp_path,monkeypatch,confirmed):
    from agent_core.isolation import DockerRunner
    from daily_coder.tool_broker import ToolBroker
    engine,state,run=make(tmp_path)
    runner=DockerRunner("python@sha256:"+"a"*64,tmp_path)
    tools={"role_allowlists":{"test_executor":["tests.run"]}}
    broker=ToolBroker(tmp_path,tools,{},isolated_runner=runner)
    def blocking(argv,timeout=900,cancel_check=None):
        assert cancel_check and not cancel_check()
        engine.request_cancel(run)
        assert cancel_check()
        return {"cancelled":True,"cancellation_confirmed":confirmed,"returncode":None}
    monkeypatch.setattr(runner,"run",blocking)
    gateway=PolicyGateway(broker,state,{},False)
    with pytest.raises(ReconciliationRequired):
        gateway.safe_execute(run,"test_executor","TEST_EXECUTE","tests.run",{"argv":["python","-V"]})
    assert bool(state.pending_tool_operations(run)) is (not confirmed)
    assert engine.run(run)["status"] == ("CANCELLED" if confirmed else "CANCEL_REQUESTED")


def test_native_resume_accepted_response_missing_phase_output_blocks_repair(tmp_path):
    engine,state,run=make(tmp_path)
    state.transition(run,"INTAKE",{},run+":intake")
    key=f"{run}:planner:PLAN:0:0:c0"
    state.record_invocation(run,"planner","PLAN",0,0,"lowest","mock",10,5,0,0,"ok",None,key)
    out=engine.run(run)
    assert out["status"]=="RECONCILIATION_REQUIRED"
    assert out["repair_cycles"]==0
    assert len([r for r in state.invocations(run) if r["role"]=="planner"])==1


@pytest.mark.parametrize("limits",[{"tokens":0},{"tokens":1},{"usd":0},{"usd":.00000001}])
def test_supervised_native_caps_deny_before_provider(tmp_path,limits):
    class Count(MockProvider):
        def __init__(self): super().__init__(); self.calls=0
        def invoke(self,request): self.calls+=1; return super().invoke(request)
    state=StateStore(tmp_path/"caps.sqlite"); provider=Count()
    engine=Orchestrator(DC,state,provider,resource_limits=limits)
    engine.pricing["mock"]={"input_per_1k":1,"output_per_1k":1}
    run=engine.create("fix typo",tmp_path)
    engine.run(run)
    assert provider.calls==0
    assert state.active_budget_reservations(run)["calls"]==0

def test_supervised_deadline_requests_cancellation_before_provider(tmp_path):
    import time
    state=StateStore(tmp_path/"deadline.sqlite")
    engine=Orchestrator(DC,state,MockProvider(),resource_limits={"deadline":time.time()-1})
    run=engine.create("fix typo",tmp_path)
    assert engine.run(run)["status"]=="CANCELLED"
    assert not state.invocations(run)

def test_settled_unreceipted_charge_survives_restart_and_blocks_replay(tmp_path):
    engine,state,run=make(tmp_path)
    engine.budget.reserve(run,"S",20,estimated_usd=.1,reservation_id="accepted")
    state.settle_budget_reservation("accepted",15,.08)
    restored=StateStore(state.path)
    assert restored.total_usage(run)=={"calls":1,"tokens":15}
    assert restored.get(run)["est_usd"]==.08
    report=engine.budget.report(run)
    assert report["est_usd"]==.08
    assert report["tokens"]==15
    from daily_coder.budget import BudgetExceeded
    engine.budget.limits["max_spend_usd_per_run"]=.09
    with pytest.raises(BudgetExceeded): engine.budget.reserve(run,"S",1,estimated_usd=.02,reservation_id="second")
    engine.budget.limits.pop("max_spend_usd_per_run")
    assert engine.run(run)["status"]=="RECONCILIATION_REQUIRED"


def test_process_crash_after_settlement_keeps_known_charge_and_denies_resume(tmp_path,monkeypatch):
    class Count(MockProvider):
        def __init__(self): super().__init__(); self.calls=0
        def invoke(self,request): self.calls+=1; return super().invoke(request)
    provider=Count(); state=StateStore(tmp_path/"crash-account.sqlite")
    engine=Orchestrator(DC,state,provider)
    engine.pricing["mock"]={"input_per_1k":1,"output_per_1k":1}
    run=engine.create("fix typo",tmp_path)
    record=state.record_invocation
    monkeypatch.setattr(state,"record_invocation",lambda *a,**kw: (_ for _ in ()).throw(KeyboardInterrupt("crash between settlement and receipt")))
    with pytest.raises(KeyboardInterrupt): engine.run(run)
    assert provider.calls==1
    restarted=StateStore(state.path)
    assert restarted.total_usage(run)["calls"]==1
    assert restarted.get(run)["est_usd"]>0
    assert engine.budget.report(run)["settled_unreceipted"]["calls"]==1
    assert restarted.list_runs()[0]["est_usd"]>0
    assert restarted.metrics_aggregate()["roles"][0]["usd"]>0
    monkeypatch.setattr(state,"record_invocation",record)
    assert engine.run(run)["status"]=="RECONCILIATION_REQUIRED"
    assert provider.calls==1

def test_settled_orphan_receipt_completion_counts_cost_and_usage_once(tmp_path):
    engine,state,run=make(tmp_path)
    engine.budget.reserve(run,"S",20,estimated_usd=.1,reservation_id="call")
    state.settle_budget_reservation("call",15,.08)
    assert state.total_usage(run)=={"calls":1,"tokens":15}
    state.record_invocation(run,"planner","PLAN",0,0,"lowest","mock",10,5,.08,0,"ok",None,"call")
    assert state.total_usage(run)=={"calls":1,"tokens":15}
    assert state.get(run)["est_usd"]==.08
    assert state.unreceipted_settlements(run)["calls"]==0


def test_resource_limits_are_copied_and_effective_cap_changes_cannot_resume(tmp_path):
    from agent_core.contracts import ContractDenied
    limits={"tokens":100}
    state=StateStore(tmp_path/"bound.sqlite")
    engine=Orchestrator(DC,state,MockProvider(),resource_limits=limits)
    run=engine.create("fix typo",tmp_path)
    limits["tokens"]=100000
    assert engine.resource_limits["tokens"]==100
    with pytest.raises(TypeError): engine.resource_limits["tokens"]=100000
    engine.budget.limits["max_tokens_per_run"]=100000
    with pytest.raises(ContractDenied,match="configuration"): engine.run(run)
    assert not state.invocations(run)


def test_optional_supervisor_deadline_none_means_no_deadline(tmp_path):
    state=StateStore(tmp_path/"optional-deadline.sqlite")
    engine=Orchestrator(DC,state,MockProvider(),resource_limits={"tokens":100000,"usd":5,"deadline":None})
    assert "deadline" not in engine.resource_limits
    run=engine.create("fix typo",tmp_path)
    assert engine.run(run)["status"]=="SIMULATED"


@pytest.mark.parametrize("folder",["agents","schemas"])
def test_native_execution_pins_role_configs_and_schemas(tmp_path,folder):
    import shutil
    root=tmp_path/"engine";root.mkdir()
    for directory in ("config","agents","schemas","skills"): shutil.copytree(DC/directory,root/directory)
    state=StateStore(tmp_path/"state.sqlite");engine=Orchestrator(root,state,MockProvider());run=engine.create("fix typo",tmp_path)
    file=next((root/folder).rglob("*.json"));file.write_text(file.read_text()+" ")
    from agent_core.contracts import ContractDenied
    with pytest.raises(ContractDenied): Orchestrator(root,state,MockProvider()).run(run)

def test_stale_write_hash_denied_without_uncertain_receipt(tmp_path):
    from daily_coder.tool_broker import ToolBroker,ToolDenied
    engine,state,run=make(tmp_path)
    (tmp_path/"a.txt").write_text("old")
    broker=ToolBroker(tmp_path,{"role_allowlists":{"implementer":["filesystem.write"]}},{})
    gateway=PolicyGateway(broker,state,{},False)
    with pytest.raises(ToolDenied): gateway.execute(run,"implementer","IMPLEMENT","filesystem.write",{"path":"a.txt","content":"new","expected_sha256":"wrong"},["a.txt"],"plan")
    assert state.pending_tool_operations(run)==[]
    assert (tmp_path/"a.txt").read_text()=="old"


def test_native_creation_identity_survives_shared_alias_crash(tmp_path,monkeypatch):
    from agent_core.engine_adapters import DailyCoderAdapter
    from agent_core.supervisor import Supervisor
    engine,state,existing=make(tmp_path)
    adapter=DailyCoderAdapter(DC)
    monkeypatch.setattr(adapter,"_engine",lambda row:engine)
    sup=Supervisor(tmp_path/"supervisor",adapters={"daily-coder":adapter})
    row=sup.create_run(sup.new_session()["session_id"],"daily-coder","inspect",tmp_path)
    original=sup.store.set_alias
    def crash(*a,**kw): raise KeyboardInterrupt("native created before link")
    monkeypatch.setattr(sup.store,"set_alias",crash)
    with pytest.raises(KeyboardInterrupt): sup.execute(row["run_id"])
    monkeypatch.setattr(sup.store,"set_alias",original)
    sup.execute(row["run_id"])
    assert len(state.list_runs())==2
    assert sup.status(row["run_id"])["legacy_id"]==row["run_id"]
