"""Health + OpenAPI hub metadata."""
from __future__ import annotations

from typing import Any

from . import common as c

# Hub-owned routes only (stable /api surface for OpenAPI parity tests).
HUB_OPENAPI_PATHS: dict[str, dict[str, Any]] = {
    "/api/health": {"get": {"summary": "Service health"}},
    "/api/agents": {"get": {"summary": "List agents"}},
    "/api/agents/{agent_id}": {"get": {"summary": "Agent detail"}},
    "/api/agents/{agent_id}/runs": {
        "get": {"summary": "List runs"},
        "post": {"summary": "Start run", "requestBody": {"required": ["request"]}},
    },
    "/api/agents/{agent_id}/runs/{run_id}": {"get": {"summary": "Run detail"}},
    "/api/agents/{agent_id}/runs/{run_id}/activity": {"get": {"summary": "Run activity"}},
    "/api/agents/{agent_id}/runs/{run_id}/approve": {"post": {"summary": "Approve or reject gate"}},
    "/api/agents/{agent_id}/runs/{run_id}/resume": {"post": {"summary": "Resume run"}},
    "/api/agents/{agent_id}/runs/{run_id}/cancel": {"post": {"summary": "Cancel run"}},
    "/api/agents/{agent_id}/approvals": {"get": {"summary": "Pending approvals"}},
    "/api/agents/{agent_id}/activity": {"get": {"summary": "Activity feed"}},
    "/api/agents/{agent_id}/metrics": {"get": {"summary": "Agent metrics"}},
    "/api/agents/{agent_id}/thread": {
        "get": {"summary": "Steer thread"},
        "post": {"summary": "Queue steer note"},
    },
    "/api/agents/{agent_id}/thread/apply": {"post": {"summary": "Apply queued steer notes"}},
    "/api/agents/{agent_id}/backend": {
        "get": {"summary": "Backend status"},
        "post": {"summary": "Backend control actions"},
    },
    "/api/usage": {"get": {"summary": "Usage events and normalized metrics"}},
    "/api/home/snapshot": {"get": {"summary": "Home dashboard snapshot"}},
    "/api/docs": {"get": {"summary": "List documentation files"}},
    "/api/docs/{name}": {"get": {"summary": "Fetch documentation markdown"}},
    "/api/config/overlay": {
        "get": {"summary": "Read config overlay"},
        "post": {"summary": "Write config overlay (data_dir)"},
    },
    "/api/setup/runtimes": {"get": {"summary": "Configured LLM providers for composer"}},
    "/api/setup/secrets": {
        "get": {"summary": "List secret fingerprints (no values)"},
        "post": {"summary": "Set or delete a Daily Coder provider secret"},
    },
    "/api/setup/palette": {"get": {"summary": "Skills and subagents for slash picker"}},
    "/api/setup/expected-agents": {"get": {"summary": "Config vs loaded agent ids (stale hub check)"}},
    "/api/openapi.json": {"get": {"summary": "Hub OpenAPI document"}},
    "/api/workspace/roots": {"get": {"summary": "Allowlisted workspace roots"}},
    "/api/workspace/tree": {"get": {"summary": "Directory tree"}},
    "/api/workspace/file": {
        "get": {"summary": "Read file"},
        "put": {"summary": "Write file"},
    },
    "/api/terminal/profiles": {"get": {"summary": "Log shell profiles"}},
    "/api/terminal/sessions": {
        "get": {"summary": "List log shell sessions"},
        "post": {"summary": "Spawn log shell session"},
    },
    "/api/terminal/sessions/{session_id}": {"get": {"summary": "Session status"}},
    "/api/terminal/sessions/{session_id}/log": {"get": {"summary": "Session log tail"}},
    "/api/terminal/sessions/{session_id}/stop": {"post": {"summary": "Stop session"}},
}


def openapi_document() -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "Agent Dashboard Hub API", "version": "1.0.0"},
        "paths": HUB_OPENAPI_PATHS,
    }


def handle_get(handler, path: str, query: dict, parts: list[str]) -> bool:
    if path == "/api/health":
        ctx = c.ctx(handler)
        registry = ctx["registry"]
        c.send(handler, 200, {
            "ok": True,
            "service": "agent-dashboard",
            "agents": len(registry.adapters),
            "auth_required": ctx["auth_required"],
        })
        return True
    if path == "/api/openapi.json":
        c.send(handler, 200, openapi_document())
        return True
    return False
