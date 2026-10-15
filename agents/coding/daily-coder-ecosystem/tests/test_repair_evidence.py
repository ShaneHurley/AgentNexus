"""Failed execution evidence reaches diagnosis and bounded repair unchanged."""
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
from agent_core.providers.base import InvocationResult
from daily_coder.context import build_packet,ContextCapacityError
spec=importlib.util.spec_from_file_location("repair_helpers",Path(__file__).with_name("test_coder_v1.py"))
helpers=importlib.util.module_from_spec(spec); spec.loader.exec_module(helpers)


def failed_fixture(tmp_path,stderr="FAIL: test_independent_bindings\nAssertionError: True is not false\n"):
    calls=[]
    class Provider(helpers.MockProvider):
        def invoke(self,request):
            calls.append(request)
            return InvocationResult(model="mock",input_tokens=1,output_tokens=1,output={
                "failure_class":"test","first_failing_signal":"assertion failed","evidence":[],
                "recommended_action":"repair","target_phase":"IMPLEMENT","rationale":"Use failing assertion","unknowns":[]})
    engine,run,packet,gateway,broker=helpers.make(tmp_path,Provider(),True)
    for phase in ("INTAKE","SIZE","DECIDE","PLAN","PLAN_REVIEW"): engine.state.transition(run,phase,{},run+phase)
    packet["plan"]=helpers.plan();engine.artifacts.put(run,"plan","planner",packet["plan"]);engine._ready_to_build(run,packet)
    engine.state.transition(run,"IMPLEMENT",{},run+":implementation")
    def execute(run_id,role,phase,tool,args,**kw):
        result={"argv":args["argv"],"returncode":1,"timeout":False,"cancelled":False,"stdout":"", "stderr":stderr,"image":"pinned-image","source_snapshot_sha256":"a"*64,"source_hashes":{"clamp.py":hashlib.sha256((broker.repo/"clamp.py").read_bytes()).hexdigest()}}
        engine.state.begin_tool_operation(kw["operation_id"],run_id,role,phase,tool,args,kw["plan_hash"])
        engine.state.finish_tool_operation(kw["operation_id"],result)
        return {"ok":True,"result":result}
    gateway.safe_execute=execute
    assert engine._run_phase(run,"TEST_EXECUTE","S",packet,gateway,broker)[0]=="repair"
    engine.state.bump_repair(run)
    return engine,run,packet,gateway,broker,calls


def test_real_failed_receipt_reaches_diagnostician_provider(tmp_path):
    engine,run,packet,gateway,broker,calls=failed_fixture(tmp_path)
    engine._invoke(run,"failure_diagnostician","DIAGNOSE",packet,0,"S",None,{"phase":"TEST_EXECUTE","failure":"isolated verification did not pass","evidence":packet["test_execute"]})
    evidence=calls[0].input_packet["VERIFICATION_EVIDENCE"]
    command=evidence["commands"][0]
    assert "AssertionError" in command["stderr"]
    assert command["returncode"]==1 and command["image"]=="pinned-image"
    assert command["source_snapshot_sha256"]=="a"*64
    assert command["operation_ref"].startswith(run+":runtime-tests:")
    assert evidence["historical"] is True
    assert "tool_requests" not in evidence
    assert not engine._acceptance_verification(run,engine.state.get(run))[0][0].get("decision")=="allow"


def test_repair_implementer_gets_diagnosis_and_persisted_failure(tmp_path):
    engine,run,packet,gateway,broker,calls=failed_fixture(tmp_path)
    diagnosis={"recommended_action":"repair","target_phase":"IMPLEMENT","rationale":"Fix incorrect assertion"}
    engine.artifacts.put(run,"diagnosis","failure_diagnostician",diagnosis)
    extra=engine._role_extra(run,"implementer",packet,broker)
    projected=build_packet("implementer",packet,extra)
    assert projected["REPAIR_CONTEXT"]["diagnosis"]==diagnosis
    assert "AssertionError" in projected["VERIFICATION_EVIDENCE"]["commands"][0]["stderr"]
    assert projected["TASK_CONTRACT"]==engine.task_contract
    assert projected["plan_slice"]==packet["plan"]["change_units"]


@pytest.mark.parametrize("fault",["missing","pending","wrong_run","wrong_role","wrong_plan","arguments","result"])
def test_unproven_receipts_do_not_become_diagnostic_evidence(tmp_path,fault):
    engine,run,packet,gateway,broker,calls=failed_fixture(tmp_path)
    with engine.state._connect() as c:
        if fault=="missing": c.execute("DELETE FROM tool_operations WHERE tool='tests.run'")
        else:
            field,value={"pending":("state","pending"),"wrong_run":("run_id","other"),"wrong_role":("role","implementer"),"wrong_plan":("plan_hash","other"),"arguments":("arguments","{}"),"result":("result","{}")}[fault]
            c.execute("UPDATE tool_operations SET "+field+"=? WHERE tool='tests.run'",(value,))
    assert engine._repair_verification_evidence(run)["incomplete"] is True


def test_large_process_text_is_sanitized_bounded_and_not_marked_complete(tmp_path):
    raw='{"api_key":"'+'not-real-value-'*4+'"}\n'+"x"*30000
    engine,run,packet,gateway,broker,calls=failed_fixture(tmp_path,raw)
    evidence=engine._repair_verification_evidence(run); command=evidence["commands"][0]
    assert len(command["stderr"])<=4000
    assert command["stderr_truncated"] is True
    assert "not-real-value" not in command["stderr"]
    assert len(json.dumps(evidence,sort_keys=True))<=24000
    assert command["stderr_sha256"]==hashlib.sha256(raw.encode()).hexdigest()


def test_oversized_repair_findings_stop_instead_of_becoming_partial_plan():
    with pytest.raises(ContextCapacityError): build_packet("implementer",{}, {"REPAIR_CONTEXT":{"diagnosis":"x"*24000}})
