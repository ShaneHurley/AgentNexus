"""Setup: runtimes, secrets proxy, slash palette (skills + subagents)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import authorized, ctx, send

# Provider id → secret name (None = no key required beyond bridges/config).
PROVIDER_SECRET: dict[str, str | None] = {
    "mock": None,
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "local": "LOCAL_API_KEY",
    "command": None,
    "http": "BRIDGE_TOKEN",
}

PROVIDER_LABELS: dict[str, str] = {
    "mock": "mock",
    "openai": "openai",
    "anthropic": "anthropic",
    "gemini": "gemini",
    "openrouter": "openrouter",
    "local": "local / Ollama",
    "command": "command bridge",
    "http": "http bridge",
}

LIVE_PROVIDERS = {
    "openai",
    "anthropic",
    "gemini",
    "openrouter",
    "local",
    "command",
    "http",
}

FALLBACK_PROVIDERS = tuple(PROVIDER_SECRET.keys())


def _repo_root(handler) -> Path:
    """Workspace root (parent of gui/)."""
    c = ctx(handler)
    config_dir: Path = c["registry"].config_dir
    return config_dir.parent.parent


def _dc_adapter(handler):
    try:
        return ctx(handler)["registry"].get("daily-coder")
    except KeyError:
        return None


def _secret_names(secrets_payload: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(secrets_payload, list):
        for row in secrets_payload:
            if isinstance(row, dict) and row.get("name"):
                names.add(str(row["name"]))
    return names


def _provider_configured(
    provider_id: str,
    secret_names: set[str],
    bridges: dict[str, bool],
) -> bool:
    if provider_id == "mock":
        return True
    if provider_id == "local":
        return True  # Ollama-style; key optional
    if provider_id == "command":
        return bool(bridges.get("command"))
    if provider_id == "http":
        return bool(bridges.get("http"))
    secret = PROVIDER_SECRET.get(provider_id)
    if not secret:
        return False
    return secret in secret_names


def _runtimes_payload(handler) -> dict[str, Any]:
    adapter = _dc_adapter(handler)
    backend: dict[str, Any] = {}
    if adapter and hasattr(adapter, "backend_status"):
        try:
            backend = adapter.backend_status() or {}
        except Exception as exc:  # noqa: BLE001
            backend = {"state": "error", "message": str(exc), "startable": True}

    bridges = backend.get("bridges") or {"command": False, "http": False}
    ready = backend.get("state") == "ready" and backend.get("auth_ok", True)

    providers_list = list(FALLBACK_PROVIDERS)
    secret_names: set[str] = set()
    source = "fallback"

    if adapter and ready:
        try:
            raw = adapter._request("GET", "/api/providers")  # noqa: SLF001
            if isinstance(raw, dict):
                plist = raw.get("providers") or []
                if plist:
                    providers_list = [str(p) for p in plist]
                secret_names = _secret_names(raw.get("secrets"))
                source = "daily-coder"
        except Exception as exc:  # noqa: BLE001
            backend = {
                **backend,
                "message": f"Providers unreachable: {exc}. Start Daily Coder from Setup.",
            }
            source = "fallback"

    providers = []
    for pid in providers_list:
        providers.append(
            {
                "id": pid,
                "label": PROVIDER_LABELS.get(pid, pid),
                "live": pid in LIVE_PROVIDERS,
                "configured": _provider_configured(pid, secret_names, bridges),
                "secret_name": PROVIDER_SECRET.get(pid),
            }
        )

    return {
        "providers": providers,
        "bridges": bridges,
        "backend": backend,
        "source": source,
        "ready": bool(ready),
    }


def _load_skills(repo: Path) -> list[dict[str, Any]]:
    catalog = repo / "agents" / "shared" / "skills" / "personal-catalog.yaml"
    out: list[dict[str, Any]] = []
    if not catalog.is_file():
        return out
    try:
        text = catalog.read_text(encoding="utf-8")
    except OSError:
        return out
    # Minimal YAML subset: id + path lines under skills list.
    current: dict[str, Any] | None = None
    in_skills = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("skills:"):
            in_skills = True
            continue
        if not in_skills:
            continue
        if stripped.startswith("- id:"):
            if current and current.get("id"):
                out.append(current)
            sid = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            current = {"id": sid, "kind": "skill", "label": sid, "token": f"@skill:{sid}"}
        elif current and stripped.startswith("path:"):
            path = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            current["path"] = path
            # label from folder name
            try:
                current["label"] = Path(path).parts[-2] if "/" in path or "\\" in path else sid
            except Exception:  # noqa: BLE001
                pass
        elif stripped.startswith("status:") and current:
            current["status"] = stripped.split(":", 1)[1].strip()
    if current and current.get("id"):
        out.append(current)
    return [s for s in out if s.get("status", "active") != "disabled"]


def _scan_agent_dirs(root: Path, *, kind: str = "subagent") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not root.is_dir():
        return out
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        # Prefer manifest.yaml / AGENT.md / folder name
        label = child.name
        for name in ("manifest.yaml", "manifest.yml", "AGENT.md", "README.md"):
            mf = child / name
            if mf.is_file():
                try:
                    head = mf.read_text(encoding="utf-8")[:800]
                    for line in head.splitlines():
                        if line.lower().startswith("name:") or line.lower().startswith("title:"):
                            label = line.split(":", 1)[1].strip().strip('"').strip("'")
                            break
                        if line.startswith("# "):
                            label = line[2:].strip()
                            break
                except OSError:
                    pass
                break
        out.append(
            {
                "id": child.name,
                "kind": kind,
                "label": label,
                "token": f"@agent:{child.name}",
            }
        )
    return out


def _daily_task_variants(repo: Path) -> list[dict[str, Any]]:
    manifest = repo / "agents" / "daily-task" / "browser" / "families" / "MANIFEST.json"
    out: list[dict[str, Any]] = []
    if not manifest.is_file():
        return out
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    agents = data.get("agents") if isinstance(data, dict) else data
    if not isinstance(agents, list):
        return out
    for row in agents:
        if not isinstance(row, dict):
            continue
        family = row.get("family") or ""
        variant = row.get("variant") or ""
        display = row.get("display_name") or f"{family}/{variant}"
        aid = f"{family}/{variant}" if variant else str(family)
        out.append(
            {
                "id": aid,
                "kind": "subagent",
                "label": display,
                "token": f"@agent:{aid}",
                "family": family,
                "variant": variant,
            }
        )
    return out


def _palette_for_agent(handler, agent_id: str) -> dict[str, Any]:
    repo = _repo_root(handler)
    skills = _load_skills(repo)
    subagents: list[dict[str, Any]] = []
    if agent_id == "daily-coder":
        subagents = _scan_agent_dirs(
            repo / "agents" / "coding" / "daily-coder-ecosystem" / "agents",
            kind="subagent",
        )
    elif agent_id == "research-forge":
        subagents = _scan_agent_dirs(
            repo / "agents" / "research" / "research-forge" / "agents",
            kind="subagent",
        )
    elif agent_id == "daily-task":
        subagents = _daily_task_variants(repo)
    else:
        # Unknown actor: shared skills only
        pass
    return {
        "agent_id": agent_id,
        "skills": skills,
        "subagents": subagents,
        "items": skills + subagents,
    }


def handle_get(handler, path: str, query: dict, parts: list[str]) -> bool:
    if path == "/api/setup/runtimes":
        if not authorized(handler):
            send(handler, 401, {"error": "unauthorized"})
            return True
        send(handler, 200, _runtimes_payload(handler))
        return True

    if path == "/api/setup/secrets":
        if not authorized(handler):
            send(handler, 401, {"error": "unauthorized"})
            return True
        adapter = _dc_adapter(handler)
        if not adapter:
            send(handler, 404, {"error": "daily-coder not registered"})
            return True
        backend = adapter.backend_status() if hasattr(adapter, "backend_status") else {}
        if backend.get("state") != "ready":
            send(
                handler,
                503,
                {
                    "error": "Daily Coder not ready — start it from Setup",
                    "backend": backend,
                    "secrets": [],
                },
            )
            return True
        try:
            raw = adapter._request("GET", "/api/providers")  # noqa: SLF001
            secrets = raw.get("secrets") if isinstance(raw, dict) else []
            send(handler, 200, {"secrets": secrets, "never_echo_values": True})
        except Exception as exc:  # noqa: BLE001
            send(handler, 503, {"error": str(exc), "secrets": []})
        return True

    if path == "/api/setup/palette":
        if not authorized(handler):
            send(handler, 401, {"error": "unauthorized"})
            return True
        agent_id = (query.get("agent_id") or ["daily-coder"])[0]
        send(handler, 200, _palette_for_agent(handler, agent_id))
        return True

    if path == "/api/setup/expected-agents":
        if not authorized(handler):
            send(handler, 401, {"error": "unauthorized"})
            return True
        cfg = ctx(handler)["registry"].config
        expected = [
            {"id": e["id"], "name": e.get("name", e["id"])}
            for e in cfg.get("agents", [])
            if e.get("enabled", True)
        ]
        loaded = list(ctx(handler)["registry"].adapters.keys())
        send(
            handler,
            200,
            {
                "expected": expected,
                "loaded": loaded,
                "stale": len(loaded) < len(expected),
            },
        )
        return True

    return False


def handle_post(handler, path: str, body: dict, parts: list[str]) -> bool:
    if path != "/api/setup/secrets":
        return False
    if not authorized(handler):
        send(handler, 401, {"error": "unauthorized"})
        return True
    adapter = _dc_adapter(handler)
    if not adapter:
        send(handler, 404, {"error": "daily-coder not registered"})
        return True
    backend = adapter.backend_status() if hasattr(adapter, "backend_status") else {}
    if backend.get("state") != "ready":
        send(
            handler,
            503,
            {"error": "Daily Coder not ready — start it from Setup", "backend": backend},
        )
        return True

    action = (body.get("action") or "set").lower()
    name = (body.get("name") or "").strip()
    if not name:
        send(handler, 400, {"error": "name is required"})
        return True

    try:
        if action == "delete":
            # Daily Coder uses DELETE /api/secrets/{name}; use _request if method supports it
            result = adapter._request("DELETE", f"/api/secrets/{name}")  # noqa: SLF001
            send(handler, 200, result if isinstance(result, dict) else {"deleted": True, "name": name})
            return True
        value = body.get("value")
        if not value:
            send(handler, 400, {"error": "value is required for set"})
            return True
        result = adapter._request("POST", "/api/secrets", {"name": name, "value": value})  # noqa: SLF001
        # Never echo secret value
        if isinstance(result, dict):
            result = {k: v for k, v in result.items() if k != "value"}
        send(handler, 200, result)
    except Exception as exc:  # noqa: BLE001
        send(handler, 503, {"error": str(exc)})
    return True
