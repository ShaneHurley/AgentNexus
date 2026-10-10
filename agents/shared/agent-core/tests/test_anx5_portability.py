import hashlib
import json
import uuid
import pytest
from agent_core.contracts import EffectiveGrant, Grant


def api():
    from agent_core import memory, memory_portability
    return memory, memory_portability


def setup(tmp_path):
    m, p = api()
    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    grant = Grant(tools=frozenset({"memory.export", "memory.import", "memory.backup", "filesystem.read"}),
                  memory_read=frozenset(f"store:{x}:{n}" for x in ids for n in ["meta", "default", "hidden"]),
                  memory_write=frozenset(f"store:{x}:{n}" for x in ids for n in ["meta", "default", "hidden"]),
                  data_classes=frozenset({"public", "private", "restricted"}),
                  workspace_roots=(str(tmp_path),), write_roots=(str(tmp_path),))
    access = m.MemoryAccess("reviewer", "run-1", EffectiveGrant((grant,), "test"))
    stores = [m.KnowledgeStore.create(tmp_path / f"{i}.sqlite", store_id=x, kind="project", access=access, raw_run_retention_days="none", confirmed=True) for i, x in enumerate(ids)]
    return m, p, access, *stores


def add(store, access, **kw):
    return store.add_draft(access, title="Private note", body="private marker", sources=[{"locator":"private://career", "retrieved_at":1, "content_hash":"a"*64, "retrieval_status":"provided", "synthetic":False}], **kw)


def test_export_import_drafts_hashes_and_local_relationships(tmp_path):
    m, p, a, s, target = setup(tmp_path)
    one = add(s,a)
    two = add(s,a, record_id=str(uuid.uuid4()))
    with s.connect(write=True) as db:
        db.execute("INSERT INTO relationships(src_id,dst_store_id,dst_id,kind) VALUES(?,?,?,?)",(one["id"],s.store_id,two["id"],"supports"))
    path = tmp_path / "portable.json"
    p.export_store(s,a,path,namespaces=["default"],confirmed=True)
    result = p.import_store(target,a,path,confirmed=True)
    assert result["imported"] == 2
    with target.connect() as db:
        assert {x[0] for x in db.execute("SELECT verification_state FROM records")} == {"draft"}
        rel = db.execute("SELECT * FROM relationships").fetchone()
        assert rel["dst_store_id"] == target.store_id
        assert db.execute("SELECT count(*) FROM import_lineage").fetchone()[0] == 2
    assert target.search("private",a) == []


def test_tampered_import_has_no_mutation(tmp_path):
    m,p,a,s,target = setup(tmp_path)
    add(s,a)
    path = tmp_path / "portable.json"
    p.export_store(s,a,path,namespaces=["default"],confirmed=True)
    doc = json.loads(path.read_text())
    doc["records"][0]["body"] = "changed"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        p.import_store(target,a,path,confirmed=True)
    with target.connect() as db:
        assert db.execute("SELECT count(*) FROM records").fetchone()[0] == 0


def test_backup_consistent_restore_and_full_scope_denial(tmp_path):
    m,p,a,s,target = setup(tmp_path)
    add(s,a,namespace="hidden")
    narrow = Grant(tools=frozenset({"memory.backup"}), memory_read=frozenset({f"store:{s.store_id}:meta",f"store:{s.store_id}:default"}), data_classes=frozenset({"public","private","restricted"}), workspace_roots=(str(tmp_path),))
    denied = m.MemoryAccess("x","y",a.effective_grant.narrow(narrow))
    with pytest.raises(PermissionError):
        p.backup_store(s,denied,tmp_path / "denied.sqlite",confirmed=True)
    assert not (tmp_path / "denied.sqlite").exists()
    p.backup_store(s,a,tmp_path / "backup.sqlite",confirmed=True)
    restored = m.KnowledgeStore(tmp_path / "backup.sqlite")
    with restored.connect() as db:
        assert db.execute("SELECT count(*) FROM records").fetchone()[0] == 1
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_promotion_transforms_private_content_and_deletion_purges_fts(tmp_path):
    m,p,a,s,target = setup(tmp_path)
    r = add(s,a)
    s.accept(r["id"],a,expected_hash=r["content_hash"],confirmed=True)
    promoted = p.promote_record(s,target,a,a,r["id"],title="Public summary",body="Reviewed safe text",expected_hash=r["content_hash"],confirmed=True)
    assert promoted["sensitivity"] == "public" and promoted["verification_state"] == "draft"
    assert "private" not in json.dumps(promoted).lower()
    p.delete_record(s,a,r["id"],expected_hash=r["content_hash"],confirmed=True)
    assert s.search("private",a,include_drafts=True) == []
    with s.connect() as db:
        deleted = db.execute("SELECT * FROM records WHERE id=?",(r["id"],)).fetchone()
        assert deleted["body"] == "" and deleted["deleted_at"]
        assert db.execute("SELECT count(*) FROM records_fts WHERE record_id=?",(r["id"],)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM memory_tombstones").fetchone()[0] == 1
    doctor = p.memory_doctor(s,a)
    assert doctor["integrity_ok"] is True
    assert "private marker" not in json.dumps(doctor)


def test_import_bad_reference_atomic_and_export_path_scope(tmp_path):
    m,p,a,s,target = setup(tmp_path)
    add(s,a)
    with pytest.raises(PermissionError):
        p.export_store(s,a,tmp_path.parent / "escape.json",namespaces=["default"],confirmed=True)
    path = tmp_path / "export.json"
    p.export_store(s,a,path,namespaces=["default"],confirmed=True)
    doc = json.loads(path.read_text())
    doc["relationships"] = [{"src_id":doc["records"][0]["id"],"dst_store_id":s.store_id,"dst_id":str(uuid.uuid4()),"kind":"supports"}]
    payload = {k:v for k,v in doc.items() if k != "manifest"}
    doc["manifest"]["payload_hash"] = hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        p.import_store(target,a,path,confirmed=True)
    with target.connect() as db:
        assert db.execute("SELECT count(*) FROM records").fetchone()[0] == 0


def test_import_invalid_second_source_rolls_back_first_draft(tmp_path):
    m,p,a,s,target = setup(tmp_path)
    add(s,a)
    add(s,a,record_id=str(uuid.uuid4()))
    path = tmp_path / "atomic.json"
    p.export_store(s,a,path,namespaces=["default"],confirmed=True)
    doc=json.loads(path.read_text())
    doc["sources"][-1]["retrieval_status"]="invented"
    doc["manifest"]["payload_hash"]=hashlib.sha256(json.dumps({k:v for k,v in doc.items() if k!="manifest"},sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        p.import_store(target,a,path,confirmed=True)
    with target.connect() as db:
        for table in ["records","sources","record_sources","dependencies","record_revisions","import_lineage","records_fts"]:
            assert db.execute("SELECT count(*) FROM "+table).fetchone()[0]==0


def test_all_operations_require_confirmation_and_backup_class(tmp_path):
    m,p,a,s,target=setup(tmp_path)
    r=add(s,a)
    with pytest.raises(ValueError):
        p.export_store(s,a,tmp_path/"no.json",namespaces=["default"])
    with pytest.raises(ValueError):
        p.backup_store(s,a,tmp_path/"no.sqlite")
    with pytest.raises(ValueError):
        p.delete_record(s,a,r["id"],expected_hash=r["content_hash"])
    narrow=Grant(tools=frozenset({"memory.backup"}),memory_read=frozenset({f"store:{s.store_id}:meta",f"store:{s.store_id}:default"}),data_classes=frozenset({"public"}),workspace_roots=(str(tmp_path),))
    denied=m.MemoryAccess("x","y",a.effective_grant.narrow(narrow))
    with pytest.raises(PermissionError):
        p.backup_store(s,denied,tmp_path/"no.sqlite",confirmed=True)
    assert not (tmp_path/"no.json").exists() and not (tmp_path/"no.sqlite").exists()


def test_promotion_rejects_stale_source_and_untransformed_title(tmp_path):
    m,p,a,s,target=setup(tmp_path)
    r=add(s,a)
    s.accept(r["id"],a,expected_hash=r["content_hash"],confirmed=True)
    with pytest.raises(ValueError):
        p.promote_record(s,target,a,a,r["id"],title=r["title"],body="Safe reviewed transformation",expected_hash=r["content_hash"],confirmed=True)
    with s.connect(write=True) as db:
        db.execute("UPDATE records SET stale=1 WHERE id=?",(r["id"],))
    with pytest.raises(ValueError):
        p.promote_record(s,target,a,a,r["id"],title="Public",body="Safe reviewed transformation",expected_hash=r["content_hash"],confirmed=True)
    with target.connect() as db:
        assert db.execute("SELECT count(*) FROM records").fetchone()[0]==0


def test_doctor_reports_content_hash_corruption_redacted(tmp_path):
    m,p,a,s,target=setup(tmp_path)
    r=add(s,a)
    with s.connect(write=True) as db:
        db.execute("UPDATE records SET body='corrupt private content' WHERE id=?",(r["id"],))
    report=p.memory_doctor(s,a)
    assert report["content_hash_errors"]==1
    assert report["fts_mismatches"]==1
    assert "private content" not in json.dumps(report)


def test_export_refuses_corrupt_content_without_publishing(tmp_path):
    m,p,a,s,target=setup(tmp_path)
    r=add(s,a)
    with s.connect(write=True) as db:
        db.execute("UPDATE records SET body='corrupt' WHERE id=?",(r["id"],))
    path=tmp_path/"corrupt.json"
    with pytest.raises(ValueError):
        p.export_store(s,a,path,namespaces=["default"],confirmed=True)
    assert not path.exists()


def test_import_rejects_unused_unvalidated_source(tmp_path):
    m,p,a,s,target=setup(tmp_path)
    add(s,a)
    path=tmp_path/"orphan.json"
    p.export_store(s,a,path,namespaces=["default"],confirmed=True)
    doc=json.loads(path.read_text())
    doc["sources"].append({"id":str(uuid.uuid4()),"locator":"unapproved private locator"})
    doc["manifest"]["payload_hash"]=hashlib.sha256(json.dumps({k:v for k,v in doc.items() if k!="manifest"},sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        p.import_store(target,a,path,confirmed=True)
    with target.connect() as db:
        assert db.execute("SELECT count(*) FROM records").fetchone()[0]==0


def test_expired_accepted_record_cannot_promote(tmp_path):
    m,p,a,s,target=setup(tmp_path)
    r=add(s,a,kind="cache",expires_at=1)
    s.accept(r["id"],a,expected_hash=r["content_hash"],confirmed=True)
    with pytest.raises(ValueError):
        p.promote_record(s,target,a,a,r["id"],title="Public summary",body="Reviewed safe text",expected_hash=r["content_hash"],confirmed=True)


def test_backup_preserves_relationships_and_schema_on_reopen(tmp_path):
    m,p,a,s,target=setup(tmp_path)
    one=add(s,a)
    two=add(s,a,record_id=str(uuid.uuid4()))
    with s.connect(write=True) as db:
        db.execute("INSERT INTO relationships VALUES(?,?,?,?)",(one["id"],s.store_id,two["id"],"supports"))
    path=tmp_path/"consistent.sqlite"
    p.backup_store(s,a,path,confirmed=True)
    restored=m.KnowledgeStore(path)
    record=restored.inspect(one["id"],a)
    assert record["relationships"][0]["dst_id"]==two["id"]
    assert p.memory_doctor(restored,a)["foreign_key_errors"]==0


def test_opaque_source_id_roundtrip_preserves_valid_provenance(tmp_path):
    m,p,a,s,target=setup(tmp_path)
    r=s.add_draft(a,title="Bounded opaque provenance",body="Human note",sources=[{"id":"SRC-0001","locator":"provided:note","retrieved_at":1,"content_hash":"a"*64,"retrieval_status":"provided","synthetic":False}])
    path=tmp_path/"opaque.json"
    p.export_store(s,a,path,namespaces=["default"],confirmed=True)
    assert json.loads(path.read_text())["sources"][0]["id"]=="SRC-0001"
    result=p.import_store(target,a,path,confirmed=True)
    imported=target.inspect(result["record_ids"][0],a)
    assert imported["body"]==r["body"]
    assert imported["sources"][0]["locator"]=="provided:note"
    assert imported["verification_state"]=="draft"


def test_promotion_requires_current_dependency_fingerprints(tmp_path):
    m,p,a,s,target=setup(tmp_path)
    r=add(s,a,dependencies={"current-file":"fingerprint-1"})
    s.accept(r["id"],a,expected_hash=r["content_hash"],confirmed=True)
    args=dict(title="Public transformed summary",body="Explicitly reviewed safe body",expected_hash=r["content_hash"],confirmed=True)
    with pytest.raises(ValueError):
        p.promote_record(s,target,a,a,r["id"],**args)
    for fingerprints in [{}, {"current-file":"changed"}, ["invalid"], {"current-file":17}, {"":"fingerprint-1"}]:
        with pytest.raises(ValueError):
            p.promote_record(s,target,a,a,r["id"],fingerprints=fingerprints,**args)
    with target.connect() as db:
        assert db.execute("SELECT count(*) FROM records").fetchone()[0]==0
    promoted=p.promote_record(s,target,a,a,r["id"],fingerprints={"current-file":"fingerprint-1"},**args)
    assert promoted["verification_state"]=="draft" and promoted["sensitivity"]=="public"


def test_import_preserves_superseded_staleness_after_acceptance(tmp_path):
    m,p,a,s,target=setup(tmp_path)
    old=add(s,a)
    s.accept(old["id"],a,expected_hash=old["content_hash"],confirmed=True)
    s.revise(old["id"],a,expected_hash=old["content_hash"],title="Revised note",body="New human information",sources=old["sources"],confirmed=True)
    path=tmp_path/"stale.json"
    p.export_store(s,a,path,namespaces=["default"],confirmed=True)
    result=p.import_store(target,a,path,confirmed=True)
    imported=[target.inspect(x,a) for x in result["record_ids"]]
    superseded=next(x for x in imported if x["body"]==old["body"])
    assert superseded["stale"]==1 and superseded["verification_state"]=="draft"
    target.accept(superseded["id"],a,expected_hash=superseded["content_hash"],confirmed=True)
    assert target.search("private",a)==[]


def test_import_preserves_conflicts_and_rejects_invalid_flags(tmp_path):
    m,p,a,s,target=setup(tmp_path)
    r=add(s,a)
    with s.connect(write=True) as db:
        db.execute("UPDATE records SET conflicted=1 WHERE id=?",(r["id"],))
    path=tmp_path/"conflict.json"
    p.export_store(s,a,path,namespaces=["default"],confirmed=True)
    doc=json.loads(path.read_text())
    doc["records"][0]["stale"]=0.5
    doc["manifest"]["payload_hash"]=hashlib.sha256(json.dumps({k:v for k,v in doc.items() if k!="manifest"},sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
    bad=tmp_path/"invalidflag.json"
    bad.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        p.import_store(target,a,bad,confirmed=True)
    result=p.import_store(target,a,path,confirmed=True)
    imported=target.inspect(result["record_ids"][0],a)
    assert imported["conflicted"]==1 and imported["verification_state"]=="draft"
    with pytest.raises(ValueError):
        target.accept(imported["id"],a,expected_hash=imported["content_hash"],confirmed=True)
    assert target.search("private",a,include_drafts=True)==[]
