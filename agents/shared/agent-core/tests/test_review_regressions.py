import sqlite3
from pathlib import Path
import os
import pytest
from agent_core.sessions import SessionStore
from agent_core.supervisor import Supervisor
from agent_core.isolation import DockerRunner

class Engine:
    def __init__(self): self.calls=0; self.result={}; self.on_execute=None
    def snapshot(self,*a): return {"provider":"mock"}
    def create(self,row): return "native-"+row["run_id"]
    def execute(self,row,answers=None):
        self.calls+=1
        self.result={"status":"SIMULATED","usage":{"tokens":0,"usd":0}}
        if self.on_execute: self.on_execute(row)
        return self.result
    def inspect(self,row): return self.result
    def cancel(self,row): pass
    def acknowledge(self,row): return self.result

def setup(tmp):
    engine=Engine();sup=Supervisor(tmp,adapters={"daily-coder":engine})
    session=sup.new_session()
    row=sup.create_run(session["session_id"],"daily-coder","root",tmp)
    return sup,engine,session,row

@pytest.mark.parametrize("status",["BLOCKED","RECONCILIATION_REQUIRED","COMPLETE"])
def test_parent_revocation_after_child_creation(tmp_path,status):
    sup,engine,session,parent=setup(tmp_path)
    child=sup.create_run(session["session_id"],"daily-coder","child",tmp_path,parent_id=parent["run_id"])
    sup.store.update(parent["run_id"],status)
    assert sup.execute(child["run_id"])["status"]=="BLOCKED"
    assert engine.calls==0

def test_cancel_races_known_native_completion(tmp_path):
    sup,engine,_,row=setup(tmp_path)
    engine.on_execute=lambda row:sup.store.request_cancel(row["run_id"])
    result=sup.execute(row["run_id"])
    if result["status"] != "CANCELLED": result=sup.cancel(row["run_id"])
    assert result["status"]=="CANCELLED" and result["acknowledged"]
    assert result["accounting"]["reserved_usd"]==0

def test_confirmed_usage_cannot_be_unknown(tmp_path):
    sup,engine,_,row=setup(tmp_path)
    sup.store.begin_call(row["run_id"],"call",10,.1)
    with pytest.raises(ValueError): sup.store.finish_call("call","confirmed",usage_status="unknown")
    assert sup.store.accounting(row["run_id"])["reserved_usd"]==.1

def test_tampered_migration_checksum_refused(tmp_path):
    store=SessionStore(tmp_path/"state.sqlite")
    with sqlite3.connect(store.path) as db: db.execute("UPDATE schema_migrations SET checksum='tampered' WHERE version=2")
    with pytest.raises(ValueError,match="checksum"): SessionStore(store.path)

def test_repeated_legacy_import_has_no_phantom_run(tmp_path):
    sup,engine,session,_=setup(tmp_path)
    engine.result={"status":"SIMULATED","usage":{"tokens":0,"usd":.1}}
    a=sup.import_legacy(session["session_id"],"daily-coder","old",tmp_path)
    b=sup.import_legacy(session["session_id"],"daily-coder","old",tmp_path)
    assert a["run_id"]==b["run_id"]
    assert len(sup.store.runs())==2

def test_snapshot_ancestor_swap_cannot_copy_outside(tmp_path,monkeypatch):
    workspace=tmp_path/"workspace";workspace.mkdir();src=workspace/"src";src.mkdir()
    (src/"data.txt").write_text("inside")
    outside=tmp_path/"private";outside.mkdir();(outside/"data.txt").write_text("outside")
    dest=tmp_path/"copy";dest.mkdir();original=os.open;swapped=False
    def swap(path,*a,**kw):
        nonlocal swapped
        if str(path).endswith("data.txt") and not swapped:
            swapped=True;src.rename(workspace/"old-src");src.symlink_to(outside,target_is_directory=True)
        return original(path,*a,**kw)
    monkeypatch.setattr(os,"open",swap)
    DockerRunner("review/image@sha256:"+"a"*64,workspace)._snapshot(dest)
    assert (dest/"src/data.txt").read_text()=="inside"


def test_live_rf_http_pause_does_not_consume_model_token_grant(tmp_path,monkeypatch):
    from agent_core.engine_adapters import ResearchForgeAdapter
    adapter=ResearchForgeAdapter(tmp_path)
    fake=type("RF",(),{"lifecycle":lambda _,key:{"checkpoint":{"state":{"paused":True}},"budget":{},"calls":[],"events":[],"reconciliation_required":False,"cancel_requested":False}})()
    monkeypatch.setattr(adapter,"_engine",lambda row:fake)
    result=adapter.inspect({"legacy_id":"native","live":True})
    assert result["usage"]["tokens"]==0


def test_genuine_v1_database_migrates(tmp_path):
    from agent_core.sessions import _SCHEMA
    path=tmp_path/"state.sqlite"
    with sqlite3.connect(path) as db:
        for statement in _SCHEMA[:3]: db.execute(statement)
        db.execute("PRAGMA user_version=1")
    store=SessionStore(path)
    assert store.sessions()==[]
    assert path.with_name("state.sqlite.pre-v2").exists()

@pytest.mark.parametrize("boundary",["alias","inspect"])
def test_interrupted_import_never_gains_replay_authority(tmp_path,monkeypatch,boundary):
    sup,engine,session,_=setup(tmp_path)
    if boundary=="alias":
        original=sup.store.set_alias
        def crash(*a,**kw): original(*a,**kw);raise KeyboardInterrupt()
        monkeypatch.setattr(sup.store,"set_alias",crash)
    else:
        def crash(*a): raise KeyboardInterrupt()
        monkeypatch.setattr(engine,"inspect",crash)
    with pytest.raises(KeyboardInterrupt): sup.import_legacy(session["session_id"],"daily-coder","old",tmp_path)
    row=next(row for row in sup.store.runs() if row.get("legacy_id")=="old")
    assert sup.execute(row["run_id"])["status"]=="RECONCILIATION_REQUIRED"
    assert engine.calls==0
