from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from ai_agents_repo.discovery import find_repo_root, repo_root
from ai_agents_repo.exceptions import LayoutError


def test_repo_root_from_live_checkout():
    root = repo_root()
    assert (root / ".ai-agents-layout").is_file()
    assert (root / "agents" / "ide" / "MANIFEST.yml").is_file()


def test_find_repo_root_unrelated_cwd(use_legacy_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    assert find_repo_root() == use_legacy_root.resolve()


def test_launch_from_package_dir(use_legacy_root: Path, monkeypatch: pytest.MonkeyPatch):
    pkg_dir = (
        use_legacy_root / "agents" / "shared" / "ai_agents_repo" / "src" / "ai_agents_repo"
    )
    pkg_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(pkg_dir)
    assert find_repo_root() == use_legacy_root.resolve()


def test_editable_install_same_root(use_legacy_root: Path, tmp_path: Path):
    env = os.environ.copy()
    env["AI_AGENTS_REPO_ROOT"] = str(use_legacy_root)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from ai_agents_repo import repo_root; print(repo_root())",
        ],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert Path(proc.stdout.strip()) == use_legacy_root.resolve()


def test_missing_root_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AI_AGENTS_REPO_ROOT", raising=False)
    with pytest.raises(LayoutError):
        find_repo_root(start=tmp_path)
