"""Load agent config and construct adapters."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from .adapters import ADAPTERS
from .steer_store import SteerStore


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_path(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value)
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


class Registry:
    def __init__(self, config: dict[str, Any], config_dir: Path, data_dir: Path):
        self.config = config
        self.config_dir = config_dir
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.steer = SteerStore(self.data_dir / "threads.jsonl")
        self.adapters: dict[str, Any] = {}
        root = config_dir.parent  # gui/ project root
        for entry in config.get("agents", []):
            if not entry.get("enabled", True):
                continue
            kind = entry["adapter"]
            if kind not in ADAPTERS:
                raise ValueError(f"Unknown adapter: {kind}")
            options = dict(entry.get("options") or {})
            for key in ("repo_root", "package_root", "workspace_root", "default_repo"):
                if key in options:
                    resolved = resolve_path(root, options[key])
                    if resolved:
                        options[key] = str(resolved)
            cls = ADAPTERS[kind]
            if kind in ("research_forge", "daily_task"):
                adapter = cls(entry["id"], entry["name"], entry.get("description", ""), options, self.data_dir)
            else:
                adapter = cls(entry["id"], entry["name"], entry.get("description", ""), options)
            self.adapters[entry["id"]] = adapter

    def get(self, agent_id: str):
        if agent_id not in self.adapters:
            raise KeyError(agent_id)
        return self.adapters[agent_id]

    def list_agents(self) -> list[dict[str, Any]]:
        out = []
        for agent_id, adapter in self.adapters.items():
            health = adapter.health()
            backend = {}
            if hasattr(adapter, "backend_status"):
                try:
                    backend = adapter.backend_status()
                except Exception as exc:  # noqa: BLE001
                    backend = {"state": "error", "message": str(exc), "startable": False}
            online = bool(backend.get("auth_ok") if backend else health.get("online"))
            if not backend:
                online = bool(health.get("online"))
            # Prefer auth-ready for HTTP agents; fall back to process online
            if backend.get("state") == "unauthorized":
                online = False
            elif backend.get("online") and backend.get("auth_ok"):
                online = True
            elif backend.get("online") and not backend.get("startable", True):
                online = True
            out.append({
                "id": agent_id,
                "name": adapter.name,
                "description": adapter.description,
                "enabled": True,
                "online": online,
                "capabilities": adapter.capabilities(),
                "detail": health.get("detail"),
                "backend": backend,
            })
        return out
