from __future__ import annotations
import json, logging, math, subprocess, threading, time, uuid
from types import MappingProxyType
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from agent_core.contracts import ContractDenied
from agent_core.lifecycle import RunLock, ReconciliationRequired
from agent_core.registry_snapshot import compile_repository
from agent_core.runtime_authority import RuntimeAuthority, repository_root, runtime_snapshot
from . import acceptance as acceptance_gate
from . import context as ctx
from .artifacts import ArtifactStore
from .budget import BudgetManager, BudgetExceeded, DailyCapExceeded
from .escalation import authorize_frontier, compress_decision_brief
from .evolution import EvolutionManager
from .jobs import JobManager
from .models import Invocation, Phase, RunStatus
from .policy import PolicyGateway, ApprovalRequired
from .router import size_request, phases_for, workflow_key
from .schemas import SchemaError, SchemaRegistry
from .secrets import SecretStore
from .skills import SkillLibrary
from .tool_broker import ToolBroker, ToolDenied
from .tool_schemas import schemas_for
from .util import load_json, sha256_text, canonical_json
from .web import WebClient, NetworkDenied
from .workflow import CONTROL_PHASES, PHASE_ROLE, WORKFLOW_VERSION, role_for

RESEARCH_ANGLES = ["implementation sites", "callers and dependents", "existing tests",
                   "documentation and configuration", "failure modes and edge cases", "adjacent modules"]
BRAINSTORM_ANGLES = ["failure-first alternative", "constraint inversion", "simpler conventional substitute"]
REPAIR_TARGET = {"PLAN_REVIEW": "PLAN", "TEST_EXECUTE": "IMPLEMENT", "CODE_REVIEW": "IMPLEMENT", "ALIGNMENT": "PLAN"}
_REPO_MAP_MAX_ENTRIES = 80
logger = logging.getLogger("daily_coder")


class Orchestrator:
    def __init__(self, root, state, provider, *, live=False, secrets=None, approvals_required=None,resource_limits=None):
        self.root = Path(root)
        self.registry_snapshot = runtime_snapshot()
        self.state = state
        self.provider = provider
        self.live = bool(live)
        limits=dict(resource_limits or {})
        if limits.get("deadline","absent") is None: limits.pop("deadline")
        for key,value in limits.items():
            if key not in {"tokens","usd","deadline"} or isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                raise ValueError("invalid supervised resource limit")
            if key=="tokens" and int(value)!=value: raise ValueError("token limit must be an integer")
        self.resource_limits=MappingProxyType(limits)
        self.config = load_json(self.root / 'config/default.json')
        self.budgets = load_json(self.root / 'config/budgets.json')
        self.models = load_json(self.root / 'config/models.json')
        self.tools_config = load_json(self.root / 'config/tools.json')
        self.policies = load_json(self.root / 'config/policies.json')
        self.pricing = self._optional('config/pricing.json', {})
        self.schema = SchemaRegistry(self.root / 'schemas')
        self.runtime_dir = self.root / self.config["runtime_dir"]
        self.artifacts = ArtifactStore(self.runtime_dir / "artifacts", state)
        self.secrets = secrets or SecretStore(self.runtime_dir / "secrets.json")
        self.budget = BudgetManager(self.budgets, state, pricing=self.pricing,
                                    limits={**self.config.get("limits", {}),
                                            **({"deadline":self.resource_limits["deadline"]} if "deadline" in self.resource_limits else {}),
                                            **({"max_tokens_per_run":self.resource_limits["tokens"]} if "tokens" in self.resource_limits else {}),
                                            **({"max_spend_usd_per_run":self.resource_limits["usd"]} if "usd" in self.resource_limits else {})})
        self.jobs = JobManager(state, self.runtime_dir / "jobs")
        self.skills = SkillLibrary(self.root / "skills")
        self.evolution = EvolutionManager(self.root, state, self.runtime_dir / "evolution")
        self._role_cache: dict[str, tuple[dict, str, dict]] = {}
        self.approvals_required = self.config.get("human_approval", {}).get("plan_before_writes", True) \
            if approvals_required is None else approvals_required
        # Live writes always require a plan approval; callers cannot weaken this invariant.
        if self.live:
            self.approvals_required = True
        self._run_locks: dict[str, threading.RLock] = {}
        self._locks_guard = threading.Lock()

    def _optional(self, rel, default):
        path = self.root / rel
        return load_json(path) if path.exists() else default

    # --- lifecycle ----------------------------------------------------
    def create(self, request, repo, *, run_id=None):
        run_id=str(uuid.UUID(run_id)) if run_id is not None else str(uuid.uuid4())
        with RunLock(self.state.path.parent/"run-locks",str(self.state.path.resolve())+":create:"+run_id):
            return self._create(request,repo,run_id)

    def _create(self,request,repo,run_id):
        self.budget.check_daily()
        repo_path = Path(repo).resolve()
        config_hash = self._execution_hash()
        try:
            existing=self.state.get(run_id)
        except KeyError:
            existing=None
        if existing:
            if (existing["request"] != request or existing["repo"] != str(repo_path)
                or existing["config_hash"] != config_hash or existing["prompt_hash"] != self._prompt_hash()
                or existing.get("registry_hash") != self.registry_snapshot.snapshot_id):
                raise ContractDenied("native creation identity changed or incomplete; reconcile before reuse")
            return run_id
        revision, dirty = _git_state(repo_path)
        self.state.create(run_id, request, str(repo_path), config_hash, f"{run_id}:create",
                          revision=revision, tree_fingerprint=dirty, prompt_hash=self._prompt_hash(),
                          workflow_version=WORKFLOW_VERSION, live=self.live)
        authority = RuntimeAuthority("dc",repo_path,snapshot=self.registry_snapshot)
        pin = authority.pin(self.runtime_dir / "registry")
        self.state.set_field(run_id,"registry_hash",pin)
        self.checkpoint(run_id,"created")
        return run_id

    def checkpoint(self,run_id,reason="boundary"):
        row=self.state.get(run_id)
        return self.artifacts.put(run_id,"checkpoint","orchestrator",{
            "phase":row["phase"],"status":row["status"],"config_hash":row["config_hash"],
            "registry_hash":row.get("registry_hash"),"plan_hash":row.get("plan_hash"),
            "reason":reason,"pending_tools":len(self.state.pending_tool_operations(run_id)),
            "reserved_calls":self.state.active_budget_reservations(run_id)["calls"],
            "settled_unreceipted_calls":self.state.unreceipted_settlements(run_id)["calls"]})

    def reconcile_tools(self,run_id):
        with RunLock(self.state.path.parent / "run-locks",str(self.state.path.resolve())+":"+run_id):
            row=self.state.get(run_id)
            if (row["config_hash"]!=self._execution_hash() or row.get("prompt_hash")!=self._prompt_hash()
                    or row.get("registry_hash")!=runtime_snapshot().snapshot_id or row.get("workflow_version")!=WORKFLOW_VERSION):
                raise ContractDenied("execution configuration changed")
            authority=RuntimeAuthority("dc",row["repo"],snapshot=self.registry_snapshot)
            broker=ToolBroker(row["repo"],self.tools_config,self.policies,authority=authority)
            gateway=PolicyGateway(broker,self.state,self.policies,True,deadline=self.resource_limits.get("deadline"))
            resolved=gateway.reconcile(run_id)
            if resolved and not self.state.active_budget_reservations(run_id)["calls"] and row["status"]=="RECONCILIATION_REQUIRED":
                self.state.set_status(run_id,"ACTIVE")
            self.checkpoint(run_id,"tool_reconciliation")
            return self.state.get(run_id)

    def request_cancel(self,run_id):
        row=self.state.request_cancel(run_id)
        self.checkpoint(run_id,"cancel_requested")
        return row

    def _cancel_boundary(self,run_id):
        if self.state.get(run_id)["status"] != RunStatus.CANCEL_REQUESTED.value: return False
        for job in self.state.jobs(run_id,active_only=True): self.jobs.cancel(job["job_id"])
        self.state.acknowledge_cancel(run_id)
        self.checkpoint(run_id,"cancel_acknowledgment")
        return True

    def _deadline_cancel(self,run_id):
        deadline=self.resource_limits.get("deadline")
        if deadline is not None and time.time()>=deadline: self.state.request_cancel(run_id)

    def _dispatch_boundary(self,run_id):
        self._deadline_cancel(run_id)
        if self._cancel_boundary(run_id):
            raise ReconciliationRequired("cancellation requested; dispatch stopped")
        if self.state.get(run_id)["status"] in {RunStatus.RECONCILIATION_REQUIRED.value,RunStatus.CANCELLED.value}:
            raise ReconciliationRequired("run dispatch blocked pending reconciliation")

    def start(self, request, repo):
        run_id = self.create(request, repo)
        return self.run(run_id)

    def _execution_hash(self):
        # Record execution conditions, including pricing and permission mode.
        # Provider consolidation will add reviewed provider-specific snapshots;
        # class identity already prevents changing provider families on resume.
        return sha256_text(canonical_json({
            "role_and_schema_hashes": {str(path.relative_to(self.root)):sha256_text(path.read_text(encoding="utf-8")) for directory in ("agents","schemas") for path in sorted((self.root/directory).rglob("*.json"))},
            "default": self.config, "budgets": self.budgets, "models": self.models,
            "tools": self.tools_config, "policies": self.policies, "pricing": self.pricing,
            "live": self.live, "approvals_required": self.approvals_required,"resource_limits":dict(self.resource_limits),"effective_budget_limits":dict(self.budget.limits),
            "provider": type(self.provider).__module__ + "." + type(self.provider).__qualname__,
            "provider_options": {key:getattr(self.provider,key) for key in
                                 ("name","base_url","default_model","timeout","command","endpoint",
                                  "supports_json_response_format","version") if hasattr(self.provider,key)},
        }))

    def _prompt_hash(self):
        parts = []
        for path in sorted((self.root / "agents").glob("*/prompt.md")):
            parts.append(path.name + sha256_text(path.read_text(encoding="utf-8")))
        return sha256_text("".join(parts))

    def run(self, run_id, _depth=0):
        with self._locks_guard:
            lock = self._run_locks.setdefault(run_id, threading.RLock())
        with lock, RunLock(self.state.path.parent / "run-locks", str(self.state.path.resolve()) + ":" + run_id):
            try:
                return self._run_locked(run_id, _depth)
            finally:
                self._cancel_boundary(run_id)
                self.checkpoint(run_id,"execution_boundary")

    def _run_locked(self, run_id, _depth=0):
        row = self.state.get(run_id)
        if row["status"] in (RunStatus.COMPLETE.value, RunStatus.FAILED.value,
                             RunStatus.CANCELLED.value, RunStatus.SIMULATED.value):
            return row
        if (row.get("config_hash") != self._execution_hash()
                or row.get("prompt_hash") != self._prompt_hash()
                or row.get("workflow_version") != WORKFLOW_VERSION):
            raise ContractDenied("execution configuration changed or legacy run is unpinned; start a new run")
        self._deadline_cancel(run_id)
        if self._cancel_boundary(run_id): return self.state.get(run_id)
        if self.state.unreceipted_settlements(run_id)["calls"]:
            self.state.set_status(run_id,RunStatus.RECONCILIATION_REQUIRED)
            return self.state.get(run_id)
        stored=self.artifacts.load_all(run_id)
        for receipt in self.state.invocations(run_id,limit=100000):
            if receipt["status"]!="ok": continue
            cycle_key=f":c{row.get('repair_cycles',0)}"
            if not (receipt["idem_key"].endswith(cycle_key) or cycle_key+":" in receipt["idem_key"]): continue
            phase=receipt["phase"]; role=receipt["role"]
            if phase not in PHASE_ROLE and phase!="SIZE" and role not in {"frontier_advisor","skill_curator"}: continue
            kind="sizing" if role=="sizer" else phase.lower()
            if role=="alignment_checker" and phase!="ALIGNMENT": kind="alignment_"+phase.lower()
            if role=="researcher": kind="research"
            if role=="failure_diagnostician": kind="diagnosis"
            if role=="frontier_advisor": kind="frontier_advice"
            if role=="skill_curator": kind="skill_candidate"
            if kind not in stored:
                self.state.set_status(run_id,RunStatus.RECONCILIATION_REQUIRED)
                return self.state.get(run_id)
        if self.state.pending_tool_operations(run_id):
            self.state.set_status(run_id,RunStatus.RECONCILIATION_REQUIRED)
            return self.state.get(run_id)
        if self.state.active_budget_reservations(run_id)["calls"]:
            self.state.set_status(run_id, RunStatus.RECONCILIATION_REQUIRED)
            return self.state.get(run_id)
        if row["status"] == RunStatus.RECONCILIATION_REQUIRED.value:
            return row
        current = runtime_snapshot()
        if row.get("registry_hash") != self.registry_snapshot.snapshot_id or current.snapshot_id != self.registry_snapshot.snapshot_id:
            raise ContractDenied("registry changed or legacy run is unpinned; start a new run")
        repo = Path(row["repo"])
        authority = RuntimeAuthority("dc",repo,snapshot=self.registry_snapshot,task_layers=self.config.get("task_grants"))
        broker = ToolBroker(repo, self.tools_config, self.policies,authority=authority)
        self._register_network(broker)
        gateway = PolicyGateway(broker, self.state, self.policies, self.approvals_required and self.live,deadline=self.resource_limits.get("deadline"))

        if row["phase"] == Phase.NEW.value:
            self.state.transition(run_id, Phase.INTAKE.value, {"request_hash": sha256_text(row["request"])}, f"{run_id}:INTAKE")
            row = self.state.get(run_id)
        if row["phase"] == Phase.INTAKE.value:
            try:
                sizing = self._size(run_id, row["request"])
            except ReconciliationRequired:
                return self.state.get(run_id)
            self.artifacts.put(run_id, "sizing", "sizer", sizing)
            self.state.set_profile(run_id, sizing["profile"])
            self.state.transition(run_id, Phase.SIZE.value, sizing, f"{run_id}:SIZE")
            row = self.state.get(run_id)

        profile = row["profile"] or "M"
        self.budget.activate_rate_limiter(profile)
        sizing = self.artifacts.load_all(run_id).get("sizing") or {}
        phases = phases_for(sizing.get("workflow") or profile)
        packet = self._rebuild_packet(run_id, row, profile)

        # A run waiting on a human or a job resumes only when the wait is satisfied.
        if row["status"] == RunStatus.WAITING_HUMAN.value:
            if not row.get("plan_hash"):
                return self._halt(run_id, "approval_state", {"detail": "waiting run has no pinned plan hash"})
            if self.state.approval_state(run_id, "plan", row["plan_hash"]) != "approved":
                return self.state.get(run_id)
            cycles = row.get("repair_cycles", 0)
            self.state.transition_status(run_id, Phase.READY_TO_BUILD.value, RunStatus.ACTIVE,
                                         {"plan_hash": row["plan_hash"], "approval": "approved"},
                                         f"{run_id}:APPROVED:{row['plan_hash']}:c{cycles}")
            row = self.state.get(run_id)
        if row["status"] == RunStatus.WAITING_JOB.value:
            evidence = self._collect_job(run_id)
            if evidence is None:
                return self.state.get(run_id)
            packet["job_evidence"] = evidence
            self.artifacts.put(run_id, "job_evidence", "orchestrator", evidence)
            self.state.set_status(run_id, RunStatus.ACTIVE)

        current = self.state.get(run_id)["phase"]
        start = phases.index(current) + 1 if current in phases else 0

        for phase in phases[start:]:
            if phase in {"INTAKE", "SIZE"}:
                continue
            try:
                self._dispatch_boundary(run_id)
                self.checkpoint(run_id,"before_"+phase)
                outcome = self._run_phase(run_id, phase, profile, packet, gateway, broker)
            except ReconciliationRequired:
                self.state.set_status(run_id, RunStatus.RECONCILIATION_REQUIRED)
                return self.state.get(run_id)
            except (BudgetExceeded, DailyCapExceeded) as exc:
                return self._halt(run_id, "budget", {"detail": str(exc)})
            except ApprovalRequired as exc:
                self._await_human(run_id, exc.subject_hash)
                return self.state.get(run_id)
            except ToolDenied as exc:
                return self._halt(run_id, "permission", {"phase": phase, "detail": str(exc)})
            except Exception as exc:
                return self._repair(run_id, phase, f"{type(exc).__name__}: {exc}", packet, _depth)
            if outcome == "wait_human":
                return self.state.get(run_id)
            if outcome == "wait_job":
                return self.state.get(run_id)
            if isinstance(outcome, tuple) and outcome[0] == "repair":
                return self._repair(run_id, phase, outcome[1], packet, _depth)
            if outcome == "stop":
                return self.state.get(run_id)
        return self.state.get(run_id)

    # --- phases -------------------------------------------------------
    def _run_phase(self, run_id, phase, profile, packet, gateway, broker):
        if phase == "READY_TO_BUILD":
            return self._ready_to_build(run_id, packet)
        if phase == "ACCEPTANCE":
            return self._acceptance(run_id, packet)
        if phase == "COMPLETE":
            self._post_run_evolution(run_id, profile, packet, gateway)
            self.state.transition(run_id, phase, {"completed": True}, f"{run_id}:{phase}")
            self.state.set_status(run_id, RunStatus.COMPLETE if self.live else RunStatus.SIMULATED)
            return "done"

        role = role_for(phase)
        if phase == "TEST_EXECUTE":
            pending = self._maybe_start_job(run_id, packet, broker)
            if pending == "wait_job":
                return "wait_job"

        if role == "researcher":
            value = self._research(run_id, profile, packet, gateway)
            self.artifacts.put(run_id, "research", "researcher", value)
            packet["research"] = value
            packet["research_digest"] = ctx.research_digest(value["cards"])
        elif role == "brainstormer":
            value = self._brainstorm(run_id, profile, packet, gateway)
            self.artifacts.put(run_id, phase.lower(), role, value)
            packet[phase.lower()] = value
        elif role == "implementer":
            value = self._implement_chunks(run_id, profile, packet, gateway, broker)
            self.artifacts.put(run_id, phase.lower(), role, value)
            packet[phase.lower()] = value
            gate = self._gate(run_id, phase, role, value, packet)
            if gate is not None:
                return gate
        else:
            extra = self._role_extra(run_id, role, packet, broker)
            value = self._invoke(run_id, role, phase, packet, 0, profile, gateway, extra)
            self.artifacts.put(run_id, phase.lower(), role, value)
            packet[phase.lower()] = value
            gate = self._gate(run_id, phase, role, value, packet)
            if gate is not None:
                return gate

        cycles = self.state.get(run_id).get("repair_cycles", 0)
        self.state.transition(run_id, phase, {"artifact_kind": phase.lower()}, f"{run_id}:{phase}:c{cycles}")
        boundary = self._boundary_alignment(run_id, phase, profile, packet, gateway)
        if boundary is not None:
            return boundary
        return "ok"

    def _post_run_evolution(self, run_id, profile, packet, gateway):
        """Periodically propose one bounded candidate; never promote it."""
        cfg = self.config.get("evolution", {})
        if not self.live or not cfg.get("enabled", False):
            return
        every = max(1, int(cfg.get("curate_every_verified_runs", 5)))
        completed = sum(1 for r in self.state.list_runs(10000) if r.get("status") == RunStatus.COMPLETE.value)
        if (completed + 1) % every:
            return
        if any(c["state"] in ("proposed", "eligible", "promoting") for c in self.state.candidates()):
            return
        summary = {"run_id": run_id, "request": packet.get("ORIGINAL_REQUEST"),
                   "acceptance": packet.get("acceptance"), "diagnosis": packet.get("diagnosis"),
                   "repairs": self.state.get(run_id).get("repair_cycles", 0)}
        candidate = self._invoke(run_id, "skill_curator", "COMPLETE", {"run_summary": summary}, 0, profile, gateway)
        self.artifacts.put(run_id, "skill_candidate", "skill_curator", candidate)
        if candidate.get("verdict") != "candidate":
            return
        required = ("kind", "target", "proposed_text")
        if not all(candidate.get(k) for k in required):
            return
        self.evolution.propose(candidate["kind"], candidate["target"], candidate["proposed_text"],
                               candidate["reason"], candidate.get("provenance") or [run_id])

    def _gate(self, run_id, phase, role, value, packet):
        if role == "planner":
            mode = str(packet.get("task_mode") or self.config.get("task_mode", "coding")).strip().lower()
            gate_unresolved = self.config.get("acceptance", {}).get("gate_unresolved_questions", True)
            if gate_unresolved and mode != "research" and value.get("unresolved_questions"):
                return ("repair", "plan contains unresolved design decisions")
            packet["file_allowlist"] = value.get("file_allowlist", [])
        if role == "plan_reviewer" and value.get("verdict") != "pass":
            return ("repair", f"plan review verdict: {value.get('verdict')}")
        if role == "test_executor" and value.get("verdict") != "pass":
            return ("repair", "tests did not pass")
        if role == "code_reviewer" and value.get("verdict") != "pass":
            return ("repair", "code review blocked acceptance")
        if role == "alignment_checker" and value.get("verdict") != "pass":
            return ("repair", "alignment check failed")
        return None

    def _ready_to_build(self, run_id, packet):
        """Writes begin only after a human approves the reviewed plan."""
        plan = packet.get("plan") or {}
        plan_hash = sha256_text(canonical_json(plan))
        packet["plan_hash"] = plan_hash
        approval = self.state.prepare_plan_approval(run_id, plan_hash, note="approve plan before repository writes")
        state = approval["state"]
        if state != "approved":
            if not self.live or not self.approvals_required:
                self.state.decide_approval(run_id, "plan", plan_hash, "approved",
                                           "auto:simulated" if not self.live else "auto:policy")
            else:
                self._await_human(run_id, plan_hash)
                return "wait_human"
        cycles = self.state.get(run_id).get("repair_cycles", 0)
        self.state.transition(run_id, "READY_TO_BUILD", {"plan_hash": plan_hash}, f"{run_id}:READY_TO_BUILD:c{cycles}")
        return "ok"

    def _acceptance(self, run_id, packet):
        row = self.state.get(run_id)
        if not row.get("plan_hash"):
            self._halt(run_id, "acceptance", {"failures": ["no pinned plan hash"]})
            return "stop"
        approvals_ok = self.state.approval_state(run_id, "plan", row["plan_hash"]) == "approved"
        verification_results = []
        for call in self.state.tool_calls(run_id, limit=1000):
            if (call["role"] != "test_executor" or call["phase"] != "TEST_EXECUTE"
                    or call["tool"] != "tests.run"):
                continue
            summary = json.loads(call["result_summary"]) if call.get("result_summary") else {}
            verification_results.append({**summary, "decision": call["decision"]})
        result = acceptance_gate.evaluate(run=row, packet=packet, artifacts=self.state.artifacts(run_id),
                                          approvals_ok=approvals_ok, live=self.live, config=self.config,
                                          verification_results=verification_results,
                                          job_results=self.state.jobs(run_id))
        packet["acceptance"] = result
        self.artifacts.put(run_id, "acceptance", "orchestrator", result)
        if result["verdict"] == "fail":
            self._halt(run_id, "acceptance", result)
            return "stop"
        self.state.transition(run_id, "ACCEPTANCE", result, f"{run_id}:ACCEPTANCE")
        return "ok"

    # --- research -----------------------------------------------------
    def _build_repo_map(self, run_id, gateway):
        """Shallow directory listing for researcher packets. Live + gateway only."""
        if not self.live or gateway is None:
            return None
        outcome = gateway.safe_execute(
            run_id, "researcher", "RESEARCH", "filesystem.list", {"path": "."},
            plan_allowlist=None, plan_hash=None,
        )
        if not outcome.get("ok"):
            return None
        result = outcome.get("result") or {}
        raw_entries = list(result.get("entries") or [])
        entries = raw_entries[:_REPO_MAP_MAX_ENTRIES]
        return {
            "root": result.get("path", "."),
            "entries": entries,
            "truncated": len(raw_entries) > _REPO_MAP_MAX_ENTRIES,
            "source": "filesystem.list",
        }

    def _research(self, run_id, profile, packet, gateway):
        repo_map = self._build_repo_map(run_id, gateway)
        if repo_map is not None:
            packet["repo_map"] = repo_map
        profile_budget = self.budgets["profiles"][profile]
        lanes = profile_budget["research_lanes"]
        early_stop_min = int(profile_budget.get("early_stop_min_cards", 2))
        workers = min(lanes, self.config.get("max_parallel_agents", 4), 2)
        def lane(i):
            angle = RESEARCH_ANGLES[i % len(RESEARCH_ANGLES)]
            card = self._invoke(
                run_id, "researcher", "RESEARCH", packet, i, profile, gateway,
                {"lane": i, "angle": angle},
            )
            # card is schema-validated research_card; do not merge metadata into it.
            return {"lane": i, "angle": angle, "card": card}
        cards = []
        index = 0
        while index < lanes:
            batch_idx = list(range(index, min(index + workers, lanes)))
            with ThreadPoolExecutor(max_workers=len(batch_idx)) as pool:
                batch = list(pool.map(lane, batch_idx))
            cards.extend(batch)
            index += len(batch_idx)
            if ctx.should_stop_research(cards, min_cards=early_stop_min):
                break
        return {"cards": cards, "early_stop": index < lanes}

    def _brainstorm(self, run_id, profile, packet, gateway):
        maximum = min(int(self.budgets["profiles"][profile].get("brainstorm_lanes", 1)), 3)
        request = (packet.get("ORIGINAL_REQUEST") or packet.get("request") or "").lower()
        divergent = any(term in request for term in
                        ("brainstorm", "compare options", "alternatives", "unclear", "not sure", "architecture choice"))
        lanes = maximum if divergent else min(maximum, 1)
        if lanes <= 1:
            return self._invoke(run_id, "brainstormer", "BRAINSTORM", packet, 0, profile, gateway,
                                {"angle": BRAINSTORM_ANGLES[0]})
        with ThreadPoolExecutor(max_workers=min(lanes,2)) as pool:
            results = list(pool.map(
                lambda i: self._invoke(run_id, "brainstormer", "BRAINSTORM", packet, i, profile, gateway,
                                       {"angle": BRAINSTORM_ANGLES[i]}), range(lanes)))
        options = []
        for result in results:
            options.extend(result.get("options", []))
        return {"options": options, "no_better_angle_found": all(r.get("no_better_angle_found", False) for r in results)}

    def _implement_chunks(self, run_id, profile, packet, gateway, broker):
        units = list((packet.get("plan") or {}).get("change_units") or [])
        config = self.config.get("decomposition", {})
        chunk_size = max(1, int(config.get("max_change_units_per_chunk", 2)))
        enabled = profile in config.get("profiles", ["L", "XL"])
        chunks = [units[i:i+chunk_size] for i in range(0, len(units), chunk_size)] if enabled else [units]
        chunks = chunks or [[]]
        max_chunks = max(1, int(config.get("max_chunks", 6)))
        if len(chunks) > max_chunks:
            raise RuntimeError(f"implementation requires {len(chunks)} chunks; maximum is {max_chunks}")
        results = []
        for index, chunk in enumerate(chunks):
            extra = self._role_extra(run_id, "implementer", packet, broker)
            extra.update({"plan_slice": chunk, "chunk": {
                "index": index + 1, "total": len(chunks),
                "purpose": "; ".join(unit.get("summary", unit.get("id", "change")) for unit in chunk),
                "instruction": "Complete only this chunk, validate it, then stop.",
            }})
            result = self._invoke(run_id, "implementer", "IMPLEMENT", packet, index, profile, gateway, extra)
            results.append(result)
            if result.get("blocked"):
                break
        return {
            "changed_files": list(dict.fromkeys(f for r in results for f in r.get("changed_files", []))),
            "commands": [c for r in results for c in r.get("commands", [])],
            "observations": [o for r in results for o in r.get("observations", [])],
            "blocked": any(r.get("blocked", False) for r in results),
            **({"blocked_reason": next((r.get("blocked_reason") for r in results if r.get("blocked_reason")), "chunk blocked")}
               if any(r.get("blocked", False) for r in results) else {}),
        }

    # --- invocation ---------------------------------------------------
    def _require_new_invocation(self,run_id,key):
        if self.state.invocation_receipt(key):
            self.state.set_status(run_id,RunStatus.RECONCILIATION_REQUIRED)
            raise ReconciliationRequired("accepted response lacks committed phase output; explicit reconciliation required")

    def _settle_response(self, run_id, estimate, result, key):
        try:
            return self.budget.settle(run_id, estimate, result.model, result.input_tokens,
                                      result.output_tokens, key)
        except Exception as exc:
            if self.live:
                self.state.set_status(run_id, RunStatus.RECONCILIATION_REQUIRED)
                raise ReconciliationRequired("response received but accounting incomplete; reservation retained") from exc
            raise

    def _role_extra(self, run_id, role, packet, broker):
        self._dispatch_boundary(run_id)
        extra = {}
        if role in ("planner", "implementer"):
            names = ((packet.get("plan") or {}).get("skills")) or self.config.get("default_skills", [])
            loaded = self.skills.load(names,authority=broker.authority,role=role)
            if loaded:
                extra["skills"] = loaded
        if role == "code_reviewer" and self.live:
            try:
                extra["diff"] = PolicyGateway(broker,self.state,self.policies,self.live,deadline=self.resource_limits.get("deadline")).execute(run_id,"code_reviewer","CODE_REVIEW","repository.diff",{})
            except (ToolDenied, Exception):
                extra["diff"] = {"unavailable": True}
        if role == "test_executor" and packet.get("job_evidence"):
            extra["job_evidence"] = packet["job_evidence"]
        if role == "implementer":
            extra["plan_slice"] = (packet.get("plan") or {}).get("change_units", [])
        return extra

    def _invoke(self, run_id, role, phase, packet, lane, profile, gateway, extra=None):
        self._dispatch_boundary(run_id)
        if self.state.get(run_id)["status"] == RunStatus.RECONCILIATION_REQUIRED.value:
            raise ReconciliationRequired("run dispatch blocked pending reconciliation")
        row = self.state.get(run_id)
        authority = RuntimeAuthority("dc",row["repo"],snapshot=self.registry_snapshot,task_layers=self.config.get("task_grants"))
        authority.dispatch(role,"ide:daily-coder")
        if role not in self._role_cache:
            cfg = load_json(self.root / f'agents/{role}/agent.json')
            prompt = (self.root / f'agents/{role}/prompt.md').read_text(encoding="utf-8")
            schema_name = cfg["output_schema"]
            schema = json.loads((self.root / f"schemas/{schema_name}.schema.json").read_text(encoding="utf-8"))
            self._role_cache[role] = (cfg, prompt, schema)
        cfg, prompt, schema = self._role_cache[role]
        model = self._model_for(cfg["model_tier"])
        self.budget.validate_model_pricing(model)
        schema_name = cfg["output_schema"]
        sliced = ctx.build_packet(role, packet, extra)
        allowed_tools = [t for t in self.tools_config["role_allowlists"].get(role, []) if t in authority.effective(role).capabilities("tools")]
        # Tools are advertised only when a gateway can actually authorize and record them.
        tool_specs = schemas_for(allowed_tools) if (self.live and gateway is not None) else []
        tool_results: list = []
        role_turns = self.config.get("role_tool_turns", {})
        max_turns = int(cfg.get("max_tool_turns", role_turns.get(role, self.config.get("max_tool_turns", 6))))
        plan_allowlist = packet.get("file_allowlist") or (packet.get("plan") or {}).get("file_allowlist") or []
        plan_hash = packet.get("plan_hash") or self.state.get(run_id).get("plan_hash")
        if self.live and role in {"implementer", "test_author", "documenter"} and not plan_hash:
            raise ValueError(f"{role} requires a pinned plan hash")

        grant = authority.effective(role)
        max_turns = min(max_turns,int(grant.ceiling("tool_turns")))
        wall_time = grant.ceiling("wall_time")
        if wall_time <= 0: raise ContractDenied("invocation has no wall-time grant")
        invocation_started = time.monotonic()
        seen_tool_calls: dict[str, int] = {}
        watchdog = self.config.get("drift_watchdog", {})
        cycles = self.state.get(run_id).get("repair_cycles", 0)
        for turn in range(max_turns + 1):
            self._dispatch_boundary(run_id)
            if self.state.get(run_id)["status"] == RunStatus.RECONCILIATION_REQUIRED.value:
                raise ReconciliationRequired("run dispatch blocked pending reconciliation")
            if time.monotonic()-invocation_started >= wall_time:
                raise ContractDenied("invocation wall-time grant exhausted")
            if time.monotonic() - invocation_started >= int(watchdog.get("reanchor_after_s", 600)):
                sliced["DRIFT_REMINDER"] = {
                    "task_anchor": packet.get("ORIGINAL_REQUEST") or packet.get("task_anchor"),
                    "current_subgoal": phase,
                    "instruction": "Reconfirm scope and the next acceptance gate before continuing.",
                }
            tool_context = ctx.project_tool_results(tool_results)
            estimate = ctx.estimate_tokens(prompt, sliced, cfg["max_output_tokens"], tool_context)
            idem_key = f"{run_id}:{role}:{phase}:{lane}:{turn}:c{cycles}"
            self._require_new_invocation(run_id,idem_key)
            self.budget.reserve(run_id, profile, estimate, model=model, reservation_id=idem_key)
            request = Invocation(run_id, role, prompt, sliced, cfg["model_tier"], cfg["max_output_tokens"],
                                 idem_key, model=model,
                                 tools=tuple(tool_specs), tool_results=tuple(tool_context), turn=turn,
                                 reasoning=bool(cfg.get("reasoning", False)), output_schema=schema)
            started = time.time()
            try:
                result = self.provider.invoke(request)
            except Exception as exc:
                if not self.live:
                    self.budget.release(run_id, estimate, idem_key)
                self.state.record_invocation(run_id, role, phase, lane, turn, cfg["model_tier"], model,
                                             0, 0, 0.0, int((time.time() - started) * 1000),
                                             "remote_outcome_unknown" if self.live else "error",
                                             type(exc).__name__, f"{idem_key}:err")
                if self.live:
                    self.state.set_status(run_id, RunStatus.RECONCILIATION_REQUIRED)
                    raise ReconciliationRequired("provider outcome unknown; reservation retained") from exc
                raise
            usd = self._settle_response(run_id, estimate, result, idem_key)
            self.state.record_invocation(run_id, role, phase, lane, turn, cfg["model_tier"], result.model,
                                         result.input_tokens, result.output_tokens, usd,
                                         int((time.time() - started) * 1000), "ok", None,
                                         idem_key)
            self._dispatch_boundary(run_id)
            if time.monotonic()-invocation_started >= wall_time:
                raise ContractDenied("invocation exceeded wall-time grant; usage recorded")
            if result.tool_calls:
                if turn >= max_turns:
                    raise RuntimeError(f"{role} exceeded the tool turn limit")
                for call_index,call in enumerate(result.tool_calls):
                    fingerprint = sha256_text(canonical_json({"tool": call.name, "arguments": call.arguments}))
                    seen_tool_calls[fingerprint] = seen_tool_calls.get(fingerprint, 0) + 1
                    if seen_tool_calls[fingerprint] > int(watchdog.get("max_identical_tool_calls", 2)):
                        raise RuntimeError(f"{role} repeated the same tool call without progress")
                    outcome = gateway.safe_execute(run_id, role, phase, call.name, call.arguments,
                                                   plan_allowlist=plan_allowlist, plan_hash=plan_hash,operation_id=f"{idem_key}:tool:{call_index}")
                    tool_results.append({"call_id": call.call_id, "tool": call.name,
                                         "arguments": call.arguments, "turn": turn, **outcome})
                continue
            max_retries = int(cfg.get("max_retries", 0))
            schema_attempts = 0
            while True:
                if time.monotonic()-invocation_started >= wall_time:
                    raise ContractDenied("invocation exceeded wall-time grant; usage recorded")
                try:
                    if result.output is None:
                        raise SchemaError(f"{role} returned empty output")
                    self.schema.validate(schema_name, result.output)
                    return result.output
                except SchemaError:
                    schema_attempts += 1
                    if schema_attempts > max_retries:
                        raise
                    estimate = ctx.estimate_tokens(prompt, sliced, cfg["max_output_tokens"], tool_context)
                    retry_key = f"{idem_key}:retry{schema_attempts}"
                    self._dispatch_boundary(run_id)
                    self._require_new_invocation(run_id,retry_key)
                    self.budget.reserve(run_id, profile, estimate, model=model, reservation_id=retry_key)
                    request = Invocation(
                        run_id, role, prompt, sliced, cfg["model_tier"], cfg["max_output_tokens"],
                        retry_key, model=model,
                        tools=tuple(tool_specs), tool_results=tuple(tool_context), turn=turn,
                        reasoning=bool(cfg.get("reasoning", False)), output_schema=schema)
                    started = time.time()
                    try:
                        result = self.provider.invoke(request)
                    except Exception as exc:
                        if not self.live:
                            self.budget.release(run_id, estimate, retry_key)
                        self.state.record_invocation(
                            run_id, role, phase, lane, turn, cfg["model_tier"], model,
                            0, 0, 0.0, int((time.time() - started) * 1000),
                            "remote_outcome_unknown" if self.live else "error",
                            type(exc).__name__, f"{retry_key}:err")
                        if self.live:
                            self.state.set_status(run_id, RunStatus.RECONCILIATION_REQUIRED)
                            raise ReconciliationRequired("provider retry outcome unknown; reservation retained") from exc
                        raise
                    usd = self._settle_response(run_id, estimate, result, retry_key)
                    self.state.record_invocation(
                        run_id, role, phase, lane, turn, cfg["model_tier"], result.model,
                        result.input_tokens, result.output_tokens, usd,
                        int((time.time() - started) * 1000), "ok", None,
                        retry_key)
                    self._dispatch_boundary(run_id)
                    if result.tool_calls:
                        raise SchemaError(f"{role} returned tool calls during schema retry")
        raise RuntimeError(f"{role} produced no final output")

    def _model_for(self, tier):
        if tier not in self.models.get("tiers", {}):
            raise ValueError(f"unknown model tier: {tier}")
        provider_name = getattr(self.provider, "name", "")
        provider_config = self.config.get("providers", {}).get(provider_name, {})
        if provider_config.get("tier_models", {}).get(tier):
            return provider_config["tier_models"][tier]
        entry = self.models["tiers"].get(tier) or {}
        models = entry.get("models") or []
        return models[0] if models else tier

    # --- sizing -------------------------------------------------------
    def _sizing_result(self, profile, score, reasons, trivial_signal):
        return {
            "profile": profile,
            "score": score,
            "reasons": reasons,
            "trivial_signal": bool(trivial_signal),
            "workflow": workflow_key(profile, trivial_signal),
        }

    def _size(self, run_id, request):
        heuristic = size_request(request)
        trivial = bool(heuristic.get("trivial_signal"))
        if not heuristic.get("ambiguous") or not self.live:
            return self._sizing_result(heuristic["profile"], heuristic["score"],
                                       heuristic["reasons"], trivial)
        try:
            refined = self._invoke(run_id, "sizer", "SIZE", {"request": request, "ORIGINAL_REQUEST": request},
                                   0, heuristic["profile"], None)
            profile = refined.get("profile", heuristic["profile"])
            return self._sizing_result(
                profile,
                int(refined.get("score", heuristic["score"])),
                list(refined.get("reasons", [])) + ["llm-sizer"],
                trivial if profile == "S" else False,
            )
        except ReconciliationRequired:
            raise
        except Exception:
            return self._sizing_result(heuristic["profile"], heuristic["score"],
                                       heuristic["reasons"], trivial)

    # --- boundaries, jobs, repair, halts -------------------------------
    def _boundary_alignment(self, run_id, phase, profile, packet, gateway):
        configured = self.config.get("boundary_alignment", {})
        phases = configured.get(profile, []) if isinstance(configured, dict) else (
            ["RESEARCH", "PLAN", "IMPLEMENT"] if configured else [])
        if phase not in phases:
            return None
        value = self._invoke(run_id, "alignment_checker", phase, packet, 0, profile, gateway,
                             {"boundary": phase})
        self.artifacts.put(run_id, f"alignment_{phase.lower()}", "alignment_checker", value)
        if value.get("verdict") != "pass":
            return ("repair", f"boundary alignment failed after {phase}")
        return None

    def _maybe_start_job(self, run_id, packet, broker):
        """Long suites run detached. The run waits without spending tokens."""
        if not self.live:
            return None
        commands = (packet.get("plan") or {}).get("verification_commands") or []
        if not commands or packet.get("job_evidence"):
            return None
        argv = commands[0] if isinstance(commands[0], list) else str(commands[0]).split()
        repo = self.state.get(run_id)["repo"]
        if broker is None:
            raise ToolDenied("detached test jobs require the policy tool broker")
        if broker.isolated_runner is None:
            raise ToolDenied("test verification requires an isolated execution backend (Docker)")
        if len(commands) > 6: raise ToolDenied("verification command count exceeds ceiling")
        gateway = PolicyGateway(broker,self.state,self.policies,True,deadline=self.resource_limits.get("deadline"))
        results=[]
        for command in commands:
            import shlex
            argv = command if isinstance(command,list) else shlex.split(command)
            results.append(gateway.execute(run_id,"test_executor","TEST_EXECUTE","tests.run",{"argv":argv,"timeout":900}))
        packet["job_evidence"] = {"isolated":True,"commands":results}
        return None

    def _collect_job(self, run_id):
        active = [j for j in self.state.jobs(run_id) if j["state"] in ("pending", "running")]
        if not active:
            finished = [j for j in self.state.jobs(run_id) if j["state"] not in ("pending", "running")]
            return self.jobs.evidence(finished[0]["job_id"]) if finished else {}
        job = self.jobs.poll(active[0]["job_id"])
        if job["state"] in ("pending", "running"):
            return None
        return self.jobs.evidence(job["job_id"])

    def _await_human(self, run_id, subject_hash):
        if not subject_hash:
            raise ValueError("cannot wait for approval without a subject hash")
        self.state.transition_status(run_id, Phase.WAITING_HUMAN.value, RunStatus.WAITING_HUMAN,
                                     {"approval": subject_hash}, f"{run_id}:WAIT:{subject_hash}")
        return self.state.get(run_id)

    def _halt(self, run_id, reason, detail):
        self.state.transition(run_id, Phase.FAILED.value, {"reason": reason, "detail": detail},
                              f"{run_id}:FAILED:{reason}:{int(time.time())}")
        self.state.set_status(run_id, RunStatus.FAILED)
        return self.state.get(run_id)

    def _repair(self, run_id, phase, reason, packet, depth):
        """Bounded repair: diagnose, last-chance frontier, then retry or stop."""
        if self.state.get(run_id)["status"] == RunStatus.RECONCILIATION_REQUIRED.value:
            return self.state.get(run_id)
        max_cycles = int(self.config.get("acceptance", {}).get("max_repair_cycles", 2))
        cycles = self.state.bump_repair(run_id)
        profile = self.state.get(run_id)["profile"] or "M"
        sizing = self.artifacts.load_all(run_id).get("sizing") or {}
        workflow = phases_for(sizing.get("workflow") or profile)
        self.state.transition(run_id, Phase.DIAGNOSE.value, {"phase": phase, "reason": reason, "cycle": cycles},
                      f"{run_id}:DIAGNOSE:{phase}:{cycles}")
        diagnosis = None
        try:
            diagnosis = self._invoke(run_id, "failure_diagnostician", "DIAGNOSE", packet, 0, profile, None,
                                     {"failure": reason, "phase": phase,
                                      "evidence": packet.get(phase.lower())})
            self.artifacts.put(run_id, "diagnosis", "failure_diagnostician", diagnosis)
            packet["diagnosis"] = diagnosis
        except ReconciliationRequired:
            return self.state.get(run_id)
        except Exception as exc:
            logger.warning("failure_diagnostician failed for run %s (phase %s): %s: %s",
                           run_id, phase, type(exc).__name__, exc, exc_info=True)
            failure_class = "plan" if phase in ("PLAN", "PLAN_REVIEW", "DECIDE") else "implementation"
            diagnosis = {
                "failure_class": failure_class,
                "first_failing_signal": str(reason)[:300],
                "evidence": [{"claim": f"Phase {phase} failed: {reason}", "locator": f"phase:{phase}", "label": "VERIFIED"}],
                "recommended_action": "repair",
                "target_phase": phase,
                "rationale": f"Fallback diagnosis generated after diagnostician error: {type(exc).__name__}: {exc}",
                "unknowns": [f"Diagnostician invocation error: {exc}"],
            }
            self.artifacts.put(run_id, "diagnosis", "failure_diagnostician_fallback", diagnosis)
            packet["diagnosis"] = diagnosis

        if cycles > max_cycles or depth >= max_cycles:
            # Exhausted: do not spend frontier — advice cannot change this run.
            return self._halt(run_id, "repair_budget", {"phase": phase, "reason": reason, "cycles": cycles})
        if diagnosis and diagnosis.get("recommended_action") == "stop":
            return self._halt(run_id, "diagnostic_stop", {"phase": phase, "reason": reason})

        # Last chance: one frontier call (if authorized) so advice is in packet for the retry.
        if cycles == max_cycles:
            try:
                self._maybe_frontier(run_id, phase, reason, packet, profile, cycles)
            except ReconciliationRequired:
                return self.state.get(run_id)

        target = REPAIR_TARGET.get(phase, phase)
        if target not in workflow:
            target = phase if phase in workflow else workflow[0]
        index = workflow.index(target) if target in workflow else 0
        predecessor = workflow[max(0, index - 1)]
        self.state.transition(run_id, predecessor, {"repair_target": target, "repair": reason, "cycle": cycles},
                      f"{run_id}:REPAIR:{phase}:{cycles}")
        # Store the last completed predecessor so the target artifact is regenerated, not patched.
        return self.run(run_id, _depth=depth + 1)

    def _maybe_frontier(self, run_id, phase, reason, packet, profile, cycles):
        if not self.live:
            return None
        row = self.state.get(run_id)
        trigger = "two_failed_repair_cycles" if cycles >= 2 else "unresolved_architecture_choice"
        ok, why = authorize_frontier(trigger, lower_tier_attempts=cycles,
                                     calls_used=int(row.get("frontier_calls") or 0),
                                     max_calls=int(self.budgets["profiles"][profile].get("frontier_calls", 0)))
        if not ok:
            self.artifacts.put(run_id, "frontier_denied", "orchestrator", {"trigger": trigger, "reason": why})
            return None
        brief = compress_decision_brief(
            question=f"How should {phase} be resolved after {cycles} failed repair cycles?",
            options=[u.get("summary", "") for u in ((packet.get("plan") or {}).get("change_units") or [])][:5],
            evidence={"reason": reason, "diagnosis": packet.get("diagnosis")},
            constraints=(packet.get("decide") or {}).get("invariants", []),
            criterion=(packet.get("decide") or {}).get("acceptance_criteria", []))
        try:
            advice = self._invoke(run_id, "frontier_advisor", "ESCALATED", {"decision_brief": brief}, 0, profile, None)
        except ReconciliationRequired:
            raise
        except Exception:
            return None
        self.state.bump_frontier(run_id)
        self.artifacts.put(run_id, "frontier_advice", "frontier_advisor", advice)
        packet["frontier_advice"] = advice
        return advice

    # --- support ------------------------------------------------------
    def _register_network(self, broker):
        policy = self.policies.get("network_policy", {})
        if not policy.get("read_only_web_enabled"):
            return
        client = WebClient(policy, self.secrets)
        def guard(fn):
            def call(args):
                try:
                    return fn(args)
                except NetworkDenied as exc:
                    return {"error": "network_denied", "message": str(exc)}
            return call
        broker.register("web.fetch", guard(client.fetch))
        broker.register("web.search", guard(client.search))
        self._register_github(broker)

    def _register_github(self, broker):
        from .github_remote import (
            GitHubRemoteError,
            list_pulls,
            parse_github_https_url,
            repo_metadata,
            resolve_github_token,
        )

        token = resolve_github_token(self.secrets)

        def meta(args):
            try:
                owner = args.get("owner")
                repo = args.get("repo")
                if args.get("url"):
                    owner, repo, _ = parse_github_https_url(args["url"])
                if not owner or not repo:
                    return {"error": "missing_owner_or_repo"}
                return repo_metadata(owner, repo, token=token)
            except GitHubRemoteError as exc:
                return {"error": "github_denied", "message": str(exc)}

        def pulls(args):
            try:
                owner = args.get("owner")
                repo = args.get("repo")
                if args.get("url"):
                    owner, repo, _ = parse_github_https_url(args["url"])
                if not owner or not repo:
                    return {"error": "missing_owner_or_repo"}
                return list_pulls(
                    owner,
                    repo,
                    state=args.get("state") or "open",
                    token=token,
                    per_page=int(args.get("per_page") or 20),
                )
            except GitHubRemoteError as exc:
                return {"error": "github_denied", "message": str(exc)}

        broker.register("github.repo.metadata", meta)
        broker.register("github.pull.list", pulls)

    def _rebuild_packet(self, run_id, row, profile):
        """Working context is projected from durable evidence, never from memory."""
        stored = self.artifacts.load_all(run_id)
        packet = {"ORIGINAL_REQUEST": row["request"], "task_anchor": row["request"], "request": row["request"],
                  "repo": row["repo"], "profile": profile,
                  "permissions": {"live": self.live, "writes_require_approval": bool(self.approvals_required)}}
        for kind, payload in stored.items():
            packet[kind] = payload
        if "research" in stored:
            packet["research_digest"] = ctx.research_digest(stored["research"].get("cards", []))
        plan = stored.get("plan") or {}
        if plan.get("file_allowlist"):
            packet["file_allowlist"] = plan["file_allowlist"]
        if plan:
            packet["plan_summary"] = ctx.plan_summary(plan)
            packet["verification_commands"] = list(plan.get("verification_commands") or [])
            packet["plan_slice"] = list(plan.get("change_units") or [])
        implement = stored.get("implement")
        if implement:
            packet["implement_summary"] = ctx.implement_summary(implement)
        if "diff" in stored:
            summary = ctx.diff_summary(stored["diff"])
            if summary is not None:
                packet["diff_summary"] = summary
        if row.get("plan_hash"):
            packet["plan_hash"] = row["plan_hash"]
        decide = stored.get("decide") or {}
        if decide.get("acceptance_criteria"):
            packet["acceptance_criteria"] = decide["acceptance_criteria"]
        if decide.get("invariants"):
            packet["constraints"] = decide["invariants"]
        return packet


def _git_state(repo: Path):
    try:
        rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, timeout=20)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None, None
    if rev.returncode:
        return None, None
    return rev.stdout.strip(), sha256_text(status.stdout or "")
