"""Filesystem store for local experiment artifacts (under workspace_root)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research_forge.experiments.config import experiments_root, load_experiment_config


class ExperimentStore:
    def __init__(
        self,
        workspace_root: Path,
        *,
        package_root: Path | None = None,
        cfg: dict[str, Any] | None = None,
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.package_root = package_root.resolve() if package_root else None
        self.cfg = cfg or load_experiment_config(self.package_root)
        self.root = experiments_root(
            self.workspace_root, self.cfg, package_root=self.package_root
        )

    def exp_dir(self, experiment_id: str, *, create: bool = True) -> Path:
        d = self.root / experiment_id
        if create:
            d.mkdir(parents=True, exist_ok=True)
        return d

    def path(self, experiment_id: str, name: str, *, create_dir: bool = True) -> Path:
        return self.exp_dir(experiment_id, create=create_dir) / name

    def write_json(self, experiment_id: str, name: str, payload: dict[str, Any]) -> Path:
        p = self.path(experiment_id, name, create_dir=True)
        p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return p

    def read_json(self, experiment_id: str, name: str) -> dict[str, Any] | None:
        p = self.path(experiment_id, name, create_dir=False)
        if not p.is_file():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def exists(self, experiment_id: str, name: str) -> bool:
        return self.path(experiment_id, name, create_dir=False).is_file()

    def set_status(self, experiment_id: str, status: str, **extra: Any) -> dict[str, Any]:
        payload = {"experiment_id": experiment_id, "status": status, **extra}
        self.write_json(experiment_id, "status.json", payload)
        return payload

    def list_ids(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(
            p.name for p in self.root.iterdir() if p.is_dir() and p.name.startswith("EXP-")
        )
