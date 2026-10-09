"""Durable tool receipts and policy enforcement before every side effect."""
from __future__ import annotations
import hashlib,json,time,uuid
from agent_core.lifecycle import ReconciliationRequired
from .tool_broker import ToolDenied,file_sha
from .util import canonical_json,sha256_text

class ApprovalRequired(RuntimeError):
    def __init__(self,kind,subject_hash,detail=None):
        super().__init__(f"approval required: {kind}")
        self.kind=kind; self.subject_hash=subject_hash; self.detail=detail or {}

WRITE_TOOLS={"filesystem.write","patch.apply"}

class PolicyGateway:
    def __init__(self,broker,state,policies,approvals_required=True,deadline=None):
        self.broker=broker; self.state=state; self.policies=policies; self.approvals_required=approvals_required; self.deadline=deadline

    def _cancel_requested(self,run_id):
        if self.deadline is not None and time.time()>=self.deadline: self.state.request_cancel(run_id)
        return self.state.get(run_id)["status"] in {"CANCEL_REQUESTED","CANCELLED"}

    def _approved(self,run_id,tool,plan_hash):
        if tool in WRITE_TOOLS and self.approvals_required:
            if self.state.approval_state(run_id,"plan",plan_hash)!="approved":
                raise ApprovalRequired("plan",plan_hash,{"tool":tool})

    def reconcile(self,run_id):
        """Prove completed CAS writes by content; never repeat an uncertain operation."""
        for op in self.state.pending_tool_operations(run_id):
            if op["tool"] not in WRITE_TOOLS or not op["expected_output_hash"]: continue
            args=json.loads(op["arguments"])
            row=self.state.get(run_id)
            if op["plan_hash"] != row.get("plan_hash"): continue
            # Recovery requires durable human approval even for an earlier mock gateway.
            if not op["plan_hash"] or self.state.approval_state(run_id,"plan",op["plan_hash"])!="approved": continue
            self.broker.authorize(op["role"],op["tool"])
            plan=next((a for a in reversed(self.state.artifacts(run_id)) if a["kind"]=="plan"),None)
            if not plan: continue
            payload=json.loads(__import__('pathlib').Path(plan["path"]).read_text())["payload"]
            path=self.broker.safe_path(args["path"],True,payload.get("file_allowlist"))
            if path.is_file() and file_sha(path)==op["expected_output_hash"]:
                result={"path":args["path"],"sha256":op["expected_output_hash"],"reconciled":True}
                self.state.finish_tool_operation(op["operation_id"],result)
        return not self.state.pending_tool_operations(run_id)

    def execute(self,run_id,role,phase,tool,arguments,plan_allowlist=None,plan_hash=None,operation_id=None):
        started=time.time(); operation=None; dispatched=False
        try:
            if self._cancel_requested(run_id) or self.state.get(run_id)["status"]=="RECONCILIATION_REQUIRED":
                raise ReconciliationRequired("tool dispatch blocked by run status")
            self.broker.authorize(role,tool)
            self._approved(run_id,tool,plan_hash)
            identity={"run":run_id,"role":role,"phase":phase,"tool":tool,"arguments":arguments,"plan":plan_hash}
            operation=operation_id or (sha256_text(canonical_json(identity)) if tool in WRITE_TOOLS else str(uuid.uuid4()))
            old=self.state.tool_operation(operation)
            if old:
                if (old["run_id"],old["role"],old["phase"],old["tool"],json.loads(old["arguments"]),old["plan_hash"]) != (run_id,role,phase,tool,arguments,plan_hash):
                    raise ReconciliationRequired("tool operation identity changed")
                if old["state"]=="completed":
                    if tool in WRITE_TOOLS:
                        observed=self.broker.safe_path(arguments["path"],True,plan_allowlist)
                        if not observed.is_file() or file_sha(observed)!=old["expected_output_hash"]:
                            raise ReconciliationRequired("completed write contents changed; explicit reconciliation required")
                    return json.loads(old["result"])
                raise ReconciliationRequired("tool outcome requires explicit reconciliation")
            path=None; expected=None
            if tool in WRITE_TOOLS:
                path=self.broker.safe_path(arguments["path"],True,plan_allowlist)
                if tool=="filesystem.write":
                    if path.exists() and (not arguments.get("expected_sha256") or file_sha(path)!=arguments["expected_sha256"]):
                        raise ToolDenied("file changed or overwrite hash missing; re-read before writing")
                    content=arguments["content"]
                else:
                    original=path.read_text(encoding="utf-8")
                    if not arguments.get("expected_sha256") or file_sha(path)!=arguments["expected_sha256"]:
                        raise ToolDenied("file changed since it was read; re-read before patching")
                    if original.count(arguments["find"])!=1: raise ToolDenied("patch find must match exactly once")
                    content=original.replace(arguments["find"],arguments["replace"],1)
                expected=hashlib.sha256(content.encode("utf-8")).hexdigest()
            old=self.state.begin_tool_operation(operation,run_id,role,phase,tool,arguments,plan_hash,str(path) if path else None,expected)
            if old:
                if old["state"]=="completed": return json.loads(old["result"])
                raise ReconciliationRequired("tool outcome unknown; explicit reconciliation required")
            dispatched=True
            if tool in {"tests.run","shell.readonly"}:
                result=self.broker.execute(role,tool,arguments,plan_allowlist=plan_allowlist,
                    cancel_check=lambda:self._cancel_requested(run_id))
            else:
                result=self.broker.execute(role,tool,arguments,plan_allowlist=plan_allowlist)
            if isinstance(result,dict) and result.get("cancelled") and not result.get("cancellation_confirmed"):
                raise ReconciliationRequired("isolated process cancellation unconfirmed")
            self.state.finish_tool_operation(operation,result)
            summary={"returncode":result.get("returncode"),"timeout":bool(result.get("timeout",False))} if tool=="tests.run" and isinstance(result,dict) else None
            self.state.record_tool_call(run_id,role,phase,tool,arguments,"allow",None,sha256_text(canonical_json(result)),int((time.time()-started)*1000),result_summary=summary)
            if self.state.get(run_id)["status"] in {"CANCEL_REQUESTED","CANCELLED"}:
                raise ReconciliationRequired("cancellation requested; tool receipt recorded")
            return result
        except ReconciliationRequired:
            self.state.set_status(run_id,"RECONCILIATION_REQUIRED")
            raise
        except (ApprovalRequired,ToolDenied) as exc:
            if dispatched:
                self.state.set_status(run_id,"RECONCILIATION_REQUIRED")
                raise ReconciliationRequired("dispatched tool outcome unconfirmed; receipt retained") from exc
            if operation: self.state.finish_tool_operation(operation,{"error":str(exc)},"denied")
            self.state.record_tool_call(run_id,role,phase,tool,arguments,"blocked" if isinstance(exc,ApprovalRequired) else "deny",str(exc),None,int((time.time()-started)*1000))
            raise
        except BaseException as exc:
            # The broker may have executed before raising, including process interruption.
            if operation:
                self.state.set_status(run_id,"RECONCILIATION_REQUIRED")
                if isinstance(exc,Exception): raise ReconciliationRequired("tool outcome unknown; receipt retained") from exc
            raise

    def safe_execute(self,run_id,role,phase,tool,arguments,plan_allowlist=None,plan_hash=None,operation_id=None):
        try:
            return {"ok":True,"result":self.execute(run_id,role,phase,tool,arguments,plan_allowlist,plan_hash,operation_id)}
        except ReconciliationRequired: raise
        except ApprovalRequired as exc:
            return {"ok":False,"error":"approval_required","message":str(exc),"kind":exc.kind}
        except ToolDenied as exc: return {"ok":False,"error":"denied","message":str(exc)}
        except Exception as exc: return {"ok":False,"error":type(exc).__name__,"message":str(exc)[:2000]}
