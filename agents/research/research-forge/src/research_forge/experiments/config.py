"""Load experiment config and resolve workspace paths."""

from __future__ import annotations

import copy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from research_forge.settings import find_package_root


@lru_cache(maxsize=8)
def _load_experiment_config_cached(package_root_str: str) -> dict[str, Any]:
    root = Path(package_root_str)
    path = root / "config" / "experiments.yaml"
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing experiment config at {path}. "
            f"package_root={root}. Set RF_PACKAGE_ROOT to the research-forge checkout "
            "or install the package from that tree."
        )
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid experiments config: {path}")
    return data


def load_experiment_config(package_root: Path | None = None) -> dict[str, Any]:
    root = (package_root or find_package_root()).resolve()
    return copy.deepcopy(_load_experiment_config_cached(str(root)))


def experiments_root(
    workspace_root: Path,
    cfg: dict[str, Any] | None = None,
    *,
    package_root: Path | None = None,
) -> Path:
    cfg = cfg or load_experiment_config(package_root)
    rel = cfg.get("workspace_relative", ".research-forge/experiments")
    root = (workspace_root / rel).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def data_allowlist_roots(workspace_root: Path, cfg: dict[str, Any]) -> list[Path]:
    roots: list[Path] = []
    for rel in cfg.get("data_allowlist_relative", []):
        roots.append((workspace_root / rel).resolve())
    return roots
