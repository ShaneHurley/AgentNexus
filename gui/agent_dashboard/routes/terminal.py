"""Log-shell terminal session API."""
from __future__ import annotations

from pathlib import Path

from . import common as c


def handle_get(handler, path: str, query: dict, parts: list[str]) -> bool:
    ctx = c.ctx(handler)
    reg = ctx["terminal_registry"]

    if path == "/api/terminal/profiles":
        c.send(handler, 200, {"profiles": reg.load_profiles()})
        return True

    if path == "/api/terminal/sessions":
        c.send(handler, 200, {"sessions": reg.list_sessions()})
        return True

    if len(parts) >= 4 and parts[0] == "api" and parts[1] == "terminal" and parts[2] == "sessions":
        session_id = parts[3]
        if len(parts) == 5 and parts[4] == "log":
            log = reg.read_log(session_id)
            c.send(handler, 200, {"id": session_id, "log": log})
            return True
        if len(parts) == 4:
            session = reg.get_session(session_id)
            if not session:
                c.send(handler, 404, {"error": "not found"})
                return True
            c.send(handler, 200, session)
            return True
    return False


def handle_post(handler, path: str, body: dict, parts: list[str]) -> bool:
    ctx = c.ctx(handler)
    reg = ctx["terminal_registry"]

    if path == "/api/terminal/sessions":
        profile_id = (body.get("profile_id") or body.get("profile") or "").strip()
        if not profile_id:
            c.send(handler, 400, {"error": "profile_id is required"})
            return True
        cwd_raw = body.get("cwd")
        cwd = Path(cwd_raw).resolve() if cwd_raw else None
        try:
            session = reg.spawn(profile_id, cwd=cwd)
        except KeyError:
            c.send(handler, 404, {"error": "unknown or disabled profile"})
            return True
        except ValueError as exc:
            c.send(handler, 400, {"error": str(exc)})
            return True
        except RuntimeError as exc:
            c.send(handler, 502, {"error": str(exc)})
            return True
        c.send(handler, 201, session)
        return True

    if len(parts) == 5 and parts[0] == "api" and parts[1] == "terminal" and parts[2] == "sessions" and parts[4] == "stop":
        session_id = parts[3]
        try:
            session = reg.stop(session_id)
        except KeyError:
            c.send(handler, 404, {"error": "not found"})
            return True
        c.send(handler, 200, session)
        return True
    return False
