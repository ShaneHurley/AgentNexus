"""Whole-source fidelity and task-bound review regressions."""
import hashlib,json,importlib.util
from pathlib import Path
import pytest
from agent_core.task_contract import scope_hash
from agent_core.lifecycle import ReconciliationRequired
from daily_coder.context import ContextCapacityError
from daily_coder.candidate_evidence import collect_source,oracle_paths
spec=importlib.util.spec_from_file_location("coder_helpers",Path(__file__).with_name("test_coder_v1.py"))
helpers=importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)

@pytest.mark.parametrize("body",[b"x=1\r\nx=2\r\n",b"x=1",b"",'s="a\u2028b"\n'.encode()])
def test_authorized_source_reconstruction_matches_exact_bytes(tmp_path,body):
    engine,run,packet,gateway,broker=helpers.make(tmp_path)
    (broker.repo/"clamp.py").write_bytes(body)
    source=collect_source(engine.state,gateway,run,"planner","PLAN","clamp.py",run+":fidelity")
    assert source["content"].encode()==body
    assert source["sha256"]==hashlib.sha256(body).hexdigest()
    assert collect_source(engine.state,gateway,run,"planner","PLAN","clamp.py",run+":fidelity",stored=True)==source

def test_invalid_utf8_does_not_become_complete_evidence(tmp_path):
    engine,run,packet,gateway,broker=helpers.make(tmp_path)
    (broker.repo/"clamp.py").write_bytes(b"x=\xff")
    with pytest.raises(ReconciliationRequired): collect_source(engine.state,gateway,run,"planner","PLAN","clamp.py",run+":invalid")

def test_long_pages_retry_smaller_ranges_and_offer_whole_line_expansion(tmp_path):
    engine,run,packet,gateway,broker=helpers.make(tmp_path)
    (broker.repo/"clamp.py").write_text(("x"*500+"\n")*100)
    extra=engine._role_extra(run,"planner",packet,broker); source=extra["SOURCE_SNAPSHOTS"][0]
    assert source["complete"] is False
    assert source["next_read"]["start"]==source["end"]+1
    assert len(source["content"])<=12000
    assert len(json.dumps(extra["SOURCE_SNAPSHOTS"],sort_keys=True))<=24000
    assert engine.state.tool_operation(run+":candidate-baseline:0:0:40") is not None

def test_small_source_and_discovery_oracle_are_correctly_resolved(tmp_path):
    engine,run,packet,gateway,broker=helpers.make(tmp_path)
    (broker.repo/"clamp.py").write_text("value=1\n"*49)
    engine.task_contract["verification_commands"]=[["python","-m","unittest","discover","-s","checks","-p","test_one.py"]]
    sources=engine._role_extra(run,"planner",packet,broker)["SOURCE_SNAPSHOTS"]
    assert sources[0]["complete"] is True and sources[0]["end"]==49
    assert [s["path"] for s in sources]==["clamp.py","checks/test_one.py"]
    assert oracle_paths([["python","-m","unittest","discover","-s","checks","-p","test_*.py"]])==[]

def reviewed_fixture(tmp_path,unused=None):
    engine,run,packet,gateway,broker=helpers.make(tmp_path,live=True)
    engine.task_contract["allowed_paths"].append("new.py"); engine.task_contract["operations"].append("create")
    if unused is not None:
        engine.task_contract["allowed_paths"].append("unused.py")
        if unused: (broker.repo/"unused.py").write_text("unused=1\n")
    gateway.task_contract=engine.task_contract; engine._source_snapshots(run,"planner",broker)
    for phase in ("INTAKE","SIZE","DECIDE","PLAN","PLAN_REVIEW"): engine.state.transition(run,phase,{},run+phase)
    plan=helpers.plan(); plan["file_allowlist"].append("new.py")
    plan["change_units"].append({"id":"new","file":"new.py","operation":"create","summary":"Create"})
    packet["plan"]=plan; engine.artifacts.put(run,"plan","planner",plan); engine._ready_to_build(run,packet); ph=packet["plan_hash"]
    for path,body in (("clamp.py","value=2\n"),("new.py","new_value=3\n")):
        args={"path":path,"content":body}
        if (broker.repo/path).exists(): args["expected_sha256"]=hashlib.sha256((broker.repo/path).read_bytes()).hexdigest()
        gateway.execute(run,"implementer","IMPLEMENT","filesystem.write",args,plan_allowlist=plan["file_allowlist"],plan_hash=ph,operation_id=run+path)
    argv=plan["verification_commands"][0]
    result={"argv":argv,"returncode":0,"timeout":False,"cancelled":False,"image":"pinned-image","source_snapshot_sha256":"b"*64,"source_hashes":{p:hashlib.sha256((broker.repo/p).read_bytes()).hexdigest() for p in engine.task_contract["allowed_paths"] if (broker.repo/p).exists()},"stderr":"Ran 2 tests in 0.1s\n\nOK\n"}
    op=f"{run}:runtime-tests:{ph}:0:c0"
    engine.state.begin_tool_operation(op,run,"test_executor","TEST_EXECUTE","tests.run",{"argv":argv,"timeout":120},ph)
    engine.state.finish_tool_operation(op,result)
    receipt={"schema_version":1,"plan_hash":ph,"repair_cycle":0,"tested_scope_hash":scope_hash(engine.task_contract),"commands":[{"ok":True,"result":result}]}
    engine.artifacts.put(run,"test_receipts","runtime",receipt)
    return engine,run,packet,gateway,broker

def test_review_includes_modified_and_untracked_created_files(tmp_path):
    engine,run,packet,gateway,broker=reviewed_fixture(tmp_path)
    manifest=engine._role_extra(run,"code_reviewer",packet,broker)["CANDIDATE_MANIFEST"]
    assert [row["path"] for row in manifest["files"]]==["clamp.py","new.py"]
    assert manifest["files"][1]["change"]=="create"
    assert "+new_value=3" in manifest["files"][1]["diff"]
    assert engine._review_manifest_valid(run)
    assert not engine._review_manifest_valid(run,require_review=True)
    assert engine._gate(run,"CODE_REVIEW","code_reviewer",{"verdict":"pass","findings":[]},packet) is None
    assert engine._review_manifest_valid(run,require_review=True)
    (broker.repo/"new.py").write_text("forged\n")
    assert not engine._review_manifest_valid(run,require_review=True)

def test_missing_source_baseline_after_write_stops(tmp_path):
    engine,run,packet,gateway,broker=reviewed_fixture(tmp_path)
    with engine.state._connect() as c: c.execute("DELETE FROM tool_operations WHERE operation_id LIKE ?",(run+":candidate-baseline:%",))
    with pytest.raises(ReconciliationRequired): engine._baseline_sources(run,broker)

def test_required_context_capacity_is_deterministic_and_does_not_dispatch(tmp_path,monkeypatch):
    engine,run,packet,gateway,broker=helpers.make(tmp_path,live=True)
    monkeypatch.setattr(engine,"_run_phase",lambda *a:(_ for _ in ()).throw(ContextCapacityError("plan_slice",25000)))
    monkeypatch.setattr(engine.provider,"invoke",lambda *a:pytest.fail("Context overflow must not call provider"))
    assert engine.run(run)["status"]=="FAILED"
    assert engine.state.total_usage(run)["calls"]==0
    assert engine.state.active_budget_reservations(run)["calls"]==0
    assert any("context_capacity" in event["payload"] for event in engine.state.events(run))


def test_forged_receipt_without_matching_durable_execution_is_incomplete(tmp_path):
    engine,run,packet,gateway,broker=reviewed_fixture(tmp_path)
    with engine.state._connect() as c:
        c.execute("DELETE FROM tool_operations WHERE role='test_executor' AND run_id=?",(run,))
    assert engine._candidate_review_manifest(run,broker)["incomplete"] is True

def test_unrecorded_source_changes_cannot_hide_from_review(tmp_path):
    from daily_coder.candidate_evidence import candidate_manifest
    before=[{"path":"a","sha256":"old"}]; after=[{"path":"a","sha256":"new"}]
    with pytest.raises(ReconciliationRequired):
        candidate_manifest({},"p",{"commands":[{}]},before,after,[])


@pytest.mark.parametrize("exists",[True,False])
def test_unchanged_authorized_source_or_absence_is_still_bound_after_review(tmp_path,exists):
    engine,run,packet,gateway,broker=reviewed_fixture(tmp_path,unused=exists)
    engine._role_extra(run,"code_reviewer",packet,broker)
    assert engine._review_manifest_valid(run)
    (broker.repo/"unused.py").write_text("unauthorized=1\n")
    assert not engine._review_manifest_valid(run)
