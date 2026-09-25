"""Daily Coder bridge commands — thin subprocess wrappers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ide_bridge.dc_runner import daily_coder_cmd_prefix, parse_last_json, run_daily_coder
from ide_bridge.exec_util import EXIT_BLOCKED, EXIT_COMPLETE, which
from ide_bridge.exit_codes import exit_code_from_cli_failure, exit_code_from_dc_row


def _resolve_dc_argv(base: list[str]) -> list[str]:
    exe = which("daily-coder")
    if exe:
        return [exe, *base]
    return daily_coder_cmd_prefix() + base


def _run_dc(
    base_argv: list[str],
    *,
    cwd: str,
    mark_simulated: bool,
) -> int:
    argv = _resolve_dc_argv(base_argv)
    work = Path(cwd).resolve() if cwd and cwd != "." else None
    code, out, err = run_daily_coder(argv, cwd=work)
    if out:
        print(out, end="" if out.endswith("\n") else "\n")
    if err:
        print(err, file=sys.stderr, end="" if err.endswith("\n") else "\n")
    if code != 0:
        return exit_code_from_cli_failure(err + out, code)
    row = parse_last_json(out)
    if not row:
        return 1 if mark_simulated else EXIT_COMPLETE
    mapped = exit_code_from_dc_row(row)
    if mapped == EXIT_COMPLETE and mark_simulated and not any(a == "--live" for a in base_argv):
        return 1
    return mapped


def cmd_run(args: argparse.Namespace) -> int:
    argv = ["run", "--request", args.request, "--repo", args.repo, "--provider", args.provider]
    if args.live:
        argv.append("--live")
    if args.provider_command:
        argv.extend(["--provider-command", args.provider_command])
    if args.provider_endpoint:
        argv.extend(["--provider-endpoint", args.provider_endpoint])
    return _run_dc(argv, cwd=args.cwd, mark_simulated=args.mark_simulated)


def cmd_approve(args: argparse.Namespace) -> int:
    argv = ["approve", args.run_id, "--kind", args.kind, "--actor", args.actor]
    if args.reject:
        argv.append("--reject")
    if args.note:
        argv.extend(["--note", args.note])
    return _run_dc(argv, cwd=args.cwd, mark_simulated=False)


def cmd_resume(args: argparse.Namespace) -> int:
    argv = ["resume", args.run_id, "--provider", args.provider]
    if args.live:
        argv.append("--live")
    return _run_dc(argv, cwd=args.cwd, mark_simulated=False)


def register(sub: argparse._SubParsersAction) -> None:
    dc = sub.add_parser("daily-coder", help="Daily Coder wrappers (mock default)")
    dc_sub = dc.add_subparsers(dest="dc_cmd", required=True)

    run_p = dc_sub.add_parser("run")
    run_p.add_argument("--request", required=True)
    run_p.add_argument("--repo", default=".")
    run_p.add_argument("--provider", default="mock")
    run_p.add_argument("--live", action="store_true")
    run_p.add_argument("--provider-command")
    run_p.add_argument("--provider-endpoint")
    run_p.add_argument("--cwd", default=".")
    run_p.add_argument("--mark-simulated", action="store_true", default=True)
    run_p.add_argument("--no-mark-simulated", dest="mark_simulated", action="store_false")
    run_p.set_defaults(handler=cmd_run)

    approve_p = dc_sub.add_parser("approve")
    approve_p.add_argument("run_id")
    approve_p.add_argument("--kind", default="plan")
    approve_p.add_argument("--actor", default="ide-bridge")
    approve_p.add_argument("--reject", action="store_true")
    approve_p.add_argument("--note")
    approve_p.add_argument("--cwd", default=".")
    approve_p.set_defaults(handler=cmd_approve)

    resume_p = dc_sub.add_parser("resume")
    resume_p.add_argument("run_id")
    resume_p.add_argument("--provider", default="mock")
    resume_p.add_argument("--live", action="store_true")
    resume_p.add_argument("--cwd", default=".")
    resume_p.set_defaults(handler=cmd_resume)
