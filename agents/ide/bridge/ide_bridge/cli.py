"""ide-bridge CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import sys

from ide_bridge import daily_coder, research_forge
from ide_bridge.exec_util import EXIT_BLOCKED, which


def cmd_doctor(_args: argparse.Namespace) -> int:
    from ide_bridge.daily_coder import _resolve_dc_argv
    from ide_bridge.dc_runner import run_daily_coder
    from ide_bridge.exec_util import EXIT_COMPLETE, EXIT_PARTIAL

    report: dict = {
        "ide_bridge_active_env": "IDE_BRIDGE_ACTIVE=1 set for child processes",
        "daily_coder": which("daily-coder"),
        "research_forge": which("research-forge"),
    }
    code, out, err = run_daily_coder(_resolve_dc_argv(["doctor"]))
    report["daily_coder_doctor_exit"] = code
    if err.strip():
        report["daily_coder_doctor_stderr"] = err.strip()
    try:
        report["daily_coder_doctor"] = json.loads(out) if out.strip() else None
    except json.JSONDecodeError:
        report["daily_coder_doctor_raw"] = out.strip() or None
    print(json.dumps(report, indent=2))
    if not report["daily_coder"] and not report["research_forge"]:
        return EXIT_BLOCKED
    tree_errors = (report.get("daily_coder_doctor") or {}).get("tree_errors") or []
    if code != 0 or tree_errors:
        return EXIT_PARTIAL
    return EXIT_COMPLETE


def cmd_plan_prep_scaffold(_args: argparse.Namespace) -> int:
    template = {
        "planning_context_version": "1.0",
        "status": "LIMITED_RESEARCH_AVAILABLE",
        "stakeholders": [],
        "constraints": [],
        "open_questions": [],
    }
    print(json.dumps(template, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ide-bridge", description="IDE → Daily Coder / Research Forge (mock default)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor").set_defaults(handler=cmd_doctor)
    pp = sub.add_parser("plan-prep")
    pp_sub = pp.add_subparsers(dest="pp_cmd", required=True)
    pp_sub.add_parser("scaffold").set_defaults(handler=cmd_plan_prep_scaffold)

    daily_coder.register(sub)
    research_forge.register(sub)

    args = ap.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        ap.print_help()
        return EXIT_BLOCKED
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
