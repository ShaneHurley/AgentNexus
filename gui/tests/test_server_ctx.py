"""Build server ctx dict for in-process HTTP tests."""
from __future__ import annotations

from pathlib import Path

from agent_dashboard.paths import docs_dir, project_root
from agent_dashboard.registry import Registry
from agent_dashboard.routes.home import SnapshotCache
from agent_dashboard.routes.workshop import WorkshopSnapshotCache
from agent_dashboard.terminal_registry import TerminalRegistry
from agent_dashboard.usage_store import UsageStore

ROOT = Path(__file__).resolve().parents[1]


def make_server_ctx(registry: Registry, *, auth_required: bool = False, token: str = "") -> dict:
    data_dir = registry.data_dir
    root = project_root(config_path=ROOT / "config" / "agents.json")
    return {
        "registry": registry,
        "auth_required": auth_required,
        "token": token,
        "config": registry.config,
        "project_root": root,
        "docs_dir": docs_dir(config_dir=ROOT / "config", project=root),
        "usage_store": UsageStore(data_dir / "usage.jsonl"),
        "home_snapshot": SnapshotCache(ttl_seconds=5.0),
        "workshop_snapshot": WorkshopSnapshotCache(ttl_seconds=5.0),
        "terminal_registry": TerminalRegistry(data_dir, ROOT / "config" / "terminal_profiles.json"),
    }
