"""Hermetic legacy / v2 fixture trees."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ai_agents_repo.discovery import repo_root as cached_repo_root_fn
from ai_agents_repo.layout import cached_layout


def reset_repo_caches() -> None:
    cached_repo_root_fn.cache_clear()
    cached_layout.cache_clear()


@pytest.fixture
def legacy_tree(tmp_path: Path) -> Path:
    root = tmp_path / "legacy-checkout"
    root.mkdir()
    (root / ".ai-agents-layout").write_text(
        json.dumps({"layout_version": 1, "layout": "legacy"}),
        encoding="utf-8",
    )
    _write_min_manifest(root / "ide-pack" / "ide-agents")
    (root / "coder" / "daily-coder-ecosystem").mkdir(parents=True)
    (root / "deep-research" / "research-forge").mkdir(parents=True)
    (root / "gui").mkdir()
    (root / "agent-core").mkdir()
    (root / "skills").mkdir()
    (root / "schemas" / "personal").mkdir(parents=True)
    (root / "browser agent").mkdir()
    (root / "ide-pack" / ".cursor" / "hooks").mkdir(parents=True)
    (root / "ide-pack" / "ide-agents" / "contracts").mkdir(parents=True)
    (root / "ide-pack" / "ide-agents" / "contracts" / "probe.md").write_text("ok", encoding="utf-8")
    return root


@pytest.fixture
def v2_tree(tmp_path: Path) -> Path:
    root = tmp_path / "v2-checkout"
    root.mkdir()
    (root / ".ai-agents-layout").write_text(
        json.dumps({"layout_version": 1, "layout": "v2"}),
        encoding="utf-8",
    )
    _write_min_manifest(root / "agents" / "ide")
    (root / "agents" / "coding" / "daily-coder-ecosystem").mkdir(parents=True)
    (root / "agents" / "research" / "research-forge").mkdir(parents=True)
    (root / "gui").mkdir()
    (root / "agents" / "shared" / "agent-core").mkdir(parents=True)
    (root / "agents" / "shared" / "skills").mkdir(parents=True)
    (root / "agents" / "shared" / "schemas" / "personal").mkdir(parents=True)
    (root / "agents" / "daily-task" / "browser" / "families").mkdir(parents=True)
    (root / "agents" / "coding" / "browser").mkdir(parents=True)
    (root / "agents" / "research" / "browser").mkdir(parents=True)
    (root / ".cursor" / "hooks").mkdir(parents=True)
    (root / "agents" / "ide" / "contracts").mkdir(parents=True)
    (root / "agents" / "ide" / "contracts" / "probe.md").write_text("ok", encoding="utf-8")
    return root


def _write_min_manifest(hub: Path) -> None:
    hub.mkdir(parents=True, exist_ok=True)
    (hub / "MANIFEST.yml").write_text(
        "pack_version: 0.0.0-fixture\ncontract_version: '1.0'\nagents: []\n",
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _isolate_repo_root_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("AI_AGENTS_REPO_ROOT", raising=False)
    monkeypatch.delenv("AI_AGENTS_LAYOUT", raising=False)
    reset_repo_caches()
    yield
    reset_repo_caches()


@pytest.fixture
def use_legacy_root(legacy_tree: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AI_AGENTS_REPO_ROOT", str(legacy_tree))
    reset_repo_caches()
    return legacy_tree


@pytest.fixture
def use_v2_root(v2_tree: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("AI_AGENTS_REPO_ROOT", str(v2_tree))
    reset_repo_caches()
    return v2_tree
