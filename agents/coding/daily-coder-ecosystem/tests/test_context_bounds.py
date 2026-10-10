"""Regressions for complete serialized tool-context bounds."""
import json
import pytest
from daily_coder.context import project_tool_results

@pytest.mark.parametrize("text", ["x" * 50000, "\U0001f642" * 10000], ids=["ascii", "unicode"])
def test_single_large_failed_result_keeps_receipt_and_status_within_bound(text):
    item={"call_id":"call-1","operation_ref":"run-1:turn-0:tool:0","tool":"tests.run", "ok":True,
          "arguments":{"command":"pytest"}, "result":{"stdout":text,"stderr":"failure details", "returncode":7,"timeout":False,"cancelled":False}}
    original=json.dumps(item,sort_keys=True)
    projected=project_tool_results([item])
    assert len(json.dumps(projected,sort_keys=True,default=str)) <= 24000
    assert projected[0]["call_id"] == "call-1"
    assert projected[0]["operation_ref"] == "run-1:turn-0:tool:0"
    assert projected[0]["result"]["returncode"] == 7
    assert projected[0]["truncated"] is True
    assert projected[0]["result_hash"]
    assert json.dumps(item,sort_keys=True) == original

def test_large_old_arguments_do_not_escape_projection_bound():
    items=[{"call_id":f"call-{i}","operation_ref":f"run:tool:{i}","tool":"filesystem.read","ok":False,
            "arguments":{"path":"x"*20000},"error":"denied","result":{}} for i in range(20)]
    projected=project_tool_results(items,max_chars=12000,recent=2)
    assert len(json.dumps(projected,sort_keys=True,default=str)) <= 12000
    assert projected[0]["compacted"] is True
    assert len(projected[0]["evidence"]) == 18
    assert projected[0]["evidence"][0]["operation_ref"] == "run:tool:0"
    assert projected[0]["evidence"][0]["error"] == "denied"

def test_unfittable_receipt_metadata_stops_instead_of_silently_discarding():
    items=[{"call_id":f"call-{i}","tool":"inspect","ok":True,"result":{}} for i in range(1000)]
    with pytest.raises(ValueError,match="stop or split"):
        project_tool_results(items,max_chars=1000)


def test_optional_arguments_are_removed_before_rejecting_fittable_receipts():
    items=[{"call_id":f"call-{i}","operation_ref":f"run:tool:{i}","tool":"filesystem.read","ok":True,
            "arguments":{"path":"x"*800},"result":{"stdout":"y"*1000}} for i in range(30)]
    projected=project_tool_results(items)
    assert len(json.dumps(projected,sort_keys=True,default=str)) <= 24000
    refs=projected[0]["evidence"]+projected[1:]
    assert len(refs) == 30
    assert all(ref["operation_ref"] for ref in refs)
    assert all(ref["arguments_hash"] for ref in refs)
