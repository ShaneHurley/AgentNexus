from __future__ import annotations

from pathlib import Path

import pytest

from research_forge.settings import load_settings


def test_precedence_cli_over_env(repo_root: Path, monkeypatch) -> None:
    monkeypatch.setenv("RF_MODE", "mock")
    s = load_settings(repo_root, cli_overrides={"mode": "mock"})
    assert s.mode == "mock"


def test_invalid_cli_key_rejected(repo_root: Path) -> None:
    with pytest.raises(Exception):
        load_settings(repo_root, cli_overrides={"not_allowed": True})
