"""Invoke daily-coder CLI with IDE_BRIDGE_ACTIVE and repo-relative PYTHONPATH."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from ai_agents_repo.bootstrap import ensure_importable

ensure_importable()

from ai_agents_repo import dc_root, repo_root  # noqa: E402

REPO_ROOT = repo_root()
DC_ROOT = dc_root()


def bridge_env() -> dict[str, str]:
    env = os.environ.copy()
    env["IDE_BRIDGE_ACTIVE"] = "1"
    extra = str(DC_ROOT)
    prev = env.get("PYTHONPATH")
    env["PYTHONPATH"] = extra if not prev else f"{extra}{os.pathsep}{prev}"
    return env


def daily_coder_cmd_prefix() -> list[str]:
    exe = os.environ.get("IDE_BRIDGE_DAILY_CODER")
    if exe:
        return [exe]
    return [sys.executable, "-m", "daily_coder.cli"]


def run_daily_coder(argv: list[str], *, cwd: Path | None = None) -> tuple[int, str, str]:
    """argv is the full command (e.g. ['daily-coder', 'run', ...] or python -m form)."""
    work = cwd or DC_ROOT
    proc = subprocess.run(
        argv,
        cwd=str(work),
        env=bridge_env(),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def parse_last_json(stdout: str) -> dict[str, Any] | None:
    text = stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None
