#!/usr/bin/env python3
"""Antigravity Execution Bridge Helper.

Safely runs ide-bridge operations from within Antigravity terminal / Agent View
with proper environment variables and error handling.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PKG = REPO_ROOT / "agents" / "ide" / "bridge"
REPO_PKG = REPO_ROOT / "agents" / "shared" / "ai_agents_repo" / "src"


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity IDE Bridge Runner")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # doctor
    subparsers.add_parser("doctor", help="Check ide-bridge health and environment")

    # plan-prep scaffold
    subparsers.add_parser("plan-prep", help="Scaffold empty planning context template")

    # daily-coder run
    run_parser = subparsers.add_parser("run", help="Run Daily Coder through ide-bridge")
    run_parser.add_argument("--request", required=True, help="Task description")
    run_parser.add_argument("--repo", default=".", help="Target repository directory")
    run_parser.add_argument("--profile", default="M", choices=["XS", "S", "M", "L", "XL"])
    run_parser.add_argument("--live", action="store_true", help="Enable live provider (default: mock)")

    # resume / approve
    app_parser = subparsers.add_parser("approve", help="Approve plan for run ID")
    app_parser.add_argument("--run-id", required=True)
    app_parser.add_argument("--plan-hash", required=True)

    args = parser.parse_args()

    env = os.environ.copy()
    env["IDE_BRIDGE_ACTIVE"] = "1"
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{REPO_PKG}:{BRIDGE_PKG}:{python_path}"

    cmd = [sys.executable, "-m", "ide_bridge"]

    if args.subcommand == "doctor":
        cmd.append("doctor")
    elif args.subcommand == "plan-prep":
        cmd.extend(["plan-prep", "scaffold"])
    elif args.subcommand == "run":
        cmd.extend(["daily-coder", "run", "--request", args.request, "--repo", args.repo, "--profile", args.profile])
        if args.live:
            cmd.append("--live")
    elif args.subcommand == "approve":
        cmd.extend(["daily-coder", "approve", "--run-id", args.run_id, "--plan-hash", args.plan_hash])

    print(f"[Antigravity Bridge] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
