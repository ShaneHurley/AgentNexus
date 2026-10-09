"""Shared supervisor access for dashboard engine adapters."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import threading


class SupervisorAccess:
    def __init__(self, engine: str, options: dict[str, Any], repository: Path):
        self.engine = engine
        self.options = options
        from agent_core.runtime_authority import repository_root
        self.repository = Path(options.get("repository_root") or repository_root()).resolve()
        self.directory = Path(options.get("supervisor_dir") or self.repository / ".agentnexus").resolve()
        self.session_id = options.get("session_id")
        self._explicit_session = bool(self.session_id)
        self._workspace_sessions = {}
        self._session_lock = threading.Lock()

    def supervisor(self):
        from agent_core.supervisor import Supervisor
        return Supervisor(self.directory, repository=self.repository)

    def owns(self, run_id: str) -> bool:
        try:
            return self.supervisor().status(run_id).get("engine") == self.engine
        except (KeyError, FileNotFoundError):
            return False

    def start(self, request: Any, workspace: Path, *, live: bool = False, provider: str = "mock") -> dict[str, Any]:
        supervisor = self.supervisor()
        with self._session_lock:
            if not self._explicit_session:
                workspace_key=str(Path(workspace).resolve())
                if workspace_key not in self._workspace_sessions:
                    self._workspace_sessions[workspace_key]=supervisor.new_session(project=workspace_key)["session_id"]
                self.session_id=self._workspace_sessions[workspace_key]
            session_id=self.session_id
        row = supervisor.create_run(session_id, self.engine, request, str(workspace), live=live, provider=provider)
        row = supervisor.execute(row["run_id"])
        return {**row, "accepted": True, "queued": False,
                "execution_started": bool(row.get("execution_started", False)),
                "acknowledged": bool(row.get("acknowledged", False))}

    def resume(self, run_id: str, answers=None) -> dict[str, Any]:
        return {**self.supervisor().execute(run_id, answers=answers), "accepted": True}

    def cancel(self, run_id: str) -> dict[str, Any]:
        row = self.supervisor().cancel(run_id)
        return {**row, "accepted": True, "cancellation_requested": True,
                "cancelled": bool(row.get("cancelled", False)),
                "acknowledged": bool(row.get("acknowledged", False))}

    def normalize(self, row: dict[str, Any], agent_id: str) -> dict[str, Any]:
        request = row.get("request", "")
        if isinstance(request, dict):
            request = request.get("topic") or request.get("objective") or ""
        return {**row, "agent_id": agent_id, "phase": row.get("phase", ""),
                "request": request, "est_usd": sum(row.get("accounting",{}).get(key,0) for key in ("estimated_usd","reported_usd","reconciled_usd")), "raw": row}

    def activity(self, run_id: str, agent_id: str, limit: int) -> list[dict[str, Any]]:
        supervisor = self.supervisor()
        row = supervisor.status(run_id)
        return [{"run_id": row["run_id"], "agent_id": agent_id,
                 "ts": event.get("created", ""), "role": "supervisor",
                 "kind": event.get("kind", "event"),
                 "summary": event.get("kind", "event"), "raw": event}
                for event in supervisor.store.events(row["run_id"])[-limit:]]

    def metrics(self) -> dict[str, Any]:
        supervisor = self.supervisor()
        rows = supervisor.runs(engine=self.engine, limit=10000)
        accounting = [supervisor.store.accounting(row["run_id"], descendants=False) for row in rows]
        return {"totals": {"runs": len(rows),
                           "queued": sum(row["status"] == "QUEUED" for row in rows),
                           "active": sum(row["status"] == "RUNNING" for row in rows),
                           "waiting_human": sum(row["status"] == "WAITING_HUMAN" for row in rows),
                           "complete": sum(row["status"] in ("COMPLETE", "SIMULATED") for row in rows),
                           "failed": sum(row["status"] == "FAILED" for row in rows)},
                "spend_usd": sum(sum(item.get(key, 0) for key in
                                     ("estimated_usd", "reported_usd", "reconciled_usd"))
                                 for item in accounting),
                "accounting_scope": "supervised engine runs", "supervised": True}
