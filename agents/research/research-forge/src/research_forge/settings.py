"""Layered settings: config YAML, allowlisted env, CLI overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

ALLOWED_ENV = frozenset({"RF_MODE", "RF_RUN_DIR", "RF_WORKSPACE", "RF_PACKAGE_ROOT"})


class Settings(BaseModel):
    mode: str = "mock"
    ledger_path: str = "runs/ledger.jsonl"
    run_workspace: str = "runs/workspace"
    policy_config: str = "config/policies.yaml"
    budget_config: str = "config/budgets.yaml"
    repo_root: Path = Field(default_factory=lambda: Path.cwd())
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def load_settings(
    repo_root: Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> Settings:
    root = repo_root or find_package_root()
    merged: dict[str, Any] = {}
    defaults_path = root / "config" / "defaults.yaml"
    merged.update(_load_yaml(defaults_path))
    for key in ALLOWED_ENV:
        if key in os.environ and key in ("RF_MODE", "RF_RUN_DIR"):
            env_key = key.removeprefix("RF_").lower()
            merged[env_key] = os.environ[key]
    if cli_overrides:
        for k, v in cli_overrides.items():
            if k not in Settings.model_fields and k != "extra":
                raise ValidationError.from_exception_data(
                    "Settings",
                    [{"type": "extra_forbidden", "loc": (k,), "input": v}],
                )
        merged.update(cli_overrides)
    merged["repo_root"] = root
    return Settings.model_validate(merged)


def _has_package_assets(root: Path) -> bool:
    return (root / "config" / "experiments.yaml").is_file() and (root / "schemas").is_dir()


def find_repo_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for _ in range(12):
        if (cur / "pyproject.toml").is_file() and (cur / "config" / "defaults.yaml").is_file():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return Path.cwd().resolve()


def find_package_root(start: Path | None = None) -> Path:
    """Locate Research Forge assets (config/, schemas/)."""
    env = os.environ.get("RF_PACKAGE_ROOT")
    if env:
        candidate = Path(env).expanduser().resolve()
        if _has_package_assets(candidate):
            return candidate
        raise FileNotFoundError(
            f"RF_PACKAGE_ROOT={candidate} missing config/experiments.yaml or schemas/"
        )

    try:
        import research_forge as _rf

        cur = Path(_rf.__file__).resolve().parent
        for _ in range(8):
            if _has_package_assets(cur):
                return cur
            if cur.parent == cur:
                break
            cur = cur.parent
    except Exception:  # noqa: BLE001
        pass

    if start is not None:
        cur = start.resolve()
        for _ in range(12):
            if _has_package_assets(cur):
                return cur
            if cur.parent == cur:
                break
            cur = cur.parent

    repo = find_repo_root(start)
    if _has_package_assets(repo):
        return repo

    raise FileNotFoundError(
        "Could not locate Research Forge package root (config/experiments.yaml + schemas/). "
        "Install the package editable from the research-forge checkout, or set RF_PACKAGE_ROOT."
    )


def find_workspace_root(explicit: Path | None = None) -> Path:
    """Project directory for .research-forge/ artifacts (defaults to cwd).

    Prefer ``RF_WORKSPACE`` for experiments. ``RF_RUN_DIR`` is a legacy alias
    shared with Wave run directories — setting it redirects experiment artifacts too.
    """
    if explicit is not None:
        return explicit.expanduser().resolve()
    for key in ("RF_WORKSPACE", "RF_RUN_DIR"):
        if key in os.environ and os.environ[key].strip():
            return Path(os.environ[key]).expanduser().resolve()
    return Path.cwd().resolve()