"""Unified /api/agents/* routes."""
from __future__ import annotations

from typing import Any

from . import common as c


def _log_usage(ctx: dict, event: str, agent_id: str, run_id: str | None = None, meta: dict | None = None) -> None:
    store = ctx.get("usage_store")
    if store:
        store.append(event, agent_id, run_id=run_id, meta=meta or {})


def handle_get(handler, path: str, query: dict, parts: list[str]) -> bool:
    if not (len(parts) >= 2 and parts[0] == "api" and parts[1] == "agents"):
        return False
    ctx = c.ctx(handler)
    registry = ctx["registry"]

    if path == "/api/agents":
        c.send(handler, 200, registry.list_agents())
        return True

    if len(parts) < 3:
        return False
    agent_id = parts[2]
    try:
        adapter = registry.get(agent_id)
    except KeyError:
        c.send(handler, 404, {"error": "unknown agent"})
        return True

    if len(parts) == 3:
        health = adapter.health()
        backend = {}
        if hasattr(adapter, "backend_status"):
            try:
                backend = adapter.backend_status()
            except Exception as exc:  # noqa: BLE001
                backend = {"state": "error", "message": str(exc), "startable": False}
        online = bool(health.get("online"))
        if backend:
            if backend.get("state") == "unauthorized":
                online = False
            elif backend.get("online") and backend.get("auth_ok"):
                online = True
            elif backend.get("online") and not backend.get("startable", True):
                online = True
        c.send(handler, 200, {
            "id": agent_id,
            "name": adapter.name,
            "description": adapter.description,
            "capabilities": adapter.capabilities(),
            "online": online,
            "detail": health.get("detail"),
            "backend": backend,
        })
        return True

    resource = parts[3]
    try:
        if resource == "runs" and len(parts) == 4:
            c.send(handler, 200, adapter.list_runs(c.limit(query)))
            return True
        if resource == "runs" and len(parts) == 5:
            c.send(handler, 200, adapter.get_run(parts[4]))
            return True
        if resource == "runs" and len(parts) == 6 and parts[5] == "activity":
            c.send(handler, 200, adapter.activity(parts[4], c.limit(query)))
            return True
        if resource == "approvals":
            c.send(handler, 200, adapter.pending_approvals())
            return True
        if resource == "activity":
            rid = query.get("run_id", [None])[0]
            c.send(handler, 200, adapter.activity(rid, c.limit(query)))
            return True
        if resource == "metrics":
            c.send(handler, 200, adapter.metrics())
            return True
        if resource == "thread":
            rid = query.get("run_id", [""])[0]
            c.send(handler, 200, registry.steer.list(agent_id, rid or None))
            return True
        if resource == "backend":
            if not hasattr(adapter, "backend_status"):
                c.send(handler, 404, {"error": "backend control not supported"})
                return True
            c.send(handler, 200, adapter.backend_status())
            return True
    except ValueError as exc:
        c.send(handler, 400, {"error": str(exc)})
        return True
    except KeyError:
        c.send(handler, 404, {"error": "unknown run"})
        return True
    except RuntimeError as exc:
        c.send(handler, 502, {"error": str(exc)})
        return True
    return False


def handle_post(handler, path: str, body: dict, parts: list[str]) -> bool:
    if len(parts) < 3 or parts[0] != "api" or parts[1] != "agents":
        return False
    ctx = c.ctx(handler)
    registry: Any = ctx["registry"]
    agent_id = parts[2]
    try:
        adapter = registry.get(agent_id)
    except KeyError:
        c.send(handler, 404, {"error": "unknown agent"})
        return True

    try:
        if len(parts) == 4 and parts[3] == "runs":
            if not body.get("request"):
                c.send(handler, 400, {"error": "request is required"})
                return True
            result = adapter.start_run(body["request"], **{k: v for k, v in body.items() if k != "request"})
            registry.steer.append(
                agent_id,
                f"Started: {body['request'][:200]}",
                run_id=result.get("run_id", ""),
                role="system",
                status="delivered",
            )
            _log_usage(ctx, "run_start", agent_id, result.get("run_id"), {"accepted": result.get("accepted")})
            c.send(handler, 202, result)
            return True

        if len(parts) == 4 and parts[3] == "backend":
            action = (body.get("action") or "").lower()
            if action == "start":
                if not hasattr(adapter, "start_backend"):
                    c.send(handler, 404, {"error": "backend control not supported"})
                    return True
                result = adapter.start_backend(force=bool(body.get("force")), provider=body.get("provider"))
                c.send(handler, 200, result)
                return True
            if action == "stop":
                if not hasattr(adapter, "stop_backend"):
                    c.send(handler, 404, {"error": "backend control not supported"})
                    return True
                c.send(handler, 200, adapter.stop_backend(force=bool(body.get("force"))))
                return True
            if action == "restart":
                if not hasattr(adapter, "start_backend"):
                    c.send(handler, 404, {"error": "backend control not supported"})
                    return True
                if hasattr(adapter, "stop_backend"):
                    adapter.stop_backend(force=True)
                result = adapter.start_backend(force=True, provider=body.get("provider"))
                c.send(handler, 200, result)
                return True
            if action == "set_token":
                if not hasattr(adapter, "set_backend_token"):
                    c.send(handler, 404, {"error": "backend control not supported"})
                    return True
                c.send(handler, 200, adapter.set_backend_token(body.get("token") or ""))
                return True
            if action == "set_provider":
                if not hasattr(adapter, "set_provider"):
                    c.send(handler, 404, {"error": "provider selection not supported"})
                    return True
                try:
                    c.send(handler, 200, adapter.set_provider(body.get("provider") or "mock"))
                except ValueError as exc:
                    c.send(handler, 400, {"error": str(exc)})
                return True
            c.send(handler, 400, {"error": "action must be start|stop|restart|set_token|set_provider"})
            return True

        if len(parts) == 4 and parts[3] == "thread":
            text = (body.get("text") or "").strip()
            if not text:
                c.send(handler, 400, {"error": "text is required"})
                return True
            msg = registry.steer.append(
                agent_id, text,
                run_id=body.get("run_id") or "",
                role=body.get("role") or "user",
                status="queued",
            )
            c.send(handler, 201, msg)
            return True

        if len(parts) == 5 and parts[3] == "thread" and parts[4] == "apply":
            run_id = body.get("run_id") or ""
            queued = registry.steer.queued_for(agent_id, run_id or None)
            notes = []
            for m in queued:
                registry.steer.mark(m["id"], "applied")
                notes.append(m["text"])
            combined = "\n".join(notes)
            if body.get("also_approve") and run_id:
                adapter.approve(run_id, reject=False, note=combined or None)
            resume_result = None
            if body.get("also_resume") and run_id:
                resume_result = adapter.resume(run_id)
                if not resume_result.get("accepted"):
                    _log_usage(ctx, "resume", agent_id, run_id, {"accepted": False})
                    c.send(
                        handler,
                        c.resume_http_status(resume_result),
                        {"applied": len(queued), "note": combined, "resume": resume_result},
                    )
                    return True
                _log_usage(ctx, "resume", agent_id, run_id, {"accepted": True})
            payload: dict[str, Any] = {"applied": len(queued), "note": combined}
            if resume_result is not None:
                payload["resume"] = resume_result
            c.send(handler, 200, payload)
            return True

        if len(parts) == 6 and parts[3] == "runs":
            run_id, action = parts[4], parts[5]
            if action == "approve":
                queued = registry.steer.queued_for(agent_id, run_id)
                note = body.get("note") or "\n".join(m["text"] for m in queued)
                for m in queued:
                    registry.steer.mark(m["id"], "applied")
                result = adapter.approve(
                    run_id,
                    reject=bool(body.get("reject")),
                    note=note or None,
                    kind=body.get("kind") or "plan",
                )
                _log_usage(ctx, "approve", agent_id, run_id, {"reject": bool(body.get("reject"))})
                c.send(handler, 200, result)
                return True
            if action == "resume":
                result = adapter.resume(run_id)
                _log_usage(ctx, "resume", agent_id, run_id, {"accepted": result.get("accepted")})
                c.send(handler, c.resume_http_status(result), result)
                return True
            if action == "cancel":
                result = adapter.cancel(run_id)
                _log_usage(ctx, "cancel", agent_id, run_id, {})
                c.send(handler, 200, result)
                return True
    except KeyError:
        c.send(handler, 404, {"error": "unknown run"})
        return True
    except RuntimeError as exc:
        c.send(handler, 502, {"error": str(exc)})
        return True
    except Exception as exc:  # noqa: BLE001
        c.send(handler, 500, {"error": str(exc)})
        return True
    return False
