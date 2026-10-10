import hashlib
import pytest
from agent_core.efficiency_tools import repo_outline, context_pack, tool_result_reduce, evidence_extract, usage_report
from agent_core.contracts import Grant, EffectiveGrant, ContractDenied, LAYERS

def access(root):
    value={"tools":["filesystem.read"],"workspace_roots":[str(root)]}
    return EffectiveGrant.evaluate({"id":"dc:researcher","active":True,"leaf":True,"grant":value},{k:value for k in LAYERS})

def test_outline_does_not_execute_and_denies_escape(tmp_path):
    p=tmp_path/"code.py";p.write_text("raise RuntimeError('must never execute')\ndef useful(a:int)->str: return str(a)\n")
    out=repo_outline(p,access(tmp_path))
    assert out["symbols"][0]["name"] == "useful"
    outside=tmp_path.parent/"outside.py";outside.write_text("pass")
    (tmp_path/"link.py").symlink_to(outside)
    with pytest.raises(ContractDenied): repo_outline(tmp_path/"link.py",access(tmp_path))

def test_context_protects_authority_and_bounds_evidence():
    protected={k:{"value":k} for k in ("intent","constraints","permissions","approval_hash","plan_hash","budget","pending_calls")}
    out=context_pack(protected,[{"id":"e1","text":"x"*20000}],evidence_tokens=10)
    assert out["protected"] == protected and not out["evidence"]
    with pytest.raises(ValueError):context_pack({},[])

def test_reduce_keeps_status_and_sanitized_original(tmp_path):
    out=tool_result_reduce({"stdout":"secret-value\n"+"x"*20000,"stderr":"bad","returncode":7},tmp_path,known_secrets=["secret-value"],max_chars=100)
    assert out["returncode"] == 7 and out["truncated"]
    original=(tmp_path/(out["artifact_id"]+".json")).read_text()
    assert "secret-value" not in original and len(original)>20000

def test_extraction_retains_table_and_provenance():
    html="<script>bad()</script><table><tr><td>Only if X</td><td>5</td></tr></table>"
    out=evidence_extract(html,{"id":"s1","retrieval_status":"retrieved"})
    assert "Only if X" in out["text"] and "5" in out["text"] and "bad()" not in out["text"]
    assert out["original_hash"] == hashlib.sha256(html.encode()).hexdigest()

def test_report_unknown_cost_is_not_zero():
    out=usage_report([{"role":"r","phase":"p","input_tokens":0,"output_tokens":0,"cost_usd":None,"evidence_status":"unknown"}])
    assert out["cost_usd"] is None and out["unknown_calls"] == 1


def test_missing_token_usage_remains_unknown():
    from agent_core.efficiency_tools import usage_report
    result=usage_report([{"input_tokens":0,"output_tokens":1,"cost_usd":0},{"output_tokens":2}])
    assert result["input_tokens"] is None and result["known_input_tokens"]==0
    assert result["output_tokens"]==3 and result["unknown_input_calls"]==1
