"""agent-nexus: shared local sessions over the existing DC/RF engines."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import time
from .contracts import ContractDenied
from .lifecycle import RunBusy
from .supervisor import Supervisor


def exit_status(row):
    status=row.get("status")
    if status == "COMPLETE": return 0
    if status == "SIMULATED": return 1
    if status == "FAILED": return 2
    return 3


def main(argv=None):
    parser=argparse.ArgumentParser(prog="agent-nexus")
    parser.add_argument("--state-dir", "--supervisor-dir", type=Path)
    parser.add_argument("--repository",type=Path)
    commands=parser.add_subparsers(dest="command",required=True)
    new=commands.add_parser("new",help="Create a durable user session")
    new.add_argument("--identity",default="local")
    new.add_argument("--project",type=Path)
    new.add_argument("--profile",default="default")
    commands.add_parser("sessions",help="List sessions")
    run=commands.add_parser("run",help="Execute supported workflow in a session")
    run.add_argument("--session",required=True)
    run.add_argument("--engine",choices=("daily-coder","research-forge"),required=True)
    source=run.add_mutually_exclusive_group(required=True)
    source.add_argument("--request")
    source.add_argument("--request-file",type=Path)
    run.add_argument("--workspace",type=Path,default=Path.cwd())
    run.add_argument("--live",action="store_true")
    run.add_argument("--provider",default="mock")
    run.add_argument("--idempotency-key")
    run.add_argument("--budget-usd",type=float,default=5.0)
    run.add_argument("--token-limit",type=int,default=80000)
    run.add_argument("--deadline-seconds",type=float)
    resume=commands.add_parser("resume",help="Reconcile and resume a pinned run")
    resume.add_argument("run_id")
    resume.add_argument("--answer",action="append",default=[])
    for name in ("status","cancel"):
        command=commands.add_parser(name)
        command.add_argument("run_id")
    runs=commands.add_parser("runs")
    runs.add_argument("--engine")
    runs.add_argument("--session")
    backup=commands.add_parser("backup",help="Consistent SQLite execution backup")
    backup.add_argument("destination",type=Path)
    args=parser.parse_args(argv)
    try:
        supervisor=Supervisor(args.state_dir,args.repository)
        code=0
        if args.command == "new": result=supervisor.new_session(args.identity,args.project,args.profile)
        elif args.command == "sessions": result=supervisor.sessions()
        elif args.command == "runs": result=supervisor.runs(args.engine,args.session)
        elif args.command == "backup": result={"backup":str(supervisor.store.export(args.destination))}
        elif args.command == "status": result=supervisor.status(args.run_id)
        elif args.command == "cancel": result=supervisor.cancel(args.run_id); code=0 if result.get("acknowledged") else 3
        elif args.command == "run":
            request=args.request_file.read_text() if args.request_file else args.request
            if args.engine == "research-forge":
                try: request=json.loads(request)
                except json.JSONDecodeError: request={"topic":request,"objective":request}
            deadline=time.time()+args.deadline_seconds if args.deadline_seconds is not None else None
            row=supervisor.create_run(args.session,args.engine,request,args.workspace,args.live,provider=args.provider,idempotency_key=args.idempotency_key,limit_usd=args.budget_usd,limit_tokens=args.token_limit,deadline=deadline)
            result=supervisor.execute(row["run_id"]); code=exit_status(result)
        elif args.command == "resume":
            answers={}
            for item in args.answer:
                key,sep,value=item.partition("=")
                if not sep or not key: raise ValueError("answer requires CLQ-ID=value")
                answers[key]=value
            result=supervisor.execute(args.run_id,answers=answers or None); code=exit_status(result)
        print(json.dumps(result,indent=2,allow_nan=False,default=str))
        return code
    except (ContractDenied,RunBusy,ValueError,KeyError,OSError,ImportError) as exc:
        print(json.dumps({"ok":False,"error":type(exc).__name__,"detail":str(exc)}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
