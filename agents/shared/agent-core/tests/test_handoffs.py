import json
import pytest
from agent_core.handoffs import normalize,incomplete
SCHEMA={"type":"object","properties":{"changed_files":{"type":"array","items":{"type":"string"}}},"required":["changed_files"],"additionalProperties":False}
@pytest.mark.parametrize("value",[{"changed_files":["a.py"]},'{"changed_files":["a.py"]}','\ufeff```json\n{"changed_files":["a.py"]}\n```','Findings follow: {"changed_files":["a.py"]} done',{"files_changed":["a.py"]}])
def test_presentation_variants(value):
    result,errors=normalize(value,SCHEMA)
    assert result=={"changed_files":["a.py"]} and not errors
def test_ambiguous_outputs_and_missing_values_are_not_fabricated():
    result,errors=normalize('{"changed_files":["a"]} {"changed_files":["b"]}',SCHEMA)
    assert result is None and errors
    assert normalize("plain incomplete findings",SCHEMA)[0] is None
def test_repeated_identical_text_is_ambiguous_and_oversized_input_is_bounded():
    result,errors=normalize('{"changed_files":["a"]} {"changed_files":["a"]}',SCHEMA)
    assert result is None and errors
    result,errors=normalize("prose"*10000+'{"changed_files":["a"]}',SCHEMA)
    assert result is None and errors==["role output exceeds recovery bound"]

def test_handoff_bounds_and_tracks_raw_context():
    value=incomplete("x"*40000,run_id="run",role="planner",phase="PLAN",invocation_id="call",recipient="plan_reviewer",contract_hash="hash")
    h=value["_incomplete_handoff"]
    assert len(h["raw"].encode())<=32000
    assert h["recipient"]=="plan_reviewer" and h["payload"] is None and h["delivery"]=="pending"
def test_transport_integrity_still_rejects_invalid_tools():
    from agent_core.providers.base import Invocation
    from agent_core.providers.codex_cli import parse_codex_jsonl,ENVELOPE_VERSION
    from agent_core.providers.http import ProviderError
    def rows(output,calls):
        return [json.dumps({"type":"thread.started","thread_id":"one"}),json.dumps({"type":"item.completed","item":{"type":"agent_message","text":json.dumps({"version":ENVELOPE_VERSION,"output_json":output,"tool_calls":calls})}}),json.dumps({"type":"turn.completed","usage":{"input_tokens":2,"output_tokens":3}})]
    request=Invocation("r","planner","prompt",{},"small",100,"key",model="pinned",output_schema=SCHEMA,allow_incomplete_output=True)
    result=parse_codex_jsonl(rows("plain findings",[]),request,model="pinned")
    assert result.output=="plain findings" and result.usage.total_tokens==5
    with pytest.raises(ProviderError):
        parse_codex_jsonl(rows(None,[{"name":"unknown","arguments_json":"{}","call_id":"x"}]),request,model="pinned")
    strict=Invocation("r","planner","prompt",{},"small",100,"key",model="pinned",output_schema=SCHEMA)
    with pytest.raises(ProviderError): parse_codex_jsonl(rows("plain findings",[]),strict,model="pinned")
