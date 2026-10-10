import uuid
from pathlib import Path
import pytest
from agent_core.contracts import LAYERS,ContractDenied
from agent_core.registry_snapshot import compile_repository
from agent_core.memory_authority import evaluate_memory_access
ROOT=Path(__file__).resolve().parents[4]

def specification(tmp_path,role='ide:daily-coder',kind='project'):
    sid=str(uuid.uuid4()); cap='store:'+sid+':default'
    g={'memory_read':[cap],'memory_write':[cap],'data_classes':['public','private'], 'workspace_roots':[str(tmp_path)],'tools':['memory.export'],'write_roots':[]}
    return sid,{'version':1,'identity':'test','run_id':'r1','role':role,'layers':{n:dict(g) for n in LAYERS}}

def test_owned_role_translates_only_selected_store(tmp_path):
    sid,spec=specification(tmp_path)
    a=evaluate_memory_access(spec,workspace=tmp_path,store_id=sid,kind='project',snapshot=compile_repository(ROOT))
    a.effective_grant.authorize('memory_write','store:'+sid+':default',tmp_path/'memory.sqlite')
    with pytest.raises(ContractDenied):a.effective_grant.authorize('memory_write','store:'+str(uuid.uuid4())+':default')

def test_researcher_cannot_acquire_writes_or_daily(tmp_path):
    sid,spec=specification(tmp_path,'dc:researcher')
    a=evaluate_memory_access(spec,workspace=tmp_path,store_id=sid,kind='project',snapshot=compile_repository(ROOT))
    with pytest.raises(ContractDenied):a.effective_grant.authorize('memory_write','store:'+sid+':default')
    a=evaluate_memory_access(spec,workspace=tmp_path,store_id=sid,kind='daily',snapshot=compile_repository(ROOT))
    with pytest.raises(ContractDenied):a.effective_grant.authorize('memory_read','store:'+sid+':default')

def test_explicit_layers_identity_and_store_uuid_required(tmp_path):
    sid,spec=specification(tmp_path);del spec['layers']['approval']
    with pytest.raises(ContractDenied):evaluate_memory_access(spec,workspace=tmp_path,store_id=sid,kind='project',snapshot=compile_repository(ROOT))
