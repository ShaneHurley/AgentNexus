from __future__ import annotations
import json, sqlite3, threading, time
from pathlib import Path
from .models import Phase, RunStatus
from .state_machine import allowed_transition

SCHEMA_VERSION=2

class StateStore:
    """SQLite is the sole authority. Files are immutable evidence only."""
    def __init__(self,path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self._lock=threading.RLock(); self._init()
    def _connect(self):
        c=sqlite3.connect(self.path,timeout=30); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c
    def _init(self):
        with self._lock,self._connect() as c:
            c.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, request TEXT NOT NULL, repo TEXT NOT NULL, phase TEXT NOT NULL, profile TEXT, config_hash TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, old_phase TEXT, new_phase TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, idem_key TEXT NOT NULL UNIQUE, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS artifacts(hash TEXT PRIMARY KEY, run_id TEXT NOT NULL, kind TEXT NOT NULL, path TEXT NOT NULL, producer TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS usage(run_id TEXT NOT NULL, role TEXT NOT NULL, calls INTEGER NOT NULL DEFAULT 0, input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(run_id,role));
            CREATE TABLE IF NOT EXISTS schema_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            row=c.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
            current=int(row[0]) if row else 1
            if current<2: self._migrate_v2(c)
            c.execute("INSERT INTO schema_meta VALUES('version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(SCHEMA_VERSION),))
            c.execute("CREATE INDEX IF NOT EXISTS idx_runs_updated ON runs(updated DESC)")
    def _migrate_v2(self,c):
        cols={r[1] for r in c.execute("PRAGMA table_info(runs)")}
        for name,ddl in [("status","ALTER TABLE runs ADD COLUMN status TEXT NOT NULL DEFAULT 'ACTIVE'"),
                         ("revision","ALTER TABLE runs ADD COLUMN revision TEXT"),
                         ("tree_fingerprint","ALTER TABLE runs ADD COLUMN tree_fingerprint TEXT"),
                         ("prompt_hash","ALTER TABLE runs ADD COLUMN prompt_hash TEXT"),
                         ("workflow_version","ALTER TABLE runs ADD COLUMN workflow_version TEXT"),
                         ("live","ALTER TABLE runs ADD COLUMN live INTEGER NOT NULL DEFAULT 0"),
                         ("plan_hash","ALTER TABLE runs ADD COLUMN plan_hash TEXT"),
                         ("repair_cycles","ALTER TABLE runs ADD COLUMN repair_cycles INTEGER NOT NULL DEFAULT 0"),
                         ("frontier_calls","ALTER TABLE runs ADD COLUMN frontier_calls INTEGER NOT NULL DEFAULT 0"),
                         ("est_usd","ALTER TABLE runs ADD COLUMN est_usd REAL NOT NULL DEFAULT 0.0")]:
            if name not in cols: c.execute(ddl)
        c.executescript("""
        CREATE TABLE IF NOT EXISTS invocations(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, role TEXT NOT NULL, phase TEXT, lane INTEGER NOT NULL DEFAULT 0, turn INTEGER NOT NULL DEFAULT 0, tier TEXT, model TEXT, input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0, est_usd REAL NOT NULL DEFAULT 0.0, latency_ms INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'ok', error TEXT, idem_key TEXT NOT NULL UNIQUE, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS tool_calls(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, role TEXT NOT NULL, phase TEXT, tool TEXT NOT NULL, arguments TEXT NOT NULL, decision TEXT NOT NULL, reason TEXT, result_hash TEXT, duration_ms INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS approvals(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, kind TEXT NOT NULL, subject_hash TEXT, state TEXT NOT NULL, actor TEXT, note TEXT, created REAL NOT NULL, decided REAL, UNIQUE(run_id,kind,subject_hash));
        CREATE TABLE IF NOT EXISTS jobs(job_id TEXT PRIMARY KEY, run_id TEXT, kind TEXT NOT NULL, argv TEXT NOT NULL, cwd TEXT NOT NULL, pid INTEGER, state TEXT NOT NULL, exit_code INTEGER, log_path TEXT, result_hash TEXT, fingerprint TEXT, started REAL, heartbeat REAL, finished REAL, timeout_s INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS job_history(id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL, repo TEXT NOT NULL, platform TEXT NOT NULL, duration_s REAL NOT NULL, exit_code INTEGER NOT NULL, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS spend(day TEXT PRIMARY KEY, tokens INTEGER NOT NULL DEFAULT 0, est_usd REAL NOT NULL DEFAULT 0.0);
        CREATE TABLE IF NOT EXISTS evaluations(id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id TEXT NOT NULL, kind TEXT NOT NULL, verdict TEXT NOT NULL, detail TEXT, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS candidates(candidate_id TEXT PRIMARY KEY, kind TEXT NOT NULL, target TEXT NOT NULL, diff TEXT NOT NULL, rationale TEXT, state TEXT NOT NULL, provenance TEXT, created REAL NOT NULL, decided REAL);
        CREATE INDEX IF NOT EXISTS idx_inv_run ON invocations(run_id);
        CREATE INDEX IF NOT EXISTS idx_tool_run ON tool_calls(run_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_run ON jobs(run_id);
        CREATE INDEX IF NOT EXISTS idx_hist_fp ON job_history(fingerprint);
        """)
    def create(self,run_id,request,repo,config_hash,idem_key,**meta):
        now=time.time()
        with self._lock,self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("INSERT INTO runs(run_id,request,repo,phase,profile,config_hash,created,updated,status,revision,tree_fingerprint,prompt_hash,workflow_version,live) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (run_id,request,repo,Phase.NEW.value,None,config_hash,now,now,RunStatus.ACTIVE.value,
                       meta.get("revision"),meta.get("tree_fingerprint"),meta.get("prompt_hash"),meta.get("workflow_version"),1 if meta.get("live") else 0))
            c.execute("INSERT INTO events(run_id,old_phase,new_phase,kind,payload,idem_key,created) VALUES(?,?,?,?,?,?,?)",(run_id,None,Phase.NEW.value,"create","{}",idem_key,now))
    def get(self,run_id):
        with self._connect() as c:
            r=c.execute("SELECT * FROM runs WHERE run_id=?",(run_id,)).fetchone()
            if not r: raise KeyError(run_id)
            return dict(r)
    def transition(self,run_id,new_phase,payload,idem_key):
        now=time.time()
        with self._lock,self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT 1 FROM events WHERE idem_key=?",(idem_key,)).fetchone(): return False
            row=c.execute("SELECT phase FROM runs WHERE run_id=?",(run_id,)).fetchone()
            if not row: raise KeyError(run_id)
            old=Phase(row[0]); new=Phase(new_phase)
            if not allowed_transition(old,new): raise ValueError(f"invalid transition {old.value}->{new.value}")
            c.execute("UPDATE runs SET phase=?,updated=? WHERE run_id=?",(new.value,now,run_id))
            c.execute("INSERT INTO events(run_id,old_phase,new_phase,kind,payload,idem_key,created) VALUES(?,?,?,?,?,?,?)",(run_id,old.value,new.value,"transition",json.dumps(payload,sort_keys=True),idem_key,now))
            return True
    def set_profile(self,run_id,profile):
        with self._connect() as c: c.execute("UPDATE runs SET profile=?,updated=? WHERE run_id=?",(profile,time.time(),run_id))
    def record_artifact(self,h,run_id,kind,path,producer):
        with self._connect() as c: c.execute("INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?,?,?)",(h,run_id,kind,str(path),producer,time.time()))
    def add_usage(self,run_id,role,input_tokens,output_tokens):
        with self._connect() as c:
            c.execute("INSERT INTO usage VALUES(?,?,?,?,?) ON CONFLICT(run_id,role) DO UPDATE SET calls=calls+1,input_tokens=input_tokens+excluded.input_tokens,output_tokens=output_tokens+excluded.output_tokens",(run_id,role,1,input_tokens,output_tokens))
    def total_usage(self,run_id):
        with self._connect() as c:
            r=c.execute("SELECT COALESCE(SUM(calls),0),COALESCE(SUM(input_tokens+output_tokens),0) FROM usage WHERE run_id=?",(run_id,)).fetchone(); return {"calls":r[0],"tokens":r[1]}

    # --- status -------------------------------------------------------
    def set_status(self,run_id,status):
        with self._lock,self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("UPDATE runs SET status=?,updated=? WHERE run_id=?",(getattr(status,"value",status),time.time(),run_id))
    def transition_status(self,run_id,new_phase,status,payload,idem_key):
        """Atomically change workflow phase and execution status."""
        now=time.time()
        with self._lock,self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            if c.execute("SELECT 1 FROM events WHERE idem_key=?",(idem_key,)).fetchone(): return False
            row=c.execute("SELECT phase FROM runs WHERE run_id=?",(run_id,)).fetchone()
            if not row: raise KeyError(run_id)
            old=Phase(row[0]); new=Phase(new_phase)
            if not allowed_transition(old,new): raise ValueError(f"invalid transition {old.value}->{new.value}")
            c.execute("UPDATE runs SET phase=?,status=?,updated=? WHERE run_id=?",(new.value,getattr(status,"value",status),now,run_id))
            c.execute("INSERT INTO events(run_id,old_phase,new_phase,kind,payload,idem_key,created) VALUES(?,?,?,?,?,?,?)",
                      (run_id,old.value,new.value,"transition",json.dumps(payload,sort_keys=True),idem_key,now))
            return True
    def prepare_plan_approval(self,run_id,plan_hash,note=None):
        """Pin the plan and create its approval request in one transaction."""
        now=time.time()
        with self._lock,self._connect() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("UPDATE runs SET plan_hash=?,updated=? WHERE run_id=?",(plan_hash,now,run_id))
            c.execute("INSERT OR IGNORE INTO approvals(run_id,kind,subject_hash,state,note,created) VALUES(?, 'plan', ?, 'pending', ?, ?)",
                      (run_id,plan_hash,note,now))
            return dict(c.execute("SELECT * FROM approvals WHERE run_id=? AND kind='plan' AND subject_hash=?",(run_id,plan_hash)).fetchone())
    def set_field(self,run_id,field,value):
        if field not in {"plan_hash","revision","tree_fingerprint","repair_cycles","frontier_calls","workflow_version","profile"}:
            raise ValueError(f"field {field} is not updatable")
        with self._lock,self._connect() as c:
            c.execute(f"UPDATE runs SET {field}=?,updated=? WHERE run_id=?",(value,time.time(),run_id))
    def bump_repair(self,run_id):
        with self._lock,self._connect() as c:
            c.execute("UPDATE runs SET repair_cycles=repair_cycles+1,updated=? WHERE run_id=?",(time.time(),run_id))
            return c.execute("SELECT repair_cycles FROM runs WHERE run_id=?",(run_id,)).fetchone()[0]
    def bump_frontier(self,run_id):
        with self._lock,self._connect() as c:
            c.execute("UPDATE runs SET frontier_calls=frontier_calls+1,updated=? WHERE run_id=?",(time.time(),run_id))
    def list_runs(self,limit=50):
        with self._connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM runs ORDER BY updated DESC LIMIT ?",(limit,))]
    def events(self,run_id,limit=200):
        with self._connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM events WHERE run_id=? ORDER BY seq DESC LIMIT ?",(run_id,limit))]
    def artifacts(self,run_id):
        with self._connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM artifacts WHERE run_id=? ORDER BY created",(run_id,))]

    # --- audit --------------------------------------------------------
    def record_invocation(self,run_id,role,phase,lane,turn,tier,model,it,ot,usd,latency_ms,status,error,idem_key):
        with self._lock,self._connect() as c:
            c.execute("INSERT OR IGNORE INTO invocations(run_id,role,phase,lane,turn,tier,model,input_tokens,output_tokens,est_usd,latency_ms,status,error,idem_key,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (run_id,role,phase,lane,turn,tier,model,it,ot,usd,latency_ms,status,error,idem_key,time.time()))
            c.execute("UPDATE runs SET est_usd=est_usd+?,updated=? WHERE run_id=?",(usd,time.time(),run_id))
    def record_tool_call(self,run_id,role,phase,tool,arguments,decision,reason=None,result_hash=None,duration_ms=0):
        with self._lock,self._connect() as c:
            c.execute("INSERT INTO tool_calls(run_id,role,phase,tool,arguments,decision,reason,result_hash,duration_ms,created) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (run_id,role,phase,tool,json.dumps(arguments,sort_keys=True)[:4000],decision,reason,result_hash,duration_ms,time.time()))
    def tool_calls(self,run_id,limit=200):
        with self._connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM tool_calls WHERE run_id=? ORDER BY id DESC LIMIT ?",(run_id,limit))]
    def invocations(self,run_id,limit=200):
        with self._connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM invocations WHERE run_id=? ORDER BY id DESC LIMIT ?",(run_id,limit))]
    def metrics_aggregate(self,run_limit=50):
        """Return dashboard aggregates with a fixed number of SQL queries."""
        with self._connect() as c:
            roles=[dict(r) for r in c.execute("""
                WITH recent AS (SELECT run_id FROM runs ORDER BY updated DESC LIMIT ?)
                SELECT role, COUNT(*) calls, COALESCE(SUM(input_tokens+output_tokens),0) tokens,
                       COALESCE(SUM(est_usd),0.0) usd,
                       SUM(CASE WHEN status!='ok' THEN 1 ELSE 0 END) errors,
                       COALESCE(AVG(latency_ms),0) avg_latency_ms
                FROM invocations WHERE run_id IN (SELECT run_id FROM recent) GROUP BY role
            """,(run_limit,))]
            denied=c.execute("""
                WITH recent AS (SELECT run_id FROM runs ORDER BY updated DESC LIMIT ?)
                SELECT COUNT(*) FROM tool_calls
                WHERE run_id IN (SELECT run_id FROM recent) AND decision!='allow'
            """,(run_limit,)).fetchone()[0]
            active_jobs=c.execute("SELECT COUNT(*) FROM jobs WHERE state IN ('pending','running')").fetchone()[0]
        return {"roles":roles,"tool_denials":denied,"jobs_active":active_jobs}

    # --- approvals ----------------------------------------------------
    def request_approval(self,run_id,kind,subject_hash,note=None):
        with self._lock,self._connect() as c:
            c.execute("INSERT OR IGNORE INTO approvals(run_id,kind,subject_hash,state,note,created) VALUES(?,?,?,'pending',?,?)",(run_id,kind,subject_hash,note,time.time()))
            return dict(c.execute("SELECT * FROM approvals WHERE run_id=? AND kind=? AND subject_hash IS ?",(run_id,kind,subject_hash)).fetchone())
    def decide_approval(self,run_id,kind,subject_hash,state,actor,note=None):
        if state not in {"approved","rejected"}: raise ValueError("state must be approved or rejected")
        with self._lock,self._connect() as c:
            cur=c.execute("UPDATE approvals SET state=?,actor=?,note=COALESCE(?,note),decided=? WHERE run_id=? AND kind=? AND subject_hash IS ? AND state='pending'",
                          (state,actor,note,time.time(),run_id,kind,subject_hash))
            return cur.rowcount>0
    def approval_state(self,run_id,kind,subject_hash):
        with self._connect() as c:
            r=c.execute("SELECT state FROM approvals WHERE run_id=? AND kind=? AND subject_hash IS ?",(run_id,kind,subject_hash)).fetchone()
            return r[0] if r else None
    def pending_approvals(self):
        with self._connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM approvals WHERE state='pending' ORDER BY created")]

    # --- jobs ---------------------------------------------------------
    def create_job(self,job_id,run_id,kind,argv,cwd,log_path,fingerprint,timeout_s):
        with self._lock,self._connect() as c:
            c.execute("INSERT INTO jobs(job_id,run_id,kind,argv,cwd,state,log_path,fingerprint,timeout_s,created) VALUES(?,?,?,?,?,'pending',?,?,?,?)",
                      (job_id,run_id,kind,json.dumps(argv),str(cwd),str(log_path),fingerprint,timeout_s,time.time()))
    def start_job(self,job_id,pid):
        now=time.time()
        with self._lock,self._connect() as c:
            c.execute("UPDATE jobs SET pid=?,state='running',started=?,heartbeat=? WHERE job_id=?",(pid,now,now,job_id))
    def heartbeat_job(self,job_id):
        with self._lock,self._connect() as c: c.execute("UPDATE jobs SET heartbeat=? WHERE job_id=?",(time.time(),job_id))
    def finish_job(self,job_id,state,exit_code,result_hash=None):
        now=time.time()
        with self._lock,self._connect() as c:
            cur=c.execute("UPDATE jobs SET state=?,exit_code=?,result_hash=?,finished=? WHERE job_id=? AND state IN ('pending','running')",
                          (state,exit_code,result_hash,now,job_id))
            if not cur.rowcount: return False
            row=c.execute("SELECT fingerprint,started,cwd FROM jobs WHERE job_id=?",(job_id,)).fetchone()
            if row and row[1]:
                import platform as _p
                c.execute("INSERT INTO job_history(fingerprint,repo,platform,duration_s,exit_code,created) VALUES(?,?,?,?,?,?)",
                          (row[0],row[2],_p.system(),max(0.0,now-row[1]),exit_code if exit_code is not None else -1,now))
            return True
    def get_job(self,job_id):
        with self._connect() as c:
            r=c.execute("SELECT * FROM jobs WHERE job_id=?",(job_id,)).fetchone()
            if not r: raise KeyError(job_id)
            return dict(r)
    def jobs(self,run_id=None,active_only=False):
        q="SELECT * FROM jobs"; args=[]; where=[]
        if run_id: where.append("run_id=?"); args.append(run_id)
        if active_only: where.append("state IN ('pending','running')")
        if where: q+=" WHERE "+" AND ".join(where)
        with self._connect() as c:
            return [dict(r) for r in c.execute(q+" ORDER BY created DESC",args)]
    def duration_estimate(self,fingerprint):
        with self._connect() as c:
            rows=[r[0] for r in c.execute("SELECT duration_s FROM job_history WHERE fingerprint=? ORDER BY created DESC LIMIT 20",(fingerprint,))]
        if not rows: return None
        s=sorted(rows)
        def pct(p):
            i=min(len(s)-1,max(0,int(round((len(s)-1)*p)))); return s[i]
        return {"samples":len(s),"p50":pct(0.5),"p90":pct(0.9),"max":s[-1]}

    # --- spend --------------------------------------------------------
    def add_spend(self,day,tokens,usd):
        with self._lock,self._connect() as c:
            c.execute("INSERT INTO spend(day,tokens,est_usd) VALUES(?,?,?) ON CONFLICT(day) DO UPDATE SET tokens=tokens+excluded.tokens,est_usd=est_usd+excluded.est_usd",(day,tokens,usd))
    def spend(self,day):
        with self._connect() as c:
            r=c.execute("SELECT tokens,est_usd FROM spend WHERE day=?",(day,)).fetchone()
            return {"tokens":r[0],"est_usd":r[1]} if r else {"tokens":0,"est_usd":0.0}

    # --- evolution ----------------------------------------------------
    def add_candidate(self,candidate_id,kind,target,diff,rationale,provenance):
        with self._lock,self._connect() as c:
            c.execute("INSERT OR IGNORE INTO candidates(candidate_id,kind,target,diff,rationale,state,provenance,created) VALUES(?,?,?,?,?,'proposed',?,?)",
                      (candidate_id,kind,target,diff,rationale,provenance,time.time()))
    def set_candidate_state(self,candidate_id,state):
        with self._lock,self._connect() as c:
            c.execute("UPDATE candidates SET state=?,decided=? WHERE candidate_id=?",(state,time.time(),candidate_id))
    def candidates(self,state=None):
        q="SELECT * FROM candidates"; a=[]
        if state: q+=" WHERE state=?"; a.append(state)
        with self._connect() as c:
            return [dict(r) for r in c.execute(q+" ORDER BY created DESC",a)]
    def add_evaluation(self,candidate_id,kind,verdict,detail):
        with self._lock,self._connect() as c:
            c.execute("INSERT INTO evaluations(candidate_id,kind,verdict,detail,created) VALUES(?,?,?,?,?)",(candidate_id,kind,verdict,json.dumps(detail,sort_keys=True)[:8000],time.time()))
    def evaluations(self,candidate_id):
        with self._connect() as c:
            return [dict(r) for r in c.execute("SELECT * FROM evaluations WHERE candidate_id=? ORDER BY created",(candidate_id,))]
