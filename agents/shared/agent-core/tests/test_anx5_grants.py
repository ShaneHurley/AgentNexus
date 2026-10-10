from pathlib import Path
import pytest
from agent_core.contracts import EffectiveGrant,LAYERS,ContractDenied
from agent_core.registry_snapshot import compile_repository
ROOT=Path(__file__).resolve().parents[4]

def test_memory_data_classes_intersect_every_layer():
    contract={'id':'test','active':True,'leaf':True,'grant':{'data_classes':['public','private']}}
    layers={name:{'data_classes':['public','private']} for name in LAYERS}
    layers['user']['data_classes']=['public']
    grant=EffectiveGrant.evaluate(contract,layers)
    grant.authorize('data_classes','public')
    with pytest.raises(ContractDenied):grant.authorize('data_classes','private')

def test_memory_capabilities_are_owned_and_role_specific():
    snapshot=compile_repository(ROOT)
    role=snapshot.role('dc:researcher')
    assert 'project:default' in role['grant']['memory_read']
    assert role['grant']['memory_write']==[]
    assert 'daily:default' not in role['grant']['memory_read']
    assert 'research:default' in snapshot.role('rf:orchestrator')['grant']['memory_write']
