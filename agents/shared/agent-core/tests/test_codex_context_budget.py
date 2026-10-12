import pytest
from daily_coder import context

def test_tool_schema_and_output_schema_are_in_full_reservation():
    base=context.estimate_tokens("prompt",{},100,[])
    tools=[{"name":"inspect","parameters":{"description":"x"*24000}}]
    complete=context.estimate_tokens("prompt",{},100,[],tools=tools,output_schema={"description":"x"*4000})
    assert complete-base>=7000

def test_estimate_rounds_up_partial_token():
    assert context.estimate_tokens("abc",{},0,[])>=2

def test_persistent_zero_api_cash_cap_allows_only_zero_cash(tmp_path):
    from daily_coder.state_store import StateStore
    state=StateStore(tmp_path/"state.sqlite")
    state.create("run","request",str(tmp_path),"hash","create")
    state.reserve_budget("run","one","today",10,0,run_token_limit=100,run_call_limit=10,run_usd_limit=0)
    with pytest.raises(ValueError):state.reserve_budget("run","two","today",10,.001,run_token_limit=100,run_call_limit=10,run_usd_limit=0)

def test_provider_failure_receipt_redacts_message_and_raw_diagnostics():
    from daily_coder.orchestrator import Orchestrator
    from agent_core.providers.http import ProviderError
    class Store:
        def put(self,*args):self.saved=args[-1]
    engine=object.__new__(Orchestrator);engine.artifacts=Store()
    error=ProviderError("private credential",category="response",remote_acceptance="unknown")
    error.reason_code="role_schema";error.diagnostics={"exit_code":1,"raw":"private credential","output_bytes":20}
    engine._record_provider_failure("run","key",error)
    assert engine.artifacts.saved["reason_code"]=="role_schema"
    assert "private credential" not in str(engine.artifacts.saved)
    assert engine.artifacts.saved["diagnostics"]=={"exit_code":1,"output_bytes":20}

def test_known_completed_schema_failure_can_settle_then_use_quality_repair():
    from daily_coder.orchestrator import Orchestrator
    from agent_core.providers.base import Invocation,InvocationResult,TokenUsage
    from agent_core.providers.http import ProviderError
    request=Invocation("run","planner","",{},"pinned",10,"key",model="model")
    receipt=InvocationResult(output=None,model="model",usage=TokenUsage(3,2,evidence_status="reported"),finish_reason="invalid_output_schema")
    error=ProviderError(category="response",remote_acceptance="accepted");error.reason_code="role_schema";error.response=receipt
    class Provider:
        name="codex_cli"
        def invoke(self,request):raise error
    engine=object.__new__(Orchestrator);engine.provider=Provider();engine._record_provider_failure=lambda *args:None
    assert engine._invoke_provider(request) is receipt
    engine.provider.name="openai"
    with pytest.raises(ProviderError):engine._invoke_provider(request)
    engine.provider.name="codex_cli";receipt.tool_calls=[object()]
    with pytest.raises(ProviderError):engine._invoke_provider(request)

def test_planning_receives_pipeline_boundary_without_write_authority():
    from daily_coder.orchestrator import Orchestrator
    class Authority:
        def effective(self,role):return type("Grant",(),{"capabilities":lambda self,kind:frozenset({"filesystem.write"}) if role=="implementer" else frozenset()})()
    engine=object.__new__(Orchestrator);engine._dispatch_boundary=lambda key:None
    engine.skills=type("Skills",(),{"load":lambda *a,**k:[]})();engine.config={}
    extra=engine._role_extra("run","planner",{},type("Broker",(),{"authority":Authority()})())
    pipeline=extra["EXECUTION_CONTRACT"]
    assert pipeline["implementer_write_tool_configured"] is True
    assert pipeline["current_role_write_authorization"] is False
    assert pipeline["plan_review_precedes_human_approval"] is True
    assert pipeline["writes_require_approved_plan"] is True
