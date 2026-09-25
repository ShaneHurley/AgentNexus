"""Append-only usage events for dashboard analytics."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UsageStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")
        self._lock = threading.Lock()

    def append(
        self,
        event: str,
        agent_id: str,
        *,
        run_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = {
            "ts": _now_iso(),
            "event": event,
            "agent_id": agent_id,
            "run_id": run_id or "",
            "meta": meta or {},
        }
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def _read_all(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self.path.is_file():
            return rows
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return rows

    def list_events(
        self,
        *,
        from_ts: str | None = None,
        to_ts: str | None = None,
        agent_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._read_all()
        out = rows
        if agent_id:
            out = [r for r in out if r.get("agent_id") == agent_id]
        if from_ts:
            out = [r for r in out if (r.get("ts") or "") >= from_ts]
        if to_ts:
            out = [r for r in out if (r.get("ts") or "") <= to_ts]
        return out
