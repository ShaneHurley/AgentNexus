import json
from agent_core.providers.base import Invocation
from agent_core.providers.codex_cli import parse_codex_jsonl,ENVELOPE_VERSION

def test_opt_in_preserves_completed_role_lexical_content():
    original='  { "ok" : true } \n'
    envelope={"version":ENVELOPE_VERSION,"output_json":original,"tool_calls":[]}
    events=[{"type":"thread.started","thread_id":"thread"},{"type":"item.completed","item":{"type":"agent_message","text":json.dumps(envelope)}},{"type":"turn.completed","usage":{"input_tokens":7,"output_tokens":1}}]
    request=Invocation("run","role","prompt",{},"strong",128,"idem",model="pinned",allow_incomplete_output=True,output_schema={"type":"object"})
    result=parse_codex_jsonl([json.dumps(row) for row in events],request,model="pinned")
    assert result.output=={"ok":True}
    assert result.raw_text==original
    assert result.usage.total_tokens==8
    assert not result.tool_calls
