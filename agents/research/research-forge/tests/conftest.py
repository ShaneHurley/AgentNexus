from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    root = Path(__file__).resolve().parents[1]
    assert (root / "pyproject.toml").is_file()
    return root


@pytest.fixture(autouse=True)
def isolated_rf_runtime(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("RF_RUNTIME_ROOT", str(tmp_path / "runtime"))
