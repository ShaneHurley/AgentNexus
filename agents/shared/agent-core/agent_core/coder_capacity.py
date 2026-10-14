"""Read-only capacity preview for the contained coder."""
import json
import sqlite3
from daily_coder.budget import _today

def capacity_snapshot(supervisor,run_id):
    row=supervisor.store.get_run(run_id)
    if row["snapshot"].get("execution_policy")!="coder-v1": return None
    root=supervisor.adapters["daily-coder"].root
    config=json.loads((root/"config/default.json").read_text())
    ceiling=config["limits"]["max_tokens_per_day"]
    source="default"
    override="codex_subscription_max_tokens_per_day"
    if row["snapshot"].get("provider")=="codex_cli" and override in config["limits"]:
        ceiling=config["limits"][override]
        if ceiling is not None and (type(ceiling) is not int or ceiling<=0):
            raise ValueError("invalid Codex subscription daily token limit")
        source=override
    day=_today()
    spent=reserved=used=own_reserved=0
    database=root/".daily-coder/state.sqlite"
    if database.exists():
        with sqlite3.connect(database.as_uri()+"?mode=ro",uri=True) as connection:
            record=connection.execute("SELECT tokens FROM spend WHERE day=?",(day,)).fetchone()
            spent=int(record[0]) if record else 0
            reserved=int(connection.execute("SELECT COALESCE(SUM(estimated_tokens),0) FROM budget_reservations WHERE day=? AND state='reserved'",(day,)).fetchone()[0])
            if row.get("legacy_id"):
                key=row["legacy_id"]
                used=int(connection.execute("SELECT COALESCE(SUM(input_tokens+output_tokens),0) FROM usage WHERE run_id=?",(key,)).fetchone()[0])
                used+=int(connection.execute("SELECT COALESCE(SUM(actual_tokens),0) FROM budget_reservations b WHERE run_id=? AND state='settled' AND NOT EXISTS (SELECT 1 FROM invocations i WHERE i.idem_key=b.reservation_id)",(key,)).fetchone()[0])
                own_reserved=int(connection.execute("SELECT COALESCE(SUM(estimated_tokens),0) FROM budget_reservations WHERE run_id=? AND state='reserved'",(key,)).fetchone()[0])
    task_limit=min(row["limit_tokens"],row["snapshot"]["task_contract"]["limits"]["tokens"])
    root_row=supervisor.store.get_run(row["root_id"])
    parent=supervisor.store.accounting(row["root_id"])
    parent_available=max(0,root_row["limit_tokens"]-parent["tokens"]-parent["reserved_tokens"])
    return {"schema_version":1,"kind":"coder_capacity","run_id":run_id,"budget_day":day,"budget_day_convention":"native-local-date",
            "daily_ceiling":ceiling,"daily_limit_source":source,"consumed_tokens":spent,"outstanding_reserved_tokens":reserved,
            "available_daily_tokens":None if ceiling is None else max(0,ceiling-spent-reserved),
            "remaining_task_grant":max(0,task_limit-used-own_reserved),
            "available_parent_tokens":parent_available,
            "note":"Preview only; atomic dispatch reservations remain authoritative."}

def announce_capacity(supervisor,run_id):
    import sys
    result=capacity_snapshot(supervisor,run_id)
    if result is not None:
        row=supervisor.store.get_run(run_id)
        supervisor.store.update(run_id,row["status"],payload={"capacity_snapshot":result})
        print(json.dumps(result,sort_keys=True,allow_nan=False),file=sys.stderr,flush=True)
    return result
