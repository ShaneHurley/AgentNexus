from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_agents_repo.exceptions import LayoutError
from ai_agents_repo.layout import layout
from ai_agents_repo.paths import (
    browser_coder_root,
    browser_daily_task_root,
    dc_root,
    gui_root,
    ide_pack_root,
    rf_root,
)


def _rel(root: Path, *parts: str) -> Path:
    return root.joinpath(*parts)


def test_legacy_paths(use_legacy_root: Path):
    root = use_legacy_root
    assert layout(root=root) == "legacy"
    assert ide_pack_root(root=root) == _rel(root, "ide-pack", "ide-agents")
    assert dc_root(root=root) == _rel(root, "coder", "daily-coder-ecosystem")
    assert gui_root(root=root) == _rel(root, "gui")
    assert rf_root(root=root) == _rel(root, "deep-research", "research-forge")


def test_v2_paths(use_v2_root: Path):
    root = use_v2_root
    assert layout(root=root) == "v2"
    assert ide_pack_root(root=root) == _rel(root, "agents", "ide")
    assert dc_root(root=root) == _rel(root, "agents", "coding", "daily-coder-ecosystem")
    assert gui_root(root=root) == _rel(root, "gui")
    assert rf_root(root=root) == _rel(root, "agents", "research", "research-forge")


def test_v2_browser_helpers(use_v2_root: Path):
    assert browser_daily_task_root(root=use_v2_root).name == "families"
    assert browser_coder_root(root=use_v2_root).name == "browser"


def test_legacy_browser_v2_only(use_legacy_root: Path):
    with pytest.raises(KeyError):
        browser_coder_root(root=use_legacy_root)


def test_mixed_tree_rejected(tmp_path: Path):
    root = tmp_path / "mixed"
    root.mkdir()
    (root / ".ai-agents-layout").write_text(
        json.dumps({"layout_version": 1, "layout": "legacy"}),
        encoding="utf-8",
    )
    (root / "ide-pack" / "ide-agents").mkdir(parents=True)
    (root / "ide-pack" / "ide-agents" / "MANIFEST.yml").write_text("agents: []\n", encoding="utf-8")
    (root / "agents" / "ide").mkdir(parents=True)
    (root / "agents" / "ide" / "MANIFEST.yml").write_text("agents: []\n", encoding="utf-8")
    with pytest.raises(LayoutError):
        layout(root=root)


def test_env_marker_conflict(use_legacy_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_AGENTS_LAYOUT", "v2")
    with pytest.raises(LayoutError):
        layout(root=use_legacy_root)


def test_explicit_legacy_on_v2_tree_fails(use_v2_root: Path):
    with pytest.raises(LayoutError):
        layout(root=use_v2_root, explicit="legacy")
