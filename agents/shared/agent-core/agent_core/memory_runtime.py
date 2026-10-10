"""Optional runtime-owned draft ingestion from already accepted engine checkpoints."""
from __future__ import annotations
import hashlib,json,time,uuid
from pathlib import Path
from .contracts import ContractDenied
from .memory_authority import read_json,evaluate_memory_access


def check_binding(snapshot):
    if "memory_binding" not in snapshot and "memory_binding_path" not in snapshot:return
    path=Path(snapshot["memory_binding_path"])
    try:read_json(path)
    except (ValueError,OSError) as exc:raise ContractDenied("memory binding unavailable or changed") from exc
    if hashlib.sha256(path.read_bytes()).hexdigest()!=snapshot["memory_binding_hash"]:
        raise ContractDenied("memory binding changed; resume requires a new run")


def pin_binding(path,session,workspace,engine):
    binding=read_json(path)
    required={"version","session_id","store","grant"}
    if not isinstance(binding,dict) or not required<=set(binding) or set(binding)-required-{"namespace","sensitivity"} or binding["version"]!=1:
        raise ContractDenied("invalid memory binding")
    grant=binding["grant"]
    if not isinstance(grant,dict):raise ContractDenied("explicit memory grant object required")
    if binding["session_id"]!=session["session_id"] or grant.get("identity")!=session["identity"] or grant.get("run_id")!=session["session_id"]:
        raise ContractDenied("memory binding must explicitly authorize originating session identity")
    allowed={"research-forge":{"ide:deep-research"},"daily-coder":{"ide:daily-coder","ide:use-master"}}
    if grant.get("role") not in allowed[engine]:raise ContractDenied("memory binding parent mismatches engine")
    from .memory import KnowledgeStore
    store=KnowledgeStore(binding["store"])
    if store.kind not in ({"research"} if engine=="research-forge" else {"project","daily"}):
        raise ContractDenied("automatic ingestion cannot cross workflow/store boundary")
    access=evaluate_memory_access(grant,workspace=workspace,store_id=store.store_id,kind=store.kind)
    store._authorize(access,binding.get("namespace","default"),write=True)
    access.effective_grant.authorize("data_classes",binding.get("sensitivity","private"))
    return {"memory_binding":binding,"memory_binding_path":str(Path(path).absolute()),"memory_binding_hash":hashlib.sha256(Path(path).read_bytes()).hexdigest(),"memory_store_id":store.store_id}


def ingest_checkpoint(row,result):
    binding=row["snapshot"].get("memory_binding")
    if not binding:return {"records":[]}
    check_binding(row["snapshot"])
    from .memory import KnowledgeStore
    store=KnowledgeStore(binding["store"])
    if store.store_id!=row["snapshot"]["memory_store_id"]:raise ContractDenied("memory store identity changed")
    grant=json.loads(json.dumps(binding["grant"]))
    # Binding explicitly authorizes this session; each recorded draft carries
    # the actual originating run, never the configuration file's narrative.
    grant["run_id"]=row["run_id"]
    access=evaluate_memory_access(grant,workspace=row["workspace"],store_id=store.store_id,kind=store.kind)
    namespace=binding.get("namespace","default");sensitivity=binding.get("sensitivity","private")
    records=[];skipped=0;skipped_deleted=0
    payloads=[]
    if row["engine"]=="research-forge":
        state=result.get("state",{})
        if state.get("run_id")!=row.get("legacy_id"):raise ContractDenied("research checkpoint origin mismatch")
        selected=set(state.get("selected_urls",[]))
        for sid,read in state.get("reads",{}).items():
            source=state.get("sources",{}).get(sid,{})
            locator=source.get("canonical_url")
            text=read.get("text")
            if locator not in selected or not isinstance(text,str) or not text.strip():skipped+=1;continue
            synthetic=not row["live"] or source.get("source_authenticity")=="synthetic_fixture" or read.get("source_authenticity")=="synthetic_fixture"
            if read.get("content_availability") in {"unavailable","failed"}:skipped+=1;continue
            content_hash=hashlib.sha256(text.encode()).hexdigest()
            payloads.append((source.get("canonical_title") or sid,text,{"id":str(uuid.uuid5(uuid.UUID(row["run_id"]),sid+":"+locator+":"+content_hash)),"locator":locator,"retrieved_at":source.get("retrieved_at") or time.time(),"content_hash":content_hash,"retrieval_status":"retrieved","synthetic":synthetic}))
    else:
        # Record a bounded outcome, not arbitrary engineering files or prompts.
        body=json.dumps({"run_id":row["run_id"],"status":result.get("status"),"phase":result.get("phase")},sort_keys=True)
        payloads.append(("Coding checkpoint",body,{"locator":"run://"+row["run_id"]+"/checkpoint","retrieved_at":time.time(),"content_hash":hashlib.sha256(body.encode()).hexdigest(),"retrieval_status":"provided","synthetic":not row["live"]}))
    for title,body,source in payloads:
        record_id=str(uuid.uuid5(uuid.UUID(row["run_id"]),namespace+":"+source["locator"]+":"+source["content_hash"]))
        # Repeat recovery does not reinsert changed timestamps/provenance.
        try:
            existing=store.inspect(record_id,access,include_deleted=True)
        except KeyError:existing=None
        if existing is not None:
            if existing["deleted_at"] is not None:
                skipped_deleted+=1
                continue
            if existing["body"]!=body:raise ContractDenied("ingestion idempotency collision")
            records.append(record_id);continue
        record=store.add_draft(access,namespace=namespace,kind="evidence",title=title,body=body,sources=[source],sensitivity=sensitivity,record_id=record_id)
        records.append(record["id"])
    return {"records":records,"skipped_unavailable":skipped,"skipped_deleted":skipped_deleted,"verification_state":"draft"}
