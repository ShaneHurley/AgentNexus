"""Local plugin registry — approved plugins only (RF-W6-A-04)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from research_forge.wave6.sdk.manifest import AdapterCapabilityManifest


@dataclass
class PluginRecord:
    plugin_id: str
    entrypoint: str
    signature: str
    approved: bool
    manifest: AdapterCapabilityManifest

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "entrypoint": self.entrypoint,
            "signature": self.signature,
            "approved": self.approved,
            "manifest": self.manifest.to_dict(),
        }


def compute_plugin_signature(manifest_dict: dict[str, Any]) -> str:
    payload = json.dumps(manifest_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class PluginRegistry:
    """Discover only configured, signed/approved local plugins."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self._plugins: dict[str, PluginRecord] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._load_log: list[dict[str, Any]] = []

    def register_factory(self, plugin_id: str, factory: Callable[[], Any]) -> None:
        self._factories[plugin_id] = factory

    def register_plugin(self, record: PluginRecord) -> dict[str, Any]:
        approved_list = set(self.config.get("approved_signatures") or [])
        if not record.approved and record.signature not in approved_list:
            entry = {"plugin_id": record.plugin_id, "loaded": False, "reason": "unapproved"}
            self._load_log.append(entry)
            return entry
        errs = record.manifest.validate()
        if errs:
            entry = {"plugin_id": record.plugin_id, "loaded": False, "reason": "invalid_manifest", "errors": errs}
            self._load_log.append(entry)
            return entry
        self._plugins[record.plugin_id] = record
        entry = {"plugin_id": record.plugin_id, "loaded": True}
        self._load_log.append(entry)
        return entry

    def load(self, plugin_id: str) -> Any | None:
        if plugin_id not in self._plugins:
            return None
        factory = self._factories.get(plugin_id)
        if not factory:
            return None
        return factory()

    def discover_from_config(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        import yaml

        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        results: list[dict[str, Any]] = []
        for entry in data.get("plugins") or []:
            manifest = AdapterCapabilityManifest(**entry["manifest"])
            sig = entry.get("signature") or compute_plugin_signature(manifest.to_dict())
            record = PluginRecord(
                plugin_id=entry["plugin_id"],
                entrypoint=entry.get("entrypoint", ""),
                signature=sig,
                approved=bool(entry.get("approved", False)),
                manifest=manifest,
            )
            results.append(self.register_plugin(record))
        return results

    def list_loaded(self) -> list[str]:
        return list(self._plugins.keys())
