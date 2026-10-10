import hashlib,json,uuid
import pytest
from agent_core.contracts import LAYERS,ContractDenied
from agent_core.memory_runtime import pin_binding,check_binding,ingest_checkpoint

def test_binding_requires_exact_session_and_grants(tmp_path):
    path=tmp_path/'binding.json'
    path.write_text(json.dumps({'version':1,'session_id':'s1','store':str(tmp_path/'m.sqlite'),'grant':{'version':1,'identity':'owner','run_id':'s1','role':'ide:deep-research','layers':{}}}))
    with pytest.raises(ContractDenied):pin_binding(path,{'session_id':'other','identity':'owner'},tmp_path,'research-forge')

def test_changed_binding_is_not_silent_on_resume(tmp_path):
    path=tmp_path/'binding.json';path.write_text('original')
    pin={'memory_binding_path':str(path),'memory_binding_hash':hashlib.sha256(path.read_bytes()).hexdigest()}
    path.write_text('changed')
    with pytest.raises(ContractDenied):check_binding(pin)

def test_no_binding_does_not_create_memory(tmp_path):
    assert ingest_checkpoint({'snapshot':{},'run_id':'r1','workspace':str(tmp_path)}, {})=={'records':[]}
    assert list(tmp_path.iterdir())==[]
