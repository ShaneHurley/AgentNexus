import hashlib,json,shutil
from datetime import datetime,timezone
from pathlib import Path
import pytest
from daily_coder.coder_v1 import CoderV1
from daily_coder.state_store import StateStore
from daily_coder.providers.mock import MockProvider
from daily_coder.policy import PolicyGateway
from daily_coder.tool_broker import ToolBroker
from agent_core.providers.base import InvocationResult
from agent_core.task_contract import DEFAULT_LIMITS,digest
from agent_core.handoffs import is_incomplete
def make(tmp_path,provider=None,live=False):
    package=tmp_path/"package"
    source=Path(__file__).resolve().parents[1]
    for folder in ("agents","schemas","skills","config"): shutil.copytree(source/folder,package/folder)
    workspace=tmp_path/"workspace";workspace.mkdir()
    (workspace/"clamp.py").write_text("value=1\n")
    request="Fix clamp"
    contract={"schema_version":1,"request_sha256":hashlib.sha256(request.encode()).hexdigest(),"workspace":str(workspace),
        "acceptance_criteria":["Correct clamp"],"allowed_paths":["clamp.py"],"operations":["modify"],
        "verification_commands":[["python","-m","unittest","-v"]],"limits":dict(DEFAULT_LIMITS),
        "authorization_source":"user-task","authorized_at":datetime.now(timezone.utc).isoformat()}
    engine=CoderV1(package,StateStore(tmp_path/"native.sqlite"),provider or MockProvider(),live=live,task_contract=contract)
    run=engine.create(request,workspace)
    packet=engine._rebuild_packet(run,engine.state.get(run),"S")
    broker=ToolBroker(workspace,engine.tools_config,engine.policies)
    gateway=PolicyGateway(broker,engine.state,engine.policies,True,task_contract=contract)
    return engine,run,packet,gateway,broker
def plan():
    return {"change_units":[{"id":"fix","file":"clamp.py","operation":"modify","summary":"Fix","verification":"unit test"}],
        "file_allowlist":["clamp.py"],"unresolved_questions":[],"verification_commands":[["python","-m","unittest","-v"]]}
def test_short_route_is_durable_and_contains_actual_role_calls(tmp_path):
    engine,run,packet,gateway,broker=make(tmp_path)
    result=engine._size(run,"Fix clamp")
    assert result["workflow"]=="CODER_V1"
    from daily_coder.workflow import workflow_for
    assert workflow_for("CODER_V1")==["INTAKE","SIZE","DECIDE","PLAN","PLAN_REVIEW","READY_TO_BUILD","IMPLEMENT","TEST_EXECUTE","CODE_REVIEW","ALIGNMENT","ACCEPTANCE","COMPLETE"]
def test_exact_plan_grant_is_derived_from_task_not_human_review(tmp_path):
    engine,run,packet,gateway,broker=make(tmp_path)
    from daily_coder.models import Phase
    engine.state.transition(run,"INTAKE",{},"i");engine.state.transition(run,"SIZE",{},"s");engine.state.transition(run,"DECIDE",{},"d");engine.state.transition(run,"PLAN",{},"p");engine.state.transition(run,"PLAN_REVIEW",{},"pr")
    packet["plan"]=plan()
    assert engine._ready_to_build(run,packet)=="ok"
    assert engine.state.approval_state(run,"plan",packet["plan_hash"])=="approved"
    grant=engine.artifacts.load_all(run)["derived_grant"]
    assert grant["source"]=="authorized by task contract" and grant["task_contract_hash"]==digest(engine.task_contract)
    assert not engine.state.pending_approvals()
def test_incomplete_plan_launches_actual_review_and_read_only_implementer(tmp_path):
    calls=[]
    class Provider(MockProvider):
        def invoke(self,request):
            calls.append(request)
            output="incomplete facts" if request.role=="planner" else {"verdict":"block","findings":[]} if request.role=="plan_reviewer" else {"changed_files":[],"commands":[],"observations":["Missing concrete plan"],"blocked":True,"blocked_reason":"No grant"}
            return InvocationResult(output=output,model="mock",input_tokens=1,output_tokens=1)
    engine,run,packet,gateway,broker=make(tmp_path,Provider(),True)
    value=engine._invoke(run,"planner","PLAN",packet,0,"S",gateway)
    assert is_incomplete(value)
    assert len([x for x in calls if x.role=="planner"])==2
    assert calls[1].tools==()
    repair=calls[1].input_packet
    assert repair["ORIGINAL_OUTPUT"]=="incomplete facts"
    assert repair["SCHEMA_ERRORS"] and repair["ROLE_OUTPUT_SCHEMA"]["type"]=="object"
    assert repair["TASK_CONSTRAINTS"]==engine.task_contract
    packet["plan"]=value
    assert engine._run_phase(run,"PLAN_REVIEW","S",packet,gateway,broker)=="stop"
    assert [x.role for x in calls][-2:]==["plan_reviewer","implementer"]
    assert all(t["name"] not in {"filesystem.write","patch.apply"} for t in calls[-1].tools)
    assert engine.state.get(run)["plan_hash"] is None
def test_restart_restores_persisted_test_candidate_hash(tmp_path):
    engine,run,packet,gateway,broker=make(tmp_path)
    from agent_core.task_contract import scope_hash
    observed=scope_hash(engine.task_contract)
    engine.artifacts.put(run,"test_receipts","runtime",{"tested_scope_hash":observed})
    rebuilt=engine._rebuild_packet(run,engine.state.get(run),"S")
    assert rebuilt["tested_scope_hash"]==observed
    (broker.repo/"clamp.py").write_text("changed after test")
    assert rebuilt["tested_scope_hash"]!=scope_hash(engine.task_contract)

def test_read_only_recovery_rejects_unadvertised_write_even_with_old_grant(tmp_path):
    from agent_core.providers.base import ToolCall
    class Provider(MockProvider):
        def invoke(self,request):
            if request.turn==0:
                return InvocationResult(model="mock",input_tokens=1,output_tokens=1,tool_calls=[ToolCall("filesystem.write",{"path":"clamp.py","content":"unauthorized recovery write","expected_sha256":hashlib.sha256(b"value=1\n").hexdigest()},"bad")])
            assert request.tool_results[-1]["ok"] is False
            return InvocationResult(model="mock",input_tokens=1,output_tokens=1,output={"changed_files":[],"commands":[],"observations":["Read-only recovery"],"blocked":True})
    engine,run,packet,gateway,broker=make(tmp_path,Provider(),True)
    engine.state.prepare_plan_approval(run,"old-grant")
    engine.state.decide_approval(run,"plan","old-grant","approved","unit-test")
    packet["plan_hash"]="old-grant";packet["file_allowlist"]=["clamp.py"]
    value=engine._invoke(run,"implementer","IMPLEMENT",packet,0,"S",gateway,{"READ_ONLY_RECOVERY":True})
    assert value["blocked"] is True
    assert (broker.repo/"clamp.py").read_text()=="value=1\n"
    assert not engine.state.pending_tool_operations(run)

def test_task_gateway_rejects_outside_path_before_receipt(tmp_path):
    engine,run,packet,gateway,broker=make(tmp_path)
    result=gateway.safe_execute(run,"implementer","IMPLEMENT","filesystem.write",{"path":"other.py","content":"bad"},plan_allowlist=["other.py"],plan_hash="fake")
    assert result["ok"] is False and not engine.state.pending_tool_operations(run)
    assert not (broker.repo/"other.py").exists()

@pytest.mark.parametrize("severity",["blocking","major"])
def test_passing_review_cannot_override_actionable_findings(tmp_path,severity):
    engine,run,packet,gateway,broker=make(tmp_path)
    review={"verdict":"pass","findings":[{"severity":severity,"claim":"Incorrect boundary","locator":"clamp.py:1"}]}
    assert not engine._review_clear(review)
    outcome=engine._gate(run,"CODE_REVIEW","code_reviewer",review,packet)
    assert outcome[0]=="repair"
    packet["code_review"]=review
    assert engine._run_phase(run,"ACCEPTANCE","S",packet,gateway,broker)=="stop"
    assert engine.state.get(run)["status"]=="FAILED"

def test_optional_curation_is_disabled_for_coder_v1(tmp_path,monkeypatch):
    engine,run,packet,gateway,broker=make(tmp_path,live=True)
    assert engine.config["evolution"]["enabled"] is False
    monkeypatch.setattr(engine,"_invoke",lambda *args,**kwargs:pytest.fail("Optional role must not be dispatched"))
    engine._post_run_evolution(run,"S",packet,gateway)

def test_planner_source_and_explicit_oracle_are_actual_read_receipts(tmp_path):
    engine,run,packet,gateway,broker=make(tmp_path)
    oracle=broker.repo/"test_clamp.py"
    oracle.write_text("import unittest\n")
    engine.task_contract["verification_commands"]=[["python","-m","unittest","discover","-p","test_clamp.py"]]
    extra=engine._role_extra(run,"planner",packet,broker)
    sources={entry["path"]:entry for entry in extra["SOURCE_SNAPSHOTS"]}
    assert sources["clamp.py"]["complete"] is True
    assert sources["clamp.py"]["sha256"]==hashlib.sha256((broker.repo/"clamp.py").read_bytes()).hexdigest()
    assert sources["test_clamp.py"]["write_scope"] is False
    for entry in sources.values():
        receipt=engine.state.tool_operation(entry["operation_ref"])
        assert receipt["state"]=="completed" and receipt["role"]=="planner" and receipt["tool"]=="filesystem.read"
        assert json.loads(receipt["arguments"])["path"]==entry["path"]
    assert engine.task_contract["allowed_paths"]==["clamp.py"]

def test_prefetch_hash_cannot_authorize_a_stale_overwrite(tmp_path):
    engine,run,packet,gateway,broker=make(tmp_path)
    extra=engine._role_extra(run,"implementer",packet,broker)
    source=extra["SOURCE_SNAPSHOTS"][0]
    (broker.repo/"clamp.py").write_text("external change\n")
    engine.state.prepare_plan_approval(run,"valid-plan")
    engine.state.decide_approval(run,"plan","valid-plan","approved","unit-test")
    outcome=gateway.safe_execute(run,"implementer","IMPLEMENT","filesystem.write",
        {"path":"clamp.py","content":"new candidate","expected_sha256":source["sha256"]},
        plan_allowlist=["clamp.py"],plan_hash="valid-plan",operation_id="stale-write")
    assert outcome["ok"] is False
    assert (broker.repo/"clamp.py").read_text()=="external change\n"
    assert not engine.state.pending_tool_operations(run)

def test_implementer_does_not_advertise_verification_tools(tmp_path):
    calls=[]
    class Provider(MockProvider):
        def invoke(self,request):
            calls.append(request)
            return InvocationResult(model="mock",input_tokens=1,output_tokens=1,
                output={"changed_files":[],"commands":[],"observations":["No additional source reads needed"],"blocked":True})
    engine,run,packet,gateway,broker=make(tmp_path,Provider(),True)
    engine.state.prepare_plan_approval(run,"valid-plan")
    engine.state.decide_approval(run,"plan","valid-plan","approved","unit-test")
    packet["plan_hash"]="valid-plan"
    extra=engine._role_extra(run,"implementer",packet,broker)
    engine._invoke(run,"implementer","IMPLEMENT",packet,0,"S",gateway,extra)
    assert calls and "SOURCE_SNAPSHOTS" in calls[0].input_packet
    assert not {"tests.run","shell.readonly"} & {tool["name"] for tool in calls[0].tools}

def role_artifact_payloads(engine,run,kind):
    return [json.loads(Path(row["path"]).read_text())["payload"] for row in engine.state.artifacts(run) if row["kind"]==kind]

@pytest.mark.parametrize("format",["json","fence"])
def test_valid_role_output_persists_original_raw_and_runtime_delivery(tmp_path,format):
    payload=plan()
    raw=json.dumps(payload,indent=2)
    if format=="fence": raw="```json\n"+raw+"\n```"
    class Provider(MockProvider):
        def invoke(self,request):
            return InvocationResult(output=payload if format=="json" else raw,raw_text=raw,model="mock",input_tokens=2,output_tokens=3)
    engine,run,packet,gateway,broker=make(tmp_path,Provider(),True)
    result=engine._invoke(run,"planner","PLAN",packet,0,"S",gateway)
    assert result==payload
    metadata=list(engine._role_handoff_metadata(run).values())[0]
    assert metadata["schema_version"]==1 and metadata["producer"]=="planner"
    assert metadata["intended_recipient"]=="runtime:plan_review" and metadata["recipient_kind"]=="runtime"
    assert metadata["parsed_payload"]==payload and metadata["validation_problems"]==[]
    assert metadata["delivery"]=="pending"
    raw_record=json.loads(Path(metadata["raw_artifact_ref"]["path"]).read_text())["payload"]
    assert raw_record["raw"]==raw
    assert raw_record["raw_sha256"]==hashlib.sha256(raw.encode()).hexdigest()==metadata["raw_sha256"]
    assert metadata["evidence_refs"][0]["invocation_id"]==metadata["invocation_id"]
    assert engine.state.total_usage(run)=={"calls":1,"tokens":5}
    engine._ack_role_handoffs(run,"runtime:plan_review")
    updated=list(engine._role_handoff_metadata(run).values())[0]
    assert updated["delivery"]=="delivered" and updated["delivered_to"]=="runtime:plan_review"
    assert updated["acknowledgment"]=="received"
    assert role_artifact_payloads(engine,run,"handoff_delivery")[-1]["recipient_kind"]=="runtime"

def test_successful_format_repair_retains_original_raw_and_counts_once(tmp_path):
    requests=[]
    original="Original findings: clamp lower branch is wrong. Preserve this fact."
    class Provider(MockProvider):
        def invoke(self,request):
            requests.append(request)
            return InvocationResult(output=original if len(requests)==1 else plan(),raw_text=original if len(requests)==1 else json.dumps(plan()),model="mock",input_tokens=2,output_tokens=3)
    engine,run,packet,gateway,broker=make(tmp_path,Provider(),True)
    assert engine._invoke(run,"planner","PLAN",packet,0,"S",gateway)==plan()
    assert len(requests)==2 and requests[1].tools==()
    raws=role_artifact_payloads(engine,run,"role_raw")
    assert [row["raw"] for row in raws]==[original,json.dumps(plan())]
    metadata=engine._role_handoff_metadata(run)
    first=metadata[requests[0].idempotency_key]
    assert first["validation_problems"] and first["parsed_payload"] is None
    assert first["delivered_to"]=="agent:planner" and first["delivery_route"]=="format_repair"
    repaired=metadata[requests[1].idempotency_key]
    assert repaired["parsed_payload"]==plan() and repaired["delivery"]=="pending"
    assert engine.state.total_usage(run)=={"calls":2,"tokens":10}

def test_raw_and_parsed_metadata_redact_sensitive_values(tmp_path):
    payload={"changed_files":[],"commands":[],"observations":["password=private-value"]}
    class Provider(MockProvider):
        def invoke(self,request):
            return InvocationResult(output=payload,raw_text=json.dumps(payload),model="mock",input_tokens=1,output_tokens=1)
    engine,run,packet,gateway,broker=make(tmp_path,Provider(),True)
    engine.state.prepare_plan_approval(run,"plan")
    engine.state.decide_approval(run,"plan","plan","approved","unit-test")
    packet["plan_hash"]="plan"
    engine._invoke(run,"implementer","IMPLEMENT",packet,0,"S",gateway)
    assert "private-value" not in json.dumps(role_artifact_payloads(engine,run,"role_raw"))
    assert "private-value" not in json.dumps(role_artifact_payloads(engine,run,"handoff_metadata"))

def test_reviewer_receives_persisted_test_evidence_and_current_read_receipts(tmp_path):
    engine,run,packet,gateway,broker=make(tmp_path)
    oracle=broker.repo/"test_clamp.py";oracle.write_text("import unittest\n")
    engine.task_contract["verification_commands"]=[["python","-m","unittest","discover","-p","test_clamp.py"]]
    result={"argv":engine.task_contract["verification_commands"][0],"returncode":0,"timeout":False,"cancelled":False,"image":"sha256:"+"a"*64,
        "source_snapshot_sha256":"b"*64,"source_hashes":{"clamp.py":hashlib.sha256((broker.repo/"clamp.py").read_bytes()).hexdigest()},"stdout":"5 tests passed"}
    engine.artifacts.put(run,"test_receipts","runtime",{"commands":[{"ok":True,"result":result}],"tested_scope_hash":"candidate"})
    engine.artifacts.put(run,"test_execute","runtime",{"verdict":"pass"})
    extra=engine._role_extra(run,"code_reviewer",packet,broker)
    evidence=extra["VERIFICATION_EVIDENCE"]
    assert evidence["verdict"]=="pass" and evidence["commands"][0]["recorded_gateway_ok"] is True
    assert evidence["commands"][0]["returncode"]==0 and evidence["commands"][0]["image"]==result["image"]
    assert evidence["commands"][0]["source_hashes"]==result["source_hashes"]
    sources=extra["SOURCE_SNAPSHOTS"]
    assert {row["path"] for row in sources}=={"clamp.py","test_clamp.py"}
    assert all(engine.state.tool_operation(row["operation_ref"])["phase"]=="CODE_REVIEW" for row in sources)
    assert all(engine.state.tool_operation(row["operation_ref"])["role"]=="code_reviewer" for row in sources)


def _approved_implementation(engine,run,packet):
    for phase in ("INTAKE","SIZE","DECIDE","PLAN","PLAN_REVIEW"):
        engine.state.transition(run,phase,{},run+":"+phase)
    packet["plan"]=plan()
    engine._ready_to_build(run,packet)
    return packet["plan_hash"]

def test_invalid_write_receipt_never_commits_implementation_or_recovers(tmp_path,monkeypatch):
    from agent_core.lifecycle import ReconciliationRequired
    engine,run,packet,gateway,broker=make(tmp_path)
    plan_hash=_approved_implementation(engine,run,packet)
    result=gateway.execute(run,"implementer","IMPLEMENT","filesystem.write",
        {"path":"clamp.py","content":"value=2\n","expected_sha256":hashlib.sha256(b"value=1\n").hexdigest()},
        plan_allowlist=["clamp.py"],plan_hash=plan_hash,operation_id="accepted")
    assert result["sha256"]
    with engine.state._connect() as c:
        c.execute("UPDATE tool_operations SET result=? WHERE operation_id='accepted'",(json.dumps({"path":"clamp.py","sha256":"0"*64}),))
    monkeypatch.setattr(engine,"_implement_chunks",lambda *a:{"changed_files":["clamp.py"],"commands":[],"observations":[],"blocked":False})
    with pytest.raises(ReconciliationRequired):
        engine._run_phase(run,"IMPLEMENT","S",packet,gateway,broker)
    assert engine.state.get(run)["phase"]=="READY_TO_BUILD"
    with pytest.raises(ReconciliationRequired): engine.reconcile_tools(run)
    assert engine.state.get(run)["status"]=="RECONCILIATION_REQUIRED"
    monkeypatch.setattr(engine,"_invoke",lambda *a,**kw:pytest.fail("Invalid write evidence cannot dispatch a model"))
    assert engine.run(run)["status"]=="RECONCILIATION_REQUIRED"

def test_real_broker_rejects_historical_traversal_and_symlink_escape(tmp_path):
    from agent_core.lifecycle import ReconciliationRequired
    engine,run,packet,gateway,broker=make(tmp_path)
    ph=_approved_implementation(engine,run,packet)
    external=tmp_path/"outside.py"; external.write_text("outside")
    for index,path in enumerate(("../outside.py","escape.py")):
        if path=="escape.py": (broker.repo/path).symlink_to(external)
        engine.task_contract["allowed_paths"]=[path]
        actor="task-contract:"+digest(engine.task_contract)
        with engine.state._connect() as c: c.execute("UPDATE approvals SET actor=? WHERE run_id=?",(actor,run))
        op="bad"+str(index)
        engine.state.set_status(run,"ACTIVE")
        engine.state.begin_tool_operation(op,run,"implementer","IMPLEMENT","filesystem.write",{"path":path,"content":"outside"},ph,str(external),hashlib.sha256(b"outside").hexdigest())
        engine.state.finish_tool_operation(op,{"path":path,"sha256":hashlib.sha256(b"outside").hexdigest()})
        with pytest.raises(ReconciliationRequired): engine._accepted_write_paths(run,broker,[path])
        with engine.state._connect() as c: c.execute("DELETE FROM tool_operations WHERE operation_id=?",(op,))

def test_narrow_repair_plan_keeps_prior_approved_effects_without_new_authority(tmp_path,monkeypatch):
    engine,run,packet,gateway,broker=make(tmp_path)
    engine.task_contract["allowed_paths"]=["clamp.py","b.py"]
    engine.task_contract["operations"]=["modify","create"]
    gateway.task_contract=engine.task_contract
    ph=_approved_implementation(engine,run,packet)
    gateway.execute(run,"implementer","IMPLEMENT","filesystem.write",
        {"path":"clamp.py","content":"value=2\n","expected_sha256":hashlib.sha256(b"value=1\n").hexdigest()},
        plan_allowlist=["clamp.py"],plan_hash=ph,operation_id="first")
    repair={"file_allowlist":["b.py"],"change_units":[{"id":"b","file":"b.py","operation":"create","summary":"Repair"}],"unresolved_questions":[],"verification_commands":plan()["verification_commands"]}
    packet["plan"]=repair
    engine.state.prepare_plan_approval(run,"repair")
    engine.state.decide_approval(run,"plan","repair","approved","task-contract:"+digest(engine.task_contract))
    gateway.execute(run,"implementer","IMPLEMENT","filesystem.write",{"path":"b.py","content":"ok\n"},plan_allowlist=["b.py"],plan_hash="repair",operation_id="second")
    assert engine._accepted_write_paths(run,broker,["b.py"])==["clamp.py","b.py"]
    engine.artifacts.put(run,"plan","planner",repair)
    packet["implement"]={"changed_files":["clamp.py","b.py"]}
    original=json.loads(json.dumps(packet["plan"]))
    def evaluate_only(self,rid,view):
        assert view["plan"]["file_allowlist"]==["b.py","clamp.py"]
        assert self.state.get(rid)["plan_hash"]=="repair"
        view["acceptance"]={"verdict":"scope-evaluated"}
        return "ok"
    from daily_coder.orchestrator import Orchestrator
    monkeypatch.setattr(Orchestrator,"_acceptance",evaluate_only)
    assert engine._acceptance(run,packet)=="ok"
    assert packet["plan"]==original
    assert engine.artifacts.load(run,"plan")==original
    assert engine.state.approval_state(run,"plan","repair")=="approved"
    rejected=gateway.safe_execute(run,"implementer","IMPLEMENT","patch.apply",{"path":"clamp.py","find":"value=2","replace":"value=3","expected_sha256":hashlib.sha256(b"value=2\n").hexdigest()},plan_allowlist=["b.py"],plan_hash="repair",operation_id="forbidden-new-write")
    assert rejected["ok"] is False
    assert (broker.repo/"clamp.py").read_text()=="value=2\n"
