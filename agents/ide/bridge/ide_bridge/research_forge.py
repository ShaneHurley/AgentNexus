"""Research Forge bridge commands (Wave 1 run/resume; mock default)."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from ide_bridge.exec_util import EXIT_BLOCKED, run_command, which


def _request_path(request: str) -> Path:
    p = Path(request)
    if p.is_file():
        return p
    # Inline JSON string
    try:
        json.loads(request)
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": "invalid_request", "detail": str(exc)}), file=sys.stderr)
        raise SystemExit(EXIT_BLOCKED)
    tmp = Path(tempfile.gettempdir()) / f"ide-bridge-rf-request-{abs(hash(request)) & 0xFFFF_FFFF}.json"
    tmp.write_text(request, encoding="utf-8")
    return tmp


def cmd_run(args: argparse.Namespace) -> int:
    rf = which("research-forge")
    if not rf:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "research-forge not on PATH",
                    "hint": "pip install -e research-forge or activate that venv",
                }
            ),
            file=sys.stderr,
        )
        return EXIT_BLOCKED

    req_path = _request_path(args.request)
    argv = [rf, "run", "--request", str(req_path)]
    if args.wave1:
        argv.append("--wave1")
    if args.dry_run:
        argv.append("--dry-run")
    if args.live:
        argv.append("--live")

    code = run_command(argv, cwd=args.cwd or args.workspace)
    if not args.live and code == 0:
        # Mock/default success — distinguish from live COMPLETE when RF only ran mock path
        return 1 if args.mark_simulated else code
    return code


def cmd_resume(args: argparse.Namespace) -> int:
    rf = which("research-forge")
    if not rf:
        print(json.dumps({"ok": False, "error": "research-forge not on PATH"}), file=sys.stderr)
        return EXIT_BLOCKED

    argv = [rf, "resume", args.run_id]
    for ans in args.answer or []:
        argv.extend(["--answer", ans])
    if args.live:
        argv.append("--live")
    return run_command(argv, cwd=args.cwd)


def register(sub: argparse._SubParsersAction) -> None:
    rf = sub.add_parser("research-forge", help="Research Forge wrappers (mock default)")
    rf_sub = rf.add_subparsers(dest="rf_cmd", required=True)

    run_p = rf_sub.add_parser("run", help="Wave 0/1 run via research-forge CLI")
    run_p.add_argument("--request", required=True, help="Path to research_request JSON or inline JSON")
    run_p.add_argument("--wave1", action="store_true", help="Force Wave 1 sequential orchestrator")
    run_p.add_argument("--dry-run", action="store_true", help="Plan only")
    run_p.add_argument("--live", action="store_true", help="Live providers (RF gates required)")
    run_p.add_argument(
        "--workspace",
        dest="cwd",
        default=".",
        help="Working directory / RF workspace (default: cwd)",
    )
    run_p.add_argument(
        "--no-mark-simulated",
        dest="mark_simulated",
        action="store_false",
        help="Return RF raw exit 0 on mock success (default: exit 1 = SIMULATED)",
    )
    run_p.set_defaults(mark_simulated=True)
    run_p.set_defaults(handler=cmd_run)

    resume_p = rf_sub.add_parser("resume", help="Resume paused Wave 1 run")
    resume_p.add_argument("run_id")
    resume_p.add_argument("--answer", "-a", action="append", default=[], help="CLQ-ID=value")
    resume_p.add_argument("--live", action="store_true")
    resume_p.add_argument("--cwd", default=".")
    resume_p.set_defaults(handler=cmd_resume)
