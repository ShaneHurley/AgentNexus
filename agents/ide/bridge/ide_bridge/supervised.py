"""Optional supervisor entry points; engines retain their own policy gates."""
from __future__ import annotations
import json
from pathlib import Path
from ide_bridge.exit_codes import exit_code_from_dc_row


def execute(args, engine: str, *, resume: bool = False) -> int:
    from agent_core.supervisor import Supervisor
    directory = Path(args.supervisor_dir).resolve()
    supervisor = Supervisor(directory)
    if resume:
        answers = {}
        for answer in getattr(args, "answer", []):
            key, separator, value = answer.partition("=")
            if not separator or not key:
                raise ValueError("Answers must have CLQ-ID=value form")
            answers[key] = value
        row = supervisor.status(args.run_id)
        if row.get("engine") != engine:
            raise ValueError("Run belongs to another engine")
        row = supervisor.execute(args.run_id, answers=answers or None)
    else:
        request = args.request
        if engine == "research-forge":
            path = Path(request)
            request = json.loads(path.read_text() if path.is_file() else request)
        workspace = str(Path(getattr(args, "repo", args.cwd)).resolve())
        session_id = args.session_id or supervisor.new_session(project=workspace)["session_id"]
        row = supervisor.create_run(session_id, engine, request, workspace, live=args.live, provider=getattr(args, "provider", "mock"))
        row = supervisor.execute(row["run_id"])
    print(json.dumps(row))
    code = exit_code_from_dc_row(row)
    if code == 0 and not row.get("live",args.live) and getattr(args, "mark_simulated", True):
        return 1
    return code


def add_options(parser):
    parser.epilog = "Supervised mock runs retain SIMULATED status; --no-mark-simulated applies only to the legacy wrapper."
    parser.add_argument("--supervisor-dir", help="Use the shared durable supervisor at this directory")
    parser.add_argument("--session-id", help="Existing shared supervisor session")
