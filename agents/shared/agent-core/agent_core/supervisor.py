"""Durable orchestration facade. Engines retain policy and workflow authority."""
from __future__ import annotations
from pathlib import Path
import sqlite3
import uuid
from .contracts import ContractDenied
from .lifecycle import RunLock, RunBusy, ReconciliationRequired
from .runtime_authority import repository_root, runtime_snapshot
from .sessions import SessionStore, TERMINAL
from .engine_adapters import DailyCoderAdapter, ResearchForgeAdapter


class Supervisor:
    def __init__(self, directory=None, repository=None, *, adapters=None):
        self.repository=Path(repository).resolve() if repository else repository_root()
        self.directory=Path(directory or self.repository/".agentnexus").resolve()
        self.store=SessionStore(self.directory/"sessions.sqlite")
        self.adapters=adapters if adapters is not None else {
            "daily-coder":DailyCoderAdapter(self.repository/"agents/coding/daily-coder-ecosystem"),
            "research-forge":ResearchForgeAdapter(self.repository/"agents/research/research-forge")}

    def new_session(self, identity="local", project=None, profile="default"):
        return self.store.new_session(identity,project,profile)
    def sessions(self): return self.store.sessions()
    def runs(self,engine=None,session_id=None,limit=50):
        return [self.status(r["run_id"]) for r in self.store.runs(engine,session_id,limit)]

    def create_run(self,session_id,engine,request,workspace,live=False, *, parent_id=None,idempotency_key=None,provider="mock",limit_usd=5.0,limit_tokens=80000,deadline=None,_imported=False,memory_binding=None):
        if engine not in self.adapters: raise ContractDenied("unknown or unavailable execution engine")
        workspace=Path(workspace).resolve()
        if not workspace.is_dir(): raise ValueError("workspace must exist")
        session=next((s for s in self.sessions() if s["session_id"]==session_id),None)
        if not session: raise KeyError(session_id)
        if session["project"] and not workspace.is_relative_to(Path(session["project"])): raise ContractDenied("workspace outside session project")
        if engine == "research-forge" and isinstance(request,str): request={"topic":request,"objective":request}
        if engine == "daily-coder" and not isinstance(request,str): raise ValueError("coding request must be text")
        if engine == "research-forge" and not isinstance(request,dict): raise ValueError("research request must be an object")
        if live and provider == "mock" and engine == "daily-coder": raise ContractDenied("live coding requires an explicit provider")
        snapshot=self.adapters[engine].snapshot(workspace,live,provider)
        snapshot["provider"]=provider if engine == "daily-coder" else ("live" if live else "mock")
        if memory_binding is not None:
            from .memory_runtime import pin_binding
            snapshot.update(pin_binding(memory_binding,session,workspace,engine))
        registry=runtime_snapshot().snapshot_id
        row=self.store.create_run(session_id,engine,request,workspace,snapshot,registry,parent_id=parent_id,task_key=idempotency_key,limit_usd=limit_usd,limit_tokens=limit_tokens,deadline=deadline,live=live,imported=_imported)
        return self.status(row["run_id"])

    def _current(self,row):
        from .routing_runtime import PIN_FIELDS
        options={"pinned":row["snapshot"]} if PIN_FIELDS <= set(row["snapshot"]) else {}
        snapshot=self.adapters[row["engine"]].snapshot(row["workspace"],row["live"],row["snapshot"]["provider"],**options)
        snapshot["provider"]=row["snapshot"]["provider"]
        from .routing_runtime import PIN_FIELDS,load_model_settings
        if PIN_FIELDS <= set(row["snapshot"]):
            snapshot.update(load_model_settings(self.repository,pinned=row["snapshot"]))
        from .memory_runtime import check_binding
        check_binding(row["snapshot"])
        for field in ("memory_binding","memory_binding_path","memory_binding_hash","memory_store_id"):
            if field in row["snapshot"]:snapshot[field]=row["snapshot"][field]
        return snapshot,runtime_snapshot().snapshot_id

    def status(self,key):
        row=self.store.get_run(key)
        events=self.store.events(row["run_id"])
        row["execution_started"]=any(e["kind"] == "status" and e["payload"].get("engine_dispatch") for e in events)
        row["accounting"]=self.store.accounting(row["run_id"])
        row["artifacts"]=self.store.artifacts(row["run_id"])
        row["cancelled"]=row["status"] == "CANCELLED"
        row["acknowledged"]=row["cancelled"] if row["cancel_requested"] else row["execution_started"]
        checkpoint=self.store.latest_checkpoint(row["run_id"])
        if checkpoint:
            row["phase"]=checkpoint.get("phase")
            row["pending_approvals"]=checkpoint.get("pending_approvals",[])
            row["result"]=checkpoint.get("result")
            row["memory"]=checkpoint.get("memory")
        return row

    def _record_memory(self,row,result):
        if not row["snapshot"].get("memory_binding"):return result
        from .memory_runtime import ingest_checkpoint
        try:return {**result,"memory":ingest_checkpoint(row,result)}
        except (ContractDenied,ValueError,KeyError,OSError,sqlite3.Error) as exc:
            # Settle known provider usage, but do not claim successful retention.
            return {**result,"status":"BLOCKED","memory":{"error":type(exc).__name__,"detail":"authorized draft ingestion failed; retry memory explicitly"}}

    def _settle(self,row,call_id,result):
        result=self._record_memory(row,result)
        usage=result.get("usage") or {}
        if usage.get("unknown") or usage.get("usd") is None or usage.get("tokens") is None or result.get("status") == "RECONCILIATION_REQUIRED":
            self.store.finish_call(call_id,"unknown")
            self.store.checkpoint(row["run_id"],result,result.get("artifacts",()))
            return self.status(row["run_id"])
        # Engine reports are cumulative; reserve/settle each supervisor segment
        # using its delta so approval/resume cannot double-count previous calls.
        accounting=self.store.accounting(row["run_id"],descendants=False)
        previous_tokens=accounting["tokens"]
        previous_usd=sum(accounting[k] for k in ("estimated_usd","reported_usd","reconciled_usd"))
        tokens=usage.get("tokens")
        if tokens is None: tokens=row["limit_tokens"]
        tokens=max(0,int(tokens)-previous_tokens)
        usd=max(0,float(usage.get("usd",0))-previous_usd)
        pending=next(c for c in self.store.pending_calls(row["run_id"]) if c["call_id"]==call_id)
        overrun=tokens > pending["estimated_tokens"] or usd > pending["estimated_usd"] + 1e-9
        self.store.finish_call(call_id,"confirmed",tokens=tokens,usd=usd,usage_status=usage.get("usage_status","estimated"))
        if overrun:
            result={**result,"status":"BLOCKED","budget_overrun":True}
        self.store.checkpoint(row["run_id"],result,result.get("artifacts",()))
        if self.store.get_run(row["run_id"])["cancel_requested"]:
            if result.get("status") in TERMINAL:
                try: self.store.acknowledge_cancel(row["run_id"])
                except ValueError: self.store.update(row["run_id"],"CANCEL_REQUESTED")
            else: self.store.update(row["run_id"],"CANCEL_REQUESTED")
        else: self.store.update(row["run_id"],result.get("status","BLOCKED"))
        return self.status(row["run_id"])

    def execute(self,key,answers=None):
        row=self.store.get_run(key); key=row["run_id"]
        with RunLock(self.directory/"locks",row["root_id"]):
            row=self.store.get_run(key)
            if row["status"] in TERMINAL: return self.status(key)
            if (row.get("provenance") or {}).get("imported") and row["completeness"] != "complete":
                self.store.update(key,"RECONCILIATION_REQUIRED",payload={"reason":"incomplete imported execution cannot replay"})
                return self.status(key)
            adapter=self.adapters[row["engine"]]
            try:
                snapshot,registry=self._current(row)
                self.store.check_pin(key,snapshot,registry)
            except (ContractDenied,ValueError) as exc:
                self.store.update(key,"BLOCKED",payload={"reason":str(exc)})
                return self.status(key)
            if row["cancel_requested"]: return self._cancel_idle(row,adapter)
            pending=self.store.pending_calls(key)
            if pending:
                result=adapter.inspect(row)
                # Only an engine-accepted terminal/human checkpoint with known
                # usage can reconcile an interrupted supervisor segment.
                if result.get("status") in TERMINAL | {"WAITING_HUMAN"} and not (result.get("usage") or {}).get("unknown"):
                    self._settle(row,pending[0]["call_id"],result)
                    return self.status(key)
                self.store.finish_call(pending[0]["call_id"],"unknown")
                return self.status(key)
            if row["status"] == "RECONCILIATION_REQUIRED": return self.status(key)
            if row["status"] == "RUNNING" and row["legacy_id"]:
                result=adapter.inspect(row)
                if result.get("status") in TERMINAL | {"WAITING_HUMAN"} and not (result.get("usage") or {}).get("unknown"):
                    result=self._record_memory(row,result)
                    self.store.checkpoint(key,result,result.get("artifacts",()))
                    self.store.update(key,result["status"])
                    return self.status(key)
            if row["limit_tokens"] <= 0 or row["limit_usd"] <= 0:
                self.store.update(key,"BLOCKED",payload={"reason":"resource ceiling exhausted before dispatch"})
                return self.status(key)
            spent=self.store.accounting(row["root_id"])
            own=self.store.accounting(key,descendants=False)
            root=self.store.get_run(row["root_id"])
            available_tokens=max(0,root["limit_tokens"]-spent["tokens"]-spent["reserved_tokens"])
            available_usd=max(0,root["limit_usd"]-sum(spent[k] for k in ("estimated_usd","reported_usd","reconciled_usd","reserved_usd")))
            tokens=max(0,row["limit_tokens"]-own["tokens"])
            usd=max(0,row["limit_usd"]-sum(own[k] for k in ("estimated_usd","reported_usd","reconciled_usd")))
            if tokens <= 0 or usd <= 0 or tokens > available_tokens or usd > available_usd + 1e-9:
                self.store.update(key,"BLOCKED",payload={"reason":"parent headroom cannot cover native remaining resource grant"})
                return self.status(key)
            if not row["legacy_id"]:
                alias=adapter.create(row)
                self.store.set_alias(key,alias,provenance={"engine":row["engine"],"created_by":"supervisor"})
                row=self.store.get_run(key)
                self.store.checkpoint(key,{"phase":"prepared","engine_id":alias,"configuration_hash":row["config_hash"]})
            call_id=str(uuid.uuid4())
            try:
                self.store.begin_call(key,call_id,tokens,usd)
            except ValueError as exc:
                self.store.update(key,"BLOCKED",payload={"reason":str(exc)})
                return self.status(key)
            self.store.update(key,"RUNNING",payload={"engine_dispatch":True,"call_id":call_id})
            try:
                result=adapter.execute(row,answers)
            except (ContractDenied,ReconciliationRequired):
                result=adapter.inspect(row)
                if result.get("status") not in TERMINAL | {"WAITING_HUMAN"}: result["status"]="RECONCILIATION_REQUIRED"; result.setdefault("usage",{})["unknown"]=True
            except Exception:
                # Do not log raw provider exceptions or assume a remote request
                # did not run. Reconciliation retains the original reservation.
                self.store.finish_call(call_id,"unknown")
                return self.status(key)
            return self._settle(row,call_id,result)

    def _cancel_idle(self,row,adapter):
        key=row["run_id"]
        if not row["legacy_id"]:
            self.store.acknowledge_cancel(key)
            return self.status(key)
        adapter.cancel(row)
        result=adapter.inspect(row)
        # Holding the execution lock proves no local supervisor is still
        # running. An idle, known native checkpoint may acknowledge STOP even
        # when the interrupted supervisor segment has not yet settled.
        if result.get("status") not in TERMINAL and not (result.get("usage") or {}).get("unknown") and hasattr(adapter,"acknowledge"):
            result=adapter.acknowledge(row)
        if not self.store.pending_calls(key):
            if result.get("status") in TERMINAL and not (result.get("usage") or {}).get("unknown"):
                self.store.acknowledge_cancel(key)
        else:
            for call in self.store.pending_calls(key):
                if result.get("status") in TERMINAL and not (result.get("usage") or {}).get("unknown"):
                    return self._settle(row,call["call_id"],result)
                self.store.finish_call(call["call_id"],"unknown")
        return self.status(key)

    def cancel(self,key):
        row=self.store.request_cancel(key)
        descendants=[r for r in self.store.runs(limit=1000) if r["root_id"]==row["root_id"] and r["cancel_requested"]]
        # Intent persists without taking the execution lock. Only idle lock
        # ownership plus engine acknowledgment may confirm local termination.
        for child in sorted(descendants,key=lambda r:r["depth"],reverse=True):
            if child["status"] in TERMINAL: continue
            adapter=self.adapters[child["engine"]]
            if child["legacy_id"]: adapter.cancel(child)
            try:
                with RunLock(self.directory/"locks",child["root_id"]): self._cancel_idle(child,adapter)
            except (RunBusy,ValueError): pass
        return self.status(row["run_id"])

    def import_legacy(self,session_id,engine,legacy_id,workspace, *, live=False,provider="mock"):
        with RunLock(self.directory/"locks","import:"+engine+":"+legacy_id):
            with self.store.connect() as connection:
                existing=connection.execute("SELECT run_id FROM runs WHERE engine=? AND legacy_id=?",(engine,legacy_id)).fetchone()
            if existing: return self.status(existing[0])
            return self._import_legacy(session_id,engine,legacy_id,workspace,live=live,provider=provider)

    def _import_legacy(self,session_id,engine,legacy_id,workspace, *, live=False,provider="mock"):
        # Import is an explicit local administrative operation; source histories
        # are retained and completeness determines whether replay is permitted.
        row=self.create_run(session_id,engine,"Imported legacy execution" if engine=="daily-coder" else {"topic":"Imported legacy execution"},workspace,live,provider=provider,_imported=True)
        self.store.set_alias(row["run_id"],legacy_id,completeness="partial",provenance={"engine":engine,"legacy_id":legacy_id,"imported":True})
        try:
            native=self.adapters[engine].inspect(self.store.get_run(row["run_id"]))
        except Exception:
            self.store.update(row["run_id"],"BLOCKED",payload={"reason":"legacy inspection failed; no replay authority"})
            raise
        imported=self.store.get_run(row["run_id"])
        usage=native.get("usage") or {}
        call_id=self.store.pending_calls(row["run_id"])[0]["call_id"]
        if usage.get("unknown") or "usd" not in usage:
            self.store.finish_call(call_id,"unknown")
            native={**native,"status":"RECONCILIATION_REQUIRED"}
        else:
            self.store.finish_call(call_id,"confirmed",tokens=usage.get("tokens") if usage.get("tokens") is not None else imported["limit_tokens"],usd=usage["usd"],usage_status=usage.get("usage_status","estimated"))
        self.store.checkpoint(row["run_id"],native,native.get("artifacts",()))
        # Incomplete legacy runs never acquire new execution authority merely
        # because current configuration can be compiled.
        self.store.update(row["run_id"],native["status"] if native["status"] in TERMINAL else "RECONCILIATION_REQUIRED")
        return self.status(row["run_id"])
