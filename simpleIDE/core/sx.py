#!/usr/bin/env python3
"""simpleIDE commands and memory. Standard library only.

Two SQLite files:
  <project>/.simpleide/project.db   everything recorded for this project
  ~/.simpleide/shared.db            lessons shared across every project

Search is FTS5 + BM25 (falls back to LIKE if this Python's SQLite has no FTS5).
Run `python3 sx.py -h` for commands.
"""
import argparse
import ast
from contextlib import contextmanager
import math
import fnmatch
import hashlib
import json
import os
import re
import shlex
import sqlite3
import socket
import subprocess
import sys
import time
import tempfile
import shutil
import uuid
from pathlib import Path

KINDS = ("request", "goal", "criteria", "assumption", "question", "decision",
         "finding", "test", "result", "lesson", "note")
EXPORT_ORDER = (("request", "Requests (primary identified above)"), ("goal", "Goal"), ("criteria", "Acceptance criteria"),
                ("assumption", "Assumptions"), ("question", "Open questions"),
                ("decision", "Decisions"), ("finding", "Findings"),
                ("test", "Tests"), ("result", "Result"),
                ("lesson", "Lessons"), ("note", "Notes"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS rec(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  uid TEXT UNIQUE,
  ts TEXT NOT NULL,
  kind TEXT NOT NULL,
  task TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '',
  refs TEXT NOT NULL DEFAULT '',
  project TEXT NOT NULL DEFAULT '',
  shared INTEGER NOT NULL DEFAULT 0   -- 0 local only, 1 waiting to sync, 2 synced
  ,uses INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS rec_kind ON rec(kind);
CREATE INDEX IF NOT EXISTS rec_task ON rec(task);
CREATE TABLE IF NOT EXISTS run(
 task TEXT PRIMARY KEY, size TEXT NOT NULL DEFAULT '', tool TEXT NOT NULL DEFAULT '',
 start TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, end TEXT, outcome TEXT NOT NULL DEFAULT '',
 repair_rounds INTEGER NOT NULL DEFAULT 0, tokens INTEGER, cost REAL,
 check_failures INTEGER NOT NULL DEFAULT 0, stop_warned INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS dispatch(
 id INTEGER PRIMARY KEY, task TEXT NOT NULL, agent TEXT NOT NULL, model TEXT NOT NULL DEFAULT '',
 brief_length INTEGER NOT NULL DEFAULT 0, ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 return_status TEXT NOT NULL DEFAULT '', host TEXT NOT NULL DEFAULT '',
 session_id TEXT NOT NULL DEFAULT '', child_id TEXT NOT NULL DEFAULT '',
 tool_call_id TEXT NOT NULL DEFAULT '', brief_hash TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS search_log(
 id INTEGER PRIMARY KEY, query TEXT NOT NULL, hit_count INTEGER NOT NULL,
 opened INTEGER NOT NULL DEFAULT 0, hits TEXT NOT NULL DEFAULT '[]',
 ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS rec_fts USING fts5(
  title, body, tags, content='rec', content_rowid='id', tokenize='porter unicode61');
CREATE TRIGGER IF NOT EXISTS rec_ai AFTER INSERT ON rec BEGIN
  INSERT INTO rec_fts(rowid, title, body, tags) VALUES (new.id, new.title, new.body, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS rec_ad AFTER DELETE ON rec BEGIN
  INSERT INTO rec_fts(rec_fts, rowid, title, body, tags)
  VALUES ('delete', old.id, old.title, old.body, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS rec_au AFTER UPDATE OF title,body,tags ON rec BEGIN
  INSERT INTO rec_fts(rec_fts,rowid,title,body,tags) VALUES('delete',old.id,old.title,old.body,old.tags);
  INSERT INTO rec_fts(rowid,title,body,tags) VALUES(new.id,new.title,new.body,new.tags);
END;
"""


def project_root():
    env = os.environ.get("SIMPLEIDE_PROJECT")
    if env:
        return Path(env).resolve()
    here = Path.cwd().resolve()
    home = Path.home().resolve()
    for d in (here, *here.parents):
        if d != home and (d / ".simpleide").is_dir():
            return d
    for d in (here, *here.parents):
        if (d / ".git").exists():
            return d
    return here


def linked_worktree(root):
    r = subprocess.run(["git", "rev-parse", "--git-dir", "--git-common-dir"], cwd=root,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return False
    lines = [line.strip() for line in r.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    git_dir = (Path(root) / lines[0]).resolve()
    common_dir = (Path(root) / lines[1]).resolve()
    return git_dir != common_dir


def standalone_marker(root):
    r = subprocess.run(["git", "rev-parse", "--git-path", "simpleide-standalone"], cwd=root,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return (Path(root) / ".git/simpleide-standalone").resolve()
    p = Path(r.stdout.strip())
    return p if p.is_absolute() else (Path(root) / p).resolve()


def store_root(root):
    explicit = os.environ.get("SIMPLEIDE_STORE")
    pointer = root / ".simpleide/context.json"
    if not explicit and not pointer.exists():
        if linked_worktree(root) and not standalone_marker(root).exists():
            raise ValueError("this is a Git linked worktree with no simpleIDE context; from the parent "
                             "checkout run: sx worktree reconcile <task> --apply, or declare it independent "
                             "with: sx context standalone")
        return root
    data = json.loads(pointer.read_text()) if pointer.exists() and not explicit else {}
    value = explicit or data.get("store_root")
    if not isinstance(value, str) or not value:
        raise ValueError("invalid worktree context; restore the parent store pointer")
    target = Path(value).expanduser().resolve()
    db = target / ".simpleide/project.db"
    if not db.is_file():
        raise ValueError("parent store is missing: " + str(db) + "; repair context explicitly")
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as c:
        identity = c.execute("SELECT value FROM meta WHERE key='store_id'").fetchone()
    if not identity or not explicit and identity[0] != data.get("store_id"):
        raise ValueError("worktree store ID mismatch; refusing a different ledger")
    return target


def ledger(root):
    return connect(store_root(root) / ".simpleide/project.db")


def identity(con):
    return con.execute("SELECT value FROM meta WHERE key='store_id'").fetchone()[0]


def task_artifact(con, root, task):
    run = con.execute("SELECT request_id FROM run WHERE task=?", (task,)).fetchone()
    request_id = run["request_id"] if run else None
    rows = con.execute("SELECT * FROM rec WHERE task=? AND (kind IN ('goal','criteria') OR id=?) ORDER BY id", (task,request_id)).fetchall()
    body = "\n\n".join("## P%d %s: %s\n%s" % (r["id"],r["kind"],r["title"],r["body"]) for r in rows)
    digest = hashlib.sha256(body.encode()).hexdigest()
    directory = store_root(root) / ".simpleide/artifacts" / task
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ("request-" + digest + ".md")
    text = "# Task " + task + "\nStore: " + identity(con) + "\nLocation: " + str(store_root(root)) + "\nContent SHA256: " + digest + "\n\n" + body
    if not path.exists() or path.read_text() != text:
        fd, temporary = tempfile.mkstemp(prefix=".request-", dir=directory)
        try:
            with os.fdopen(fd,"w") as f: f.write(text)
            os.replace(temporary,path)
        finally:
            if Path(temporary).exists(): Path(temporary).unlink()
    return path


def shared_path():
    return Path(os.environ.get("SIMPLEIDE_HOME") or Path.home() / ".simpleide") / "shared.db"


SCHEMA_VERSION = 1


def sql_script(con, script):
    # executescript commits implicitly; execute complete statements inside our transaction.
    statement = ""
    for line in script.splitlines(True):
        statement += line
        if sqlite3.complete_statement(statement):
            con.execute(statement)
            statement = ""
    if statement.strip():
        con.execute(statement)


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=30)
    con.row_factory = sqlite3.Row
    try:
        with con:
            con.execute("BEGIN IMMEDIATE")
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError("store schema is newer than this runtime")
            if version < SCHEMA_VERSION:
                if tables:
                    backup = path.with_name(path.name + ".pre-v%d-%s.bak" % (SCHEMA_VERSION, uuid.uuid4().hex))
                    source = sqlite3.connect(str(path), timeout=30)
                    dest = sqlite3.connect(str(backup))
                    try:
                        source.backup(dest)
                    finally:
                        source.close(); dest.close()
                if "rec" in tables:
                    for trigger in ("rec_ai", "rec_ad", "rec_au"):
                        con.execute("DROP TRIGGER IF EXISTS " + trigger)
                    con.execute("DROP TABLE IF EXISTS rec_fts")
                    old_columns = [r[1] for r in con.execute("PRAGMA table_info(rec)")]
                    con.execute("ALTER TABLE rec RENAME TO rec_legacy")
                    sql_script(con, SCHEMA[:SCHEMA.index("CREATE INDEX")])
                    columns = ",".join(old_columns)
                    con.execute("INSERT INTO rec(" + columns + ") SELECT " + columns + " FROM rec_legacy")
                    con.execute("DROP TABLE rec_legacy")
                sql_script(con, SCHEMA)
                additions = {
                    "rec": {"uses": "INTEGER NOT NULL DEFAULT 0", "host": "TEXT NOT NULL DEFAULT ''",
                            "session_id": "TEXT NOT NULL DEFAULT ''", "resolved_by": "INTEGER"},
                    "run": {"request_id": "INTEGER", "retry_of": "TEXT", "provenance": "TEXT NOT NULL DEFAULT ''",
                            "actor": "TEXT", "result_id": "INTEGER", "outcome_refs": "TEXT", "usage_source": "TEXT"},
                    "dispatch": {**{n: "TEXT NOT NULL DEFAULT ''" for n in
                                   ("host", "session_id", "child_id", "tool_call_id", "brief_hash", "requested_model")},
                                 "state": "TEXT NOT NULL DEFAULT 'unknown'", "observed_launch": "INTEGER NOT NULL DEFAULT 0"},
                    "search_log": {"hits": "TEXT NOT NULL DEFAULT '[]'", "context": "TEXT NOT NULL DEFAULT ''"}}
                for table, columns in additions.items():
                    existing = {r[1] for r in con.execute("PRAGMA table_info(" + table + ")")}
                    for name, definition in columns.items():
                        if name not in existing:
                            con.execute("ALTER TABLE " + table + " ADD COLUMN " + name + " " + definition)
                sql_script(con, """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE session(host TEXT, session_id TEXT, task TEXT NOT NULL, request_id INTEGER,
 PRIMARY KEY(host,session_id));
CREATE TABLE binding_log(id INTEGER PRIMARY KEY, host TEXT, session_id TEXT, task TEXT, request_id INTEGER,
 ts TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE check_obs(id INTEGER PRIMARY KEY, record_id INTEGER, task TEXT, name TEXT, command TEXT,
 config_hash TEXT, execution_root TEXT, before_hash TEXT, after_hash TEXT, exit_code INTEGER,
 duration REAL, artifact TEXT);
CREATE TABLE worktree(id INTEGER PRIMARY KEY, task TEXT, piece TEXT, path TEXT UNIQUE, branch TEXT,
 base_commit TEXT, state TEXT, diagnostic TEXT DEFAULT '', UNIQUE(task,piece));
CREATE TABLE search_open(search_id INTEGER, ident TEXT, PRIMARY KEY(search_id,ident));
CREATE TABLE hook_observation(id INTEGER PRIMARY KEY, host TEXT, session_id TEXT, event TEXT, detail TEXT,
 ts TEXT DEFAULT CURRENT_TIMESTAMP);
""")
                con.execute("INSERT INTO meta VALUES('store_id',?)", (uuid.uuid4().hex,))
                con.execute("INSERT INTO meta VALUES('migration',?)", (time.strftime("%Y-%m-%d %H:%M:%S"),))
                con.execute("UPDATE run SET provenance='legacy-unverified' WHERE outcome<>''")
                con.execute("PRAGMA user_version=" + str(SCHEMA_VERSION))
            # A fallback-only ledger may gain FTS on a later interpreter, at the same schema version.
            existed = has_fts(con)
            try:
                sql_script(con, FTS)
                if not existed:
                    con.execute("INSERT INTO rec_fts(rec_fts) VALUES('rebuild')")
            except sqlite3.OperationalError as err:
                if "no such module: fts5" not in str(err):
                    raise
        return con
    except Exception:
        con.close()
        raise


def has_fts(con):
    return con.execute("SELECT 1 FROM sqlite_master WHERE name='rec_fts'").fetchone() is not None


def norm(s):
    return re.sub(r"\s+", " ", s.strip().lower())


@contextmanager
def transaction(con):
    if con.in_transaction:
        yield
    else:
        with con:
            con.execute("BEGIN IMMEDIATE")
            yield


def insert(con, kind, title, body="", task="", tags="", refs="", project="", shared=0, ts=None, host="", session="", request=None, retry_of=None):
    """Insert one record. Returns (id, created)."""
    scope = "" if kind == "lesson" else task
    uid = hashlib.sha1("|".join((kind, scope, norm(title), norm(body))).encode()).hexdigest()[:16]
    if kind in ("request", "test"):
        # These are events: equal contents on different runs are distinct evidence.
        uid = uuid.uuid4().hex
    with transaction(con):
        if kind == "goal" and task:
            old = con.execute("SELECT outcome FROM run WHERE task=?", (task,)).fetchone()
            if old and old["outcome"]:
                raise ValueError("terminal task slug is immutable; use a new slug with --retry-of")
        cur = con.execute(
            "INSERT OR IGNORE INTO rec(uid,ts,kind,task,title,body,tags,refs,project,shared) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (uid, ts or time.strftime("%Y-%m-%d %H:%M"), kind, task, title.strip(), body if kind == "request" else body.strip(),
             tags.strip(), refs.strip(), project, shared))
        row = con.execute("SELECT id FROM rec WHERE uid=?", (uid,)).fetchone()
        if kind == "request":
            con.execute("UPDATE rec SET host=?,session_id=? WHERE id=?", (host, session, row["id"]))
        if shared:
            con.execute("UPDATE rec SET shared=1 WHERE id=? AND shared=0", (row["id"],))
        if kind == "goal" and task:
            con.execute("INSERT OR IGNORE INTO run(task) VALUES(?)", (task,))
            if retry_of:
                if retry_of == task or not con.execute("SELECT 1 FROM run WHERE task=? AND outcome<>''", (retry_of,)).fetchone():
                    raise ValueError("--retry-of requires a different terminal task")
                con.execute("UPDATE run SET retry_of=? WHERE task=?", (retry_of, task))
            if request:
                bind_task(con, task, request)
    return row["id"], bool(cur.rowcount)


def bind_task(con, task, request=None, host=None, session=None):
    validate_slug(task)
    run = con.execute("SELECT * FROM run WHERE task=?", (task,)).fetchone()
    if not run or run["outcome"]:
        raise ValueError("binding requires an existing open task")
    rid = None
    if request:
        rid = record_number(request, "P")
        r = con.execute("SELECT * FROM rec WHERE id=? AND kind='request'", (rid,)).fetchone()
        if not r or (r["task"] and r["task"] != task):
            raise ValueError("request is missing or belongs to another task")
        if host and r["host"] and host != r["host"] or session and r["session_id"] and session != r["session_id"]:
            raise ValueError("request identity conflicts with binding")
        host, session = host or r["host"], session or r["session_id"]
    if not host or not session:
        raise ValueError("binding needs captured request identity or explicit --host and --session")
    con.execute("INSERT INTO session VALUES(?,?,?,?) ON CONFLICT(host,session_id) DO UPDATE SET task=excluded.task,request_id=excluded.request_id",
                (host, session, task, rid))
    con.execute("INSERT INTO binding_log(host,session_id,task,request_id) VALUES(?,?,?,?)", (host, session, task, rid))
    if rid:
        con.execute("UPDATE rec SET task=? WHERE id=?", (task, rid))
        con.execute("UPDATE run SET request_id=? WHERE task=?", (rid, task))


def selected_task(con, root, explicit="", host="", session=""):
    context_task = ""
    context = root / ".simpleide/context.json"
    if context.exists():
        context_task = json.loads(context.read_text()).get("task", "")
    binding = con.execute("SELECT task FROM session WHERE host=? AND session_id=?", (host, session)).fetchone() if session else None
    choices = {t for t in (explicit, context_task, binding["task"] if binding else "") if t}
    if len(choices) > 1:
        raise ValueError("task conflicts with execution context or session binding; bind deliberately first")
    task = next(iter(choices), "")
    if task:
        validate_slug(task)
        if not con.execute("SELECT 1 FROM run WHERE task=?", (task,)).fetchone():
            raise ValueError("unknown task: " + task)
    return task


def brief_sections(brief):
    headings = r"GOAL|CONTEXT|DO NOT TOUCH|DO|DONE WHEN|RETURN|TASK|REPAIR ROUND"
    matches = list(re.finditer(r"(?im)^[ \t]*(" + headings + r")(?:[ \t]*:[ \t]*|[ \t]*$)", brief))
    return {m[1].upper(): brief[m.end():matches[i+1].start() if i+1<len(matches) else len(brief)].strip()
            for i, m in enumerate(matches)}


def sync(pcon):
    """Copy lessons waiting in the project db into the shared db. Returns count."""
    rows = pcon.execute("SELECT * FROM rec WHERE shared=1").fetchall()
    if not rows:
        return 0
    scon = connect(shared_path())
    for r in rows:
        insert(scon, r["kind"], r["title"], r["body"], r["task"], r["tags"], r["refs"],
               r["project"], 2, r["ts"])
        pcon.execute("UPDATE rec SET shared=2 WHERE id=?", (r["id"],))
    pcon.commit()
    scon.close()
    return len(rows)


def search(con, query, kind=None, limit=5):
    toks = re.findall(r"[\w][\w./-]*", query)
    if not toks:
        return []
    kindsql, kindarg = (" AND r.kind=?", [kind]) if kind else ("", [])
    if has_fts(con):
        match = " OR ".join('"%s"' % t.replace('"', "") for t in toks)
        try:
            return con.execute(
                "SELECT r.* FROM rec_fts JOIN rec r ON r.id=rec_fts.rowid "
                "WHERE rec_fts MATCH ?" + kindsql +
                " ORDER BY bm25(rec_fts, 3.0, 1.0, 2.0) LIMIT ?",
                [match, *kindarg, limit]).fetchall()
        except sqlite3.OperationalError:
            raise
    like = " OR ".join("(r.title LIKE ? OR r.body LIKE ? OR r.tags LIKE ?)" for _ in toks)
    args = [a for t in toks for a in ("%" + t + "%",) * 3]
    return con.execute("SELECT r.* FROM rec r WHERE (" + like + ")" + kindsql +
                       " ORDER BY r.id DESC LIMIT ?", [*args, *kindarg, limit]).fetchall()


def line(prefix, r, width=160):
    body = re.sub(r"\s+", " ", r["body"])
    if len(body) > width:
        body = body[:width - 1] + "…"
    bits = ["%s%d" % (prefix, r["id"]), r["kind"], r["ts"][:10]]
    if r["task"]:
        bits.append("task=" + r["task"])
    if r["tags"]:
        bits.append("[" + r["tags"] + "]")
    if prefix == "S" and r["project"]:
        bits.append("from=" + r["project"])
    return " ".join(bits) + " | " + r["title"] + (" :: " + body if body else "")


def record_number(ident, prefix=None):
    if not isinstance(ident, str) or not re.fullmatch(r"[PSps][1-9][0-9]{0,17}", ident):
        raise ValueError("record ID must be P<number> or S<number>")
    if prefix and ident[0].upper() != prefix:
        raise ValueError("expected " + prefix + " record in this store")
    return int(ident[1:])


def read_body(v):
    return sys.stdin.read() if v == "-" else (v or "")


def mem_main(argv=None):
    p = argparse.ArgumentParser(prog="mem.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="record something for this project")
    a.add_argument("kind", choices=KINDS)
    a.add_argument("title")
    a.add_argument("--body", default="", help="text, or - to read stdin")
    a.add_argument("--task", default="", help="short task slug, e.g. login-fix")
    a.add_argument("--tags", default="")
    a.add_argument("--refs", default="", help="paths, ids, urls the record rests on")
    a.add_argument("--request", help="captured primary P record with host/session identity")
    a.add_argument("--retry-of")
    a.add_argument("--size", choices=("SMALL", "MEDIUM", "LARGE"), help="task size when adding a goal")

    l = sub.add_parser("lesson", help="record a reusable lesson (project + shared)")
    l.add_argument("title")
    l.add_argument("--body", default="")
    l.add_argument("--task", default="")
    l.add_argument("--tags", default="")
    l.add_argument("--refs", default="")
    l.add_argument("--local", action="store_true", help="keep it in this project only")

    s = sub.add_parser("search", help="ranked search of project and shared memory")
    s.add_argument("query")
    s.add_argument("--kind", choices=KINDS)
    s.add_argument("--scope", choices=("all", "project", "shared"), default="all")
    s.add_argument("--limit", type=int, default=5)

    sh = sub.add_parser("show", help="print full records, e.g. show P12 S3")
    sh.add_argument("ids", nargs="+")
    sh.add_argument("--search-id", type=int)
    for parser in (sh, s):
        parser.add_argument("--host", default=os.environ.get("SIMPLEIDE_HOST", ""))
        parser.add_argument("--session", default=os.environ.get("SIMPLEIDE_SESSION", ""))

    r = sub.add_parser("recent", help="latest project records")
    r.add_argument("--kind", choices=KINDS)
    r.add_argument("--task")
    r.add_argument("--limit", type=int, default=10)

    e = sub.add_parser("export", help="write a readable Markdown record from stored entries")
    e.add_argument("--task")
    e.add_argument("--out", help="file to write (default: print)")

    f = sub.add_parser("forget", help="delete records that turned out wrong, e.g. forget P12 S3")
    f.add_argument("ids", nargs="+")

    resolve = sub.add_parser("resolve", help="explicitly resolve a question with its decision")
    resolve.add_argument("question"); resolve.add_argument("--decision", required=True)
    sub.add_parser("sync", help="push lessons that could not reach the shared db earlier")
    sub.add_parser("stats", help="where the databases are and what is in them")
    sub.add_parser("prune", help="list unused lessons older than 90 days")

    args = p.parse_args(argv)
    root = project_root()
    ppath = store_root(root) / ".simpleide" / "project.db"

    def pdb():
        return connect(ppath)

    def sdb():
        return connect(shared_path())

    if args.cmd in ("add", "lesson"):
        if args.cmd == "add" and args.kind != "goal" and (args.request or args.retry_of):
            raise ValueError("--request and --retry-of apply only to goals")
        if args.task: validate_slug(args.task)
        kind = "lesson" if args.cmd == "lesson" else args.kind
        share = 1 if (args.cmd == "lesson" and not args.local) else 0
        con = pdb()
        rid, created = insert(con, kind, args.title, read_body(args.body), args.task,
                              args.tags, args.refs, root.name, share,
                              request=getattr(args, "request", None), retry_of=getattr(args, "retry_of", None))
        if args.cmd == "add" and kind == "goal" and args.task and args.size:
            con.execute("UPDATE run SET size=? WHERE task=?", (args.size, args.task))
            con.commit()
        msg = "P%d %s %s" % (rid, kind, "saved" if created else "already recorded")
        if share:
            try:
                sync(con)
                state = con.execute("SELECT shared FROM rec WHERE id=?",(rid,)).fetchone()[0]
                msg += " + shared (synced)" if state == 2 else " (queued)"
            except (sqlite3.Error, OSError) as err:
                msg += " (shared db not writable now: %s; queued, run `sync` later)" % err
        print(msg)
        if kind == "goal" and not getattr(args, "request", None):
            print("Unbound task; use sx task bind " + args.task + " --request Pn (or --host HOST --session ID).")

    elif args.cmd == "search":
        if not 1 <= args.limit <= 100:
            raise ValueError("search limit must be 1..100 (total displayed hits)")
        candidates, local_uids = [], set()
        if ppath.exists():
            local_uids = {r[0] for r in pdb().execute("SELECT uid FROM rec")}
        if args.scope in ("all", "project") and ppath.exists():
            candidates += [("P",r) for r in search(pdb(),args.query,args.kind,-1)]
        if args.scope in ("all", "shared") and shared_path().exists():
            # SQL/FTS corruption is surfaced. An unavailable shared file is a diagnostic.
            try:
                rows = search(sdb(),args.query,args.kind,-1)
                candidates += [("S",r) for r in rows if args.scope == "shared" or r["uid"] not in local_uids]
            except OSError as err:
                print("shared search unavailable: " + str(err),file=sys.stderr)
        displayed = candidates[:args.limit]
        print("\n".join(line(prefix,r) for prefix,r in displayed) if displayed else "no matches")
        con = pdb()
        context = json.dumps([args.host,args.session])
        hit_ids = [prefix+str(r["id"]) for prefix,r in displayed]
        with con:
            search_id = con.execute("INSERT INTO search_log(query,hit_count,hits,context) VALUES(?,?,?,?)", (args.query,len(displayed),json.dumps(hit_ids),context)).lastrowid
        print("search_id=" + str(search_id) + "; limit is total displayed hits")

    elif args.cmd == "show":
        for ident in args.ids:
            con = sdb() if ident[:1].upper() == "S" else pdb()
            r = con.execute("SELECT * FROM rec WHERE id=?", (record_number(ident),)).fetchone()
            if not r:
                print("%s: not found" % ident)
                continue
            log = pdb()
            context = json.dumps([args.host,args.session])
            searches = log.execute("SELECT * FROM search_log WHERE context=?" + (" AND id=?" if args.search_id is not None else ""),
                                   (context,args.search_id) if args.search_id is not None else (context,)).fetchall()
            matches = [row for row in searches if ident.upper() in json.loads(row["hits"])]
            if len(matches) == 1 and (args.search_id is not None or (args.host and args.session)):
                with transaction(log):
                    created = log.execute("INSERT OR IGNORE INTO search_open VALUES(?,?)", (matches[0]["id"],ident.upper())).rowcount
                    log.execute("UPDATE search_log SET opened=1 WHERE id=?", (matches[0]["id"],))
                    if created and r["kind"] == "lesson" and ident[0].upper() == "P":
                        log.execute("UPDATE rec SET uses=uses+1 WHERE id=?", (r["id"],))
                if created and r["kind"] == "lesson" and ident[0].upper() == "S":
                    with con: con.execute("UPDATE rec SET uses=uses+1 WHERE id=?",(r["id"],))
            print("%s %s %s task=%s tags=%s project=%s\n%s\n%s\nrefs: %s\n" % (
                ident.upper(), r["kind"], r["ts"], r["task"] or "-", r["tags"] or "-",
                r["project"] or "-", r["title"], r["body"], r["refs"] or "-"))

    elif args.cmd == "recent":
        q, a2 = "SELECT * FROM rec WHERE 1=1", []
        if args.kind:
            q, a2 = q + " AND kind=?", a2 + [args.kind]
        if args.task:
            q, a2 = q + " AND task=?", a2 + [args.task]
        rows = pdb().execute(q + " ORDER BY id DESC LIMIT ?", a2 + [args.limit]).fetchall()
        print("\n".join(line("P", r) for r in rows) if rows else "nothing recorded yet")

    elif args.cmd == "export":
        q, a2 = "SELECT * FROM rec", []
        if args.task:
            q, a2 = q + " WHERE task=?", [args.task]
        rows = pdb().execute(q + " ORDER BY id", a2).fetchall()
        con = pdb()
        md = ["# %s — work record" % (args.task or root.name), "",
              "Store: " + identity(con) + "; location: " + str(ppath), ""]
        runs = con.execute("SELECT * FROM run" + (" WHERE task=?" if args.task else ""), (args.task,) if args.task else ()).fetchall()
        for run in runs:
            md += ["Task: " + run["task"], "Primary request: " + ("P%d" % run["request_id"] if run["request_id"] else "unavailable"),
                   "Outcome: " + (run["outcome"] or "open") + "; provenance=" + run["provenance"] + "; actor=" + str(run["actor"]) + "; refs=" + str(run["outcome_refs"]),
                   "Current checks: " + (" | ".join(check_summary(con,root,run["task"])) or "none configured"), ""]
        observations = con.execute("SELECT * FROM check_obs" + (" WHERE task=?" if args.task else "") + " ORDER BY id", (args.task,) if args.task else ()).fetchall()
        if observations:
            md += ["## Historical check observations", "", *["- " + json.dumps(dict(r)) for r in observations], ""]
        for kind, head in EXPORT_ORDER:
            items = [r for r in rows if r["kind"] == kind]
            if not items:
                continue
            md += ["## " + head, ""]
            for r in items:
                if kind == "question":
                    md.append("  " + ("resolved by P%d" % r["resolved_by"] if r["resolved_by"] else "open/unresolved"))
                md.append("- **%s**%s%s _(%s, P%d)_" % (
                    r["title"], " — " + r["body"] if r["body"] else "",
                    " Refs: " + r["refs"] + "." if r["refs"] else "", r["ts"], r["id"]))
            md.append("")
        text = "\n".join(md)
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            print("wrote %s (%d records)" % (out, len(rows)))
        else:
            print(text)

    elif args.cmd == "forget":
        for ident in args.ids:
            con = sdb() if ident[:1].upper() == "S" else pdb()
            number = record_number(ident)
            if con.execute("SELECT 1 FROM run WHERE request_id=? OR result_id=? UNION ALL SELECT 1 FROM rec WHERE resolved_by=? UNION ALL SELECT 1 FROM check_obs WHERE record_id=? LIMIT 1", (number,number,number,number)).fetchone():
                raise ValueError("record supports a durable association; retain it and record a correction")
            n = con.execute("DELETE FROM rec WHERE id=?", (number,)).rowcount
            con.commit()
            print("%s %s" % (ident.upper(), "deleted" if n else "not found"))

    elif args.cmd == "resolve":
        con = pdb()
        question, decision = record_number(args.question,"P"), record_number(args.decision,"P")
        with transaction(con):
            q = con.execute("SELECT * FROM rec WHERE id=? AND kind='question'",(question,)).fetchone()
            d = con.execute("SELECT * FROM rec WHERE id=? AND kind='decision'",(decision,)).fetchone()
            if not q or not d or not q["task"] or q["task"] != d["task"]:
                raise ValueError("question and decision must exist in the same task")
            if q["resolved_by"] and q["resolved_by"] != decision:
                raise ValueError("question already resolved by another decision")
            con.execute("UPDATE rec SET resolved_by=? WHERE id=?",(decision,question))
        print(args.question + " resolved by " + args.decision)

    elif args.cmd == "sync":
        try:
            print("synced %d lesson(s) to %s" % (sync(pdb()), shared_path()))
        except (sqlite3.Error, OSError) as err:
            print("shared db not writable: %s" % err)
            return 1

    elif args.cmd == "stats":
        for name, path in (("project", ppath), ("shared", shared_path())):
            if not path.exists():
                print("%s: %s (not created yet)" % (name, path))
                continue
            con = connect(path)
            counts = con.execute("SELECT kind, COUNT(*) n FROM rec GROUP BY kind ORDER BY n DESC").fetchall()
            print("%s: %s fts5=%s %s" % (name, path, "yes" if has_fts(con) else "no",
                                         ", ".join("%s=%d" % (c["kind"], c["n"]) for c in counts) or "empty"))
            if name == "project":
                pend = con.execute("SELECT COUNT(*) FROM rec WHERE shared=1").fetchone()[0]
                if pend:
                    print("  %d lesson(s) waiting for `sync`" % pend)
    elif args.cmd == "prune":
        for prefix, path in (("P", ppath), ("S", shared_path())):
            if not path.exists():
                continue
            rows = connect(path).execute(
                "SELECT * FROM rec WHERE kind='lesson' AND uses=0 "
                "AND datetime(ts) < datetime('now','-90 days') ORDER BY id").fetchall()
            for row in rows:
                print(line(prefix, row))
    return 0


def git(root, *args, check=True):
    p = subprocess.run(["git", *args], cwd=root, capture_output=True)
    p.stdout = p.stdout.decode("utf-8", "surrogateescape")
    p.stderr = p.stderr.decode("utf-8", "surrogateescape")
    if check and p.returncode:
        raise ValueError(p.stderr.strip() or "git command failed")
    return p


def changed(root, base):
    files = set(git(root, "diff", "--name-only", "-z", base, "--").stdout.rstrip("\0").split("\0"))
    files.update(git(root, "ls-files", "-z", "--others", "--exclude-standard").stdout.rstrip("\0").split("\0"))
    return sorted(files - {""})


def proposed_checks(root):
    checks = {}
    if (root / "pyproject.toml").exists():
        checks["test"] = "python3 -m pytest -q"
    if (root / "package.json").exists():
        try:
            scripts = json.loads((root / "package.json").read_text()).get("scripts", {})
            for key in ("test", "lint", "typecheck"):
                if key in scripts:
                    checks[key] = "npm run " + key
        except (ValueError, OSError):
            pass
    if (root / "Cargo.toml").exists():
        checks["test"] = "cargo test"
    if (root / "go.mod").exists():
        checks["test"] = "go test ./..."
    return checks


def validate_slug(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value):
        raise ValueError("task slug must contain only letters, digits, hyphens or underscores")


def check_config(root):
    path = root / ".simpleide/config.json"
    if not path.exists():
        return None
    cfg = json.loads(path.read_text())
    if not isinstance(cfg, dict) or not isinstance(cfg.get("checks"), dict):
        raise ValueError("config must contain a checks object")
    for name, command in cfg["checks"].items():
        validate_slug(name)
        if not isinstance(command, str) or not command.strip():
            raise ValueError("invalid check command: " + name)
    return cfg


def config_hash(cfg):
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()


def revision(root, depth=0):
    if depth > 5:
        return None
    head = git(root, "rev-parse", "HEAD", check=False)
    if head.returncode:
        return None
    digest = hashlib.sha256(b"git-source-v2\0" + head.stdout.encode())
    tracked = set()
    submodules = set()
    for entry in git(root, "ls-files", "-s", "-z").stdout.split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)
        mode, _obj, stage = meta.split(" ")
        if stage != "0":
            return None
        tracked.add(path)
        if mode == "160000":
            submodules.add(path)
    untracked = set(git(root, "ls-files", "-z", "--others", "--exclude-standard").stdout.split("\0")) - {""}
    for path in sorted(tracked | untracked):
        if path.startswith((".simpleide/project.db", ".simpleide/artifacts/", ".simpleide/context.json",
                            ".simpleide/worktrees.json", ".simpleide/hook-created-")):
            continue
        digest.update(b"path\0" + path.encode("utf-8", "surrogateescape") + b"\0")
        f = root / path
        if path in submodules:
            sub = root / path
            if not (sub / ".git").exists():
                return None
            top = git(sub, "rev-parse", "--show-toplevel", check=False)
            if top.returncode or Path(top.stdout.strip()).resolve() != sub.resolve():
                return None
            inner = revision(sub, depth + 1)
            if inner is None:
                return None
            digest.update(b"submodule\0" + inner.encode() + b"\0")
        elif f.is_symlink():
            digest.update(b"symlink:" + os.readlink(f).encode("utf-8", "surrogateescape"))
        elif f.is_file():
            digest.update(str(f.stat().st_mode).encode())
            with f.open("rb") as source:
                for block in iter(lambda: source.read(65536), b""):
                    digest.update(block)
        elif f.is_dir():
            return None
        else:
            digest.update(b"deleted\0")
    return "v2:" + digest.hexdigest()


def check_states(con, root, task):
    cfg = check_config(root)
    if cfg is None:
        historical = con.execute("SELECT COUNT(*) FROM rec WHERE task=? AND kind='test'", (task,)).fetchone()[0]
        return [("*", "historical")] if historical else []
    if cfg.get("confirmed") is not True:
        return [("*", "unconfirmed")]
    fingerprint = revision(root)
    states = []
    for name in cfg["checks"]:
        row = con.execute("SELECT * FROM check_obs WHERE task=? AND name=? AND execution_root=? ORDER BY id DESC LIMIT 1",
                          (task, name, str(root))).fetchone()
        if not row:
            state = "missing"
        elif row["exit_code"] is None or row["exit_code"] < 0:
            state = "interrupted"
        elif row["exit_code"]:
            state = "failed"
        elif not fingerprint:
            state = "unknown"
        elif row["before_hash"] != fingerprint or row["after_hash"] != fingerprint or row["config_hash"] != config_hash(cfg):
            state = "stale"
        else:
            state = "current"
        states.append((name, state))
    return states


def check_summary(con, root, task):
    display_map = {
        "historical": "historical/unverified checks",
        "unconfirmed": "checks unverified: configuration unconfirmed",
        "missing": "missing/unverified",
        "interrupted": "interrupted/unverified",
        "failed": "failed (FAIL)",
        "unknown": "freshness unknown/unverified",
        "stale": "stale/unverified",
        "current": "PASS current",
    }
    summaries = []
    for name, state in check_states(con, root, task):
        if name == "*":
            summaries.append(display_map[state])
        else:
            summaries.append(name + ": " + display_map[state])
    return summaries


def check_cmd(root, name, task):
    if task:
        validate_slug(task)
    path = root / ".simpleide/config.json"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"confirmed": False, "checks": proposed_checks(root)}, indent=2) + "\n")
        print("Wrote proposed checks to %s; inspect and set confirmed to true." % path)
        return 2
    cfg = check_config(root)
    if cfg.get("confirmed") is not True:
        raise ValueError("Confirm .simpleide/config.json by setting confirmed to true after inspection")
    checks = cfg["checks"]
    names = [name] if name else list(checks)
    if not names or any(n not in checks for n in names):
        raise ValueError("Unknown or empty check. Available: " + ", ".join(checks))
    failed, messages = False, []
    con = ledger(root)
    if (root / ".simpleide/context.json").exists(): task = selected_task(con,root,task)
    for n in names:
        artifact_dir = store_root(root) / ".simpleide/artifacts" / (task or "untagged")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        fd, filename = tempfile.mkstemp(prefix=n + "-", suffix=".txt", dir=artifact_dir)
        artifact = Path(filename)
        before = revision(root)
        command = checks[n]
        with transaction(con):
            rid, _ = insert(con, "test", n + ": RUNNING", command, task, refs=str(artifact))
            obs = con.execute("INSERT INTO check_obs(record_id,task,name,command,config_hash,execution_root,before_hash,artifact) VALUES(?,?,?,?,?,?,?,?)",
                              (rid, task, n, command, config_hash(cfg), str(root), before, str(artifact))).lastrowid
        start = time.monotonic()
        code = -1
        try:
            with os.fdopen(fd, "w") as output:
                try:
                    code = subprocess.run(command, shell=True, cwd=root, stdout=output, stderr=subprocess.STDOUT).returncode
                except (KeyboardInterrupt, OSError) as err:
                    output.write("\ninterrupted/error: " + str(err) + "\n")
                    code = -2
        finally:
            duration = time.monotonic() - start
            status = "PASS" if code == 0 else "FAIL" if code > 0 else "INTERRUPTED"
            with transaction(con):
                con.execute("UPDATE rec SET title=? WHERE id=?", (n + ": " + status, rid))
                con.execute("UPDATE check_obs SET after_hash=?,exit_code=?,duration=? WHERE id=?", (revision(root), code, duration, obs))
                if code:
                    con.execute("UPDATE run SET check_failures=check_failures+1 WHERE task=?", (task,))
        failed |= code != 0
        messages.append(f"{n}: {status} ({duration:.2f}s; exit {code})")
        if code:
            with artifact.open(errors="replace") as output:
                count = 0
                for line in output:
                    if re.search(r"FAIL|ERROR|failed|error:", line, re.I):
                        messages.append("  " + line.strip()[:180]); count += 1
                        if count == 3: break
        messages.append("  full output: " + str(artifact))
    print("\n".join(messages[:14] + (["... remaining evidence in artifacts"] if len(messages)>14 else [])))
    return int(failed)


def scope_cmd(root, base, allows):
    if not allows:
        raise ValueError("at least one --allow pattern is required")
    outside = [p for p in changed(root, base) if not any(fnmatch.fnmatch(p, a) for a in allows)]
    print("\n".join(json.dumps(p, ensure_ascii=False) for p in outside), end="\n" if outside else "")
    return 1 if outside else 0


def pack_cmd(root, task, base, allows):
    con = ledger(root)
    rows = con.execute("SELECT * FROM rec WHERE task=? ORDER BY id", (task,)).fetchall()
    run = con.execute("SELECT request_id FROM run WHERE task=?",(task,)).fetchone()
    request = next((r for r in rows if run and r["id"] == run["request_id"]),None)
    criteria = [r for r in rows if r["kind"] == "criteria"]
    tests = [r for r in rows if r["kind"] == "test"]
    files = changed(root, base)
    # --no-renames makes each NUL record a simple add/delete path, including tab/newline names.
    stat = git(root, "diff", "--numstat", "-z", "--no-renames", base, "--").stdout.split("\0")
    numbers = {line.split("\t", 2)[2]: line.split("\t", 2)[:2] for line in stat if line.count("\t") >= 2}
    artifact = task_artifact(con, root, task)
    print("REQUEST  " + (f"P{request['id']} (sx mem show P{request['id']})" if request else "missing"))
    print("CRITERIA " + (" ".join(f"P{r['id']}" for r in criteria) or "missing"))
    print("BASE     " + base)
    for path in files[:17]:
        a, d = numbers.get(path, ("?", "?"))
        print(f"CHANGED  {json.dumps(path, ensure_ascii=False)} +{a} -{d}")
    if len(files) > 17:
        print(f"CHANGED  ... {len(files)-17} more; git diff --name-only {base}")
    summary = check_summary(con, root, task)
    print("CHECKS   " + (" | ".join(summary) or "none configured"))
    outside = [p for p in files if allows and not any(fnmatch.fnmatch(p, a) for a in allows)]
    print("SCOPE    " + ("outside: " + ", ".join(outside[:3]) if outside else "ok" if allows else "not supplied"))
    print("READ     " + str(artifact) + "; git diff " + shlex.quote(base) + " -- <paths>")
    return 0


def worktree_inventory(root):
    result = git(root, "worktree", "list", "--porcelain", "-z", check=False)
    if result.returncode:
        # Git before 2.36 lacks worktree -z. Porcelain quotes embedded newlines.
        output = git(root, "-c", "core.quotePath=false", "worktree", "list", "--porcelain").stdout
        entries = {}
        for block in output.split("\n\n"):
            values = dict(f.split(" ",1) for f in block.splitlines() if " " in f)
            if "worktree" in values:
                path = values["worktree"]
                if path.startswith('"'): path = ast.literal_eval(path)
                entries[str(Path(path).resolve())] = values.get("branch", "")
        return entries
    output = result.stdout
    entries = {}
    for block in output.split("\0\0"):
        fields = block.split("\0")
        values = dict(f.split(" ", 1) for f in fields if " " in f)
        if "worktree" in values:
            entries[str(Path(values["worktree"]).resolve())] = values.get("branch", "")
    return entries


def worker_runtime(root):
    for base in (root,Path.home()):
        directory = base / ".simpleide"
        manifest_path = directory / "install-manifest.json"
        if not manifest_path.is_file(): continue
        manifest = json.loads(manifest_path.read_text())
        if not manifest.get("hosts"): continue
        for relative, asset in manifest["assets"].items():
            path = base / relative
            if not path.is_file(): raise ValueError("worker asset missing; reinstall/commit: " + str(path))
            text = path.read_text()
            if asset["kind"] == "block":
                match = re.search(r"<!-- simpleIDE:start.*?<!-- simpleIDE:end -->",text,re.S)
                text = match.group().strip() if match else ""
            if hashlib.sha256(text.encode()).hexdigest() != asset["hash"]:
                raise ValueError("worker asset changed; reinstall/commit: " + str(path))
        return directory / "sx.py"
    raise ValueError("worker runtime missing; commit local installation and host assets or install globally")


def archive_worker(con, root, entry):
    worker = Path(entry["path"])
    # Validate a managed pointer, even if there is no local database.
    if (worker / ".simpleide/context.json").exists():
        if store_root(worker) != store_root(root):
            raise ValueError("worker points at a different evidence store")
    local_db = worker / ".simpleide/project.db"
    directory = store_root(root) / ".simpleide/artifacts" / entry["task"] / ("archive-" + entry["piece"])
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"parent_store": identity(con), "worker": str(worker)}
    artifacts = worker / ".simpleide/artifacts"
    if local_db.exists():
        legacy = connect(local_db)
        backup = directory / ("store-" + identity(legacy) + ".db")
        dest = sqlite3.connect(backup)
        legacy.backup(dest)
        manifest["store_id"] = identity(legacy)
        legacy.close()
        if dest.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("legacy evidence archive failed verification")
        dest.close()
        manifest["database"] = str(backup)
    if artifacts.exists():
        shutil.copytree(artifacts, directory / "artifacts", dirs_exist_ok=True)
        for f in artifacts.rglob("*"):
            if f.is_file() and f.read_bytes() != (directory / "artifacts" / f.relative_to(artifacts)).read_bytes():
                raise ValueError("worker artifact archive verification failed")
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return str(directory / "manifest.json")


def write_context(path, root, con, slug):
    path = Path(path)
    pointer = path / ".simpleide/context.json"
    pointer.parent.mkdir(exist_ok=True)
    pointer.write_text(json.dumps({"store_root": str(store_root(root)), "store_id": identity(con), "task": slug}, indent=2) + "\n")
    exclude = Path(git(path, "rev-parse", "--git-path", "info/exclude").stdout.strip())
    if not exclude.is_absolute(): exclude = path / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude.read_text() if exclude.exists() else ""
    if ".simpleide/context.json" not in existing:
        with exclude.open("a") as f: f.write("\n.simpleide/context.json\n")


def worktree_cmd(root, action, slug, piece=None, discard=False, apply=False):
    validate_slug(slug)
    if (root / ".simpleide/context.json").exists():
        raise ValueError("manage worktrees from the parent execution checkout")
    con = ledger(root)
    task_key = "operation:task:" + slug
    add_prefix = "operation:add:" + slug + ":"
    if action == "reconcile":
        locks = con.execute("SELECT * FROM meta WHERE key=? OR key LIKE ?", (task_key,add_prefix+"%")).fetchall()
        for lock in locks:
            owner = json.loads(lock["value"])
            alive = True
            if owner.get("host") == socket.gethostname():
                try: os.kill(owner["pid"],0)
                except ProcessLookupError: alive = False
            print("operation " + lock["key"] + ": owner=" + lock["value"] + "; alive=" + str(alive))
            if apply:
                if alive: raise ValueError("cannot reconcile an operation whose owner may still be running")
                with con: con.execute("DELETE FROM meta WHERE key=?",(lock["key"],))
        return _worktree_cmd(root,action,slug,piece,discard,apply)
    key = add_prefix + (piece or "") if action == "add" else task_key
    with transaction(con):
        busy = con.execute("SELECT key FROM meta WHERE key=? OR key=?" + (" OR key LIKE ?" if action != "add" else ""),
                           (task_key,key,add_prefix+"%") if action != "add" else (task_key,key)).fetchone()
        if busy: raise ValueError("worktree operation reserved; inspect worktree reconcile " + slug)
        con.execute("INSERT INTO meta VALUES(?,?)",(key,json.dumps({"host":socket.gethostname(),"pid":os.getpid()})))
    try:
        return _worktree_cmd(root,action,slug,piece,discard,apply)
    finally:
        with con: con.execute("DELETE FROM meta WHERE key=?",(key,))
        con.close()


def _worktree_cmd(root, action, slug, piece=None, discard=False, apply=False):
    validate_slug(slug)
    con = ledger(root)
    # Import once, retaining the original JSON and a backup. Never renumber its records.
    legacy = store_root(root) / ".simpleide/worktrees.json"
    with transaction(con):
        if legacy.exists() and not con.execute("SELECT 1 FROM meta WHERE key='worktrees_imported'").fetchone():
            data = json.loads(legacy.read_text())
            shutil.copy2(legacy, legacy.with_suffix(".json.imported.bak"))
            for task, items in data.items():
                for e in items:
                    con.execute("INSERT OR IGNORE INTO worktree(task,piece,path,branch,base_commit,state) VALUES(?,?,?,?,?,?)",
                                (task,e["piece"],e["path"],e["branch"],"", "merged" if e.get("merged") else "added"))
            con.execute("INSERT INTO meta VALUES('worktrees_imported','1')")
    if action == "add":
        if not con.execute("SELECT 1 FROM run WHERE task=? AND outcome=''",(slug,)).fetchone():
            raise ValueError("worktree add requires an existing open task")
        if not piece or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", piece):
            raise ValueError("piece must be a lowercase slug")
        # Refuse before Git mutation if an untracked parent installation would be missing.
        if git(root, "cat-file", "-e", "HEAD:.simpleide/sx.py", check=False).returncode:
            global_script = Path.home() / ".simpleide/sx.py"
            if not global_script.exists() or not (global_script.parent / "install-manifest.json").exists():
                raise ValueError("commit local simpleIDE runtime/host assets before adding worktrees, or install globally")
        path = root.parent / f"{root.name}-sx-{slug}-{piece}"
        branch = f"codex/sx-{slug}-{piece}"
        inventory = worktree_inventory(root)
        base_commit = git(root,"rev-parse","HEAD").stdout.strip()
        idempotent = False
        with transaction(con):
            old = con.execute("SELECT * FROM worktree WHERE task=? AND piece=?", (slug,piece)).fetchone()
            if old and old["state"] not in ("adding", "error"):
                if old["state"] in ("added", "merged") and str(path) in inventory:
                    idempotent = True
                else:
                    raise ValueError("piece state requires reconciliation: " + old["state"])
            if not old:
                con.execute("INSERT INTO worktree(task,piece,path,branch,base_commit,state) VALUES(?,?,?,?,?,'adding')",
                            (slug,piece,str(path),branch,base_commit))
        if idempotent:
            worker_runtime(path)
            if not (path / ".simpleide/context.json").exists() or store_root(path) != store_root(root):
                raise ValueError("worker context missing/conflicting; explicitly restore its store pointer")
            print(path); return 0
        try:
            inventory = worktree_inventory(root)
            if str(path) in inventory:
                if inventory[str(path)] != "refs/heads/" + branch:
                    raise ValueError("existing worktree branch conflicts with reserved piece")
            else:
                exists = git(root, "show-ref", "--verify", "refs/heads/" + branch, check=False).returncode == 0
                command = ["worktree", "add", str(path), branch] if exists else ["worktree", "add", "-b", branch, str(path)]
                git(root, *command)
            worker_runtime(path)
            write_context(path, root, con, slug)
            task_artifact(con, root, slug)
            with con:
                con.execute("UPDATE worktree SET state='added',diagnostic='' WHERE task=? AND piece=?", (slug,piece))
        except (ValueError, OSError) as err:
            with con:
                con.execute("UPDATE worktree SET state='error',diagnostic=? WHERE task=? AND piece=?", (str(err),slug,piece))
            raise
        print(path)
        return 0
    entries = con.execute("SELECT * FROM worktree WHERE task=? ORDER BY id", (slug,)).fetchall()
    inventory = worktree_inventory(root)
    if action == "reconcile":
        for e in entries:
            present = e["path"] in inventory
            actual = inventory.get(e["path"], "") if present else ""
            actual_branch = actual.replace("refs/heads/", "") if actual.startswith("refs/heads/") else (actual or "detached")
            worker_head = git(Path(e["path"]), "rev-parse", "HEAD", check=False).stdout.strip() if present else ""
            integrated = git(root, "merge-base", "--is-ancestor", worker_head, "HEAD", check=False).returncode == 0 if (present and worker_head) else False
            print(f"{e['piece']}: recorded={e['state']} present={present} actual={actual_branch} integrated={integrated} diagnostic={e['diagnostic']}")
            if apply:
                branch_matches = (actual == "refs/heads/" + e["branch"])
                if present and branch_matches and not (Path(e["path"]) / ".simpleide/context.json").exists():
                    write_context(e["path"], root, con, slug)
                    print("restored context for " + e["piece"])
                state = "removed" if not present and e["state"] == "removing" and Path(e["diagnostic"]).is_file() else "merged" if present and branch_matches and integrated else None
                if state:
                    with con: con.execute("UPDATE worktree SET state=? WHERE id=?",(state,e["id"]))
        return 0
    if action == "merge" and git(root, "status", "--porcelain").stdout.strip():
        raise ValueError("main checkout has uncommitted work; resolve/commit any merge before retry")
    # Every piece and pointer is checked before the first destructive operation.
    heads = {}
    for entry in entries:
        path = Path(entry["path"])
        if entry["state"] == "removed": continue
        if entry["path"] not in inventory:
            if entry["state"] == "removing" and Path(entry["diagnostic"]).is_file():
                with con: con.execute("UPDATE worktree SET state='removed' WHERE id=?",(entry["id"],))
                continue
            raise ValueError("worktree missing unexpectedly; run worktree reconcile " + slug)
        actual = inventory[entry["path"]]
        if actual != "refs/heads/" + entry["branch"]:
            raise ValueError("piece %s: worktree is on %s, expected %s; restore the expected branch first"
                             % (entry["piece"], actual or "a detached HEAD", entry["branch"]))
        heads[entry["id"]] = git(path, "rev-parse", "HEAD").stdout.strip()
        if git(path,"status","--porcelain").stdout.strip():
            raise ValueError("worktree has uncommitted work: " + str(path))
        if (path / ".simpleide/context.json").exists():
            if store_root(path) != store_root(root): raise ValueError("worker evidence store differs")
        integrated = git(root,"merge-base","--is-ancestor",heads[entry["id"]],"HEAD",check=False).returncode == 0
        if action == "clean" and not integrated and not discard:
            raise ValueError("unintegrated branch: " + entry["branch"] + "; merge it or explicitly use --discard")
    if action == "clean":
        archives = {e["id"]: archive_worker(con, root, e) for e in entries if Path(e["path"]).exists() and e["state"] != "removed"}
        for entry in entries:
            if not Path(entry["path"]).exists() or entry["state"] == "removed": continue
            current_head = git(Path(entry["path"]), "rev-parse", "HEAD").stdout.strip()
            current_branch = worktree_inventory(root).get(entry["path"], "")
            if current_head != heads[entry["id"]] or current_branch != "refs/heads/" + entry["branch"]:
                raise ValueError("piece %s changed during clean; aborting" % entry["piece"])
            with con:
                con.execute("UPDATE worktree SET state='removing',diagnostic=? WHERE id=?", (archives[entry["id"]],entry["id"]))
            git(root,"worktree","remove",entry["path"])
            with con: con.execute("UPDATE worktree SET state='removed' WHERE id=?", (entry["id"],))
            print("removed " + entry["path"])
    elif action == "merge":
        for entry in entries:
            if entry["state"] == "removed": continue
            commit = heads[entry["id"]]
            integrated = git(root,"merge-base","--is-ancestor",commit,"HEAD",check=False).returncode == 0
            if not integrated:
                with con: con.execute("UPDATE worktree SET state='merging' WHERE id=?", (entry["id"],))
                p = git(root,"merge","--no-ff","--no-edit",commit,check=False)
                if p.returncode:
                    with con: con.execute("UPDATE worktree SET diagnostic=? WHERE id=?", (p.stderr or p.stdout,entry["id"]))
                    raise ValueError("merge conflict at " + entry["piece"] + "; resolve and commit before retry")
                if git(root,"merge-base","--is-ancestor",commit,"HEAD",check=False).returncode != 0:
                    raise ValueError("merged commit %s is not an ancestor of HEAD" % commit[:12])
            with con: con.execute("UPDATE worktree SET state='merged',diagnostic='' WHERE id=?", (entry["id"],))
            print("merged %s %s" % (entry["piece"], commit[:12]))
    return 0


def doctor_cmd(root):
    install_dir = root / ".simpleide"
    if not (install_dir / "install-manifest.json").exists():
        install_dir = Path.home() / ".simpleide"
    path = install_dir / "install-manifest.json"
    if not path.is_file():
        print("MISSING install-manifest.json; reinstall to establish ownership")
        return 1
    manifest = json.loads(path.read_text())
    if manifest.get("version") != 1 or not manifest.get("hosts") or not isinstance(manifest.get("assets"),dict):
        raise ValueError("invalid/empty installation manifest")
    base, ok = install_dir.parent, True
    for relative, asset in manifest["assets"].items():
        f = base / relative
        present = f.is_file()
        if present:
            text = f.read_text()
            if asset["kind"] == "block":
                block = re.search(r"<!-- simpleIDE:start.*?<!-- simpleIDE:end -->",text,re.S)
                text = block.group().strip() if block else ""
            present = hashlib.sha256(text.encode()).hexdigest() == asset["hash"]
            if f.suffix == ".json": json.loads(f.read_text())
            if f.suffix == ".toml":
                try:
                    import tomllib
                    tomllib.loads(f.read_text())
                except ImportError: pass
        print(("OK " if present else "MISSING/CHANGED ") + str(f))
        ok &= present
    models = json.loads((install_dir / "models.json").read_text())
    for host in manifest["hosts"]:
        roles = models.get(host)
        valid = isinstance(roles,dict) and {"planner","worker","tester","reviewer"} <= roles.keys() and all(isinstance(v,dict) and isinstance(v.get("model"),str) and v["model"].strip() for v in roles.values())
        print(host + " models: " + ("configured" if valid else "missing/empty")); ok &= valid
    for host in manifest["hosts"]:
        if not manifest.get("hooks",{}).get(host): print(host + " hooks: optional, not configured")
    for host, events in manifest.get("hook_entries",{}).items():
        f = base / {"codex":".codex/hooks.json","cursor":".cursor/hooks.json","claude":".claude/settings.json"}[host]
        data = json.loads(f.read_text()) if f.exists() else {}
        valid = isinstance(data,dict) and isinstance(data.get("hooks"),dict) and all(e in data["hooks"].get(event,[]) for event,entries in events.items() for e in entries)
        print(host + " hooks: " + ("configured/present" if valid else "MISSING entries")); ok &= valid
    con = ledger(root)
    healthy = con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    ok &= healthy
    print("store: " + identity(con) + "; path=" + str(store_root(root)) + "; integrity=" + str(healthy))
    print("python: " + sys.version.split()[0] + "; FTS5: " + ("yes" if has_fts(con) else "no"))
    try:
        connect(shared_path()).close(); print("shared db: writable")
    except (OSError,sqlite3.Error): print("shared db: lessons will queue")
    print("Files configured/present only. Live role discovery, actual model and hook enforcement require host observations.")
    return 0 if ok else 1


def close_task(con, root, args):
    validate_slug(args.slug)
    if args.outcome == "accepted" and (root / ".simpleide/context.json").exists():
        raise ValueError("accepted closure requires the integrated parent execution checkout")
    with transaction(con):
        row = con.execute("SELECT * FROM run WHERE task=?", (args.slug,)).fetchone()
        result = con.execute("SELECT * FROM rec WHERE id=? AND kind='result' AND task=?", (record_number(args.result, "P"), args.slug)).fetchone()
        if not row or not result or not args.refs.strip():
            raise ValueError("close requires an existing task, its result P record, and evidence refs")
        refs = args.refs
        if args.exception:
            decision = con.execute("SELECT * FROM rec WHERE id=? AND task=? AND kind='decision'", (record_number(args.exception,"P"),args.slug)).fetchone()
            if not decision:
                raise ValueError("acceptance exception must be a decision in this task")
            refs += " exception=" + args.exception
        if row["outcome"]:
            if (row["outcome"], row["result_id"], row["actor"], row["outcome_refs"]) == (args.outcome, result["id"], args.by, refs):
                return
            raise ValueError("terminal outcome is immutable; export evidence for an explicit correction")
        states = check_states(con, root, args.slug)
        summaries = check_summary(con, root, args.slug)
        if args.outcome == "accepted" and any(st != "current" for _, st in states) and not args.exception:
            raise ValueError("acceptance requires current checks or --exception Pdecision: " + " | ".join(summaries))
        con.execute("UPDATE run SET end=CURRENT_TIMESTAMP,outcome=?,provenance='explicit',actor=?,result_id=?,outcome_refs=? WHERE task=?",
                    (args.outcome, args.by, result["id"], refs, args.slug))


def stats_cmd(root, task=None, cost=None, tokens=None, usage_source=None):
    con = ledger(root)
    if cost is not None or tokens is not None:
        if not task or not con.execute("SELECT 1 FROM run WHERE task=?", (task,)).fetchone():
            raise ValueError("usage requires an existing --task")
        if any(v is not None and (not math.isfinite(v) or v < 0) for v in (cost, tokens)):
            raise ValueError("usage must be finite and nonnegative")
        if not usage_source or not usage_source.strip():
            raise ValueError("usage requires --usage-source")
        with con:
            if cost is not None: con.execute("UPDATE run SET cost=? WHERE task=?", (cost,task))
            if tokens is not None: con.execute("UPDATE run SET tokens=? WHERE task=?", (tokens,task))
            con.execute("UPDATE run SET usage_source=? WHERE task=?", (usage_source,task))
    rows = con.execute("SELECT * FROM run" + (" WHERE task=?" if task else ""), (task,) if task else ()).fetchall()
    if not rows:
        print("no tasks recorded")
    for size in sorted({r["size"] for r in rows}):
        group = [r for r in rows if r["size"] == size]
        user = sum(r["outcome"] == "accepted" and r["provenance"] == "explicit" and r["actor"] == "user" for r in group)
        assistant = sum(r["outcome"] == "accepted" and r["provenance"] == "explicit" and r["actor"] == "assistant" for r in group)
        legacy = sum(r["outcome"] == "accepted" and r["provenance"] == "legacy-unverified" for r in group)
        dispatches = sum(con.execute("SELECT COUNT(*) FROM dispatch WHERE task=? AND observed_launch=1",(r["task"],)).fetchone()[0] for r in group)
        usage = []
        for field in ("tokens", "cost"):
            values = [r[field] for r in group if r[field] is not None]
            usage.append(field + "=" + (str(sum(values)) if values else "unknown") + " coverage=%d/%d" % (len(values),len(group)))
        seconds = [float(con.execute("SELECT (julianday(end)-julianday(start))*86400 FROM run WHERE task=?",(r["task"],)).fetchone()[0]) for r in group if r["end"]]
        elapsed = str(round(sum(seconds)/len(seconds),2)) if seconds else "unknown"
        counts = "failed=%d abandoned=%d avg_repairs=%.2f avg_seconds=%s " % (sum(r["outcome"]=="failed" for r in group),sum(r["outcome"]=="abandoned" for r in group),sum(r["repair_rounds"] for r in group)/len(group),elapsed)
        print(counts + f"{size} tasks={len(group)} accepted={user+assistant} user={user} assistant={assistant} legacy-unverified={legacy} observed_dispatches={dispatches} check_failures={sum(r['check_failures'] for r in group)} " + " ".join(usage))
    return 0


def dispatch_identity(payload):
    session = payload.get("parent_conversation_id") or payload.get("conversation_id") or payload.get("session_id") or ""
    child = payload.get("subagent_id") or payload.get("agent_id") or payload.get("child_conversation_id") or ""
    call_id = payload.get("tool_use_id") or payload.get("tool_call_id") or payload.get("parent_tool_call_id") or ""
    if any(not isinstance(value,str) or len(value)>4096 for value in (session,child,call_id)):
        raise ValueError("hook identities must be bounded strings")
    return session, child, call_id


def dispatch_match(con, host, session, agent, child, call_id, brief="", task=""):
    """Only correlate a unique row. Unknown IDs never fall back to another worker."""
    query, values = "SELECT * FROM dispatch WHERE host=? AND session_id=?", [host, session]
    if agent:
        query += " AND agent=?"
        values.append(agent)
    if task:
        query += " AND task=?"
        values.append(task)
    ids, id_values = [], []
    for column, value in (("child_id", child), ("tool_call_id", call_id)):
        if value:
            ids.append("(" + column + "=? OR " + column + "='')")
            id_values.append(value)
    if ids:
        query += " AND " + " AND ".join(ids)
        values += id_values
        # A pending call is matchable only by its actual call ID, never an empty child.
        query += " AND (" + " OR ".join(column + "=?" for column,value in (("child_id",child),("tool_call_id",call_id)) if value) + ")"
        values += [value for value in (child,call_id) if value]
    elif brief:
        query += " AND brief_hash=?"
        values.append(hashlib.sha256(brief.strip().encode()).hexdigest())
    # Include completed rows: a repeated return must not consume the next worker.
    rows = con.execute(query + " LIMIT 2", values).fetchall()
    return rows[0] if len(rows) == 1 else None


def dispatch_reply(host, event, reason=""):
    if host == "cursor":
        output = {"permission": "deny" if reason else "allow"}
        if reason:
            output["user_message"] = reason
        print(json.dumps(output))
    elif reason:
        output = {"hookEventName": event}
        if event == "SubagentStart":
            output["additionalContext"] = reason
        else:
            output.update(permissionDecision="deny", permissionDecisionReason=reason)
        print(json.dumps({"hookSpecificOutput": output}))


def shell_commands(command):
    """Tokenize simple shell commands without executing or expanding any input."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    words = []
    for word in lexer:
        if word and all(c in ";&|()\n" for c in word):
            if words:
                yield words
                words = []
        else:
            words.append(word)
    if words:
        yield words


def git_flags(args, subcommand):
    """Do not mistake option values (e.g. clean -e -n) for dry-run flags."""
    takes_value = {"push": {"o", "--push-option", "--receive-pack", "--exec", "--repo"},
                   "clean": {"e", "--exclude"}}.get(subcommand, set())
    short, long = set(), set()
    values = iter(args)
    for arg in values:
        if arg == "--":
            break
        if arg.startswith("--"):
            name = arg.split("=", 1)[0]
            long.add(name)
            if name in takes_value and "=" not in arg:
                next(values, None)
        elif arg.startswith("-"):
            for index, flag in enumerate(arg[1:], 2):
                short.add(flag)
                if flag in takes_value:
                    if index == len(arg):
                        next(values, None)
                    break
    return short, long


def shell_unsafe(command, root, cwd=None, readonly=False, depth=0):
    """A bounded guard for common command forms, not a general shell sandbox."""
    if depth > 4:
        return True
    if re.search(r"\bDROP\s+(?:DATABASE|TABLE)\b", command, re.I):
        return True
    if readonly and re.search(r"(?:^|\s)>>?", command):
        return True
    directory = Path(cwd) if cwd else root
    if not directory.is_absolute():
        directory = root / directory
    for words in shell_commands(command):
        while words and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]) or
                         Path(words[0]).name in ("command", "builtin", "exec", "env", "sudo")):
            wrapper = Path(words.pop(0)).name
            while words and words[0].startswith("-"):
                option = words.pop(0)
                if wrapper == "sudo" and option in ("-u", "-g", "--user", "--group") and words:
                    words.pop(0)
        if not words:
            continue
        executable, args = Path(words[0]).name, words[1:]
        if executable == "cd":
            while args and args[0] in ("--", "-L", "-P", "-e"):
                option = args.pop(0)
                if option == "--":
                    break
            target = args[0] if args else str(Path.home())
            if any(c in target for c in "$`*") or target == "-":
                directory = None
            else:
                path = Path(target).expanduser()
                directory = path if path.is_absolute() else directory / path if directory else None
            continue
        if executable in ("sh", "bash", "zsh", "dash", "ksh"):
            for i, arg in enumerate(args[:-1]):
                if arg.startswith("-") and "c" in arg[1:]:
                    if shell_unsafe(args[i + 1], root, directory or "/", readonly, depth + 1):
                        return True
                    break
        if executable == "git":
            # Skip Git's global options (including options with separate values).
            while args and args[0].startswith("-"):
                option = args.pop(0)
                if option in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") and args:
                    args.pop(0)
            subcommand = args.pop(0) if args else ""
            short, long = git_flags(args, subcommand)
            dry_run = "--dry-run" in long or (subcommand in ("push", "clean") and "n" in short)
            if not dry_run and (
                (subcommand == "push" and ("f" in short or long & {"--force", "--force-with-lease", "--force-if-includes"})) or
                (subcommand == "reset" and "--hard" in long) or
                (subcommand == "clean" and ("f" in short or "--force" in long))
            ):
                return True
            if readonly and subcommand in ("add", "commit", "merge", "reset", "clean", "push", "checkout", "switch", "restore"):
                return True
        if executable == "rm":
            flags, targets, parsing_options = [], [], True
            for arg in args:
                if parsing_options and arg == "--":
                    parsing_options = False
                elif parsing_options and arg.startswith("-"):
                    flags.append(arg)
                else:
                    targets.append(arg)
            recursive = any(a == "--recursive" or (not a.startswith("--") and any(c in a[1:] for c in "rR")) for a in flags)
            if recursive:
                for target in targets:
                    if any(c in target for c in "$`*"):
                        return True
                    path = Path(target).expanduser()
                    if not path.is_absolute():
                        if directory is None:
                            return True
                        path = directory / path
                    try:
                        path.resolve().relative_to(root.resolve())
                    except ValueError:
                        return True
        if (executable, args[:1]) in (("npm", ["publish"]), ("cargo", ["publish"]), ("twine", ["upload"])) and "--dry-run" not in args:
            return True
        if readonly and (executable in ("rm", "mv", "cp", "tee", "touch", "mkdir") or
                         (executable == "sed" and any(a.startswith("-i") for a in args))):
            return True
    return False


def hook_cmd(root, event, host=None):
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("hook input must be a JSON object")
    except (ValueError, OSError) as err:
        raise ValueError("Invalid hook input: " + str(err))
    con = ledger(root)
    tool = host or ("cursor" if "subagent_type" in payload or "conversation_id" in payload else "codex" if "hook_event_name" in payload else "claude")
    task = payload.get("task_slug") or os.environ.get("SIMPLEIDE_TASK", "")
    session, child, call_id = dispatch_identity(payload)
    if event == "capture-request":
        prompt = payload.get("prompt") or payload.get("user_prompt") or ""
        task = selected_task(con, root, task, tool, session)
        if task and con.execute("SELECT outcome FROM run WHERE task=?",(task,)).fetchone()[0]:
            task = ""  # A new prompt after closure is not evidence owned by that completed task.
        if isinstance(prompt, str) and prompt.strip():
            title = next((line.strip() for line in prompt.splitlines() if line.strip()), "request")[:120]
            insert(con, "request", title, prompt, task,
                   host=tool, session=session)
        return 0
    if event == "dispatch-guard":
        arg = payload.get("tool_input") or {}
        if not isinstance(arg, dict):
            raise ValueError("dispatch tool_input must be an object")
        agent = payload.get("subagent_type") or payload.get("agent_type") or arg.get("subagent_type") or arg.get("agent_type") or ""
        brief = payload.get("task") or arg.get("prompt") or arg.get("task") or arg.get("message") or ""
        model = payload.get("subagent_model") or payload.get("model") or ""
        if not isinstance(brief, str): brief = ""
        task_match = re.search(r"(?im)^[ \t]*TASK[ \t]*:[ \t]*([a-z0-9][a-z0-9_-]*)[ \t]*$", brief)
        if not task and task_match:
            task = task_match.group(1)
        hook_event = payload.get("hook_event_name", "PreToolUse")
        lifecycle = hook_event == "SubagentStart" and tool in ("claude", "codex")
        if not isinstance(agent, str) or not agent:
            return 0
        if agent.startswith("sx-") and (brief or not lifecycle):
            sections = brief_sections(brief)
            missing = [name for name in ("GOAL", "DONE WHEN") if not sections.get(name)]
            if missing:
                dispatch_reply(tool, hook_event, "simpleIDE brief missing content: " + ", ".join(missing))
                return 0
        with con:
            con.execute("BEGIN IMMEDIATE")
            replay = dispatch_match(con, tool, session, agent, child, call_id) if child or call_id else None
            if lifecycle:
                if replay and replay["state"] == "pending" and call_id and replay["tool_call_id"] == call_id:
                    con.execute("UPDATE dispatch SET child_id=?,model=?,state='started',observed_launch=1 WHERE id=?", (child, model, replay["id"]))
                elif not replay:
                    # Lifecycle without an exact admission join is observed, but uncorrelated.
                    con.execute("INSERT INTO dispatch(task,agent,model,host,session_id,child_id,tool_call_id,state,observed_launch) VALUES('',?,?,?,?,?,?,'unknown',1)",
                                (agent, model, tool, session, child, call_id))
                if not replay:
                    con.execute("INSERT INTO hook_observation(host,session_id,event,detail) VALUES(?,?,?,?)",
                                (tool,session,"uncorrelated-start",json.dumps({"child":child,"call":call_id})))
                    print("simpleIDE: uncorrelated lifecycle observation; pending intents require explicit reconciliation",file=sys.stderr)
                dispatch_reply(tool, hook_event)
                return 0
            if replay:
                dispatch_reply(tool, hook_event)
                return 0
            task = selected_task(con, root, task, tool, session)
            if task and con.execute("SELECT outcome FROM run WHERE task=?",(task,)).fetchone()[0]:
                dispatch_reply(tool,hook_event,"simpleIDE: terminal task; create and bind a new slug")
                return 0
            if agent.startswith("sx-"):
                active = con.execute("SELECT COUNT(*) FROM dispatch WHERE task=? AND agent='sx-worker' AND state IN ('pending','started')", (task,)).fetchone()[0]
                round_match = re.search(r"(?im)^\s*REPAIR ROUND\s*:\s*(\d+)", brief)
                repair = int(round_match.group(1)) if round_match else 0
                if (task and agent == "sx-worker" and active >= 3) or repair > 2:
                    dispatch_reply(tool, hook_event, "simpleIDE dispatch limit: three concurrent workers, two repair rounds")
                    return 0
                if repair:
                    con.execute("UPDATE run SET repair_rounds=MAX(repair_rounds,?) WHERE task=?", (repair, task))
            state = "started" if tool == "cursor" else "pending" if call_id and session else "unknown"
            if tool == "cursor" or state == "pending":
                brief_hash = hashlib.sha256(brief.strip().encode()).hexdigest()
                requested = arg.get("model", "")
                con.execute("INSERT INTO dispatch(task,agent,model,brief_length,host,session_id,child_id,tool_call_id,brief_hash,state,requested_model,observed_launch) "
                            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (task, agent, model if tool == "cursor" else "", len(brief), tool, session, child, call_id, brief_hash, state, requested, int(tool == "cursor")))
        dispatch_reply(tool, hook_event)
        return 0
    if event == "shell-guard":
        arg = payload.get("tool_input") or {}
        command = payload.get("command") or (arg.get("command") or arg.get("cmd") if isinstance(arg, dict) else "")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("Invalid shell hook command")
        cwd = payload.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            raise ValueError("Invalid shell hook working directory")
        readonly = (payload.get("agent_type") or payload.get("subagent_type")) in ("sx-planner", "sx-reviewer", "sx-scout")
        if shell_unsafe(command, root, cwd, readonly):
            msg = "simpleIDE blocked shell command: destructive or read-only role"
            if tool == "cursor": print(json.dumps({"permission": "deny", "user_message": msg}))
            elif tool == "claude": print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": msg}}))
            else: print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": msg}}))
            return 0
        if tool == "cursor": print('{"permission":"allow"}')
        return 0
    if event == "return-log":
        agent = payload.get("subagent_type") or payload.get("agent_type") or ""
        message = payload.get("last_assistant_message") or payload.get("summary") or payload.get("response") or ""
        status = re.search(r"(?m)^STATUS:\s*(\w+)", str(message))
        session, child, call_id = dispatch_identity(payload)
        brief = payload.get("task") if isinstance(payload.get("task"), str) else ""
        with con:
            con.execute("BEGIN IMMEDIATE")
            row = dispatch_match(con, tool, session, agent, child, call_id, brief, task) if agent or child or call_id else None
            if not row:
                con.execute("INSERT INTO hook_observation(host,session_id,event,detail) VALUES(?,?,?,?)", (tool,session,"unmatched-return",json.dumps({"child":child,"call":call_id})))
                print("simpleIDE: unmatched return retained; no dispatch was completed",file=sys.stderr)
            if row and not row["return_status"]:
                con.execute("UPDATE dispatch SET return_status=?,state='returned' WHERE id=?", (status.group(1) if status else "missing block", row["id"]))
        if tool == "codex": print("{}")
        return 0
    if event in ("stop-check", "resume"):
        task = selected_task(con, root, task, tool, session)
        row = con.execute("SELECT * FROM run WHERE task=?", (task,)).fetchone() if task else None
        if event == "stop-check":
            if row and not row["outcome"] and row["size"] in ("MEDIUM", "LARGE") and not row["stop_warned"]:
                con.execute("UPDATE run SET stop_warned=1 WHERE task=?", (task,)); con.commit()
                summaries = check_summary(con, root, task)
                msg = "simpleIDE: open task %s requires explicit close; %s." % (task, " | ".join(summaries) or "no checks configured")
                if tool == "cursor": print(json.dumps({"followup_message": msg}))
                else: print(json.dumps({"decision": "block", "reason": msg}))
            elif tool == "codex": print("{}")
            return 0
        if row:
            goal = con.execute("SELECT title FROM rec WHERE task=? AND kind='goal' ORDER BY id LIMIT 1", (task,)).fetchone()
            criteria = con.execute("SELECT COUNT(*) FROM rec WHERE task=? AND kind='criteria'", (task,)).fetchone()[0]
            questions = con.execute("SELECT COUNT(*) FROM rec WHERE task=? AND kind='question' AND resolved_by IS NULL", (task,)).fetchone()[0]
            command = "python3 " + shlex.quote(str(Path(__file__).resolve())) + " mem export --task " + shlex.quote(task)
            store_id = con.execute("SELECT value FROM meta WHERE key='store_id'").fetchone()[0]
            lines = ["simpleIDE task: " + task + "; store=" + store_id + "; location=" + str(store_root(root)),
                     "original request: " + ("P%d" % row["request_id"] if row["request_id"] else "unavailable"),
                     "goal: " + (re.sub(r"\s+", " ", goal[0])[:160] if goal else "missing"),
                     "criteria: %d; retrieve ALL: %s" % (criteria, command),
                     "open questions: %d; retrieve: %s" % (questions, command)]
        else:
            lines = ["simpleIDE session unbound; use sx task bind SLUG --request Pn or --host HOST --session ID"]
        if tool == "cursor": print(json.dumps({"additional_context": "\n".join(lines)}))
        else: print("\n".join(lines))
        return 0
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sx.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("mem")
    c = sub.add_parser("check"); c.add_argument("name", nargs="?"); c.add_argument("--task", default="")
    s = sub.add_parser("scope"); s.add_argument("--base", required=True); s.add_argument("--allow", action="append", default=[])
    p = sub.add_parser("pack"); p.add_argument("--task", required=True); p.add_argument("--base", required=True); p.add_argument("--allow", action="append", default=[])
    w = sub.add_parser("worktree"); w.add_argument("action", choices=("add", "merge", "clean", "reconcile")); w.add_argument("slug"); w.add_argument("piece", nargs="?"); w.add_argument("--discard", action="store_true"); w.add_argument("--apply", action="store_true")
    t = sub.add_parser("task"); ts = t.add_subparsers(dest="action", required=True)
    tb = ts.add_parser("bind"); tb.add_argument("slug"); tb.add_argument("--request"); tb.add_argument("--host", choices=("claude","cursor","codex","antigravity")); tb.add_argument("--session")
    cl = ts.add_parser("close"); cl.add_argument("slug"); cl.add_argument("--outcome", choices=("accepted","failed","abandoned"), required=True); cl.add_argument("--result", required=True); cl.add_argument("--by", choices=("user","assistant"), required=True); cl.add_argument("--refs", required=True); cl.add_argument("--exception")
    td = ts.add_parser("dispatches"); td.add_argument("slug")
    tc = ts.add_parser("cancel"); tc.add_argument("slug"); tc.add_argument("--dispatch", type=int, required=True); tc.add_argument("--refs", required=True)
    sub.add_parser("doctor")
    st = sub.add_parser("stats"); st.add_argument("--task"); st.add_argument("--cost", type=float); st.add_argument("--tokens", type=int); st.add_argument("--usage-source")
    cx = sub.add_parser("context"); cx.add_argument("mode", choices=("standalone",))
    h = sub.add_parser("hook"); h.add_argument("event", choices=("capture-request", "dispatch-guard", "shell-guard", "return-log", "stop-check", "resume")); h.add_argument("--host", choices=("claude", "cursor", "codex"))
    args, rest = ap.parse_known_args(argv)
    root = project_root()
    try:
        if args.cmd == "mem": return mem_main(rest)
        if rest: ap.error("unrecognized arguments: " + " ".join(rest))
        if args.cmd == "check": return check_cmd(root, args.name, args.task)
        if args.cmd == "scope": return scope_cmd(root, args.base, args.allow)
        if args.cmd == "pack": return pack_cmd(root, args.task, args.base, args.allow)
        if args.cmd == "worktree": return worktree_cmd(root, args.action, args.slug, args.piece, args.discard, args.apply)
        if args.cmd == "task":
            con = ledger(root)
            with con:
                con.execute("BEGIN IMMEDIATE")
                if args.action == "bind":
                    bind_task(con, args.slug, args.request, args.host, args.session)
                elif args.action == "close":
                    close_task(con, root, args)
                elif args.action == "cancel":
                    if not con.execute("UPDATE dispatch SET state='cancelled',return_status=? WHERE id=? AND task=? AND state IN ('pending','unknown','started')",
                                       ("cancelled: " + args.refs, args.dispatch, args.slug)).rowcount:
                        raise ValueError("only an active dispatch in this task can be explicitly cancelled")
                else:
                    for r in con.execute("SELECT * FROM dispatch WHERE task=?", (args.slug,)):
                        print(json.dumps(dict(r)))
            return 0
        if args.cmd == "doctor": return doctor_cmd(root)
        if args.cmd == "context":
            if (root / ".simpleide/context.json").exists():
                raise ValueError("managed worktree; use worktree reconcile")
            marker = standalone_marker(root)
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({"declared": time.time()}) + "\n")
            print(marker)
            return 0
        if args.cmd == "stats": return stats_cmd(root, args.task, args.cost, args.tokens, args.usage_source)
        if args.cmd == "hook": return hook_cmd(root, args.event, args.host)
    except (ValueError, OSError, sqlite3.Error) as err:
        print("sx: " + str(err), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
