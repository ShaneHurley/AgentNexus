"""Subprocess helpers and exit-code normalization."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from typing import Sequence

from ide_bridge.env import bridge_env

# Plan exit codes
EXIT_COMPLETE = 0
EXIT_SIMULATED = 1
EXIT_PARTIAL = 2
EXIT_BLOCKED = 3
EXIT_POLICY_DENIED = 4


def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def run_command(
    argv: Sequence[str],
    *,
    cwd: str | None = None,
    env_extra: dict[str, str] | None = None,
) -> int:
    if not argv:
        return EXIT_BLOCKED
    try:
        proc = subprocess.run(
            list(argv),
            cwd=cwd,
            env=bridge_env(env_extra),
            check=False,
        )
    except FileNotFoundError:
        print(json.dumps({"ok": False, "error": "command_not_found", "argv": list(argv)}), file=sys.stderr)
        return EXIT_BLOCKED
    return _map_child_exit(proc.returncode)


def _map_child_exit(code: int) -> int:
    if code == 0:
        return EXIT_COMPLETE
    if code == 1:
        return EXIT_SIMULATED
    if code == 2:
        return EXIT_PARTIAL
    if code == 4:
        return EXIT_POLICY_DENIED
    if code >= 3:
        return EXIT_BLOCKED
    return EXIT_PARTIAL
