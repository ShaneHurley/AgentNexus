import json
import sqlite3
from daily_coder.budget import _today
from types import SimpleNamespace
from agent_core.coder_capacity import capacity_snapshot

def fixture(tmp_path):
    root=tmp_path
    (root/"config").mkdir()
    (root/"config/default.json").write_text(json.dumps({"limits":{"max_tokens_per_day":750000}}))
    (root/".daily-coder").mkdir()
    database=root/".daily-coder/state.sqlite"
    with sqlite3.connect(database) as connection:
        connection.executescript("CREATE TABLE spend(day TEXT,tokens INT);CREATE TABLE budget_reservations(reservation_id TEXT,run_id TEXT,day TEXT,state TEXT,estimated_tokens INT,actual_tokens INT);CREATE TABLE usage(run_id TEXT,input_tokens INT,output_tokens INT);CREATE TABLE invocations(idem_key TEXT);")
        day=_today()
        connection.execute("INSERT INTO spend VALUES(?,?)",(day,123000))
        connection.execute("INSERT INTO budget_reservations VALUES(?,?,?,?,?,?)",("unknown","other",day,"reserved",42000,0))
        connection.execute("INSERT INTO usage VALUES(?,?,?)",("native",18000,2000))
    row={"snapshot":{"execution_policy":"coder-v1","task_contract":{"limits":{"tokens":80000}}},"root_id":"run","limit_tokens":50000,"legacy_id":"native"}
    store=SimpleNamespace(get_run=lambda key:row,accounting=lambda key:{"tokens":20000,"reserved_tokens":0})
    supervisor=SimpleNamespace(store=store,adapters={"daily-coder":SimpleNamespace(root=root)})
    return supervisor,database

def test_capacity_retains_unknown_reservations_and_lower_limits(tmp_path):
    supervisor,database=fixture(tmp_path)
    before=database.read_bytes()
    result=capacity_snapshot(supervisor,"run")
    assert result["available_daily_tokens"]==585000
    assert result["outstanding_reserved_tokens"]==42000
    assert result["remaining_task_grant"]==30000
    assert result["available_parent_tokens"]==30000
    assert capacity_snapshot(supervisor,"run")==result
    assert database.read_bytes()==before

def test_orphan_settled_usage_and_own_reservation_reduce_task_grant(tmp_path):
    supervisor,database=fixture(tmp_path)
    day=_today()
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO budget_reservations VALUES(?,?,?,?,?,?)",("orphan","native",day,"settled",0,7000))
        connection.execute("INSERT INTO budget_reservations VALUES(?,?,?,?,?,?)",("pending","native",day,"reserved",5000,0))
    assert capacity_snapshot(supervisor,"run")["remaining_task_grant"]==18000

def test_legacy_has_no_new_capacity_notice(tmp_path):
    supervisor,_=fixture(tmp_path)
    supervisor.store.get_run("run")["snapshot"]["execution_policy"]="legacy"
    assert capacity_snapshot(supervisor,"run") is None

def test_preview_uses_authoritative_budget_day_at_utc_rollover(tmp_path,monkeypatch):
    import agent_core.coder_capacity as module
    supervisor,database=fixture(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO spend VALUES(?,?)",("2001-01-01",600000))
        connection.execute("INSERT INTO budget_reservations VALUES(?,?,?,?,?,?)",("old-unknown","other","2001-01-01","reserved",100000,0))
    monkeypatch.setattr(module,"_today",lambda:"2001-01-01")
    result=module.capacity_snapshot(supervisor,"run")
    assert result["budget_day"]=="2001-01-01"
    assert result["available_daily_tokens"]==50000
