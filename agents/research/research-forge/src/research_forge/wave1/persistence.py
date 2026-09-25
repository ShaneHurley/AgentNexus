"""Durable Wave 1 RunState persistence (REC-01).

States live under ``{repo_root}/runs/wave1/{run_id}/state.json`` with atomic replace.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from research_forge.wave1.orchestrator import RunState

SCHEMA_VERSION = "wave1-run-state/1.0"


def runs_root(repo_root: Path) -> Path:
    return (repo_root / "runs" / "wave1").resolve()


def state_path(repo_root: Path, run_id: str) -> Path:
    safe = "".join(c for c in run_id if c.isalnum() or c in ("-", "_", "."))
    if not safe or safe != run_id:
        raise ValueError(f"invalid run_id: {run_id!r}")
    return runs_root(repo_root) / safe / "state.json"


def save_run_state(repo_root: Path, state: RunState | dict[str, Any], *, live: bool = False) -> Path:
    data = state.to_dict() if isinstance(state, RunState) else dict(state)
    run_id = str(data.get("run_id") or "")
    if not run_id:
        raise ValueError("run_id required")
    path = state_path(repo_root, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "live": bool(live),
        "state": data,
    }
    raw = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(raw)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path


def load_run_state(repo_root: Path, run_id: str) -> tuple[RunState, dict[str, Any]]:
    path = state_path(repo_root, run_id)
    if not path.is_file():
        raise FileNotFoundError(f"no persisted state for run {run_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported state schema: {payload.get('schema_version')}")
    raw_state = payload.get("state") or {}
    return RunState.from_dict(raw_state), payload


def status_payload(repo_root: Path, run_id: str | None) -> dict[str, Any]:
    root = runs_root(repo_root)
    if run_id:
        path = state_path(repo_root, run_id)
        if not path.is_file():
            return {"ok": False, "run_id": run_id, "found": False}
        st, meta = load_run_state(repo_root, run_id)
        return {
            "ok": True,
            "found": True,
            "run_id": st.run_id,
            "phase": st.phase,
            "paused": st.paused,
            "live": bool(meta.get("live")),
            "path": str(path),
            "state": st.to_dict(),
        }
    if not root.is_dir():
        return {"ok": True, "runs": [], "latest": None}
    runs: list[dict[str, Any]] = []
    for child in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        sp = child / "state.json"
        if not sp.is_file():
            continue
        try:
            data = json.loads(sp.read_text(encoding="utf-8"))
            st = data.get("state") or {}
            runs.append(
                {
                    "run_id": st.get("run_id") or child.name,
                    "phase": st.get("phase"),
                    "paused": st.get("paused"),
                    "mtime": sp.stat().st_mtime,
                }
            )
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    latest = runs[0]["run_id"] if runs else None
    return {"ok": True, "runs": runs, "latest": latest}
