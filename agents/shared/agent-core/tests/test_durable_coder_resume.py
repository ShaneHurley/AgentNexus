import importlib.util
from pathlib import Path
from types import SimpleNamespace
import hashlib,json
import pytest
from agent_core.engine_adapters import DailyCoderAdapter
from agent_core.supervisor import Supervisor

spec=importlib.util.spec_from_file_location("acceptance_helpers",Path(__file__).resolve().parents[3]/"coding/daily-coder-ecosystem/tests/test_coder_v1.py")
helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)

def state_for_proof():
    return SimpleNamespace(events=lambda *a,**k:[{"seq":4,"kind":"transition","new_phase":"IMPLEMENT","created":5}],
        artifacts=lambda *a:[{"kind":"implement","hash":"artifact","created":4}],
        invocations=lambda *a,**k:[{"created":3}],tool_calls=lambda *a,**k:[],
        jobs=lambda *a:[])

@pytest.mark.parametrize("defect",[None,"unknown","reservation","pendingtool","missingphase","missingartifact","subsequentinvocation","subsequenttool","job"])
def test_native_boundary_proof_rejects_uncertain_or_partial_work(defect):
    state=state_for_proof();native={"status":"ACTIVE","phase":"IMPLEMENT","run_id":"native"}
    report={"settled_unreceipted":{"calls":0}};pending={"calls":0};tools=[]
    if defect=="unknown": report["settled_unreceipted"]["calls"]=1
    if defect=="reservation": pending["calls"]=1
    if defect=="pendingtool": tools=[{}]
    if defect=="missingphase": state.events=lambda *a,**k:[]
    if defect=="missingartifact": state.artifacts=lambda *a:[]
    if defect=="subsequentinvocation": state.invocations=lambda *a,**k:[{"created":6}]
    if defect=="subsequenttool": state.tool_calls=lambda *a,**k:[{"created":6}]
    if defect=="job": state.jobs=lambda *a:[{"state":"running"}]
    proof=DailyCoderAdapter._resumable_checkpoint(SimpleNamespace(state=state),native,report,pending,tools)
    assert bool(proof) is (defect is None)

class Engine:
    def __init__(self,proof=True,unknown=False): self.calls=0;self.proof=proof;self.unknown=unknown
    def snapshot(self,*args): return {"provider":"mock","execution_policy":"coder-v1"}
    def create(self,row): return row["run_id"]
    def execute(self,row,answers=None):
        self.calls+=1
        if self.calls==1: raise KeyboardInterrupt("after durable implementation")
        return {"status":"SIMULATED","phase":"done","usage":{"tokens":20,"usd":0.02,"usage_status":"estimated"}}
    def inspect(self,row):
        result={"status":"RUNNING","phase":"IMPLEMENT","usage":{"tokens":10,"usd":0.01,"unknown":self.unknown,"usage_status":"estimated"}}
        if self.proof: result["resumable_checkpoint"]={"schema_version":1,"engine":"daily-coder","run_id":row["legacy_id"],"phase":"IMPLEMENT","transition_sequence":4,"artifact_hash":"proof"}
        return result

@pytest.mark.parametrize("proof,unknown,expected",[(True,False,"SIMULATED"),(False,False,"RECONCILIATION_REQUIRED"),(True,True,"RECONCILIATION_REQUIRED")])
def test_public_resume_settles_proven_boundary_without_replaying_accepted_write(tmp_path,proof,unknown,expected):
    engine=Engine(proof,unknown);sup=Supervisor(tmp_path,adapters={"daily-coder":engine})
    contract_engine,*_=helpers.make(tmp_path/"contract")
    contract=contract_engine.task_contract
    run=sup.create_run(sup.new_session()["session_id"],"daily-coder","Fix clamp",contract["workspace"],
        execution_policy="coder-v1",approval_mode="task",task_contract=contract,limit_tokens=contract["limits"]["tokens"])
    # Exercise actual public task authorization and preserved source pins.
    with pytest.raises(KeyboardInterrupt): sup.execute(run["run_id"])
    out=Supervisor(tmp_path,adapters={"daily-coder":engine}).execute(run["run_id"])
    assert out["status"]==expected
    assert engine.calls==(2 if expected=="SIMULATED" else 1)
    if expected=="SIMULATED":
        assert out["accounting"]["tokens"]==20 and out["accounting"]["reserved_tokens"]==0
    else: assert out["accounting"]["reserved_tokens"]>0

@pytest.mark.parametrize("defect",[None,"oldcycle","wrongplan","tamperedresult","missingoperation","zero_tests","sourcechanged"])
def test_acceptance_uses_current_durable_attempt_preserving_failed_history(tmp_path,defect):
    engine,run,packet,gateway,broker=helpers.make(tmp_path)
    p=helpers.plan();engine.artifacts.put(run,"plan","planner",p)
    row={**engine.state.get(run),"plan_hash":"candidate","repair_cycles":1}
    argv=p["verification_commands"][0]
    args={"argv":argv,"timeout":engine.task_contract["limits"]["verification_timeout"]}
    prior=f"{run}:runtime-tests:candidate:0:c0"
    engine.state.begin_tool_operation(prior,run,"test_executor","TEST_EXECUTE","tests.run",args,"candidate")
    engine.state.finish_tool_operation(prior,{"returncode":1})
    current=f"{run}:runtime-tests:candidate:0:c1"
    result={"argv":argv,"returncode":0,"stderr":"Ran 5 tests in 0.001s\n\nOK\n","source_hashes":{"clamp.py":hashlib.sha256((broker.repo/"clamp.py").read_bytes()).hexdigest()},"image":"image","source_snapshot_sha256":"snapshot"}
    if defect=="zero_tests": result["stderr"]="Ran 0 tests in 0.001s\n\nOK\n"
    if defect!="missingoperation":
        engine.state.begin_tool_operation(current,run,"test_executor","TEST_EXECUTE","tests.run",args,"candidate")
        engine.state.finish_tool_operation(current,result)
    from agent_core.task_contract import scope_hash
    receipt={"schema_version":1,"plan_hash":"candidate","repair_cycle":1,"tested_scope_hash":scope_hash(engine.task_contract),"commands":[{"ok":True,"result":result.copy()}]}
    if defect=="oldcycle": receipt["repair_cycle"]=0
    if defect=="wrongplan": receipt["plan_hash"]="old"
    if defect=="tamperedresult": receipt["commands"][0]["result"]["returncode"]=1
    if defect=="sourcechanged": (broker.repo/"clamp.py").write_text("new")
    engine.artifacts.put(run,"test_receipts","runtime",receipt)
    results,jobs=engine._acceptance_verification(run,row)
    assert len(results)==1 and jobs==[]
    assert results[0]["decision"]==("allow" if defect is None else "deny")
    assert json.loads(engine.state.tool_operation(prior)["result"])["returncode"]==1
