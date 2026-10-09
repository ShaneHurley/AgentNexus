import json
from pathlib import Path
from unittest.mock import patch
import pytest
from daily_coder.tool_broker import ToolBroker, ToolDenied
from daily_coder.skills import SkillLibrary
from daily_coder.orchestrator import Orchestrator
from daily_coder.state_store import StateStore
from daily_coder.providers.mock import MockProvider
from agent_core.contracts import ContractDenied
from agent_core.isolation import DockerRunner
DC=Path(__file__).resolve().parents[1]
def broker(tmp_path,**kw):
    return ToolBroker(tmp_path,json.loads((DC/'config/tools.json').read_text()),json.loads((DC/'config/policies.json').read_text()),**kw)

def test_runtime_unknown_and_extra_callback_do_not_expand(tmp_path):
    b=broker(tmp_path,extra_tools={'tests.run':lambda a: {'returncode':0}})
    with pytest.raises(ToolDenied): b.execute('test_executor','tests.run',{'argv':['python','-V']})
    with pytest.raises(ToolDenied): b.authorize('made_up','filesystem.read')
    with pytest.raises(ToolDenied): b.authorize('researcher','filesystem.write')
    with pytest.raises(ContractDenied): b.authority.memory('researcher','daily')

def test_skills_enforced_and_symlink_denied(tmp_path):
    b=broker(tmp_path)
    with pytest.raises(ContractDenied): b.authority.skill('researcher','skill:dc:read-only-research')
    library=SkillLibrary(DC/'skills')
    assert library.load(['read-only-research'],authority=b.authority,role='implementer')
    with pytest.raises(ContractDenied): library.load(['read-only-research'])
    outside=tmp_path/'out'; outside.mkdir(); (outside/'SKILL.md').write_text('private')
    root=tmp_path/'skills'; root.mkdir(); (root/'escape').symlink_to(outside,target_is_directory=True)
    with pytest.raises(ContractDenied): SkillLibrary(root).index()

def test_broker_uses_actual_runner_and_no_callback(tmp_path):
    runner=DockerRunner('python@sha256:'+'a'*64,tmp_path)
    b=broker(tmp_path,isolated_runner=runner,extra_tools={'tests.run':lambda a: pytest.fail('callback bypass')})
    with patch.object(DockerRunner,'run',return_value={'returncode':0}) as run:
        assert b.execute('test_executor','tests.run',{'argv':['python','-V']})['returncode']==0
        run.assert_called_once()

def test_run_registry_pin_and_unknown_dispatch(tmp_path):
    state=StateStore(tmp_path/'state.sqlite'); o=Orchestrator(DC,state,MockProvider())
    run=o.create('fix a typo',tmp_path)
    assert state.get(run)['registry_hash']==o.registry_snapshot.snapshot_id
    with pytest.raises(ContractDenied): o._invoke(run,'made_up','RESEARCH',{},0,'S',None)
    state.set_field(run,'registry_hash','a'*64)
    with pytest.raises(ContractDenied): o.run(run)


def test_schema4_upgrade_preserves_rows_and_schema_guard(tmp_path):
    import sqlite3
    path=tmp_path/'state.sqlite'; original=StateStore(path)
    original.create('legacy','request',str(tmp_path),'old','legacy-create')
    with sqlite3.connect(path) as c:
        c.execute('ALTER TABLE runs DROP COLUMN registry_hash')
        c.execute("UPDATE schema_meta SET value='4' WHERE key='version'")
    migrated=StateStore(path)
    assert migrated.get('legacy')['request']=='request'
    assert migrated.get('legacy')['registry_hash'] is None
    assert path.with_name(path.name+'.pre-v6').is_file()
    with sqlite3.connect(path) as c: c.execute("UPDATE schema_meta SET value='999' WHERE key='version'")
    with pytest.raises(ValueError,match='newer'): StateStore(path)


def test_task_workspace_narrowing_applies_to_search_and_compat_reads(tmp_path):
    from agent_core.runtime_authority import RuntimeAuthority
    from agent_core.contracts import Grant, LAYERS
    sub=tmp_path/'allowed'; sub.mkdir(); (tmp_path/'other.txt').write_text('private')
    authority=RuntimeAuthority('dc',tmp_path)
    base=authority.snapshot.role('dc:researcher',tmp_path)['grant']
    base['workspace_roots']=[str(sub)]
    authority.task_layers={name:base for name in LAYERS}
    b=broker(tmp_path,authority=authority)
    with pytest.raises(ToolDenied): b.execute('researcher','filesystem.search',{'query':'private'})
    with pytest.raises(ToolDenied): b.read('researcher','other.txt')


def test_runtime_dispatch_checks_recursion_and_concurrency(tmp_path):
    from agent_core.runtime_authority import RuntimeAuthority
    a=RuntimeAuthority('dc',tmp_path)
    with pytest.raises(ContractDenied): a.dispatch('researcher','ide:daily-coder',depth=2)
    with pytest.raises(ContractDenied): a.dispatch('researcher','ide:daily-coder',active_children=2)
    with pytest.raises(ContractDenied): a.dispatch('researcher','ide:daily-coder',task_key='same',ancestor_keys=['same'])


def test_plugin_cannot_replace_typed_write_gateway(tmp_path):
    called=[]
    b=broker(tmp_path,extra_tools={'filesystem.write':lambda a: called.append(a)})
    with pytest.raises(ToolDenied): b.execute('implementer','filesystem.write',{'path':'x','content':'x'},plan_allowlist=['x'])
    assert not called and not (tmp_path/'x').exists()
