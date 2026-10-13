"""Explicit recovery of lost built-in filesystem reads; never re-executes tools."""
from __future__ import annotations
import json
import time
from agent_core.contracts import ContractDenied
from agent_core.lifecycle import RunLock


def reconcile_read(state, run_id, operation_id, *, actor, acknowledge_unavailable=False):
    if not acknowledge_unavailable or not isinstance(actor, str) or not actor.strip() or len(actor) > 200:
        raise ContractDenied("Explicit acknowledgment and a bounded actor are required")
    with RunLock(state.path.parent / "run-locks", str(state.path.resolve()) + ":" + run_id):
        with state._lock, state._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = connection.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            op = connection.execute("SELECT * FROM tool_operations WHERE operation_id=?", (operation_id,)).fetchone()
            if not run or not op or op["run_id"] != run_id:
                raise ContractDenied("Read receipt does not belong to this run")
            if op["tool"] not in {"filesystem.read", "filesystem.list"} or op["path"] or op["expected_output_hash"]:
                raise ContractDenied("Only built-in pure filesystem reads can be reconciled")
            if op["state"] == "completed":
                result = json.loads(op["result"])
                if isinstance(result, dict) and result.get("reconciled_read") is True:
                    return result
                raise ContractDenied("Receipt already has a result")
            if op["state"] != "pending" or run["status"] not in {"RECONCILIATION_REQUIRED", "CANCEL_REQUESTED"}:
                raise ContractDenied("Run is not awaiting read reconciliation")
            if connection.execute("SELECT 1 FROM budget_reservations WHERE run_id=? AND state='reserved'", (run_id,)).fetchone():
                raise ContractDenied("Model usage is still unknown")
            if connection.execute(
                "SELECT 1 FROM budget_reservations b WHERE run_id=? AND state='settled' "
                "AND NOT EXISTS (SELECT 1 FROM invocations i WHERE i.idem_key=b.reservation_id)",
                (run_id,),
            ).fetchone():
                raise ContractDenied("Model settlement lacks a durable invocation")
            if connection.execute(
                "SELECT 1 FROM jobs WHERE run_id=? AND state IN ('pending','running','cancel_requested')",
                (run_id,),
            ).fetchone():
                raise ContractDenied("Worker outcome is still unknown")
            now = time.time()
            result = {"read_failed": True, "error": "ResultUnavailable",
                      "message": "Original read result unavailable",
                      "reconciled_read": True, "actor": actor.strip(), "reconciled_at": now}
            connection.execute(
                "UPDATE tool_operations SET state='completed',result=?,updated=? "
                "WHERE operation_id=? AND state='pending'",
                (json.dumps(result, sort_keys=True), now, operation_id),
            )
            connection.execute(
                "INSERT INTO events(run_id,old_phase,new_phase,kind,payload,idem_key,created) "
                "VALUES(?,?,?,?,?,?,?)",
                (run_id, run["phase"], run["phase"], "read_result_unavailable",
                 json.dumps({"operation_id": operation_id, "actor": actor.strip(), "tool": op["tool"]}, sort_keys=True),
                 run_id + ":reconcile-read:" + operation_id, now),
            )
            return result
