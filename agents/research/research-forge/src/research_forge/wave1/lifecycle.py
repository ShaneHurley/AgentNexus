"""Runtime-owned durable RF checkpoints and append-only lifecycle ledger."""
from __future__ import annotations
import fcntl
import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from agent_core.contracts import ContractDenied

SCHEMA_VERSION = 1

class LifecycleJournal:
    def __init__(self, root: Path, run_id: str):
        from research_forge.wave1.persistence import state_path
        self.directory = state_path(root, run_id).parent
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "lifecycle.sqlite"
        if self.path.is_symlink() or (self.directory/"execution.lock").is_symlink():
            raise ContractDenied("RF journal and lock must not be symlinks")
        existing = self.path.exists()
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if existing and version != SCHEMA_VERSION:
                raise ContractDenied(f"unsupported RF journal schema {version}; preserve journal and start a new run")
            if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ContractDenied("corrupt RF journal; preserve journal and reconcile manually")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS checkpoint (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS calls (key TEXT PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS control (id INTEGER PRIMARY KEY CHECK(id=1), cancel INTEGER NOT NULL);
            INSERT OR IGNORE INTO control VALUES (1,0);
            PRAGMA user_version=1;
            """)
    def backup(self):
        target = self.directory / ("lifecycle-backup-" + uuid.uuid4().hex + ".sqlite")
        with self.connect() as source, sqlite3.connect(target) as destination:
            source.backup(destination)
        return target
    @contextmanager
    def connect(self):
        if self.path.is_symlink() or self.directory.is_symlink():
            raise ContractDenied("RF journal path changed to a symlink")
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("PRAGMA synchronous=FULL")
        try:
            with db:
                yield db
        finally:
            db.close()
    @contextmanager
    def lock(self):
        import os
        if self.directory.is_symlink():
            raise ContractDenied("RF execution directory must not be a symlink")
        descriptor=os.open(self.directory/"execution.lock",os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,"a") as fh:
            try:
                fcntl.flock(fh,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ContractDenied("RF run is already executing") from exc
            try:
                yield
            finally:
                fcntl.flock(fh,fcntl.LOCK_UN)
    def event(self, db, kind, payload):
        db.execute("INSERT INTO events(kind,payload) VALUES (?,?)", (kind,json.dumps(payload,sort_keys=True)))
    def load(self):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM checkpoint WHERE id=1").fetchone()
        return json.loads(row[0]) if row else None
    def checkpoint(self, state, budget, pins, result=None):
        payload = {"state":state.to_dict(), "budget":asdict(budget.state) if budget.state else None, "pins":pins, "result":result}
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO checkpoint VALUES (1,?)", (json.dumps(payload,sort_keys=True),))
            self.event(db,"checkpoint",{"phase":state.phase, "run_id":state.run_id})
        from research_forge.wave1.persistence import save_run_state
        save_run_state(self.directory.parents[2],state,live=pins["live"])
    def cancelled(self):
        with self.connect() as db:
            return bool(db.execute("SELECT cancel FROM control WHERE id=1").fetchone()[0])
    def cancel(self):
        with self.connect() as db:
            db.execute("UPDATE control SET cancel=1 WHERE id=1")
            self.event(db,"cancel_intent",{})
    def check_dispatch(self):
        if self.cancelled():
            with self.connect() as db:
                unknown = any(json.loads(row[0])["status"] == "unknown" for row in db.execute("SELECT payload FROM calls"))
                self.event(db,"cancel_acknowledged" if not unknown else "cancel_pending_reconciliation",{})
            raise ContractDenied("CANCELLED" if not unknown else "RECONCILIATION_REQUIRED: cancellation has unresolved provider exposure")
    def incomplete(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT payload FROM calls") if json.loads(row[0])["status"] == "unknown"]
    def call(self,key):
        with self.connect() as db:
            row=db.execute("SELECT payload FROM calls WHERE key=?",(key,)).fetchone()
        return json.loads(row[0]) if row else None
    def prepare(self,key,cost,budget,auth):
        row={"call_id":str(uuid.uuid4()),"key":key,"status":"unknown","estimated_usd":cost,"reported_usd":None,"accounting":"unknown","budget":asdict(budget.state),"auth":auth}
        with self.connect() as db:
            if db.execute("SELECT cancel FROM control WHERE id=1").fetchone()[0]:
                raise ContractDenied("CANCELLED")
            db.execute("INSERT INTO calls VALUES (?,?)",(key,json.dumps(row,sort_keys=True)))
            self.event(db,"call_started",row)
        return row
    def complete(self,row,result,budget):
        row.update(status="completed",accounting="estimated",result=result,budget=asdict(budget.state))
        with self.connect() as db:
            db.execute("UPDATE calls SET payload=? WHERE key=?",(json.dumps(row,sort_keys=True),row["key"]))
            self.event(db,"call_completed",row)
    def view(self):
        with self.connect() as db:
            events=[{"seq":s,"kind":k,"payload":json.loads(p)} for s,k,p in db.execute("SELECT seq,kind,payload FROM events ORDER BY seq")]
            calls=[json.loads(r[0]) for r in db.execute("SELECT payload FROM calls")]
        checkpoint=self.load()
        budget=checkpoint.get("budget") if checkpoint else None
        if calls:
            budget=calls[-1]["budget"]
        return {"checkpoint":checkpoint,"calls":calls,"events":events,"budget":budget,"cancel_requested":self.cancelled(),"reconciliation_required":bool(self.incomplete())}
