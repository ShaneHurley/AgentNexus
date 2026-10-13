import hashlib,json
from pathlib import Path
from unittest.mock import patch
from daily_coder.state_store import StateStore
from daily_coder.tool_broker import ToolBroker
from daily_coder.policy import PolicyGateway

DC=Path(__file__).resolve().parents[1]

def test_supplied_hash_binds_inspected_bytes_when_file_changes(tmp_path):
    target=tmp_path/"code.py";original=b"value = 1\n";target.write_bytes(original)
    broker=ToolBroker(tmp_path,json.loads((DC/"config/tools.json").read_text()),json.loads((DC/"config/policies.json").read_text()))
    read_bytes=Path.read_bytes
    def racing_read(path):
        result=read_bytes(path)
        if path==target: path.write_bytes(b"value = 2\n")
        return result
    with patch.object(Path,"read_bytes",racing_read):
        result=broker.execute("implementer","filesystem.read",{"path":"code.py"})
    assert result["content"]=="1\tvalue = 1"
    assert result["sha256"]==hashlib.sha256(original).hexdigest()
    state=StateStore(tmp_path/"state.sqlite");state.create("run","task",str(tmp_path),"pin","run:create")
    state.prepare_plan_approval("run","plan")
    state.decide_approval("run","plan","plan","approved","operator")
    gateway=PolicyGateway(broker,state,broker.policy,True)
    denied=gateway.safe_execute("run","implementer","IMPLEMENT","filesystem.write",{"path":"code.py","content":"value = 3\n","expected_sha256":result["sha256"]},plan_allowlist=["code.py"],plan_hash="plan")
    assert denied["ok"] is False
    assert target.read_bytes()==b"value = 2\n"
