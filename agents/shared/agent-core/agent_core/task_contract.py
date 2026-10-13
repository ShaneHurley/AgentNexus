"""Immutable task authority for the opt-in contained coder."""
from __future__ import annotations
import hashlib, json, math
from datetime import datetime
from pathlib import Path, PurePosixPath
from .contracts import ContractDenied

POLICY_VERSION="coder-v1/1"
DEFAULT_LIMITS={"tokens":300000,"calls":30,"repair_cycles":2,"tool_rounds":6,"verification_timeout":120,"deadline_seconds":1800}
def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def literal_path(value):
    if not isinstance(value,str) or not value or "\\" in value or any(c in value for c in "*?["):
        raise ContractDenied("task paths must be concrete relative paths")
    path=PurePosixPath(value)
    if path.is_absolute() or any(part in {".",".."} for part in value.split("/")) or path.as_posix()!=value:
        raise ContractDenied("invalid task path")
    if path.parts[0] in {".git",".agentnexus",".daily-coder"}:
        raise ContractDenied("runtime paths cannot be task targets")
    return value
def resolve_path(workspace,path):
    path=literal_path(path)
    root=Path(workspace).resolve()
    target=(root/path).resolve()
    if not target.is_relative_to(root):
        raise ContractDenied("task path escapes workspace")
    return target
def validate_contract(value,request,workspace,*,parent_tokens=300000):
    fields={"schema_version","request_sha256","workspace","acceptance_criteria","allowed_paths","operations","verification_commands","limits","authorization_source","authorized_at"}
    if not isinstance(value,dict) or set(value)!=fields or type(value["schema_version"]) is not int or value["schema_version"]!=1:
        raise ContractDenied("invalid task contract fields")
    if value["request_sha256"]!=hashlib.sha256(request.encode()).hexdigest() or value["workspace"]!=str(Path(workspace).resolve()):
        raise ContractDenied("task contract request or workspace mismatch")
    if value["authorization_source"]!="user-task":
        raise ContractDenied("task authorization source must be user-task")
    try:
        stamp=datetime.fromisoformat(value["authorized_at"].replace("Z","+00:00"))
        if stamp.tzinfo is None: raise ValueError()
    except (ValueError,TypeError,AttributeError):
        raise ContractDenied("task authorization needs a timezone-aware timestamp") from None
    criteria=value["acceptance_criteria"]
    if not isinstance(criteria,list) or not criteria or any(not isinstance(x,str) or not x.strip() for x in criteria):
        raise ContractDenied("task acceptance criteria are required")
    paths=value["allowed_paths"]
    if not isinstance(paths,list) or not paths or len(paths)>3 or any(not isinstance(x,str) for x in paths) or len(set(paths))!=len(paths):
        raise ContractDenied("contained coder requires one to three concrete paths")
    for path in paths: resolve_path(workspace,path)
    ops=value["operations"]
    if not isinstance(ops,list) or not ops or any(not isinstance(x,str) or x not in {"create","modify"} for x in ops):
        raise ContractDenied("unsupported task operation")
    commands=value["verification_commands"]
    if not isinstance(commands,list) or not commands:
        raise ContractDenied("task verification commands are required")
    for argv in commands:
        if not isinstance(argv,list) or not argv or any(not isinstance(x,str) or not x or "\x00" in x for x in argv):
            raise ContractDenied("verification argv must contain nonempty strings")
    limits=value["limits"]
    if not isinstance(limits,dict) or set(limits)!=set(DEFAULT_LIMITS):
        raise ContractDenied("invalid task resource limits")
    for key,ceiling in DEFAULT_LIMITS.items():
        n=limits[key]
        if type(n) is not int or n<0 or (n==0 and key!="repair_cycles") or n>ceiling:
            raise ContractDenied("task limit outside coder-v1 ceiling: "+key)
    if limits["tokens"]>parent_tokens:
        raise ContractDenied("task token limit exceeds parent")
    return json.loads(json.dumps(value,sort_keys=True,allow_nan=False))
def validate_plan(contract,plan):
    if not isinstance(plan,dict) or plan.get("unresolved_questions"):
        raise ContractDenied("plan incomplete or unresolved")
    allow=plan.get("file_allowlist")
    units=plan.get("change_units")
    commands=plan.get("verification_commands")
    if not isinstance(allow,list) or not allow or not isinstance(units,list) or not units or not commands:
        raise ContractDenied("plan needs concrete changes and verification")
    for path in allow:
        resolve_path(contract["workspace"],path)
        if path not in contract["allowed_paths"]: raise ContractDenied("plan path outside task contract")
    ids=[]
    for unit in units:
        if not isinstance(unit,dict) or not isinstance(unit.get("id"),str) or not unit["id"] or unit["id"] in ids:
            raise ContractDenied("change unit identifiers must be unique")
        ids.append(unit["id"])
        if unit.get("file") not in allow or unit.get("operation") not in contract["operations"]:
            raise ContractDenied("change unit outside task authority")
    pending=list(units); ordered=[]; done=set()
    while pending:
        selected=None
        for unit in pending:
            deps=unit.get("depends_on",[])
            if not isinstance(deps,list) or any(not isinstance(x,str) or x not in ids for x in deps):
                raise ContractDenied("unknown change dependency")
            if set(deps)<=done:
                selected=unit; break
        if selected is None: raise ContractDenied("change dependency cycle")
        pending.remove(selected); ordered.append(selected); done.add(selected["id"])
    if any(argv not in contract["verification_commands"] for argv in commands):
        raise ContractDenied("verification command outside task contract")
    result=dict(plan); result["change_units"]=ordered
    return result
def validate_call(contract,tool,args,workspace):
    if str(Path(workspace).resolve())!=contract["workspace"]:
        raise ContractDenied("task workspace changed")
    if tool in {"filesystem.write","patch.apply"}:
        path=literal_path(args.get("path"))
        target=resolve_path(workspace,path)
        if path not in contract["allowed_paths"]: raise ContractDenied("write outside task contract")
        operation="modify" if target.exists() else "create"
        if operation not in contract["operations"]: raise ContractDenied("write operation outside task contract")
    if tool in {"tests.run","shell.readonly"}:
        if args.get("argv") not in contract["verification_commands"] or "command" in args:
            raise ContractDenied("command outside task contract")
        timeout=args.get("timeout",contract["limits"]["verification_timeout"])
        if type(timeout) is not int or not 0<timeout<=contract["limits"]["verification_timeout"]:
            raise ContractDenied("verification timeout outside task contract")
def scope_hash(contract):
    rows=[]
    for path in sorted(contract["allowed_paths"]):
        target=resolve_path(contract["workspace"],path)
        rows.append((path,hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None))
    return digest(rows)
