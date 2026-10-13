"""Optional supervisor entry points; engines retain their own policy gates."""
from __future__ import annotations
import json
import argparse
import math
import time
from pathlib import Path
from ide_bridge.exit_codes import exit_code_from_dc_row


def execute(args, engine: str, *, resume: bool = False) -> int:
    if resume and any(getattr(args,key,None) is not None for key in ("token_limit","deadline_seconds","execution_policy","approval_mode","task_contract")):
        raise ValueError("Resume retains pinned resource limits; start a new run to change them")
    from agent_core.supervisor import Supervisor
    directory = Path(args.supervisor_dir).resolve()
    supervisor = Supervisor(directory, repository=getattr(args,"repository",None))
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
        workspace = str(Path(getattr(args, "repo", None) or getattr(args, "cwd", ".")).resolve())
        session_id = args.session_id or supervisor.new_session(project=workspace)["session_id"]
        token_limit=getattr(args,"token_limit",None)
        seconds=getattr(args,"deadline_seconds",None)
        task_options={}
        if any(getattr(args,key,None) is not None for key in ("execution_policy","approval_mode","task_contract")):
            task_options={"execution_policy":getattr(args,"execution_policy",None) or "legacy","approval_mode":getattr(args,"approval_mode",None) or "plan"}
        contract_path=getattr(args,"task_contract",None)
        if contract_path: task_options["task_contract"]=json.loads(Path(contract_path).read_text())
        row = supervisor.create_run(session_id, engine, request, workspace, live=args.live, provider=getattr(args, "provider", "mock"),limit_tokens=token_limit if token_limit is not None else 80000,deadline=time.time()+seconds if seconds is not None else None,**task_options)
        row = supervisor.execute(row["run_id"])
    print(json.dumps(row))
    code = exit_code_from_dc_row(row)
    if code == 0 and not row.get("live",args.live) and getattr(args, "mark_simulated", True):
        return 1
    return code


def positive_tokens(value):
    try:
        number=int(value)
    except (ValueError,TypeError):
        raise argparse.ArgumentTypeError("token limit must be a positive integer") from None
    if number<=0: raise argparse.ArgumentTypeError("token limit must be a positive integer")
    return number

def positive_seconds(value):
    try:
        number=float(value)
    except (ValueError,TypeError):
        raise argparse.ArgumentTypeError("deadline must be finite and positive") from None
    if not math.isfinite(number) or number<=0: raise argparse.ArgumentTypeError("deadline must be finite and positive")
    return number

def add_options(parser):
    parser.epilog = "Supervised mock runs retain SIMULATED status; --no-mark-simulated applies only to the legacy wrapper."
    parser.add_argument("--supervisor-dir", help="Use the shared durable supervisor at this directory")
    parser.add_argument("--session-id", help="Existing shared supervisor session")
    parser.add_argument("--token-limit",type=positive_tokens,default=None,help="Explicit supervised run token ceiling")
    parser.add_argument("--deadline-seconds",type=positive_seconds,default=None,help="Explicit supervised active execution deadline")
    parser.add_argument("--repository",type=Path,help="AgentNexus runtime repository for the supervisor")
    parser.add_argument("--execution-policy",choices=("legacy","coder-v1"),default=None)
    parser.add_argument("--approval-mode",choices=("plan","task"),default=None)
    parser.add_argument("--task-contract",type=Path,default=None)
