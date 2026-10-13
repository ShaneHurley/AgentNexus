"""agent-nexus: shared local sessions over the existing DC/RF engines."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import time
import sqlite3
from .contracts import ContractDenied
from .lifecycle import RunBusy
from .supervisor import Supervisor
from .providers.http import ProviderError


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
    codex=commands.add_parser("codex",help="Explicit reviewed ChatGPT CLI transport configuration")
    codex_sub=codex.add_subparsers(dest="codex_command",required=True)
    configure=codex_sub.add_parser("configure")
    configure.add_argument("--pins",type=Path,required=True)
    configure.add_argument("--confirm",action="store_true")
    codex_sub.add_parser("inspect")
    codex_sub.add_parser("doctor").add_argument("--json",action="store_true")
    agents=commands.add_parser("agents",help="Read-only audit of existing IDE and browser capabilities")
    audit=agents.add_subparsers(dest="agents_command",required=True).add_parser("audit")
    audit.add_argument("--select",action="append",default=[])
    audit.add_argument("--max-prompt-bytes",type=int,default=32000)
    audit.add_argument("--check",action="store_true",help="Return blocked status when audit errors exist")
    run=commands.add_parser("run",help="Execute supported workflow in a session")
    run.add_argument("--session",required=True)
    run.add_argument("--engine",choices=("daily-coder","research-forge"),required=True)
    source=run.add_mutually_exclusive_group(required=True)
    source.add_argument("--request")
    source.add_argument("--request-file",type=Path)
    run.add_argument("--workspace",type=Path,default=Path.cwd())
    run.add_argument("--reference-document",action="append",default=[],help="Explicit workspace-contained supplied-plan references; evaluation-only")
    run.add_argument("--context-variant",choices=("baseline","bounded-context-v1"),default="baseline")
    run.add_argument("--context-evaluation",action="store_true",help="Explicit candidate measurement; does not activate production context")
    run.add_argument("--memory-binding",type=Path,help="Explicit session-scoped memory binding; automatic drafts only")
    run.add_argument("--live",action="store_true")
    run.add_argument("--provider",default="mock")
    run.add_argument("--idempotency-key")
    run.add_argument("--budget-usd",type=float,default=5.0)
    run.add_argument("--token-limit",type=int,default=80000)
    run.add_argument("--deadline-seconds",type=float)
    run.add_argument("--execution-policy",choices=("legacy","coder-v1"),default="legacy")
    run.add_argument("--approval-mode",choices=("plan","task"),default="plan")
    run.add_argument("--task-contract",type=Path)
    resume=commands.add_parser("resume",help="Reconcile and resume a pinned run")
    resume.add_argument("run_id")
    resume.add_argument("--answer",action="append",default=[])
    for name in ("status","cancel"):
        command=commands.add_parser(name)
        command.add_argument("run_id")
    reconcile=commands.add_parser("reconcile-read",help="Acknowledge an unavailable pure read without rerunning it")
    reconcile.add_argument("run_id")
    reconcile.add_argument("--operation-id",required=True)
    reconcile.add_argument("--actor",required=True)
    reconcile.add_argument("--ack-result-unavailable",action="store_true")
    runs=commands.add_parser("runs")
    runs.add_argument("--engine")
    runs.add_argument("--session")
    backup=commands.add_parser("backup",help="Consistent SQLite execution backup")
    backup.add_argument("destination",type=Path)
    from .model_commands import register,HANDLED_COMMANDS,execute
    register(commands)
    from . import efficiency_commands
    efficiency_commands.register(commands)
    from . import memory_cli
    memory_cli.register(commands)
    args=parser.parse_args(argv)
    try:
        if args.command=="codex":
            from .runtime_authority import repository_root
            from .codex_settings import configure,load_settings
            repository=args.repository or repository_root()
            if args.codex_command=="doctor":
                from .codex_doctor import doctor
                result=doctor(repository)
                print(json.dumps(result,indent=2,allow_nan=False))
                return 0 if result["ready"] else 3
            result=configure(repository,json.loads(args.pins.read_text()),confirmed=args.confirm) if args.codex_command=="configure" else load_settings(repository)
            print(json.dumps(result,indent=2,allow_nan=False));return 0
        if args.command == "agents":
            from .agent_inventory import build_inventory
            from .runtime_authority import repository_root
            result=build_inventory(args.repository or repository_root(),selected=args.select,max_prompt_bytes=args.max_prompt_bytes)
            print(json.dumps(result,indent=2,allow_nan=False,default=str))
            return 3 if args.check and any(f["severity"]=="error" for f in result["findings"]) else 0
        if args.command == "memory":
            result=memory_cli.execute(args)
            print(json.dumps(result,indent=2,allow_nan=False,default=str))
            return 0
        if args.command in HANDLED_COMMANDS | efficiency_commands.HANDLED_COMMANDS:
            from .runtime_authority import repository_root
            result=(efficiency_commands.execute if args.command=="tools" else execute)(args,args.repository or repository_root())
            print(json.dumps(result,indent=2,allow_nan=False,default=str))
            return 3 if args.command == "eval" and result.get("ok") is False else 0
        supervisor=Supervisor(args.state_dir,args.repository)
        code=0
        if args.command == "new": result=supervisor.new_session(args.identity,args.project,args.profile)
        elif args.command == "sessions": result=supervisor.sessions()
        elif args.command == "runs": result=supervisor.runs(args.engine,args.session)
        elif args.command == "backup": result={"backup":str(supervisor.store.export(args.destination))}
        elif args.command == "status": result=supervisor.status(args.run_id)
        elif args.command == "cancel": result=supervisor.cancel(args.run_id); code=0 if result.get("acknowledged") else 3
        elif args.command == "run":
            request=args.request_file.read_bytes().decode("utf-8") if args.request_file else args.request
            if args.engine == "research-forge":
                try: request=json.loads(request)
                except json.JSONDecodeError: request={"topic":request,"objective":request}
            deadline=time.time()+args.deadline_seconds if args.deadline_seconds is not None else None
            row=supervisor.create_run(args.session,args.engine,request,args.workspace,args.live,provider=args.provider,idempotency_key=args.idempotency_key,limit_usd=args.budget_usd,limit_tokens=args.token_limit,deadline=deadline,memory_binding=args.memory_binding,context_variant=args.context_variant,context_evaluation=args.context_evaluation,reference_documents=args.reference_document,execution_policy=args.execution_policy,approval_mode=args.approval_mode,task_contract=json.loads(args.task_contract.read_text()) if args.task_contract else None)
            from .coder_capacity import announce_capacity
            announce_capacity(supervisor,row["run_id"])
            result=supervisor.execute(row["run_id"]); code=exit_status(result)
        elif args.command == "reconcile-read":
            result=supervisor.reconcile_read(args.run_id,args.operation_id,actor=args.actor,acknowledge_unavailable=args.ack_result_unavailable)
            code=0
        elif args.command == "resume":
            answers={}
            for item in args.answer:
                key,sep,value=item.partition("=")
                if not sep or not key: raise ValueError("answer requires CLQ-ID=value")
                answers[key]=value
            from .coder_capacity import announce_capacity
            announce_capacity(supervisor,args.run_id)
            result=supervisor.execute(args.run_id,answers=answers or None); code=exit_status(result)
        print(json.dumps(result,indent=2,allow_nan=False,default=str))
        return code
    except ProviderError as exc:
        print(json.dumps({"ok":False,"error":"ProviderError","category":exc.category,"remote_acceptance":exc.remote_acceptance,
                          "detail":"pinned provider preflight or invocation failed; no automatic retry"}))
        return 3
    except (ContractDenied,RunBusy,ValueError,KeyError,OSError,ImportError,sqlite3.Error) as exc:
        print(json.dumps({"ok":False,"error":type(exc).__name__,"detail":str(exc)}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
