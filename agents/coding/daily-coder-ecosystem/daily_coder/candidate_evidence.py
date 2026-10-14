"""Gateway source receipts for bounded context and complete candidate review."""
import difflib,json,hashlib
from pathlib import PurePosixPath
from agent_core.task_contract import literal_path,digest
from agent_core.lifecycle import ReconciliationRequired
from .context import ContextCapacityError
PAGE_LINES=80
MAX_SOURCE_CHARS=1000000

def oracle_paths(commands):
    paths=[]
    for argv in commands:
        if "unittest" in argv and "discover" in argv:
            start=argv[argv.index("-s")+1] if "-s" in argv else "."
            pattern=argv[argv.index("-p")+1] if "-p" in argv else None
            candidates=[str(PurePosixPath(start)/pattern)] if pattern and pattern.endswith(".py") else []
        else: candidates=[arg for arg in argv if isinstance(arg,str) and arg.endswith(".py")]
        for path in candidates:
            try: path=literal_path(path)
            except PermissionError: continue
            if path not in paths: paths.append(path)
    return paths

def collect_source(state,gateway,run,role,phase,path,prefix,*,stored=False):
    numbered=[]; parts=[]; refs=[]; snapshot=None; start=1; size=0
    for page in range(4096):
        for window in (80,40,20,10,5,2,1):
            opid=prefix+":"+str(page)+":"+str(window); args={"path":path,"start":start,"end":start+window-1}
            if stored:
                op=state.tool_operation(opid)
                if (not op or op["run_id"]!=run or op["role"]!=role or op["phase"]!=phase or op["tool"]!="filesystem.read" or op["state"]!="completed" or json.loads(op["arguments"])!=args):
                    raise ReconciliationRequired("Source baseline receipt missing or inconsistent")
                result=json.loads(op["result"])
            else: result=gateway.execute(run,role,phase,"filesystem.read",args,operation_id=opid)
            refs.append(opid)
            if not result.get("truncated"): break
        if result.get("read_failed"):
            if page==0 and result.get("error")=="FileNotFoundError":
                return {"path":path,"status":"absent","sha256":None,"content":"","numbered":"","total_lines":0,"operation_refs":refs}
            raise ReconciliationRequired("Authorized source read unavailable")
        if result.get("truncated") or result.get("redacted"): raise ContextCapacityError("source_line",MAX_SOURCE_CHARS+1,MAX_SOURCE_CHARS)
        if snapshot is None: snapshot=result["sha256"]
        if result.get("path")!=path or result.get("start")!=start or result.get("sha256")!=snapshot: raise ReconciliationRequired("Source changed between authorized read pages")
        source=result.get("source_text")
        if not isinstance(source,str): raise ReconciliationRequired("Exact source text is unavailable")
        numbered.extend(result.get("content","").splitlines()); parts.append(source); size+=len(source)
        if MAX_SOURCE_CHARS < size: raise ContextCapacityError("source_file",size,MAX_SOURCE_CHARS)
        if result["end"]==result["total_lines"]:
            content="".join(parts)
            if hashlib.sha256(content.encode("utf-8")).hexdigest()!=snapshot: raise ReconciliationRequired("Source text does not match recorded byte hash")
            return {"path":path,"status":"available","sha256":snapshot,"content":content,"numbered":"\n".join(numbered),"total_lines":result["total_lines"],"operation_refs":refs}
        if result["end"] < start: raise ReconciliationRequired("Source page made no progress")
        start=result["end"]+1
    raise ContextCapacityError("source_pages",4097,4096)

def excerpts(records,allowed):
    entries=[]
    for row in records:
        selected=[]; size=0
        for line in row["numbered"].splitlines():
            if 12000 < size+len(line)+1: break
            selected.append(line); size+=len(line)+1
        entry={key:row[key] for key in ("path","status","sha256","total_lines","operation_refs")}
        entry.update(content="\n".join(selected),content_format="numbered source lines",write_scope=row["path"] in allowed); entries.append(entry)
    def refresh(entry):
        count=len(entry["content"].splitlines()); entry.update(start=1,end=count,operation_ref=entry["operation_refs"][0])
        entry["complete"]=entry["status"]=="available" and count==entry["total_lines"]
        entry["next_read"]=None if entry["complete"] or entry["status"]=="absent" else {"path":entry["path"],"start":count+1,"end":count+PAGE_LINES}
    for entry in entries: refresh(entry)
    while 24000 < len(json.dumps(entries,sort_keys=True)):
        selected=max(entries,key=lambda item:len(item["content"]))
        if not selected["content"]: raise ContextCapacityError("SOURCE_SNAPSHOTS",len(json.dumps(entries)),24000)
        selected["content"]="\n".join(selected["content"].splitlines()[:-1]); refresh(selected)
    return entries

def candidate_manifest(contract,plan_hash,receipt,baseline,current,changed):
    previous={row["path"]:row for row in baseline}; now={row["path"]:row for row in current}; rows=[]
    if not receipt.get("commands"): raise ReconciliationRequired("Review has no test receipts")
    if set(previous)!=set(now): raise ReconciliationRequired("Source coverage changed")
    observed={path for path in previous if previous[path]["sha256"]!=now[path]["sha256"]}
    if observed-set(changed): raise ReconciliationRequired("Changed source has no accepted write receipt")
    for path in sorted(changed):
        old,new=previous[path],now[path]
        if new["status"]!="available": raise ReconciliationRequired("Candidate source missing")
        for command in receipt["commands"]:
            result=command.get("result") or {}
            if command.get("ok") is not True or result.get("source_hashes",{}).get(path)!=new["sha256"]: raise ReconciliationRequired("Review candidate differs from tested source")
        patch="".join(difflib.unified_diff(old["content"].splitlines(True),new["content"].splitlines(True),fromfile="/dev/null" if old["status"]=="absent" else "a/"+path,tofile="b/"+path))
        rows.append({"path":path,"before_sha256":old["sha256"],"after_sha256":new["sha256"],"change":"create" if old["status"]=="absent" else "modify","diff":patch,"baseline_refs":old["operation_refs"],"candidate_refs":new["operation_refs"],"complete":True})
    value={"schema_version":1,"task_contract_hash":digest(contract),"plan_hash":plan_hash,"test_receipt_hash":digest(receipt),"tested_scope_hash":receipt.get("tested_scope_hash"),"files":rows}
    size=len(json.dumps(value,sort_keys=True))
    if 24000 < size: raise ContextCapacityError("CANDIDATE_MANIFEST",size)
    return value
