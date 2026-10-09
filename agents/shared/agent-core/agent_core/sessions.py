"""Local durable session, execution and reservation authority.

Knowledge memory is deliberately separate. Transactions serialize writers; OS
execution locks live in lifecycle.py. All foreign references are checked here.
"""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import math
import sqlite3
import time
import uuid
from .lifecycle import RunLock

SCHEMA_VERSION = 2
TERMINAL = frozenset({"COMPLETE", "SIMULATED", "FAILED", "CANCELLED"})


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def resources(tokens, usd):
    if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
        raise ValueError("tokens must be a nonnegative integer")
    if isinstance(usd, bool) or not isinstance(usd, (int, float)) or not math.isfinite(usd) or usd < 0:
        raise ValueError("cost must be finite and nonnegative")


class SessionStore:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with RunLock(self.path.parent / "locks", str(self.path) + ":migration"):
            with self.connect() as c:
                version = c.execute("PRAGMA user_version").fetchone()[0]
                if version > SCHEMA_VERSION:
                    raise ValueError("session schema is newer than this runtime")
                if version and version < SCHEMA_VERSION:
                    backup = self.path.with_name(self.path.name + ".pre-v" + str(SCHEMA_VERSION))
                    if not backup.exists():
                        with sqlite3.connect(backup) as target: c.backup(target)
                        backup.chmod(0o600)
                expected={1:digest(_SCHEMA[:3]),2:digest(_SCHEMA[3:])}
                ledger=bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone())
                if version >= 2 and not ledger:
                    raise ValueError("session migration checksum ledger missing")
                if version and ledger:
                    recorded=dict(c.execute("SELECT version,checksum FROM schema_migrations"))
                    if version >= 2 and not {1,2}.issubset(recorded):
                        raise ValueError("session migration checksum history incomplete")
                    for migration,checksum in recorded.items():
                        if migration not in expected or checksum != expected[migration]:
                            raise ValueError("session migration checksum mismatch")
                c.execute("PRAGMA journal_mode=WAL")
                c.execute("BEGIN IMMEDIATE")
                try:
                    for statement in _SCHEMA: c.execute(statement)
                    c.execute("INSERT OR IGNORE INTO schema_migrations VALUES(1,?,?)", (digest(_SCHEMA[:3]), time.time()))
                    c.execute("INSERT OR IGNORE INTO schema_migrations VALUES(2,?,?)", (digest(_SCHEMA[3:]), time.time()))
                    c.execute("PRAGMA user_version=2")
                    c.commit()
                except BaseException:
                    c.rollback(); raise
        self.path.chmod(0o600)

    @contextmanager
    def connect(self, write=False):
        c = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            if write: c.execute("BEGIN IMMEDIATE")
            yield c
            if write: c.commit()
        except BaseException:
            if write: c.rollback()
            raise
        finally:
            c.close()

    def _event(self, c, run_id, kind, payload):
        c.execute("INSERT INTO events(run_id,kind,payload,created) VALUES(?,?,?,?)", (run_id, kind, canonical(payload), time.time()))

    def new_session(self, identity="local", project=None, profile="default"):
        if not all(isinstance(v, str) and v for v in (identity, profile)):
            raise ValueError("identity and profile required")
        key = str(uuid.uuid4())
        with self.connect(True) as c:
            c.execute("INSERT INTO sessions VALUES(?,?,?,?,?)", (key, identity, str(Path(project).resolve()) if project else None, profile, time.time()))
        return {"session_id":key, "identity":identity, "project":str(Path(project).resolve()) if project else None, "profile":profile}

    def sessions(self):
        with self.connect() as c: return [dict(r) for r in c.execute("SELECT * FROM sessions ORDER BY created DESC")]

    def create_run(self, session_id, engine, request, workspace, snapshot, registry_hash, *, parent_id=None, task_key=None, limit_usd=5.0, limit_tokens=80000, deadline=None, live=False, imported=False):
        resources(limit_tokens, limit_usd)
        if deadline is not None and (isinstance(deadline,bool) or not isinstance(deadline,(int,float)) or not math.isfinite(deadline)):
            raise ValueError("deadline must be a finite timestamp")
        if engine not in ("daily-coder", "research-forge"): raise ValueError("unknown engine")
        key = str(uuid.uuid4()); workspace = str(Path(workspace).resolve())
        with self.connect(True) as c:
            if not c.execute("SELECT 1 FROM sessions WHERE session_id=?", (session_id,)).fetchone(): raise KeyError(session_id)
            root, depth = key, 0
            if task_key and c.execute("SELECT 1 FROM runs WHERE session_id=? AND task_key=?", (session_id,task_key)).fetchone(): raise ValueError("duplicate task/idempotency key")
            if parent_id:
                p = c.execute("SELECT * FROM runs WHERE run_id=?",(parent_id,)).fetchone()
                if not p or p["session_id"] != session_id: raise ValueError("parent must belong to this session")
                if p["engine"] != engine: raise ValueError("cross-workflow delegation requires a reviewed handoff")
                if bool(live) != bool(p["live"]) or snapshot.get("provider") != json.loads(p["snapshot"]).get("provider"):
                    raise ValueError("parent execution policy cannot be widened or replaced")
                if deadline is not None and p["deadline"] is not None and deadline > p["deadline"]:
                    raise ValueError("parent deadline cannot be widened")
                if deadline is None: deadline=p["deadline"]
                limit_usd=min(limit_usd,p["limit_usd"])
                limit_tokens=min(limit_tokens,p["limit_tokens"])
                if p["cancel_requested"] or p["status"] in TERMINAL | {"BLOCKED","RECONCILIATION_REQUIRED"}: raise ValueError("parent cannot dispatch")
                inherited=json.loads(p["snapshot"])
                if registry_hash != p["registry_hash"] or {k:v for k,v in snapshot.items() if k != "workspace"} != {k:v for k,v in inherited.items() if k != "workspace"}:
                    raise ValueError("parent pinned authority cannot be replaced")
                if not Path(workspace).is_relative_to(Path(p["workspace"])): raise ValueError("parent workspace boundary")
                root, depth = p["root_id"], p["depth"] + 1
                if depth > 2: raise ValueError("delegation depth exceeded")
                if c.execute("SELECT COUNT(*) FROM runs WHERE parent_id=? AND status NOT IN ('COMPLETE','SIMULATED','FAILED','CANCELLED')",(parent_id,)).fetchone()[0] >= 2: raise ValueError("child concurrency exceeded")
            c.execute("INSERT INTO runs(run_id,session_id,engine,parent_id,root_id,depth,task_key,workspace,request,snapshot,config_hash,registry_hash,limit_usd,limit_tokens,deadline,live,created,updated,status,completeness,provenance) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (key, session_id,engine,parent_id,root,depth,task_key,workspace,canonical(request),canonical(snapshot),digest(snapshot),registry_hash,limit_usd,limit_tokens,deadline,live,time.time(),time.time(),"RECONCILIATION_REQUIRED" if imported else "QUEUED","partial" if imported else "complete",canonical({"imported":True,"engine":engine}) if imported else "{}"))
            if imported:
                c.execute("INSERT INTO calls(call_id,run_id,estimated_tokens,estimated_usd,state,outcome,usage_status,created,updated) VALUES(?,?,?,?,'unknown','unknown','unknown',?,?)",("import:"+key,key,limit_tokens,limit_usd,time.time(),time.time()))
            self._event(c,key,"created",{"config_hash":digest(snapshot),"registry_hash":registry_hash,"parent_id":parent_id})
        return self.get_run(key)

    @staticmethod
    def _row(row):
        out = dict(row)
        for field in ("snapshot", "request", "provenance"):
            out[field] = json.loads(out[field]) if out.get(field) else None
        out["cancel_requested"] = bool(out["cancel_requested"])
        out["live"] = bool(out["live"])
        return out

    def get_run(self, key):
        with self.connect() as c:
            rows = c.execute("SELECT * FROM runs WHERE run_id=? OR legacy_id=?",(key,key)).fetchall()
            if not rows: raise KeyError(key)
            if len(rows) != 1: raise ValueError("ambiguous legacy run alias")
            return self._row(rows[0])

    def runs(self, engine=None, session_id=None, limit=50):
        sql, args = "SELECT * FROM runs WHERE 1=1", []
        for field, value in (("engine",engine),("session_id",session_id)):
            if value: sql += " AND " + field + "=?"; args.append(value)
        args.append(min(1000,max(1,int(limit))))
        with self.connect() as c: return [self._row(r) for r in c.execute(sql + " ORDER BY created DESC LIMIT ?", args)]

    def set_alias(self, key, legacy_id, *, completeness="complete", provenance=None):
        with self.connect(True) as c:
            c.execute("UPDATE runs SET legacy_id=?,completeness=?,provenance=?,updated=? WHERE run_id=?", (legacy_id,completeness,canonical(provenance or {}),time.time(),key))
            self._event(c,key,"engine_linked",{"legacy_id":legacy_id,"completeness":completeness})

    def check_pin(self, key, snapshot, registry_hash):
        row = self.get_run(key)
        if row["config_hash"] != digest(snapshot): raise ValueError("execution configuration changed")
        if row["registry_hash"] != registry_hash: raise ValueError("registry changed")
        return row

    def update(self, key, status, *, payload=None):
        with self.connect(True) as c:
            row=c.execute("SELECT cancel_requested,status FROM runs WHERE run_id=?",(key,)).fetchone()
            if not row: raise KeyError(key)
            # No late response may erase a STOP request or reopen a terminal run.
            if row["status"] in TERMINAL and status != row["status"]: raise ValueError("terminal run cannot be reopened")
            if row["cancel_requested"] and status not in ("CANCELLED","RECONCILIATION_REQUIRED"):
                status="CANCEL_REQUESTED"
            c.execute("UPDATE runs SET status=?,updated=? WHERE run_id=?",(status,time.time(),key))
            self._event(c,key,"status",{"status":status, **(payload or {})})
        return self.get_run(key)

    def checkpoint(self, key, state, artifacts=()):
        raw=canonical(state); h=hashlib.sha256(raw.encode()).hexdigest()
        with self.connect(True) as c:
            c.execute("INSERT INTO checkpoints(run_id,hash,state,created) VALUES(?,?,?,?)",(key,h,raw,time.time()))
            for artifact in artifacts:
                c.execute("INSERT OR REPLACE INTO artifacts VALUES(?,?,?)",(key,str(artifact["id"]),canonical(artifact)))
            self._event(c,key,"checkpoint",{"hash":h})
        return h

    def latest_checkpoint(self, key):
        with self.connect() as c:
            row=c.execute("SELECT * FROM checkpoints WHERE run_id=? ORDER BY seq DESC LIMIT 1",(key,)).fetchone()
            return json.loads(row["state"]) if row else None

    def begin_call(self, key, call_id, estimated_tokens, estimated_usd):
        resources(estimated_tokens, estimated_usd)
        with self.connect(True) as c:
            row=c.execute("SELECT * FROM runs WHERE run_id=?",(key,)).fetchone()
            if not row: raise KeyError(key)
            ancestors=c.execute("WITH RECURSIVE parents(id,parent_id,status,cancel_requested) AS (SELECT run_id,parent_id,status,cancel_requested FROM runs WHERE run_id=? UNION ALL SELECT r.run_id,r.parent_id,r.status,r.cancel_requested FROM runs r JOIN parents p ON r.run_id=p.parent_id) SELECT * FROM parents WHERE id != ?",(key,key)).fetchall()
            if any(p["cancel_requested"] or p["status"] in TERMINAL | {"BLOCKED","RECONCILIATION_REQUIRED"} for p in ancestors):
                raise ValueError("parent authority no longer permits dispatch")
            if row["cancel_requested"]: raise ValueError("cancel requested; new dispatch denied")
            if row["status"] in TERMINAL: raise ValueError("terminal run cannot dispatch")
            if row["deadline"] and time.time() >= row["deadline"]: raise ValueError("run deadline exhausted")
            if row["status"] == "RECONCILIATION_REQUIRED" or c.execute("SELECT 1 FROM calls WHERE run_id=? AND state IN ('pending','unknown')",(key,)).fetchone(): raise ValueError("reconciliation required before replay")
            root=c.execute("SELECT limit_tokens,limit_usd FROM runs WHERE run_id=?",(row["root_id"],)).fetchone()
            totals=c.execute("SELECT COALESCE(SUM(CASE WHEN calls.state IN ('pending','unknown') THEN estimated_tokens ELSE COALESCE(tokens,0) END),0), COALESCE(SUM(CASE WHEN calls.state IN ('pending','unknown') THEN estimated_usd ELSE COALESCE(usd,0) END),0) FROM calls JOIN runs USING(run_id) WHERE root_id=?",(row["root_id"],)).fetchone()
            if totals[0]+estimated_tokens > root[0] or totals[1]+estimated_usd > root[1]: raise ValueError("root/descendant budget exceeded")
            c.execute("INSERT INTO calls(call_id,run_id,estimated_tokens,estimated_usd,state,created,updated) VALUES(?,?,?,?,'pending',?,?)",(call_id,key,estimated_tokens,estimated_usd,time.time(),time.time()))
            c.execute("UPDATE runs SET status='RUNNING',updated=? WHERE run_id=?",(time.time(),key))
            self._event(c,key,"call_reserved",{"call_id":call_id,"tokens":estimated_tokens,"usd":estimated_usd})

    def finish_call(self, call_id, outcome, *, tokens=0, usd=0.0, usage_status="estimated"):
        if outcome not in ("confirmed", "not_dispatched", "unknown"): raise ValueError("invalid call outcome")
        if usage_status not in ("estimated", "reported", "reconciled", "unknown"): raise ValueError("invalid usage status")
        if outcome != "unknown" and usage_status == "unknown":
            raise ValueError("known settlement requires known usage category")
        resources(tokens,usd)
        with self.connect(True) as c:
            row=c.execute("SELECT * FROM calls WHERE call_id=?",(call_id,)).fetchone()
            if not row: raise KeyError(call_id)
            if row["state"] == "settled":
                if row["outcome"] != outcome or row["tokens"] != tokens or row["usd"] != usd: raise ValueError("conflicting settlement")
                return
            if outcome == "unknown":
                c.execute("UPDATE calls SET state='unknown',outcome=?,usage_status='unknown',updated=? WHERE call_id=?",(outcome,time.time(),call_id))
                c.execute("UPDATE runs SET status='RECONCILIATION_REQUIRED',updated=? WHERE run_id=?",(time.time(),row["run_id"]))
            else:
                if outcome == "not_dispatched" and (tokens or usd): raise ValueError("undispatched call cannot incur reported usage")
                c.execute("UPDATE calls SET state='settled',outcome=?,tokens=?,usd=?,usage_status=?,updated=? WHERE call_id=?",(outcome,tokens,usd,usage_status,time.time(),call_id))
            self._event(c,row["run_id"],"call_outcome",{"call_id":call_id,"outcome":outcome,"usage_status":usage_status})

    def pending_calls(self, key):
        with self.connect() as c: return [dict(r) for r in c.execute("SELECT * FROM calls WHERE run_id=? AND state IN ('pending','unknown')",(key,))]

    def accounting(self, key, *, descendants=True):
        root=self.get_run(key)["run_id"]
        with self.connect() as c:
            if descendants:
                rows=c.execute("WITH RECURSIVE children(id) AS (SELECT ? UNION ALL SELECT runs.run_id FROM runs JOIN children ON runs.parent_id=children.id) SELECT calls.* FROM calls JOIN children ON calls.run_id=children.id",(root,)).fetchall()
            else:
                rows=c.execute("SELECT * FROM calls WHERE run_id=?",(root,)).fetchall()
        result={"reserved_usd":0.0,"reserved_tokens":0,"estimated_usd":0.0,"reported_usd":0.0,"reconciled_usd":0.0,"tokens":0,"usage_status":"recorded"}
        for r in rows:
            if r["state"] in ("pending","unknown"):
                result["reserved_usd"]+=r["estimated_usd"]; result["reserved_tokens"]+=r["estimated_tokens"]; result["usage_status"]="unknown"
            else:
                result[r["usage_status"]+"_usd"]+=r["usd"]
                result["tokens"]+=r["tokens"]
        return result

    def request_cancel(self, key):
        key=self.get_run(key)["run_id"]
        with self.connect(True) as c:
            rows=c.execute("WITH RECURSIVE children(id) AS (SELECT ? UNION ALL SELECT runs.run_id FROM runs JOIN children ON runs.parent_id=children.id) SELECT runs.* FROM runs JOIN children ON runs.run_id=children.id",(key,)).fetchall()
            for r in rows:
                if r["status"] in TERMINAL: continue
                c.execute("UPDATE runs SET cancel_requested=1,status='CANCEL_REQUESTED',updated=? WHERE run_id=?",(time.time(),r["run_id"]))
                self._event(c,r["run_id"],"cancel_requested",{"root":key})
        return self.get_run(key)

    def acknowledge_cancel(self, key):
        with self.connect(True) as c:
            row=c.execute("SELECT * FROM runs WHERE run_id=?",(key,)).fetchone()
            if not row or not row["cancel_requested"]: raise ValueError("cancellation was not requested")
            if c.execute("SELECT 1 FROM calls WHERE run_id=? AND state IN ('pending','unknown')",(key,)).fetchone(): raise ValueError("outstanding external calls; termination unconfirmed")
            if c.execute("SELECT 1 FROM runs WHERE parent_id=? AND status NOT IN ('COMPLETE','SIMULATED','FAILED','CANCELLED')",(key,)).fetchone(): raise ValueError("outstanding descendants")
            c.execute("UPDATE runs SET status='CANCELLED',updated=? WHERE run_id=?",(time.time(),key))
            self._event(c,key,"cancel_acknowledged",{})
        return self.get_run(key)

    def events(self, key):
        with self.connect() as c:
            return [{**dict(r),"payload":json.loads(r["payload"])} for r in c.execute("SELECT * FROM events WHERE run_id=? ORDER BY seq",(key,))]

    def artifacts(self, key):
        with self.connect() as c: return [json.loads(r[0]) for r in c.execute("SELECT metadata FROM artifacts WHERE run_id=?",(key,))]

    def export(self, destination):
        destination=Path(destination)
        if destination.resolve() == self.path or destination.exists(): raise ValueError("export requires a new destination")
        with self.connect() as c, sqlite3.connect(destination) as target: c.backup(target)
        destination.chmod(0o600)
        return destination


_SCHEMA = [
"CREATE TABLE IF NOT EXISTS sessions(session_id TEXT PRIMARY KEY,identity TEXT NOT NULL,project TEXT,profile TEXT NOT NULL,created REAL NOT NULL)",
"CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY,session_id TEXT NOT NULL REFERENCES sessions(session_id),engine TEXT NOT NULL,legacy_id TEXT,parent_id TEXT REFERENCES runs(run_id),root_id TEXT NOT NULL,depth INTEGER NOT NULL DEFAULT 0,task_key TEXT,workspace TEXT NOT NULL,request TEXT NOT NULL,snapshot TEXT NOT NULL,config_hash TEXT NOT NULL,registry_hash TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'QUEUED',cancel_requested INTEGER NOT NULL DEFAULT 0,completeness TEXT NOT NULL DEFAULT 'complete',provenance TEXT NOT NULL DEFAULT '{}',limit_usd REAL NOT NULL,limit_tokens INTEGER NOT NULL,deadline REAL,live INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL,updated REAL NOT NULL,UNIQUE(engine,legacy_id),UNIQUE(session_id,task_key))",
"CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL REFERENCES runs(run_id),kind TEXT NOT NULL,payload TEXT NOT NULL,created REAL NOT NULL)",
"CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY,checksum TEXT NOT NULL,applied REAL NOT NULL)",
"CREATE TABLE IF NOT EXISTS calls(call_id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES runs(run_id),estimated_tokens INTEGER NOT NULL,estimated_usd REAL NOT NULL,state TEXT NOT NULL,outcome TEXT,tokens INTEGER,usd REAL,usage_status TEXT NOT NULL DEFAULT 'unknown',created REAL NOT NULL,updated REAL NOT NULL)",
"CREATE TABLE IF NOT EXISTS checkpoints(seq INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL REFERENCES runs(run_id),hash TEXT NOT NULL,state TEXT NOT NULL,created REAL NOT NULL)",
"CREATE TABLE IF NOT EXISTS artifacts(run_id TEXT NOT NULL REFERENCES runs(run_id),artifact_id TEXT NOT NULL,metadata TEXT NOT NULL,PRIMARY KEY(run_id,artifact_id))",
"CREATE INDEX IF NOT EXISTS idx_calls_run ON calls(run_id,state)",
"CREATE INDEX IF NOT EXISTS idx_runs_parent ON runs(parent_id)",
]
