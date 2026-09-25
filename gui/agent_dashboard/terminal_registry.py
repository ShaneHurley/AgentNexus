"""Log-shell session registry (spawn + log poll + stop, no PTY)."""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TerminalRegistry:
    def __init__(self, data_dir: Path, profiles_path: Path):
        self.sessions_dir = data_dir / "terminal_sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_path = profiles_path
        self._lock = threading.Lock()
        self._sessions: dict[str, dict[str, Any]] = {}
        self._procs: dict[str, subprocess.Popen] = {}

    def load_profiles(self) -> list[dict[str, Any]]:
        if not self.profiles_path.is_file():
            return []
        try:
            data = json.loads(self.profiles_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        profiles = data.get("profiles") if isinstance(data, dict) else []
        out: list[dict[str, Any]] = []
        for p in profiles if isinstance(profiles, list) else []:
            if not isinstance(p, dict) or not p.get("id"):
                continue
            enabled = p.get("enabled", True)
            out.append({
                "id": p["id"],
                "label": p.get("label") or p["id"],
                "enabled": bool(enabled),
                "command": p.get("command") or [],
            })
        return out

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        for p in self.load_profiles():
            if p["id"] == profile_id and p.get("enabled", True):
                return p
        return None

    def spawn(self, profile_id: str, *, cwd: Path | None = None) -> dict[str, Any]:
        profile = self.get_profile(profile_id)
        if not profile:
            raise KeyError("unknown or disabled profile")
        cmd = list(profile.get("command") or [])
        if not cmd:
            raise ValueError("profile has empty command")
        if cmd[0] == "python":
            cmd[0] = sys.executable
        session_id = secrets.token_hex(8)
        log_path = self.sessions_dir / f"{session_id}.log"
        meta_path = self.sessions_dir / f"{session_id}.json"

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

        with log_path.open("w", encoding="utf-8", errors="replace") as log_fh:
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(cwd) if cwd else None,
                    stdout=log_fh,
                    stderr=subprocess.STDOUT,
                    creationflags=creationflags,
                )
            except OSError as exc:
                raise RuntimeError(f"spawn failed: {exc}") from exc

        time.sleep(0.15)
        if proc.poll() is not None:
            tail = _tail_file(log_path)
            raise RuntimeError(f"process exited early (code {proc.returncode}). {tail}")

        session = {
            "id": session_id,
            "profile_id": profile_id,
            "label": profile.get("label") or profile_id,
            "state": "running",
            "pid": proc.pid,
            "log_path": str(log_path),
            "created_at": _now(),
            "stopped_at": None,
        }
        meta_path.write_text(json.dumps(session, indent=2), encoding="utf-8")
        with self._lock:
            self._sessions[session_id] = session
            self._procs[session_id] = proc
        return session

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            self._refresh_all()
            return [self._public(s) for s in self._sessions.values()]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._ensure_loaded(session_id)
            self._refresh_one(session_id)
            s = self._sessions.get(session_id)
            return self._public(s) if s else None

    def read_log(self, session_id: str, *, tail_lines: int = 200) -> str:
        with self._lock:
            self._ensure_loaded(session_id)
        path = self.sessions_dir / f"{session_id}.log"
        if not path.is_file():
            return ""
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-tail_lines:])

    def stop(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded(session_id)
            proc = self._procs.get(session_id)
            session = self._sessions.get(session_id)
            if not session:
                raise KeyError(session_id)
            if proc and proc.poll() is None:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                    )
                else:
                    proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
            session["state"] = "stopped"
            session["stopped_at"] = _now()
            self._persist(session)
            self._procs.pop(session_id, None)
            return self._public(session)

    def _public(self, session: dict[str, Any] | None) -> dict[str, Any]:
        if not session:
            return {}
        return {
            "id": session["id"],
            "profile_id": session["profile_id"],
            "label": session["label"],
            "state": session["state"],
            "pid": session.get("pid"),
            "created_at": session.get("created_at"),
            "stopped_at": session.get("stopped_at"),
        }

    def _ensure_loaded(self, session_id: str) -> None:
        if session_id in self._sessions:
            return
        meta_path = self.sessions_dir / f"{session_id}.json"
        if meta_path.is_file():
            try:
                self._sessions[session_id] = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

    def _refresh_one(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if not session or session.get("state") != "running":
            return
        proc = self._procs.get(session_id)
        if proc is None:
            pid = session.get("pid")
            if pid and not _pid_alive(pid):
                session["state"] = "stopped"
                session["stopped_at"] = _now()
                self._persist(session)
            return
        if proc.poll() is not None:
            session["state"] = "stopped"
            session["stopped_at"] = _now()
            self._procs.pop(session_id, None)
            self._persist(session)

    def _refresh_all(self) -> None:
        for p in self.sessions_dir.glob("*.json"):
            self._ensure_loaded(p.stem)
        for sid in list(self._sessions):
            self._refresh_one(sid)

    def _persist(self, session: dict[str, Any]) -> None:
        meta_path = self.sessions_dir / f"{session['id']}.json"
        meta_path.write_text(json.dumps(session, indent=2), encoding="utf-8")


def _tail_file(path: Path, n: int = 8) -> str:
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:])


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
