import importlib.util
from pathlib import Path
from types import SimpleNamespace
from agent_core.providers.base import InvocationResult,Invocation

def driver():
    path=Path(__file__).resolve().parents[1]/"tools/coder-fixtures/run_acceptance.py"
    spec=importlib.util.spec_from_file_location("acceptance_driver",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def test_format_variant_preserves_payload_usage_and_tools():
    result=InvocationResult(output={"files":["source.py"]},model="mock",input_tokens=7,output_tokens=3)
    request=Invocation("run","planner","prompt",{},"strong",100,"id",allow_incomplete_output=True)
    assert driver().format_completed_result(request,result)
    from agent_core.handoffs import normalize
    parsed,errors=normalize(result.output,{"type":"object","required":["files"]})
    assert parsed=={"files":["source.py"]} and not errors
    assert result.input_tokens==7 and result.output_tokens==3 and not result.tool_calls
    assert result.raw_text==result.output

def test_format_variant_does_not_change_tool_responses():
    result=SimpleNamespace(output=None,tool_calls=["existing tool"])
    request=SimpleNamespace(role="planner")
    assert driver().format_completed_result(request,result) is False
    assert result.tool_calls==["existing tool"]
