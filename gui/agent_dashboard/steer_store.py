"""Local conversation / steer notes owned by the dashboard.

Checkpoint-style: messages are queued until the human applies them at a safe
gate (approve / resume / next start). Agents do not need a chat API.
"""
from __future__ import annotations
import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SteerStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")
        self._lock = threading.Lock()

    def _read_all(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def list(self, agent_id: str, run_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._read_all()
        out = [r for r in rows if r.get("agent_id") == agent_id]
        if run_id:
            out = [r for r in out if r.get("run_id") == run_id]
        return out[-limit:]

    def append(
        self,
        agent_id: str,
        text: str,
        *,
        run_id: str = "",
        role: str = "user",
        status: str = "queued",
    ) -> dict[str, Any]:
        msg = {
            "id": secrets.token_hex(8),
            "agent_id": agent_id,
            "run_id": run_id or "",
            "role": role,
            "text": text,
            "status": status,
            "created_at": _now(),
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        return msg

    def mark(self, message_id: str, status: str) -> dict[str, Any] | None:
        with self._lock:
            rows = self._read_all()
            found = None
            for row in rows:
                if row.get("id") == message_id:
                    row["status"] = status
                    found = row
            self.path.write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                encoding="utf-8",
            )
            return found

    def queued_for(self, agent_id: str, run_id: str | None = None) -> list[dict[str, Any]]:
        return [
            m for m in self.list(agent_id, run_id, limit=500)
            if m.get("status") == "queued" and m.get("role") == "user"
        ]
