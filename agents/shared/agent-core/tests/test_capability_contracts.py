import copy
from pathlib import Path
import pytest
from agent_core.contracts import ContractDenied, Grant, EffectiveGrant, LAYERS
from agent_core.registry_snapshot import compile_repository, SnapshotStore, validate_snapshot, digest
ROOT = Path(__file__).resolve().parents[4]

def test_compile_sources_and_six_entry_points():
    s = compile_repository(ROOT)
    assert len([r for r in s.data['roles'].values() if r['user_invocable']]) == 6
    assert s.role('dc:researcher')['leaf']
    assert 'agents/shared/agent-core/registry.yaml' in s.data['sources']
    assert s.role('dc:researcher')['grant']['memory_write'] == []
    with pytest.raises(ContractDenied): s.authorize_dispatch('dc:implementer', caller='rf:orchestrator')
    with pytest.raises(ContractDenied): s.authorize_dispatch('dc:implementer', caller=None, user_invoked=True)
    with pytest.raises(ContractDenied): s.role('missing')

def test_intersection_and_symlink(tmp_path):
    root = tmp_path / 'project'; root.mkdir(); outside = tmp_path / 'outside'; outside.mkdir()
    (root / 'escape').symlink_to(outside, target_is_directory=True)
    grant = Grant.from_mapping({'tools':['read'], 'workspace_roots':[str(root)]})
    contract = {'id':'role', 'active':True, 'leaf':True, 'grant':grant.as_mapping()}
    effective = EffectiveGrant.evaluate(contract, {n:grant for n in LAYERS})
    effective.authorize('tools','read',root/'ok')
    with pytest.raises(ContractDenied): effective.authorize('tools','read',root/'escape'/'data')
    with pytest.raises(ContractDenied): effective.authorize('tools','write')
    with pytest.raises(ContractDenied): effective.authorize('memory_read','project')
    with pytest.raises(ContractDenied): EffectiveGrant.evaluate(contract, {'user':grant})
    layers = {n:grant for n in LAYERS}; layers['parent'] = Grant()
    with pytest.raises(ContractDenied): EffectiveGrant.evaluate(contract,layers).authorize('tools','read')

def test_leaf_and_recursion():
    g=Grant.from_mapping({'delegation':['child'],'resources':{'delegation_depth':2,'concurrency':2}})
    c={'id':'parent','active':True,'leaf':True,'grant':g.as_mapping()}
    with pytest.raises(ContractDenied): EffectiveGrant.evaluate(c,{n:g for n in LAYERS})
    c['leaf']=False; e=EffectiveGrant.evaluate(c,{n:g for n in LAYERS})
    with pytest.raises(ContractDenied): e.authorize_delegation('child',depth=0,active_children=0,task_key='a',ancestor_keys=['a'])
    with pytest.raises(ContractDenied): e.authorize_delegation('child',depth=2,active_children=0,task_key='b')

def test_atomic_snapshot_and_rollback_cannot_restore_revocation(tmp_path):
    s=compile_repository(ROOT); store=SnapshotStore(tmp_path); key=store.publish(s)
    ceiling={k:Grant.from_mapping(v['grant']) for k,v in s.data['roles'].items()}
    store.activate(key,ceiling=ceiling)
    assert store.load().snapshot_id == key
    with pytest.raises(ContractDenied): store.rollback(key,ceiling=ceiling,revoked=['filesystem.read'])
    assert store.load().snapshot_id == key
    with pytest.raises(ContractDenied): store.load('../escape')

def test_plugin_cannot_expand_leaf_or_activate_without_installation():
    s=compile_repository(ROOT); d=copy.deepcopy(s.data); r=d['roles']['dc:researcher']
    r['grant']['delegation']=['dc:implementer']; r['content_hash']=digest({k:v for k,v in r.items() if k!='content_hash'})
    with pytest.raises(ContractDenied): validate_snapshot(d)
    d=copy.deepcopy(s.data); t=d['tools']['filesystem.read']; t['installed']=False
    t['content_hash']=digest({k:v for k,v in t.items() if k!='content_hash'})
    with pytest.raises(ContractDenied): validate_snapshot(d)


def test_snapshot_read_cannot_mutate_authority():
    s=compile_repository(ROOT); original=s.snapshot_id
    s.data['roles']['dc:researcher']['grant']['tools'].append('filesystem.write')
    assert s.snapshot_id==original
    assert 'filesystem.write' not in s.role('dc:researcher')['grant']['tools']

def test_explicit_task_grants_deny_dispatch(tmp_path):
    from agent_core.runtime_authority import RuntimeAuthority
    authority=RuntimeAuthority('dc',tmp_path,task_layers={name:Grant().as_mapping() for name in LAYERS})
    with pytest.raises(ContractDenied): authority.dispatch('researcher','ide:daily-coder')


def test_runtime_uses_reviewed_snapshot_and_revocations_survive_rollback(tmp_path,monkeypatch):
    from agent_core.registry_snapshot import RegistrySnapshot
    from agent_core.runtime_authority import RuntimeAuthority
    baseline=compile_repository(ROOT); data=baseline.data
    for row in data['roles'].values():
        row['grant']['tools']=[x for x in row['grant']['tools'] if x!='filesystem.read']
        row['content_hash']=digest({k:v for k,v in row.items() if k!='content_hash'})
    narrowed=RegistrySnapshot(data); store=SnapshotStore(tmp_path/'registry')
    old_key=store.publish(baseline); new_key=store.publish(narrowed)
    ceilings={key:Grant.from_mapping(row['grant']) for key,row in baseline.data['roles'].items()}
    store.activate(new_key,ceiling=ceilings,revoked=['filesystem.read'])
    monkeypatch.setenv('AGENTNEXUS_REGISTRY_STORE',str(tmp_path/'registry'))
    authority=RuntimeAuthority('dc',tmp_path)
    assert authority.snapshot.snapshot_id==new_key
    with pytest.raises(ContractDenied): authority.tool('researcher','filesystem.read')
    with pytest.raises(ContractDenied): store.rollback(old_key,ceiling=ceilings)
    assert store.load().snapshot_id==new_key


def test_concurrent_activation_retains_both_revocations(tmp_path):
    import json
    from concurrent.futures import ThreadPoolExecutor
    from agent_core.registry_snapshot import RegistrySnapshot
    baseline=compile_repository(ROOT); data=baseline.data
    for row in data['roles'].values():
        row['grant']['tools']=[]
        row['content_hash']=digest({k:v for k,v in row.items() if k!='content_hash'})
    store=SnapshotStore(tmp_path); key=store.publish(RegistrySnapshot(data))
    ceiling={k:Grant.from_mapping(v['grant']) for k,v in baseline.data['roles'].items()}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(store.activate,key,ceiling=ceiling,revoked=[tool]) for tool in ['filesystem.read','filesystem.write']]
        for future in futures: future.result()
    assert set(json.loads((tmp_path/'active.json').read_text())['revoked'])=={'filesystem.read','filesystem.write'}
