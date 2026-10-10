import sqlite3
import time
import uuid
from pathlib import Path
import pytest
from hypothesis import given, strategies as st
from agent_core.contracts import Grant, EffectiveGrant, ContractDenied
from agent_core.memory import KnowledgeStore, MemoryAccess

def access(path, sid, namespaces=("meta", "default"), classes=("public", "private", "restricted")):
    scopes=frozenset(f"store:{sid}:{n}" for n in namespaces)
    g=Grant(memory_read=scopes,memory_write=scopes,data_classes=frozenset(classes),workspace_roots=(str(path.parent),))
    return MemoryAccess("human", "run-test", EffectiveGrant((g,), "test"))

@pytest.fixture
def memory(tmp_path):
    sid=str(uuid.uuid4()); p=tmp_path/"knowledge.sqlite"; a=access(p,sid)
    return KnowledgeStore.create(p,store_id=sid,kind="project",access=a,raw_run_retention_days="none",confirmed=True),a

def draft(s,a,**kw):
    args=dict(title="solar evidence",body="solar systems evidence",sources=[dict(locator="human:note",retrieved_at=time.time(),content_hash="a"*64,retrieval_status="provided",synthetic=False)])
    args.update(kw); return s.add_draft(a,**args)

def test_creation_requires_confirmation_retention_scope(tmp_path):
    p=tmp_path/"s.sqlite"; sid=str(uuid.uuid4()); a=access(p,sid)
    with pytest.raises(ValueError): KnowledgeStore.create(p,store_id=sid,kind="project",access=a,raw_run_retention_days="none")
    assert not p.exists()
    with pytest.raises(ValueError): KnowledgeStore.create(p,store_id=sid,kind="project",access=a,raw_run_retention_days=-1,confirmed=True)
    with pytest.raises(ContractDenied): KnowledgeStore.create(p,store_id=sid,kind="project",access=access(p,sid,("default",)),raw_run_retention_days=0,confirmed=True)
    assert not p.exists()

def test_actual_fts_acceptance_cas_restart(memory):
    s,a=memory; r=draft(s,a)
    assert s.search("solar",a)==[]
    assert s.search("solar",a,include_drafts=True)[0]["verification_state"]=="draft"
    with pytest.raises(ValueError): s.accept(r["id"],a,expected_hash=r["content_hash"])
    with pytest.raises(ValueError): s.accept(r["id"],a,expected_hash="bad",confirmed=True)
    s.accept(r["id"],a,expected_hash=r["content_hash"],confirmed=True)
    reopened=KnowledgeStore(s.path)
    assert reopened.search("solar",a)[0]["id"]==r["id"]
    with pytest.raises(ValueError): s.search('"',a)

def test_project_namespace_sensitivity_denied(memory,tmp_path):
    s,a=memory; r=draft(s,a)
    with pytest.raises(ContractDenied): s.inspect(r["id"],access(s.path,s.store_id,classes=("public",)))
    with pytest.raises(ContractDenied): s.search("solar",access(s.path,s.store_id,("meta",)))
    sid=str(uuid.uuid4()); p=tmp_path/"other.sqlite"; other=KnowledgeStore.create(p,store_id=sid,kind="project",access=access(p,sid),raw_run_retention_days=0,confirmed=True)
    with pytest.raises(ContractDenied): other.search("solar",a)

def test_dependency_default_exclusion_refresh_revision(memory):
    s,a=memory; r=draft(s,a,dependencies={"file":"abc"}); s.accept(r["id"],a,expected_hash=r["content_hash"],confirmed=True)
    assert s.search("solar",a)==[]
    assert s.search("solar",a,fingerprints={"file":"abc"})
    assert s.refresh_dependencies(a,{"file":"different"})["stale"]==1
    assert s.search("solar",a,fingerprints={"file":"abc"})==[]
    new=s.revise(r["id"],a,expected_hash=r["content_hash"],title="new solar",body="updated solar",sources=r["sources"],confirmed=True)
    assert new["id"]!=r["id"] and new["verification_state"]=="draft"
    assert s.inspect(r["id"],a)["stale"]

def test_provenance_secrets_and_expiry(memory):
    s,a=memory
    with pytest.raises(ValueError): draft(s,a,sources=[])
    with pytest.raises(ValueError): draft(s,a,body="password=abc123")
    r=draft(s,a,sources=[dict(locator="fixture:test",retrieved_at=time.time(),content_hash="a"*64,retrieval_status="retrieved",synthetic=True)])
    with pytest.raises(ValueError): s.accept(r["id"],a,expected_hash=r["content_hash"],confirmed=True)
    c=draft(s,a,kind="cache",title="cached",expires_at=time.time()-1)
    assert all(x["id"]!=c["id"] for x in s.search("systems",a,include_drafts=True))
    assert draft(s,a,kind="cache",title="new cache")["expires_at"]>time.time()

def test_missing_symlink_newer_schema(memory,tmp_path):
    s,a=memory
    with pytest.raises(FileNotFoundError): KnowledgeStore(tmp_path/"missing")
    link=tmp_path/"link"; link.symlink_to(s.path)
    with pytest.raises(ValueError): KnowledgeStore(link)
    with s.connect(write=True) as db: db.execute("UPDATE store_meta SET value='999' WHERE key='schema_version'")
    with pytest.raises(ValueError): KnowledgeStore(s.path)

def test_atomic_rollback_and_duplicate(memory):
    s,a=memory
    with pytest.raises(RuntimeError):
        with s.connect(write=True) as db:
            db.execute("INSERT INTO store_meta VALUES('rollback','yes')")
            raise RuntimeError("abort")
    with s.connect() as db: assert db.execute("SELECT * FROM store_meta WHERE key='rollback'").fetchone() is None
    r=draft(s,a); s.accept(r["id"],a,expected_hash=r["content_hash"],confirmed=True)
    with pytest.raises(ValueError): draft(s,a,record_id=r["id"],body="different")

@given(st.lists(st.sampled_from(["draft","accept","search","refresh"]),min_size=1,max_size=20))
def test_lifecycle_never_implicitly_accepts(tmp_path_factory,events):
    p=tmp_path_factory.mktemp("sequence")/"s.db"; sid=str(uuid.uuid4()); a=access(p,sid); s=KnowledgeStore.create(p,store_id=sid,kind="project",access=a,raw_run_retention_days="none",confirmed=True)
    accepted=set(); records=[]
    for event in events:
        if event=="draft": records.append(draft(s,a,title="solar "+str(len(records))))
        elif event=="accept" and records:
            r=records[-1]; s.accept(r["id"],a,expected_hash=r["content_hash"],confirmed=True); accepted.add(r["id"])
        elif event=="refresh": s.refresh_dependencies(a,{})
        else: assert {r["id"] for r in s.search("solar",a)}<=accepted

def test_bounded_busy_writer(memory):
    s,a=memory
    with sqlite3.connect(s.path,timeout=0) as external:
        external.execute("BEGIN IMMEDIATE")
        start=time.monotonic()
        with pytest.raises(sqlite3.OperationalError): draft(s,a)
        assert time.monotonic()-start<3
        external.rollback()
    assert draft(s,a)

def test_source_conflict_rolls_back_whole_draft(memory):
    s,a=memory; first=draft(s,a)
    source=dict(first["sources"][0]); source["locator"]="human:different"
    with pytest.raises(ValueError): draft(s,a,title="second solar",sources=[source])
    assert len(s.search("solar",a,include_drafts=True))==1

def test_schema_structure_tampering_refused(memory):
    s,a=memory
    with s.connect(write=True) as db: db.execute("DROP TABLE dependencies")
    with pytest.raises(ValueError): KnowledgeStore(s.path)

def test_read_connection_cannot_mutate(memory):
    s,a=memory
    with s.connect() as db:
        with pytest.raises(sqlite3.OperationalError): db.execute("DELETE FROM records")

def test_budget_includes_expanded_provenance(memory):
    s,a=memory; r=draft(s,a)
    assert s.search("solar",a,include_drafts=True,token_budget=1)==[]
    assert len(s.search("solar",a,include_drafts=True,limit=1))==1

def test_draft_option_requires_boolean(memory):
    s,a=memory; draft(s,a)
    with pytest.raises(ValueError): s.search("solar",a,include_drafts="false")

def test_unicode_budget_cannot_expand_unbounded(memory):
    s,a=memory; draft(s,a,body="solar "+"界"*100)
    assert s.search("solar",a,include_drafts=True,token_budget=400)==[]

def test_symlink_parent_and_no_overwrite(memory,tmp_path):
    s,a=memory; sid=s.store_id
    with pytest.raises(FileExistsError): KnowledgeStore.create(s.path,store_id=sid,kind="project",access=a,raw_run_retention_days="none",confirmed=True)
    folder=tmp_path/"dir"; folder.mkdir(); link=tmp_path/"dirlink"; link.symlink_to(folder,target_is_directory=True)
    with pytest.raises(ValueError): KnowledgeStore.create(link/"x.db",store_id=sid,kind="project",access=a,raw_run_retention_days=0,confirmed=True)

@pytest.mark.parametrize("overrides", [{"limit":9},{"limit":100},{"limit":10**12},{"token_budget":4001},{"token_budget":100000},{"token_budget":10**12}])
def test_search_rejects_hard_ceiling_overrides(memory,overrides):
    s,a=memory; draft(s,a)
    with pytest.raises(ValueError): s.search("solar",a,include_drafts=True,**overrides)

def test_search_accepts_exact_hard_boundaries(memory):
    s,a=memory; draft(s,a)
    assert s.search("solar",a,include_drafts=True,limit=8,token_budget=4000)

@pytest.mark.parametrize("prefix,size", [("sk-"+"proj-",40),("sk-"+"ant-api03-",40),("gh"+"p_",36),("github_"+"pat_",50),("gh"+"o_",36),("gh"+"u_",36),("gh"+"s_",36),("gh"+"r_",36),("xox"+"b-",40)])
def test_recognizable_synthetic_tokens_rejected(memory,prefix,size):
    s,a=memory
    with pytest.raises(ValueError): draft(s,a,body="evidence "+prefix+"A"*size)

@pytest.mark.parametrize("body", ['{"password": "syntheticvalue"}', '{"api_key": "syntheticvalue"}', '{"credentials": {"token": "syntheticvalue"}}', '[{"private_key": "syntheticvalue"}]'])
def test_string_encoded_credential_fields_rejected(memory,body):
    s,a=memory
    with pytest.raises(ValueError): draft(s,a,body=body)

def test_opaque_credential_references_and_prose_allowed(memory):
    s,a=memory
    assert draft(s,a,body='Use credential://vault/team-service. Discuss password policy and API key rotation. {"credential_reference":"opaque-id"}')
