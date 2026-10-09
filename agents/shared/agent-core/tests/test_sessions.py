from pathlib import Path
import importlib.util
import sqlite3
import pytest


def store(path):
    assert importlib.util.find_spec("agent_core.sessions") is not None, "durable session store missing"
    from agent_core.sessions import SessionStore
    return SessionStore(path)


def run(s, session, **kw):
    return s.create_run(session["session_id"], "daily-coder", "fix", "/tmp", {"config": 1}, "registry", **kw)


def test_sessions_and_pins_survive_restart(tmp_path):
    p = tmp_path / "sessions.sqlite"; s = store(p)
    session = s.new_session("stable-user", "/tmp", "default")
    r = run(s, session)
    restored = store(p)
    assert restored.sessions()[0]["identity"] == "stable-user"
    assert restored.get_run(r["run_id"])["snapshot"] == {"config": 1}
    with pytest.raises(ValueError, match="configuration"):
        restored.check_pin(r["run_id"], {"config": 2}, "registry")
    with pytest.raises(ValueError, match="registry"):
        restored.check_pin(r["run_id"], {"config": 1}, "new")


def test_duplicate_task_and_cross_session_parent_are_denied(tmp_path):
    s = store(tmp_path / "sessions.sqlite"); session = s.new_session()
    r = run(s, session, task_key="once")
    with pytest.raises(ValueError, match="duplicate"):
        run(s, session, task_key="once")
    other = s.new_session()
    with pytest.raises(ValueError, match="parent"):
        run(s, other, parent_id=r["run_id"])


def test_interrupted_call_keeps_exposure_across_restart(tmp_path):
    p=tmp_path / "sessions.sqlite"; s=store(p); session=s.new_session(); r=run(s,session)
    s.begin_call(r["run_id"], "call-id", 100, .5)
    restored=store(p)
    assert restored.pending_calls(r["run_id"])[0]["call_id"] == "call-id"
    assert restored.accounting(r["run_id"])["reserved_usd"] == .5
    with pytest.raises(ValueError, match="reconciliation"):
        restored.begin_call(r["run_id"], "another-call", 100, .5)
    restored.finish_call("call-id", "unknown")
    assert restored.get_run(r["run_id"])["status"] == "RECONCILIATION_REQUIRED"
    assert restored.accounting(r["run_id"])["reserved_usd"] == .5
    with pytest.raises(ValueError): restored.finish_call("call-id", "confirmed", tokens=-1, usd=0)


def test_parent_accounting_and_cancel_reaches_children(tmp_path):
    s=store(tmp_path / "sessions.sqlite"); session=s.new_session(); parent=run(s,session,limit_usd=1)
    child=run(s,session,parent_id=parent["run_id"])
    s.begin_call(child["run_id"], "child-call", 1, .6)
    with pytest.raises(ValueError, match="budget"):
        s.begin_call(parent["run_id"], "parent-call", 1, .6)
    assert s.accounting(parent["run_id"])["reserved_usd"] == .6
    s.request_cancel(parent["run_id"])
    assert s.get_run(child["run_id"])["cancel_requested"]
    with pytest.raises(ValueError, match="cancel"):
        s.begin_call(parent["run_id"], "next", 0, 0)
    with pytest.raises(ValueError, match="outstanding"):
        s.acknowledge_cancel(child["run_id"])
    s.finish_call("child-call", "not_dispatched")
    s.acknowledge_cancel(child["run_id"])
    assert s.get_run(child["run_id"])["status"] == "CANCELLED"
    s.acknowledge_cancel(parent["run_id"])
    assert s.get_run(parent["run_id"])["status"] == "CANCELLED"


def test_newer_schema_refused_without_modification_and_backup_upgrade(tmp_path):
    p=tmp_path / "sessions.sqlite"; s=store(p); session=s.new_session()
    with sqlite3.connect(p) as c: c.execute("PRAGMA user_version=999")
    with pytest.raises(ValueError, match="newer"): store(p)
    with sqlite3.connect(p) as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 999
        c.execute("PRAGMA user_version=1")
    restored=store(p)
    assert restored.sessions()[0]["session_id"] == session["session_id"]
    assert p.with_name(p.name + ".pre-v2").is_file()


def test_completed_calls_settle_once_and_alias_import_has_provenance(tmp_path):
    s=store(tmp_path / "sessions.sqlite"); session=s.new_session(); r=run(s,session)
    s.set_alias(r["run_id"], "legacy-id", completeness="partial", provenance={"source": "legacy-state"})
    assert s.get_run("legacy-id")["run_id"] == r["run_id"]
    assert s.get_run(r["run_id"])["completeness"] == "partial"
    s.begin_call(r["run_id"], "once", 10, .5)
    s.finish_call("once", "confirmed", tokens=8, usd=.3, usage_status="reported")
    s.finish_call("once", "confirmed", tokens=8, usd=.3, usage_status="reported")
    assert s.accounting(r["run_id"])["reported_usd"] == .3
    assert s.accounting(r["run_id"])["reserved_usd"] == 0
    assert len(s.events(r["run_id"])) >= 3


@pytest.mark.parametrize("field,value", [("live", True), ("deadline", 9999999999)])
def test_children_cannot_widen_parent_execution_policy(tmp_path, field, value):
    s=store(tmp_path / "sessions.sqlite"); session=s.new_session()
    parent=run(s,session,live=False,deadline=1000)
    with pytest.raises(ValueError,match="parent"):
        run(s,session,parent_id=parent["run_id"],**{field:value})


def test_child_limits_intersect_parent_and_usage_does_not_mix_own_receipts(tmp_path):
    s=store(tmp_path / "sessions.sqlite"); session=s.new_session()
    parent=run(s,session,limit_usd=.5,limit_tokens=100)
    child=run(s,session,parent_id=parent["run_id"],limit_usd=5,limit_tokens=1000)
    assert child["limit_usd"] == .5 and child["limit_tokens"] == 100
    s.begin_call(child["run_id"],"child",10,.1)
    s.finish_call("child","confirmed",tokens=10,usd=.1)
    assert s.accounting(parent["run_id"],descendants=False)["tokens"] == 0
    assert s.accounting(parent["run_id"])["tokens"] == 10


@pytest.mark.parametrize("deadline", [float("nan"),float("inf"),"later"])
def test_invalid_deadlines_are_denied(tmp_path,deadline):
    s=store(tmp_path / "sessions.sqlite"); session=s.new_session()
    with pytest.raises(ValueError,match="deadline"):
        run(s,session,deadline=deadline)


@pytest.mark.parametrize("change", ["registry","config","blocked","reconciliation"])
def test_parent_drift_and_blocked_state_cannot_delegate(tmp_path,change):
    s=store(tmp_path / "sessions.sqlite"); session=s.new_session(); parent=run(s,session)
    if change in ("blocked","reconciliation"): s.update(parent["run_id"],"BLOCKED" if change=="blocked" else "RECONCILIATION_REQUIRED")
    with pytest.raises(ValueError,match="parent"):
        s.create_run(session["session_id"],"daily-coder","child","/tmp",{"config":2 if change=="config" else 1},"new" if change=="registry" else "registry",parent_id=parent["run_id"])
