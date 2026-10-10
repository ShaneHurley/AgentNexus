import hashlib,json,uuid
import pytest
from agent_core.contracts import LAYERS,ContractDenied
from agent_core.memory import KnowledgeStore
from agent_core.memory_authority import evaluate_memory_access
from agent_core.memory_runtime import pin_binding,check_binding,ingest_checkpoint
from agent_core.nexus_cli import main

def setup_binding(tmp_path,engine='research-forge'):
    sid=str(uuid.uuid4());session=str(uuid.uuid4());role='ide:deep-research' if engine=='research-forge' else 'ide:daily-coder'
    g={'memory_read':['store:'+sid+':default','store:'+sid+':meta'],'memory_write':['store:'+sid+':default','store:'+sid+':meta'],'data_classes':['public','private'],'workspace_roots':[str(tmp_path)],'tools':['memory.import','memory.export','memory.backup']}
    spec={'version':1,'identity':'owner','run_id':session,'role':role,'layers':{n:dict(g) for n in LAYERS}}
    access=evaluate_memory_access(spec,workspace=tmp_path,store_id=sid,kind='research' if engine=='research-forge' else 'project')
    store=KnowledgeStore.create(tmp_path/'memory.sqlite',store_id=sid,kind='research' if engine=='research-forge' else 'project',access=access,raw_run_retention_days='none',confirmed=True)
    path=tmp_path/'binding.json';path.write_text(json.dumps({'version':1,'session_id':session,'store':str(store.path),'grant':spec}))
    pins=pin_binding(path,{'session_id':session,'identity':'owner'},tmp_path,engine)
    row={'snapshot':pins,'run_id':str(uuid.uuid4()),'engine':engine,'live':False,'workspace':str(tmp_path),'legacy_id':'legacy1'}
    return store,access,row,spec

def test_research_runtime_keeps_only_authorized_origin_and_explicit_drafts(tmp_path):
    store,access,row,spec=setup_binding(tmp_path)
    result={'state':{'run_id':'legacy1','selected_urls':['https://example.org/source'],'sources':{'s1':{'canonical_url':'https://example.org/source','canonical_title':'Evidence'}},'reads':{'s1':{'text':'authorized evidence text'}}}}
    first=ingest_checkpoint(row,result);second=ingest_checkpoint(row,result)
    assert first['records']==second['records'] and len(first['records'])==1
    assert store.search('evidence',access)==[]
    drafts=store.search('evidence',access,include_drafts=True)
    assert len(drafts)==1 and drafts[0]['verification_state']=='draft'
    assert drafts[0]['run_id']==row['run_id']
    with pytest.raises(ValueError):store.accept(drafts[0]['id'],access,expected_hash=drafts[0]['content_hash'],confirmed=True)
    result['state']['run_id']='other'
    with pytest.raises(ContractDenied):ingest_checkpoint(row,result)

def test_coding_runtime_outcomes_do_not_ingest_private_files(tmp_path):
    store,access,row,spec=setup_binding(tmp_path,'daily-coder')
    private=tmp_path/'private.txt';private.write_text('Do not retain this private file')
    first=ingest_checkpoint(row,{'status':'SIMULATED','phase':'done','artifacts':[{'path':str(private)}]})
    body=store.inspect(first['records'][0],access)['body']
    assert 'private' not in body
    assert 'SIMULATED' in body

def test_cli_memory_uses_real_role_and_confirmation_without_sessions(tmp_path,capsys):
    store,access,row,spec=setup_binding(tmp_path)
    grant=tmp_path/'grant.json';grant.write_text(json.dumps(spec))
    draft=store.add_draft(access,title='Provided note',body='Searchable memory note',sources=[{'locator':'user://note','retrieved_at':1,'content_hash':hashlib.sha256(b'note').hexdigest(),'retrieval_status':'provided','synthetic':False}])
    common=['--state-dir',str(tmp_path/'execution'),'memory']
    scoped=['--store',str(store.path),'--workspace',str(tmp_path),'--grant-file',str(grant)]
    assert main(common+['accept']+scoped+['--record',draft['id'],'--expected-hash',draft['content_hash']])==3
    assert store.inspect(draft['id'],access)['verification_state']=='draft'
    assert main(common+['accept']+scoped+['--record',draft['id'],'--expected-hash',draft['content_hash'],'--confirm'])==0
    assert main(common+['search']+scoped+['--query','Searchable'])==0
    assert not (tmp_path/'execution').exists()


def test_supervisor_settles_usage_and_reports_ingestion_failure(tmp_path):
    from agent_core.supervisor import Supervisor
    class Adapter:
        def snapshot(self,*a,**kw):return {'provider':'mock'}
        def create(self,row):return 'legacy1'
        def execute(self,row,answers):return {'status':'SIMULATED','phase':'done','state':{'run_id':'different'},'usage':{'tokens':0,'usd':0},'artifacts':[]}
    store,access,fixture,spec=setup_binding(tmp_path)
    supervisor=Supervisor(tmp_path/'execution',adapters={'research-forge':Adapter()})
    session=supervisor.new_session('owner',tmp_path)
    binding=tmp_path/'supervisor-binding.json'
    spec['run_id']=session['session_id']
    binding.write_text(json.dumps({'version':1,'session_id':session['session_id'],'store':str(store.path),'grant':spec}))
    row=supervisor.create_run(session['session_id'],'research-forge',{'topic':'test'},tmp_path,memory_binding=binding)
    result=supervisor.execute(row['run_id'])
    assert result['status']=='BLOCKED'
    assert result['memory']['error']=='ContractDenied'
    assert result['accounting']['reserved_usd']==0
    assert store.search('test',access,include_drafts=True)==[]

def test_supervisor_retains_authorized_research_drafts(tmp_path):
    from agent_core.supervisor import Supervisor
    class Adapter:
        calls=0
        def snapshot(self,*a,**kw):return {'provider':'mock'}
        def create(self,row):return 'legacy1'
        def execute(self,row,answers):
            self.calls+=1
            return {'status':'SIMULATED','phase':'done','state':{'run_id':'legacy1','selected_urls':['https://example.org/source'],'sources':{'s1':{'canonical_url':'https://example.org/source','canonical_title':'Retained'}},'reads':{'s1':{'text':'Retained authorized evidence'}}},'usage':{'tokens':0,'usd':0},'artifacts':[]}
    store,access,fixture,spec=setup_binding(tmp_path)
    adapter=Adapter();supervisor=Supervisor(tmp_path/'execution',adapters={'research-forge':adapter})
    session=supervisor.new_session('owner',tmp_path);spec['run_id']=session['session_id']
    binding=tmp_path/'supervisor-binding.json';binding.write_text(json.dumps({'version':1,'session_id':session['session_id'],'store':str(store.path),'grant':spec}))
    row=supervisor.create_run(session['session_id'],'research-forge',{'topic':'test'},tmp_path,memory_binding=binding)
    first=supervisor.execute(row['run_id']);second=supervisor.execute(row['run_id'])
    assert first['status']=='SIMULATED' and first['memory']['records']==second['memory']['records']
    assert adapter.calls==1
    assert len(store.search('Retained',access,include_drafts=True))==1


def test_research_sources_are_qualified_across_runs(tmp_path):
    store,access,row,spec=setup_binding(tmp_path)
    def result(text):return {'state':{'run_id':'legacy1','selected_urls':['https://example.org/source'],'sources':{'s1':{'canonical_url':'https://example.org/source','canonical_title':'Evidence'}},'reads':{'s1':{'text':text}}}}
    first=ingest_checkpoint(row,result('first text'))
    row['run_id']=str(uuid.uuid4())
    second=ingest_checkpoint(row,result('second text'))
    assert first['records']!=second['records']
    assert len(store.search('text',access,include_drafts=True))==2


@pytest.mark.parametrize('engine',['research-forge','daily-coder'])
def test_checkpoint_replay_preserves_confirmed_deletion(tmp_path,engine):
    from agent_core.memory_portability import delete_record
    store,access,row,spec=setup_binding(tmp_path,engine)
    result={'status':'SIMULATED','phase':'done','state':{'run_id':'legacy1','selected_urls':['https://example.org/source'],'sources':{'s1':{'canonical_url':'https://example.org/source','canonical_title':'Evidence'}},'reads':{'s1':{'text':'authorized evidence text'}}}}
    first=ingest_checkpoint(row,result)
    record=store.inspect(first['records'][0],access)
    delete_record(store,access,record['id'],expected_hash=record['content_hash'],confirmed=True)
    replay=ingest_checkpoint(row,result)
    assert replay['records']==[] and replay['skipped_deleted']==1
    assert store.search('evidence OR Coding',access,include_drafts=True)==[]
    assert store.inspect(record['id'],access,include_deleted=True)['deleted_at'] is not None


@pytest.mark.parametrize('engine',['research-forge','daily-coder'])
def test_supervisor_reconciles_deleted_memory_without_replay_or_exposure(tmp_path,engine):
    from agent_core.supervisor import Supervisor
    from agent_core.memory_portability import delete_record
    class Adapter:
        def snapshot(self,*args,**kwargs):return {'provider':'mock'}
        def inspect(self,row):
            return {'status':'SIMULATED','phase':'done','state':{'run_id':'legacy1','selected_urls':['https://example.org/source'],'sources':{'s1':{'canonical_url':'https://example.org/source','canonical_title':'Evidence'}},'reads':{'s1':{'text':'authorized evidence text'}}},'usage':{'tokens':0,'usd':0},'artifacts':[]}
        def execute(self,*args):raise AssertionError('recovery must not redispatch')
    store,access,fixture,spec=setup_binding(tmp_path,engine)
    adapter=Adapter();supervisor=Supervisor(tmp_path/'execution',adapters={engine:adapter})
    session=supervisor.new_session('owner',tmp_path);spec['run_id']=session['session_id']
    binding=tmp_path/'supervisor-binding.json';binding.write_text(json.dumps({'version':1,'session_id':session['session_id'],'store':str(store.path),'grant':spec}))
    request={'topic':'test'} if engine=='research-forge' else 'test'
    run=supervisor.create_run(session['session_id'],engine,request,tmp_path,memory_binding=binding)
    supervisor.store.set_alias(run['run_id'],'legacy1')
    row=supervisor.store.get_run(run['run_id'])
    supervisor.store.begin_call(row['run_id'],str(uuid.uuid4()),100,1)
    supervisor.store.update(row['run_id'],'RUNNING')
    native=adapter.inspect(row)
    retained=ingest_checkpoint(row,native)
    record=store.inspect(retained['records'][0],access)
    delete_record(store,access,record['id'],expected_hash=record['content_hash'],confirmed=True)
    reconciled=supervisor.execute(row['run_id'])
    assert reconciled['status']=='SIMULATED'
    assert reconciled['memory']['skipped_deleted']==1 and reconciled['memory']['records']==[]
    assert reconciled['accounting']['reserved_usd']==0
    assert reconciled['accounting']['reserved_tokens']==0
    assert not supervisor.store.pending_calls(row['run_id'])
