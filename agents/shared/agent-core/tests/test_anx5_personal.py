import json
from pathlib import Path
import pytest
from agent_core import personal_store as p


def draft(tmp_path, **changes):
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(dict(id="ACC-1", context="work", action="built", result_status="USER_CONFIRMED", confidentiality="private", **changes)))
    return path


def test_previews_do_not_create_store(tmp_path):
    root = tmp_path / "absent"
    assert p.append_accomplishment(root, draft(tmp_path), False) == 0
    assert not root.exists()
    assert p.profile_show(root) == 1
    assert not root.exists()
    proposed = tmp_path / "proposal.yaml"
    proposed.write_text("version: '1'\nidentity: {}\n")
    assert p.profile_apply(root, proposed, False) == 0
    assert not root.exists()
    assert p.export_store(root, tmp_path / "export") == 1
    assert not root.exists() and not (tmp_path / "export").exists()


def test_schema_rejection_leaves_existing_files(tmp_path):
    root = tmp_path / "career"
    p.ensure_layout(root)
    before = {x.name: x.read_bytes() for x in root.iterdir() if x.is_file()}
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(dict(id="wrong", context=12, action="a", result_status="UNKNOWN", confidentiality="private")))
    assert p.append_accomplishment(root, bad, True) == 1
    proposal = tmp_path / "bad.yaml"
    proposal.write_text("version: 12\nidentity: []\n")
    assert p.profile_apply(root, proposal, True) == 1
    assert before == {x.name: x.read_bytes() for x in root.iterdir() if x.is_file()}


def test_personal_symlink_refused(tmp_path):
    actual = tmp_path / "actual"
    p.ensure_layout(actual)
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    assert p.append_accomplishment(link, draft(tmp_path), True) == 1
    assert (actual / "accomplishments.jsonl").read_text() == ""


def test_artifact_lineage_and_stale_inspection(tmp_path):
    root = tmp_path / "career"
    p.ensure_layout(root)
    assert p.append_accomplishment(root, draft(tmp_path), True) == 0
    assert p.artifact_derive(root, ["ACC-1"], "resume-1", False) == 0
    assert not (root / "artifacts.jsonl").exists()
    assert p.artifact_derive(root, ["ACC-1"], "resume-1", True) == 0
    artifact = json.loads((root / "artifacts.jsonl").read_text())
    assert artifact["source_ids"] == ["ACC-1"] and artifact["source_fingerprints"]["ACC-1"]
    original = (root / "accomplishments.jsonl").read_text()
    record = json.loads(original)
    record["action"] = "updated"
    (root / "accomplishments.jsonl").write_text(json.dumps(record) + "\n")
    assert p.artifact_stale(root, "ACC-1", False) == 0
    assert json.loads((root / "artifacts.jsonl").read_text())["stale"] is False
    assert p.artifact_stale(root, "ACC-1", True) == 0
    assert json.loads((root / "artifacts.jsonl").read_text())["stale"] is True
    assert json.loads((root / "accomplishments.jsonl").read_text())["action"] == "updated"


def test_selected_personal_import_retains_sources_and_drafts(tmp_path):
    from tests.test_anx5_portability import setup
    m, port, access, store, _ = setup(tmp_path)
    root = tmp_path / "career"
    p.ensure_layout(root)
    assert p.append_accomplishment(root, draft(tmp_path), True) == 0
    before = (root / "accomplishments.jsonl").read_bytes()
    with pytest.raises(ValueError):
        p.import_personal_files(root, store, access, [], confirmed=True)
    result = p.import_personal_files(root, store, access, ["accomplishments.jsonl"], confirmed=True)
    assert result["imported"] == 1 and result["originals_retained"] is True
    record = store.inspect(result["record_ids"][0], access)
    assert record["verification_state"] == "draft"
    assert record["sources"][0]["content_hash"]
    assert before == (root / "accomplishments.jsonl").read_bytes()
    port.delete_record(store, access, record["id"], expected_hash=record["content_hash"], confirmed=True)
    assert before == (root / "accomplishments.jsonl").read_bytes()


def test_confirmed_accomplishment_appends_serialize_stale_reads(tmp_path, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    root=tmp_path/"career"
    p.ensure_layout(root)
    first=draft(tmp_path)
    second=tmp_path/"second.json"
    value=json.loads(first.read_text())
    value["id"]="ACC-2"
    second.write_text(json.dumps(value))
    original=p._atomic
    first_at_write=threading.Event()
    second_done=threading.Event()
    def synchronized_write(path,text):
        if path.name=="accomplishments.jsonl" and '"ACC-1"' in text and '"ACC-2"' not in text:
            first_at_write.set()
            second_done.wait(0.3)
        return original(path,text)
    monkeypatch.setattr(p,"_atomic",synchronized_write)
    def second_append():
        try:
            return p.append_accomplishment(root,second,True)
        finally:
            second_done.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        one=pool.submit(p.append_accomplishment,root,first,True)
        assert first_at_write.wait(2)
        two=pool.submit(second_append)
        assert one.result(timeout=3)==0 and two.result(timeout=3)==0
    records=[json.loads(x) for x in (root/"accomplishments.jsonl").read_text().splitlines()]
    assert {r["id"] for r in records}=={"ACC-1","ACC-2"}
    assert len(records)==2


def test_duplicate_confirmed_appends_serialize_and_preview_creates_no_lock(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    root=tmp_path/"career"
    proposed=draft(tmp_path)
    assert p.append_accomplishment(root,proposed,False)==0
    assert set(tmp_path.iterdir())=={proposed}
    p.ensure_layout(root)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(p.append_accomplishment,root,proposed,True) for _ in range(2)]
        assert sorted(f.result(timeout=3) for f in futures)==[0,1]
    assert len((root/"accomplishments.jsonl").read_text().splitlines())==1


def test_artifact_derivation_serializes_stale_read_updates(tmp_path, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    root=tmp_path/"career"
    p.ensure_layout(root)
    assert p.append_accomplishment(root,draft(tmp_path),True)==0
    original=p._atomic
    first_at_write=threading.Event()
    second_done=threading.Event()
    def synchronized_write(path,text):
        if path.name=="artifacts.jsonl" and '"id": "artifact-1"' in text and '"id": "artifact-2"' not in text:
            first_at_write.set()
            second_done.wait(0.3)
        return original(path,text)
    monkeypatch.setattr(p,"_atomic",synchronized_write)
    def second_derive():
        try:
            return p.artifact_derive(root,["ACC-1"],"artifact-2",True)
        finally:
            second_done.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        one=pool.submit(p.artifact_derive,root,["ACC-1"],"artifact-1",True)
        assert first_at_write.wait(2)
        two=pool.submit(second_derive)
        assert one.result(timeout=3)==0 and two.result(timeout=3)==0
    artifacts=[json.loads(x) for x in (root/"artifacts.jsonl").read_text().splitlines()]
    assert {r["id"] for r in artifacts}=={"artifact-1","artifact-2"}


def test_cross_process_writer_lock_has_bounded_busy_failure(tmp_path):
    import os
    import subprocess
    import sys
    root=tmp_path/"career"
    p.ensure_layout(root)
    proposed=draft(tmp_path)
    env=dict(os.environ)
    env["PYTHONPATH"]=str(Path(p.__file__).resolve().parent.parent)
    code="from pathlib import Path; import sys; from agent_core.personal_store import append_accomplishment; sys.exit(append_accomplishment(Path(sys.argv[1]),Path(sys.argv[2]),True))"
    with p._mutation_lock(root):
        child=subprocess.run([sys.executable,"-c",code,str(root),str(proposed)],env=env,capture_output=True,text=True,timeout=4)
    assert child.returncode==1 and "writer busy" in child.stderr
    assert (root/"accomplishments.jsonl").read_text()==""
    assert p.append_accomplishment(root,proposed,True)==0



@pytest.mark.parametrize("filename", ["profile.yaml", "accomplishments.jsonl"])
def test_personal_import_parses_the_hashed_snapshot(tmp_path,monkeypatch,filename):
    import hashlib,os
    from tests.test_anx5_portability import setup
    m,port,access,store,_=setup(tmp_path)
    root=tmp_path/"career"
    p.ensure_layout(root)
    assert p.append_accomplishment(root,draft(tmp_path),True)==0
    path=root/filename
    original=path.read_bytes()
    original_mtime=path.stat().st_mtime
    original_open=Path.open
    original_validate=p._validate_store
    ready=False
    replaced=False
    def validate_first(*args):
        nonlocal ready
        original_validate(*args)
        ready=True
    class Snapshot:
        def __init__(self,stream):self.stream=stream
        def __enter__(self):self.stream.__enter__();return self
        def __exit__(self,*args):return self.stream.__exit__(*args)
        def fileno(self):return self.stream.fileno()
        def read(self,*args):
            nonlocal replaced
            value=self.stream.read(*args)
            if not replaced:
                replacement=path.with_name(path.name+'.replacement')
                if filename=='profile.yaml':data="version: '1'\nidentity: {name: changed}\n"
                else:
                    record=json.loads(original.decode());record['action']='changed';data=json.dumps(record)+'\n'
                with original_open(replacement,'w') as out:out.write(data)
                os.utime(replacement,(original_mtime+100,original_mtime+100))
                os.replace(replacement,path)
                replaced=True
            return value
    def snapshot_open(self,mode='r',*args,**kwargs):
        stream=original_open(self,mode,*args,**kwargs)
        if self==path and ready and mode in {'r','rb'}:return Snapshot(stream)
        return stream
    monkeypatch.setattr(p,'_validate_store',validate_first)
    monkeypatch.setattr(Path,'open',snapshot_open)
    result=p.import_personal_files(root,store,access,[filename],confirmed=True)
    record=store.inspect(result['record_ids'][0],access)
    expected=hashlib.sha256(original).hexdigest()
    assert replaced
    assert record['sources'][0]['content_hash']==expected
    assert record['sources'][0]['retrieved_at']==original_mtime
    assert record['dependencies'][path.as_uri()]==expected
    if filename=='profile.yaml':assert json.loads(record['body'])['identity'].get('name')!='changed'
    else:assert json.loads(record['body'])['action']=='built'
