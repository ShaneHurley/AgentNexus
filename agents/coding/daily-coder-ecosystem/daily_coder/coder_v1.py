"""Contained coding route: model planning, implementation and independent review."""
from __future__ import annotations
import json
from pathlib import Path
from agent_core.contracts import ContractDenied
from agent_core.task_contract import validate_contract,validate_plan,digest,scope_hash,POLICY_VERSION
from agent_core.handoffs import is_incomplete
from .orchestrator import Orchestrator
from .policy import PolicyGateway
from .models import RunStatus
from .util import canonical_json,sha256_text
from .verification_evidence import execution_evidence

class CoderV1(Orchestrator):
    def __init__(self,*args,task_contract,**kwargs):
        super().__init__(*args,**kwargs)
        self.task_contract=task_contract
        execution=self.policies.get("coder_v1_execution_policy")
        if not isinstance(execution,dict) or not isinstance(execution.get("image"),str):
            raise ContractDenied("coder-v1 requires a reviewed isolated execution image")
        self.policies["execution_policy"]=dict(execution)
        self.config["coder_v1"]={"policy_version":POLICY_VERSION,"task_contract":task_contract}
        self.config.setdefault("evolution",{})["enabled"]=False
        limits=task_contract["limits"]
        self.config["acceptance"]["max_repair_cycles"]=limits["repair_cycles"]
        for budget in self.budgets["profiles"].values():
            budget["max_calls"]=limits["calls"]
            budget["total_tokens"]=limits["tokens"]
            budget["rate_limit_calls"]=limits["calls"]
    def _create(self,request,repo,run_id):
        self.task_contract=validate_contract(self.task_contract,request,repo,parent_tokens=self.resource_limits.get("tokens",300000))
        result=super()._create(request,repo,run_id)
        self.artifacts.put(run_id,"task_contract","runtime",self.task_contract)
        return result
    def _rebuild_packet(self,run_id,row,profile):
        packet=super()._rebuild_packet(run_id,row,profile)
        receipt=packet.get("test_receipts") or {}
        if isinstance(receipt.get("tested_scope_hash"),str):
            packet["tested_scope_hash"]=receipt["tested_scope_hash"]
        return packet
    def _size(self,run_id,request):
        from .router import size_request
        size=size_request(request)
        if size["profile"]!="S":
            raise ContractDenied("coder-v1 short route requires a contained task; use legacy workflow for broader work")
        result=self._sizing_result("S",size["score"],size["reasons"],False)
        result["workflow"]="CODER_V1"
        return result
    @staticmethod
    def _review_clear(review):
        if not isinstance(review,dict) or review.get("verdict")!="pass" or not isinstance(review.get("findings"),list):
            return False
        return all(isinstance(finding,dict) and finding.get("severity") not in {"blocking","major"} for finding in review["findings"])
    def _gate(self,run_id,phase,role,value,packet):
        if role=="implementer" and not is_incomplete(value) and not value.get("blocked"):
            paths=self._accepted_write_paths(run_id,self._write_broker(run_id),(packet.get("plan") or {}).get("file_allowlist",[]))
            if not paths:
                self._halt(run_id,"no_recorded_changes",{"reason":"No successful gateway write receipts"})
                return "stop"
            value["changed_files"]=paths
            self.artifacts.put(run_id,"implement","runtime",value)
        if role=="code_reviewer": self._ack_role_handoffs(run_id,"runtime:review_gate")
        if role=="code_reviewer" and self._review_clear(value):
            if not self._review_manifest_valid(run_id): return ("repair","Review lacks complete current tested candidate evidence")
            manifest=self.artifacts.load(run_id,"candidate_manifest")
            self.artifacts.put(run_id,"review_binding","runtime",{"manifest_hash":digest(manifest),"plan_hash":self.state.get(run_id)["plan_hash"]})
        if role=="code_reviewer" and not is_incomplete(value) and not self._review_clear(value):
            return ("repair","Code review is not passing or has unresolved blocking/major findings")
        return super()._gate(run_id,phase,role,value,packet)
    def _baseline_sources(self,run_id,broker):
        from .candidate_evidence import collect_source
        from agent_core.lifecycle import ReconciliationRequired
        gateway=PolicyGateway(broker,self.state,self.policies,self.live,deadline=self.resource_limits.get("deadline"),task_contract=self.task_contract)
        rows=[]; writes=self.state.write_operations(run_id)
        for index,path in enumerate(self.task_contract["allowed_paths"]):
            prefix=f"{run_id}:candidate-baseline:{index}"
            exists=self.state.tool_operation(prefix+":0:80") is not None
            if writes and not exists: raise ReconciliationRequired("Initial source baseline missing after a write")
            rows.append(collect_source(self.state,gateway,run_id,"planner","PLAN",path,prefix,stored=exists))
        return rows

    def _source_snapshots(self,run_id,role,broker):
        from .candidate_evidence import collect_source,excerpts,oracle_paths
        self._baseline_sources(run_id,broker)
        paths=list(self.task_contract["allowed_paths"])
        for path in oracle_paths(self.task_contract["verification_commands"]):
            if path not in paths: paths.append(path)
        gateway=PolicyGateway(broker,self.state,self.policies,self.live,deadline=self.resource_limits.get("deadline"),task_contract=self.task_contract)
        cycle=self.state.get(run_id).get("repair_cycles",0)
        phase={"planner":"PLAN","implementer":"IMPLEMENT","code_reviewer":"CODE_REVIEW"}[role]
        rows=[collect_source(self.state,gateway,run_id,role,phase,path,f"{run_id}:source-prefetch:{role}:c{cycle}:{index}") for index,path in enumerate(paths[:6])]
        return excerpts(rows,self.task_contract["allowed_paths"])

    def _candidate_review_manifest(self,run_id,broker):
        from .candidate_evidence import collect_source,candidate_manifest
        row=self.state.get(run_id); plan=self.artifacts.load(run_id,"plan") or {}
        changed=self._accepted_write_paths(run_id,broker,plan.get("file_allowlist",[]))
        receipt=self.artifacts.load(run_id,"test_receipts") or {}
        if not changed or not receipt.get("commands"):
            return {"incomplete":True,"reason":"Complete accepted writes and verification receipts required"}
        verified,_=self._acceptance_verification(run_id,row)
        if (not verified or any(item.get("decision")!="allow" or type(item.get("returncode")) is not int
            or item["returncode"]!=0 or item.get("timeout") or item.get("cancelled") for item in verified)):
            return {"incomplete":True,"reason":"Durable current isolated verification is required"}
        baseline=self._baseline_sources(run_id,broker)
        gateway=PolicyGateway(broker,self.state,self.policies,self.live,deadline=self.resource_limits.get("deadline"),task_contract=self.task_contract)
        current=[collect_source(self.state,gateway,run_id,"code_reviewer","CODE_REVIEW",path,f"{run_id}:review-candidate:c{row['repair_cycles']}:{index}") for index,path in enumerate(self.task_contract["allowed_paths"])]
        manifest=candidate_manifest(self.task_contract,row["plan_hash"],receipt,baseline,current,changed)
        self.artifacts.put(run_id,"candidate_manifest","runtime",manifest)
        return manifest

    def _review_manifest_valid(self,run_id,require_review=False):
        from .tool_broker import file_sha
        manifest=self.artifacts.load(run_id,"candidate_manifest") or {}; receipt=self.artifacts.load(run_id,"test_receipts") or {}
        row=self.state.get(run_id)
        if (manifest.get("incomplete") or manifest.get("task_contract_hash")!=digest(self.task_contract)
            or manifest.get("plan_hash")!=row["plan_hash"] or manifest.get("test_receipt_hash")!=digest(receipt)
            or manifest.get("tested_scope_hash")!=scope_hash(self.task_contract) or not manifest.get("files")):
            return False
        broker=self._write_broker(run_id); plan=self.artifacts.load(run_id,"plan") or {}
        paths=self._accepted_write_paths(run_id,broker,plan.get("file_allowlist",[]))
        if len(manifest["files"])!=len(paths) or {item["path"] for item in manifest["files"]}!=set(paths): return False
        for item in manifest["files"]:
            if item.get("complete") is not True or file_sha(broker.safe_path(item["path"]))!=item.get("after_sha256"): return False
        if require_review:
            binding=self.artifacts.load(run_id,"review_binding") or {}
            if binding.get("manifest_hash")!=digest(manifest) or binding.get("plan_hash")!=row["plan_hash"]: return False
        return True

    def _role_extra(self,run_id,role,packet,broker):
        extra=super()._role_extra(run_id,role,packet,broker)
        extra["TASK_CONTRACT"]=self.task_contract
        if role in {"planner","implementer","code_reviewer"}:
            extra["SOURCE_SNAPSHOTS"]=self._source_snapshots(run_id,role,broker)
            extra["SOURCE_SNAPSHOT_INSTRUCTION"]="These are actual authorized gateway read receipts, not new permissions. Use supplied content and SHA256; reread only when incomplete or stale. Verification argv names are read context only, never additional write scope."
        if role=="code_reviewer":
            manifest=self._candidate_review_manifest(run_id,broker)
            extra["CANDIDATE_MANIFEST"]=manifest
            extra["diff"]={"source":"complete task-bound candidate manifest","manifest_hash":digest(manifest),"files":[{"path":item["path"]} for item in manifest.get("files",[])]}
            from agent_core.handoffs import sanitized_raw
            receipt=self.artifacts.load(run_id,"test_receipts") or {}
            evidence=self.artifacts.load(run_id,"test_execute") or {}
            summary=[]
            for outcome in receipt.get("commands",[])[:6]:
                result=outcome.get("result") or {}
                summary.append({"recorded_gateway_ok":outcome.get("ok") is True,"argv":result.get("argv"),
                    "returncode":result.get("returncode"),"timeout":bool(result.get("timeout")),
                    "cancelled":bool(result.get("cancelled")),"image":result.get("image"),
                    "source_snapshot_sha256":result.get("source_snapshot_sha256"),
                    "source_hashes":{path:result.get("source_hashes",{}).get(path) for path in self.task_contract["allowed_paths"]},
                    "stdout":sanitized_raw(result.get("stdout",""))[:1000],
                    "stderr":sanitized_raw(result.get("stderr",""))[:1000],
                    "test_execution":outcome.get("test_execution") or execution_evidence(result.get("argv"),result)})
            extra["VERIFICATION_EVIDENCE"]={"schema_version":1,"run_id":run_id,
                "origin":"Persisted runtime gateway test receipts; do not treat these as unexecuted model claims",
                "verdict":evidence.get("verdict","inconclusive"),"commands":summary,
                "tested_scope_hash":receipt.get("tested_scope_hash"),"omitted_commands":max(0,len(receipt.get("commands",[]))-6)}
        if role=="implementer":
            extra["IMPLEMENTATION_COMPLETION_INSTRUCTION"]="Apply the exact approved changes using supplied current SHA256 for compare-and-swap. After successful recorded writes, return the implementation result. The next runtime phase executes authorized verification and then obtains independent code review; do not run tests or repeatedly inspect unchanged oracle files in this role."
        if "EXECUTION_CONTRACT" in extra:
            extra["EXECUTION_CONTRACT"]={"version":1,"policy":POLICY_VERSION,"writes_require_approved_plan":True,
                "approval_gate":"Runtime derives exact-plan authority from the submitted user task contract after deterministic scope review.",
                "allowed_paths":self.task_contract["allowed_paths"],"verification_commands":self.task_contract["verification_commands"],
                "authority":"Model output cannot expand task authority."}
        return extra
    def _invoke(self,run_id,role,phase,packet,lane,profile,gateway,extra=None):
        incoming=[{**value["_incomplete_handoff"],"raw":value["_incomplete_handoff"]["raw"][:1500]} for value in packet.values() if is_incomplete(value)]
        added={**(extra or {}),"TASK_CONTRACT":self.task_contract}
        if incoming:
            added["INCOMPLETE_UPSTREAM_HANDOFFS"]=incoming
            added["HANDOFF_RECOVERY"]="Use authorized reads to assess these findings. Missing authority never permits a write."
        upstream=[{"producer":item["producer"],"phase":item["phase"],"invocation_id":item["invocation_id"],"raw_artifact_ref":item["raw_artifact_ref"],"parsed_payload":item["parsed_payload"]}
            for item in self._role_handoff_metadata(run_id).values()
            if item["delivery"]=="pending" and item["intended_recipient"]=="agent:"+role and item["parsed_payload"] is not None]
        if upstream: added["UPSTREAM_ROLE_HANDOFFS"]=upstream
        return super()._invoke(run_id,role,phase,packet,lane,profile,gateway,added)
    def _record(self,run_id,phase,packet,value):
        kind=phase.lower()
        packet[kind]=value
        self.artifacts.put(run_id,kind,"runtime",value)
        cycles=self.state.get(run_id).get("repair_cycles",0)
        self.state.transition(run_id,phase,{"artifact_kind":kind},f"{run_id}:{phase}:c{cycles}")
        recipient={"PLAN_REVIEW":"runtime:plan_review","TEST_EXECUTE":"runtime:test_execute","ALIGNMENT":"runtime:alignment"}.get(phase)
        if recipient: self._ack_role_handoffs(run_id,recipient)
        return "ok"
    def _recover_then_stop(self,run_id,role,phase,packet,gateway,reason):
        # Invoke the actual workflow recipient with existing read authority.
        value=self._invoke(run_id,role,phase,packet,0,"S",gateway,
            {"HANDOFF_RECOVERY":reason,"READ_ONLY_RECOVERY":True})
        self.artifacts.put(run_id,"handoff_recovery",role,value)
        self._halt(run_id,"incomplete_handoff",{"reason":reason,"recipient":role})
        return "stop"
    def _ready_to_build(self,run_id,packet):
        plan=validate_plan(self.task_contract,packet.get("plan"))
        packet["plan"]=plan
        plan_hash=sha256_text(canonical_json(plan))
        packet["plan_hash"]=plan_hash
        self.state.prepare_plan_approval(run_id,plan_hash,note="authorized by task contract")
        grant={"schema_version":1,"policy_version":POLICY_VERSION,"task_contract_hash":digest(self.task_contract),
            "plan_hash":plan_hash,"source":"authorized by task contract","allowed_paths":plan["file_allowlist"],
            "verification_commands":plan["verification_commands"]}
        self.artifacts.put(run_id,"derived_grant","runtime",grant)
        self.state.decide_approval(run_id,"plan",plan_hash,"approved","task-contract:"+digest(self.task_contract),note="authorized by task contract")
        self.state.transition(run_id,"READY_TO_BUILD",{"plan_hash":plan_hash,"task_contract_hash":grant["task_contract_hash"]},
            f"{run_id}:READY_TO_BUILD:c{self.state.get(run_id).get('repair_cycles',0)}")
        return "ok"
    def _acceptance_verification(self,run_id,row):
        receipt=self.artifacts.load(run_id,"test_receipts") or {}
        denied=([{"decision":"deny","reason":"Current verification receipts are absent or inconsistent"}],[])
        plan=self.artifacts.load(run_id,"plan") or {}
        cycle=row.get("repair_cycles",0)
        if receipt.get("plan_hash")!=row.get("plan_hash") or receipt.get("repair_cycle")!=cycle:
            return denied
        if receipt.get("tested_scope_hash")!=scope_hash(self.task_contract): return denied
        try: plan=validate_plan(self.task_contract,plan)
        except ContractDenied: return denied
        commands=plan["verification_commands"]
        outcomes=receipt.get("commands",[])
        if len(outcomes)!=len(commands): return denied
        verified=[]
        for index,(argv,outcome) in enumerate(zip(commands,outcomes)):
            operation_id=f"{run_id}:runtime-tests:{row['plan_hash']}:{index}:c{cycle}"
            operation=self.state.tool_operation(operation_id)
            if not operation or operation["state"]!="completed" or operation["run_id"]!=run_id:
                return denied
            if operation["role"]!="test_executor" or operation["phase"]!="TEST_EXECUTE" or operation["tool"]!="tests.run" or operation["plan_hash"]!=row["plan_hash"]:
                return denied
            arguments=json.loads(operation["arguments"])
            if arguments!={"argv":argv,"timeout":self.task_contract["limits"]["verification_timeout"]}: return denied
            result=json.loads(operation["result"])
            if outcome.get("ok") is not True or result!=outcome.get("result"): return denied
            if not execution_evidence(argv,result)["positive"]: return denied
            verified.append({**result,"decision":"allow"})
        return verified,[]

    def _write_broker(self,run_id):
        from .tool_broker import ToolBroker
        from agent_core.runtime_authority import RuntimeAuthority
        row=self.state.get(run_id)
        return ToolBroker(row["repo"],self.tools_config,self.policies,
            authority=RuntimeAuthority("dc",row["repo"],snapshot=self.registry_snapshot))

    def reconcile_tools(self,run_id):
        from agent_core.lifecycle import RunLock
        key=str(self.state.path.resolve())+":"+run_id
        with RunLock(self.state.path.parent/"run-locks",key):
            result=super().reconcile_tools(run_id)
            if result["status"]=="ACTIVE":
                plan=self.artifacts.load(run_id,"plan") or {}
                self._accepted_write_paths(run_id,self._write_broker(run_id),plan.get("file_allowlist",[]))
            return self.state.get(run_id)

    def _acceptance(self,run_id,packet):
        plan=packet.get("plan") or {}
        paths=self._accepted_write_paths(run_id,self._write_broker(run_id),plan.get("file_allowlist",[]))
        if not paths or set(paths)!=set((packet.get("implement") or {}).get("changed_files",[])):
            self._halt(run_id,"write_evidence",{"reason":"Implementation scope lacks complete durable evidence"})
            return "stop"
        # Historical approved effects remain in candidate scope. This local
        # evaluation view is never persisted as a new plan or used for dispatch.
        view={**packet,"plan":{**plan,"file_allowlist":sorted(set(plan["file_allowlist"])|set(paths))}}
        result=super()._acceptance(run_id,view)
        if "acceptance" in view: packet["acceptance"]=view["acceptance"]
        return result

    def _accepted_write_paths(self,run_id,broker,plan_allowlist):
        from agent_core.lifecycle import ReconciliationRequired
        from agent_core.task_contract import literal_path
        from .tool_broker import file_sha
        def deny(reason):
            self.state.set_status(run_id,RunStatus.RECONCILIATION_REQUIRED)
            raise ReconciliationRequired(reason)
        if self.state.pending_tool_operations(run_id):
            deny("Pending tool effects prevent accepted-write accounting")
        latest={}
        try:
            for op in self.state.write_operations(run_id):
                if op["state"]=="denied":
                    continue
                if (op["state"]!="completed" or op["run_id"]!=run_id
                    or op["role"]!="implementer" or op["phase"]!="IMPLEMENT"
                    or op["tool"] not in {"filesystem.write","patch.apply"}
                    or not op["plan_hash"] or op["approval_state"]!="approved"
                    or op["approval_actor"]!="task-contract:"+digest(self.task_contract)):
                    deny("Write receipt lacks completed task-derived authority")
                args=json.loads(op["arguments"]); result=json.loads(op["result"])
                if not isinstance(args,dict) or not isinstance(result,dict):
                    deny("Malformed durable write receipt")
                path=literal_path(args["path"])
                if (path not in self.task_contract["allowed_paths"] or
                    (op["plan_hash"]==self.state.get(run_id).get("plan_hash") and path not in plan_allowlist)):
                    deny("Accepted write is outside the current task or plan")
                target=broker.safe_path(path)
                expected=op["expected_output_hash"]
                if (op["path"]!=str(target) or result.get("path")!=path
                    or not isinstance(expected,str) or len(expected)!=64
                    or any(c not in "0123456789abcdef" for c in expected)
                    or result.get("sha256")!=expected):
                    deny("Durable write paths or output hashes disagree")
                latest[path]=(target,expected)
            for target,expected in latest.values():
                if not target.is_file() or file_sha(target)!=expected:
                    deny("Accepted write source changed; reconciliation required")
        except (ValueError,KeyError,TypeError,OSError,PermissionError) as exc:
            deny("Invalid durable write evidence: "+type(exc).__name__)
        return list(latest)

    def _run_phase(self,run_id,phase,profile,packet,gateway,broker):
        received={"PLAN_REVIEW":"runtime:plan_review","TEST_EXECUTE":"runtime:test_execute"}.get(phase)
        if received: self._ack_role_handoffs(run_id,received)
        if phase=="DECIDE":
            value={"intent":packet["ORIGINAL_REQUEST"],"chosen_approach":"Implement the bounded user task and verify the exact authorized commands.",
                "acceptance_criteria":self.task_contract["acceptance_criteria"],"scope":self.task_contract["allowed_paths"],
                "invariants":["User task contract bounds every write and verification call."],"non_goals":[],"rejected_alternatives":[],"risk":"contained","unresolved_questions":[]}
            return self._record(run_id,phase,packet,value)
        if phase=="PLAN_REVIEW":
            if is_incomplete(packet.get("plan")):
                packet["plan_review"]=self._invoke(run_id,"plan_reviewer",phase,packet,0,profile,gateway,{"READ_ONLY_RECOVERY":True})
                return self._recover_then_stop(run_id,"implementer","IMPLEMENT",packet,gateway,"Plan remains incomplete; inspect only, no execution grant exists.")
            try:
                packet["plan"]=validate_plan(self.task_contract,packet.get("plan"))
            except ContractDenied as error:
                self.artifacts.put(run_id,"scope_question","runtime",{"reason":str(error),"task_contract_hash":digest(self.task_contract)})
                self._invoke(run_id,"plan_reviewer",phase,packet,0,profile,gateway,{"READ_ONLY_RECOVERY":True,"scope_failure":str(error)})
                self._halt(run_id,"scope_denied",{"reason":str(error)})
                return "stop"
            return self._record(run_id,phase,packet,{"verdict":"pass","findings":[],"checked":["Concrete task scope","Change dependency DAG","Exact verification argv"],"limitations":["Natural-language acceptance remains subject to code review."]})
        if phase=="IMPLEMENT":
            outcome=super()._run_phase(run_id,phase,profile,packet,gateway,broker)
            value=packet.get("implement") or {}
            if is_incomplete(value) or value.get("blocked"):
                return self._recover_then_stop(run_id,"code_reviewer","CODE_REVIEW",packet,gateway,"Implementation evidence incomplete; inspect actual diff without claiming completion.")
            return outcome
        if phase=="TEST_EXECUTE":
            commands=[]; receipts=[]; passed=True
            plan=validate_plan(self.task_contract,packet.get("plan"))
            for index,argv in enumerate(plan["verification_commands"]):
                outcome=gateway.safe_execute(run_id,"test_executor",phase,"tests.run",
                    {"argv":argv,"timeout":self.task_contract["limits"]["verification_timeout"]},
                    plan_allowlist=plan["file_allowlist"],plan_hash=packet["plan_hash"],
                    operation_id=f"{run_id}:runtime-tests:{packet['plan_hash']}:{index}:c{self.state.get(run_id).get('repair_cycles',0)}")
                result=outcome.get("result") or {}
                test_evidence=execution_evidence(argv,result)
                outcome={**outcome,"test_execution":test_evidence}
                hashes=result.get("source_hashes")
                valid=outcome.get("ok") is True and type(result.get("returncode")) is int and result["returncode"]==0 and not result.get("timeout") and not result.get("cancelled")
                valid=valid and test_evidence["positive"]
                valid=valid and isinstance(hashes,dict) and isinstance(result.get("source_snapshot_sha256"),str) and bool(result.get("image"))
                if valid:
                    import hashlib
                    for path in self.task_contract["allowed_paths"]:
                        target=Path(self.task_contract["workspace"])/path
                        if target.is_file() and hashes.get(path)!=hashlib.sha256(target.read_bytes()).hexdigest(): valid=False
                passed=passed and valid
                receipts.append(outcome)
                if type(result.get("returncode")) is int:
                    commands.append({"argv":argv,"returncode":result["returncode"],"duration_s":result.get("duration_s",0)})
            packet["tested_scope_hash"]=scope_hash(self.task_contract)
            self.artifacts.put(run_id,"test_receipts","runtime",{"schema_version":1,"plan_hash":packet["plan_hash"],
                "repair_cycle":self.state.get(run_id).get("repair_cycles",0),
                "commands":receipts,"tested_scope_hash":packet["tested_scope_hash"]})
            evidence={"verdict":"pass" if passed else "inconclusive","commands":commands,"evidence":["Recorded isolated gateway verification receipts"],"limitations":[] if passed else ["Verification failed, no executed tests were confirmed, or pinned image/source evidence unavailable"]}
            self._record(run_id,phase,packet,evidence)
            return "ok" if passed else ("repair","isolated verification did not pass with source evidence")
        if phase=="CODE_REVIEW":
            outcome=super()._run_phase(run_id,phase,profile,packet,gateway,broker)
            if is_incomplete(packet.get("code_review")):
                return self._recover_then_stop(run_id,"alignment_checker","ALIGNMENT",packet,gateway,"Review findings incomplete; inspect criteria and evidence without certifying success.")
            return outcome
        if phase=="ALIGNMENT":
            ok=self._review_clear(packet.get("code_review")) and packet.get("test_execute",{}).get("verdict")=="pass"
            ok=ok and packet.get("tested_scope_hash")==scope_hash(self.task_contract)
            self._record(run_id,phase,packet,{"verdict":"pass" if ok else "fail","evidence":["Task scope and tested candidate hashes checked"],"limitations":["Semantic correctness relies on tests and code review."]})
            if not ok:
                self._halt(run_id,"candidate_changed",{"reason":"Review/test evidence or tested candidate changed"})
                return "stop"
            return "ok"
        if phase=="ACCEPTANCE" and not self._review_clear(packet.get("code_review")):
            self._halt(run_id,"blocking_review_findings",{"reason":"Passing verdict cannot override unresolved blocking or major findings"})
            return "stop"
        return super()._run_phase(run_id,phase,profile,packet,gateway,broker)
