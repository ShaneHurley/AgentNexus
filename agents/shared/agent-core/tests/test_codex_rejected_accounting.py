"""Rejected role content never executes; proven usage remains accountable."""
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
from agent_core.providers.base import Invocation
from agent_core.providers.codex_cli import parse_codex_jsonl
from agent_core.providers.http import ProviderError


def request():
    return Invocation("run","planner","prompt",{},"strong",128,"key",model="mock")


def stream():
    envelope={"version":"anx_codex_role_v2","output_json":json.dumps({"ok":True}),"tool_calls":[]}
    return [json.dumps(event) for event in [
        {"type":"thread.started","thread_id":"12345678-1234-1234-1234-123456789abc"},
        {"type":"item.completed","item":{"type":"agent_message","text":"{rejected content}"}},
        {"type":"item.completed","item":{"type":"agent_message","text":json.dumps(envelope)}},
        {"type":"turn.completed","usage":{"input_tokens":3,"output_tokens":4}}]]


def rejection(lines,req=None):
    with pytest.raises(ProviderError) as error:
        parse_codex_jsonl(lines,req or request(),model="mock")
    return error.value


def test_rejected_output_preserves_only_proven_usage():
    lines=stream(); error=rejection(lines)
    assert error.reason_code=="preceding_structured" and error.remote_acceptance=="accepted"
    assert not hasattr(error,"response")
    receipt=error.accounting_receipt
    assert receipt.output is None and receipt.tool_calls==[] and receipt.raw_text is None
    assert (receipt.input_tokens,receipt.output_tokens)==(3,4)
    assert error.accounting_metadata["stream_sha256"]==hashlib.sha256("\n".join(lines).encode()).hexdigest()
    assert "rejected content" not in repr(error.accounting_metadata)


@pytest.mark.parametrize("defect",["missing_usage","missing_terminal","duplicate_terminal","after_terminal","native","unknown","failed","duplicate_field","bad_usage","duplicate_start","bad_final"])
def test_uncertain_stream_retains_reservation(defect):
    lines=stream()
    if defect=="missing_usage": lines[-1]=json.dumps({"type":"turn.completed"})
    if defect=="missing_terminal": lines.pop()
    if defect=="duplicate_terminal": lines.append(lines[-1])
    if defect=="after_terminal": lines.append(json.dumps({"type":"turn.started"}))
    if defect=="native": lines.insert(2,json.dumps({"type":"item.completed","item":{"type":"command_execution"}}))
    if defect=="unknown": lines.append(json.dumps({"type":"mystery"}))
    if defect=="failed": lines.append(json.dumps({"type":"turn.failed"}))
    if defect=="duplicate_field": lines[-1]='{"type":"turn.completed","usage":{"input_tokens":3,"input_tokens":8,"output_tokens":4}}'
    if defect=="bad_usage": lines[-1]=json.dumps({"type":"turn.completed","usage":{"input_tokens":True,"output_tokens":4}})
    if defect=="duplicate_start": lines.insert(1,lines[0])
    if defect=="bad_final": lines[-2]=json.dumps({"type":"item.completed","item":{"type":"agent_message","text":"{bad}"}})
    error=rejection(lines)
    assert not hasattr(error,"accounting_receipt")
    assert error.remote_acceptance=="unknown"


spec=importlib.util.spec_from_file_location("accounting_helpers",Path(__file__).resolve().parents[3]/"coding/daily-coder-ecosystem/tests/test_coder_v1.py")
helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)


class RejectingProvider:
    name="codex_cli"
    billing_kind="chatgpt_subscription"
    subscription_models=("mock",)
    max_parallelism=1
    def __init__(self): self.calls=0
    def resolve_for_role(self,*args,**kwargs): return "mock"
    def invoke(self,req):
        self.calls+=1
        raise rejection(stream(),req)


def test_runtime_settles_failed_invocation_without_repair_or_execution(tmp_path):
    provider=RejectingProvider()
    engine,run,*_=helpers.make(tmp_path,provider,live=True)
    result=engine.run(run)
    assert result["status"]=="FAILED"
    assert provider.calls==1
    assert engine.state.active_budget_reservations(run)=={"tokens":0,"calls":0,"est_usd":0.0}
    assert engine.state.total_usage(run)["tokens"]==7
    records=engine.state.invocations(run)
    assert len(records)==1 and records[0]["status"]=="error_accounted"
    assert engine.state.write_operations(run)==[]
    assert "plan" not in engine.artifacts.load_all(run)
    assert "accounting_only_failure" in engine.artifacts.load_all(run)


@pytest.mark.parametrize("tamper",[None,"run","invocation","model","thread","usage","payload"])
def test_accounting_correlation_and_duplicate_settlement(tmp_path,tamper):
    import time
    from agent_core.providers.base import TokenUsage
    from daily_coder.budget import _today
    engine,run,*_=helpers.make(tmp_path,RejectingProvider(),live=True)
    req=Invocation(run,"planner","prompt",{"phase":"UNTRUSTED"},"strong",128,"receipt",model="mock")
    error=rejection(stream(),req)
    if tamper=="run": error.accounting_metadata["run_id"]="other"
    if tamper=="invocation": error.accounting_metadata["invocation_id"]="other"
    if tamper=="model": error.accounting_receipt.model="other"
    if tamper=="thread": error.accounting_receipt.raw_ref="codex-thread:other"
    if tamper=="usage": error.accounting_receipt.usage=TokenUsage(input_tokens=8,output_tokens=4,evidence_status="reported")
    if tamper=="payload": error.accounting_receipt.output={"ok":True}
    estimate=100
    engine.budget.reserve(run,"S",estimate,model="mock",reservation_id=req.idempotency_key)
    cfg={"_phase":"PLAN","model_tier":"strong"}
    assert engine._account_rejected_call(req,error,estimate,"main",0,cfg,time.time()) is (tamper is None)
    if tamper:
        assert engine.state.active_budget_reservations(run)["tokens"]==100
        assert engine.state.total_usage(run)["tokens"]==0
        assert not engine.state.invocations(run)
    else:
        assert engine._account_rejected_call(req,error,estimate,"main",0,cfg,time.time())
        assert engine.state.total_usage(run)["tokens"]==7
        assert engine.state.spend(_today())["tokens"]==7
        assert engine.state.unreceipted_settlements(run)["calls"]==0
        assert len(engine.state.invocations(run))==1
        assert engine.state.invocations(run)[0]["phase"]=="PLAN"


def test_budget_refusal_reports_task_profile_and_daily_headroom(tmp_path):
    from daily_coder.budget import BudgetExceeded,_today
    engine,run,*_=helpers.make(tmp_path,RejectingProvider(),live=True)
    budget=engine.budget
    budget.limits.update(max_tokens_per_run=50000,max_tokens_per_day=500000)
    budget.config["profiles"]["S"]["total_tokens"]=80000
    engine.state.record_invocation(run,"implementer","IMPLEMENT","main",0,"strong","mock",30000,7604,0,0,"error_accounted","rejected","old")
    engine.state.add_spend(_today(),37604,0)
    with pytest.raises(BudgetExceeded) as error:
        budget.reserve(run,"S",13000,model="mock",reservation_id="next")
    report=error.value.args[0]
    assert report["reason"]=="persistent_budget_cap"
    d=report["diagnostics"]
    assert d["run_grant_tokens"]==d["effective_run_tokens"]==50000
    assert d["consumed_tokens"]==37604 and d["next_call_estimate"]==13000
    assert d["daily_headroom"]==462396 and d["daily_ceiling"]==500000
    assert d["active_provider_reservations"]["tokens"]==0
    assert engine.state.total_usage(run)["tokens"]==37604


def test_diagnostician_rejection_stops_without_fallback_or_retry(tmp_path):
    provider=RejectingProvider()
    engine,run,packet,*_=helpers.make(tmp_path,provider,live=True)
    result=engine._repair(run,"PLAN","original failure",packet,0)
    assert result["status"]=="FAILED" and provider.calls==1
    assert engine.state.total_usage(run)["tokens"]==7
    assert engine.state.active_budget_reservations(run)["calls"]==0
    assert "diagnosis" not in engine.artifacts.load_all(run)


@pytest.mark.parametrize("boundary",["size","frontier"])
def test_optional_fallbacks_propagate_accounted_failure(tmp_path,monkeypatch,boundary):
    from daily_coder.orchestrator import Orchestrator,AccountedProviderFailure
    import daily_coder.orchestrator as module
    engine,run,*_=helpers.make(tmp_path,RejectingProvider(),live=True)
    calls=[]
    def reject(*args,**kwargs):
        calls.append(args)
        raise AccountedProviderFailure("preceding_structured")
    monkeypatch.setattr(engine,"_invoke",reject)
    monkeypatch.setattr(module,"size_request",lambda value:{"ambiguous":True,"profile":"S","score":1,"reasons":[]})
    monkeypatch.setattr(module,"authorize_frontier",lambda *args,**kwargs:(True,"test"))
    with pytest.raises(AccountedProviderFailure):
        if boundary=="size": Orchestrator._size(engine,run,"ambiguous")
        else: engine._maybe_frontier(run,"PLAN","failure",{},"S",2)
    assert len(calls)==1
    assert "frontier_advice" not in engine.artifacts.load_all(run)


class RepairRejectingProvider(RejectingProvider):
    def invoke(self,req):
        from agent_core.providers.base import InvocationResult
        self.calls+=1
        if self.calls==1:
            return InvocationResult(output={"invalid":"role"},input_tokens=2,output_tokens=1,model="mock")
        assert req.input_packet.get("OUTPUT_CORRECTION")
        raise rejection(stream(),req)


def test_format_repair_rejection_accounts_both_calls_then_stops(tmp_path):
    provider=RepairRejectingProvider()
    engine,run,*_=helpers.make(tmp_path,provider,live=True)
    result=engine.run(run)
    assert result["status"]=="FAILED" and provider.calls==2
    assert engine.state.total_usage(run)["tokens"]==10
    assert engine.state.active_budget_reservations(run)["calls"]==0
    assert sorted(row["status"] for row in engine.state.invocations(run))==["error_accounted","ok"]
    assert engine.state.write_operations(run)==[]
    assert "plan" not in engine.artifacts.load_all(run)
