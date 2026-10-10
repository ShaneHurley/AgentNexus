"""Thin scoped memory commands. They never construct a permissive grant or execution DB."""
from pathlib import Path
from .contracts import ContractDenied
from .memory_authority import read_json,evaluate_memory_access


def register(commands):
    memory=commands.add_parser("memory",help="Scoped knowledge stores; explicit grants and confirmation required")
    sub=memory.add_subparsers(dest="memory_command",required=True)
    for name in ("init","search","inspect","draft","accept","refresh","revise","promote","export","import","backup","delete","doctor"):
        p=sub.add_parser(name)
        p.add_argument("--store",type=Path,required=True)
        p.add_argument("--workspace",type=Path,required=True)
        p.add_argument("--grant-file",type=Path,required=True)
        if name in {"init","accept","revise","promote","export","import","backup","delete"}:p.add_argument("--confirm",action="store_true")
        if name=="init":
            p.add_argument("--store-id",required=True);p.add_argument("--kind",choices=("project","research","daily","shared"),required=True)
            p.add_argument("--raw-run-retention",required=True,help="days >=0 or none")
        if name in {"search","draft","refresh","promote"}:p.add_argument("--namespace",default="default")
        if name=="search":
            p.add_argument("--query",required=True);p.add_argument("--include-drafts",action="store_true")
            p.add_argument("--limit",type=int,default=8);p.add_argument("--token-budget",type=int,default=4000);p.add_argument("--fingerprints",type=Path)
        if name in {"inspect","accept","revise","promote","delete"}:p.add_argument("--record",required=True)
        if name in {"accept","revise","promote","delete"}:p.add_argument("--expected-hash",required=True)
        if name in {"draft","refresh","revise","import"}:p.add_argument("--input",type=Path,required=True)
        if name in {"export","backup","promote"}:p.add_argument("--destination",type=Path,required=True)
        if name=="export":p.add_argument("--namespaces",nargs="+",required=True)
        if name=="promote":
            p.add_argument("--fingerprints",type=Path,help="Current source dependency fingerprints; required when source has dependencies")
            p.add_argument("--destination-grant-file",type=Path,required=True)
            p.add_argument("--destination-workspace",type=Path,required=True)
            p.add_argument("--title",required=True);p.add_argument("--body",required=True)


def execute(args):
    from .memory import KnowledgeStore
    from . import memory_portability as portability
    spec=read_json(args.grant_file)
    if args.memory_command=="init":
        access=evaluate_memory_access(spec,workspace=args.workspace,store_id=args.store_id,kind=args.kind)
        retention="none" if args.raw_run_retention=="none" else int(args.raw_run_retention)
        store=KnowledgeStore.create(args.store,store_id=args.store_id,kind=args.kind,access=access,raw_run_retention_days=retention,confirmed=args.confirm)
        return {"store_id":store.store_id,"kind":store.kind,"metadata":store.metadata}
    store=KnowledgeStore(args.store)
    access=evaluate_memory_access(spec,workspace=args.workspace,store_id=store.store_id,kind=store.kind)
    name=args.memory_command
    def input_value(path):
        access.effective_grant.authorize("tools","memory.import",path)
        return read_json(path)
    if name=="search":return store.search(args.query,access,namespace=args.namespace,include_drafts=args.include_drafts,limit=args.limit,token_budget=args.token_budget,fingerprints=input_value(args.fingerprints) if args.fingerprints else None)
    if name=="inspect":return store.inspect(args.record,access)
    if name=="draft":return store.add_draft(access,namespace=args.namespace,**input_value(args.input))
    if name=="accept":return store.accept(args.record,access,expected_hash=args.expected_hash,confirmed=args.confirm)
    if name=="refresh":return store.refresh_dependencies(access,input_value(args.input),namespace=args.namespace)
    if name=="revise":return store.revise(args.record,access,expected_hash=args.expected_hash,confirmed=args.confirm,**input_value(args.input))
    if name=="export":return portability.export_store(store,access,args.destination,namespaces=args.namespaces,confirmed=args.confirm)
    if name=="import":return portability.import_store(store,access,args.input,confirmed=args.confirm)
    if name=="backup":return portability.backup_store(store,access,args.destination,confirmed=args.confirm)
    if name=="delete":return portability.delete_record(store,access,args.record,expected_hash=args.expected_hash,confirmed=args.confirm)
    if name=="doctor":return portability.memory_doctor(store,access)
    if name=="promote":
        destination=KnowledgeStore(args.destination)
        target=evaluate_memory_access(read_json(args.destination_grant_file),workspace=args.destination_workspace,store_id=destination.store_id,kind=destination.kind)
        if access.identity!=target.identity or access.run_id!=target.run_id:
            raise ContractDenied("promotion grants must share originating identity and run")
        return portability.promote_record(store,destination,access,target,args.record,namespace=args.namespace,title=args.title,body=args.body,expected_hash=args.expected_hash,confirmed=args.confirm,fingerprints=input_value(args.fingerprints) if args.fingerprints else None)
    raise ValueError("unknown memory command")
