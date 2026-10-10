"""Lifecycle adapters retain workflow engines and their authoritative gateways."""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import os
import uuid
from .contracts import ContractDenied


def source_snapshot(root, engine, live, provider, workspace):
    paths=[]
    for folder in ("config", "schemas", "agents", "skills", "daily_coder", "src/research_forge", "docs/decisions"):
        directory=root/folder
        if directory.exists():
            paths.extend(p for p in directory.rglob("*") if p.is_file() and p.suffix in (".json",".yaml",".yml",".md",".py") and "__pycache__" not in p.parts)
    files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    shared=root.parents[2]/"agents/shared/agent-core"
    for folder in ("agent_core","config"):
        for path in sorted((shared/folder).rglob("*")):
            if path.is_file() and path.suffix in {".py",".yaml",".json"}:
                files["shared/"+str(path.relative_to(shared))]=hashlib.sha256(path.read_bytes()).hexdigest()
    return {"engine":engine,"live":live,"provider":provider,"workspace":str(Path(workspace).resolve()),"source_hashes":files,
            "effective_environment":{k:os.environ.get(k) for k in ("RF_MODE", "RF_RATE_LIMIT_CALLS", "RF_RATE_LIMIT_WINDOW", "RF_RATE_LIMIT_MAX_WAIT", "RF_RATE_LIMIT_ENABLED") if engine == "research-forge"}}


class DailyCoderAdapter:
    def __init__(self, root): self.root=Path(root)
    def snapshot(self, workspace, live, provider, *, pinned=None):
        from daily_coder.providers.registry import is_live, PROVIDERS
        if provider not in PROVIDERS: raise ContractDenied("unknown provider")
        if is_live(provider) != bool(live): raise ContractDenied("provider and explicit live authorization differ")
        from .routing_runtime import load_model_settings
        return {**source_snapshot(self.root,"daily-coder",live,provider,workspace),**load_model_settings(self.root.parents[2],pinned=pinned)}
    def _engine(self, row):
        from daily_coder.state_store import StateStore
        from daily_coder.orchestrator import Orchestrator
        from daily_coder.providers.mock import MockProvider
        from .providers.registry import build_provider
        from .routing_runtime import SupervisedProvider,load_model_settings
        from .secret_broker import SecretBroker
        name=row["snapshot"]["provider"]
        if name not in {"mock","openrouter","openai","anthropic","local"}:
            raise ContractDenied("provider lacks reviewed supervised adapter; legacy native interface remains available")
        config=json.loads((self.root/"config/default.json").read_text())
        pins=load_model_settings(self.root.parents[2],pinned=row["snapshot"])
        broker=SecretBroker(self.root.parents[2]/".agentnexus/secret-references.sqlite") if name not in {"mock","local"} else None
        wrapper=SupervisedProvider(None,pins,provider_name=name,run_id=row["run_id"],workspace=row["workspace"],broker=broker)
        wrapper.provider=MockProvider() if name=="mock" else build_provider(name,config=config,secret_broker=broker,secret_grant_factory=wrapper.secret_grant)
        wrapper.capabilities=getattr(wrapper.provider,"capabilities",None)
        class ReferencesOnly:
            def get(self,*args,**kwargs):raise ContractDenied("tool credential use requires SecretBroker authorization")
        engine=Orchestrator(self.root,StateStore(self.root/".daily-coder/state.sqlite"),wrapper,live=row["live"],secrets=ReferencesOnly(),
                            resource_limits={"tokens":row["limit_tokens"],"usd":row["limit_usd"],"deadline":row["deadline"]})
        # Shared routing prices are the authority; unknown catalog prices must
        # not inherit unrelated legacy estimates for the same model name.
        engine.pricing.clear()
        for model in pins["model_catalog"]["models"].values():
            if model["provider"]!=name:continue
            price=model["pricing"]
            if price["input_per_million"] is not None and price["output_per_million"] is not None:
                reviewed={"input_per_1k":price["input_per_million"]/1000,"output_per_1k":price["output_per_million"]/1000}
                previous=engine.pricing.get(model["model"])
                if previous is not None and previous!=reviewed:raise ContractDenied("conflicting prices for provider/model")
                engine.pricing[model["model"]]=reviewed
        return engine
    def create(self, row): return self._engine(row).create(row["request"],row["workspace"],run_id=row["run_id"])
    def execute(self, row, answers=None):
        self._engine(row).run(row["legacy_id"])
        return self.inspect(row)
    def inspect(self,row):
        engine=self._engine(row); native=engine.state.get(row["legacy_id"])
        report=engine.budget.report(row["legacy_id"])
        pending=engine.state.active_budget_reservations(row["legacy_id"])
        pending_tools=engine.state.pending_tool_operations(row["legacy_id"]) if hasattr(engine.state,"pending_tool_operations") else []
        status=native["status"]
        if (pending["calls"] or pending_tools) and status != "CANCEL_REQUESTED": status="RECONCILIATION_REQUIRED"
        return {"status":"RUNNING" if status == "ACTIVE" else status,"phase":native["phase"],"state":native,
                "usage":{"tokens":report["tokens"],"usd":report["est_usd"],"usage_status":"estimated","unknown":bool(pending["calls"] or pending_tools or report.get("settled_unreceipted",{}).get("calls"))},
                "artifacts":[{"id":a["hash"],**a} for a in engine.state.artifacts(row["legacy_id"])],
                "pending_approvals":[a for a in engine.state.pending_approvals() if a["run_id"]==row["legacy_id"]]}
    def cancel(self,row): return self._engine(row).request_cancel(row["legacy_id"])
    def acknowledge(self,row):
        engine=self._engine(row)
        # run starts by checking cancellation before any provider/tool dispatch.
        engine.run(row["legacy_id"])
        return self.inspect(row)


class ResearchForgeAdapter:
    def __init__(self, root): self.root=Path(root)
    def snapshot(self,workspace,live,provider, *, pinned=None):
        from research_forge.decisions.validator import validate_decisions_for_gate
        from research_forge.settings import load_settings
        ok,messages=validate_decisions_for_gate(self.root,"wave_1_live" if live else "wave_1_mock")
        if not ok: raise ContractDenied("RF decision gate denied execution: " + "; ".join(messages))
        # Wave 1 uses retrieval, not model calls. Credentials are checked by the
        # authorized search adapter immediately before dispatch.
        snap=source_snapshot(self.root,"research-forge",live,"live" if live else "mock",workspace)
        settings=load_settings(self.root)
        snap["effective_settings"]={"mode":settings.mode,"policy_config":settings.policy_config,"budget_config":settings.budget_config,"extra_hash":hashlib.sha256(json.dumps(settings.extra,sort_keys=True,default=str).encode()).hexdigest()}
        from .routing_runtime import load_model_settings
        snap.update(load_model_settings(self.root.parents[2],pinned=pinned))
        return snap
    def _engine(self,row):
        from research_forge.wave1.orchestrator import Wave1Orchestrator
        search=None
        if row["live"]:
            from .secret_broker import SecretBroker
            from .routing_runtime import SupervisedProvider
            from research_forge.providers.live_search import LiveSearchAdapter
            broker=SecretBroker(self.root.parents[2]/".agentnexus/secret-references.sqlite")
            authority=SupervisedProvider(None,row["snapshot"],provider_name="brave",run_id=row["run_id"],workspace=row["workspace"],namespace="rf",broker=broker)
            class AuthorizedSearch:
                adapter_id="public_search_v1"
                def search(self,query,**kwargs):
                    request=type("Search",(),dict(run_id=row["run_id"],role="orchestrator",credential_ref="provider/brave",deadline=row["deadline"]))()
                    grant=authority.secret_grant(request)
                    if not broker.probe(grant):raise ContractDenied("retrieval credential unavailable")
                    return broker.use(grant,lambda key:LiveSearchAdapter(api_key=key).search(query,**kwargs))
            search=AuthorizedSearch()
        return Wave1Orchestrator(self.root,live=row["live"],workspace=Path(row["workspace"]),search_adapter=search,model=object() if row["live"] else None,
                                 resource_limits={"tokens":row["limit_tokens"],"usd":row["limit_usd"],"deadline":row["deadline"]})
    def create(self,row): return "run-" + str(uuid.uuid4())
    def execute(self,row,answers=None):
        engine=self._engine(row)
        view=engine.lifecycle(row["legacy_id"])
        if view["checkpoint"]:
            from research_forge.wave1.orchestrator import RunState
            state=RunState.from_dict(view["checkpoint"]["state"])
            dispatch=lambda:engine.resume(state,answers=answers)
        else:
            dispatch=lambda:engine.run(row["request"],run_id=row["legacy_id"])
        from research_forge.errors import ForgeException
        try:
            result=dispatch()
        except ForgeException:
            result=self.inspect(row)
            # A known policy/budget denial before dispatch has no uncertain
            # remote outcome. Preserve evidence and settle its known usage.
            if not result["usage"].get("unknown"):
                return {**result,"status":"BLOCKED"}
            raise
        return {**self.inspect(row),"result":result}
    def inspect(self,row):
        view=self._engine(row).lifecycle(row["legacy_id"])
        saved=view["checkpoint"] or {}; state=saved.get("state",{}); status="QUEUED"
        if state.get("phase") == "done": status="COMPLETE" if row["live"] else "SIMULATED"
        elif state.get("paused"): status="WAITING_HUMAN"
        elif state: status="RUNNING"
        if view["reconciliation_required"]: status="RECONCILIATION_REQUIRED"
        if view["cancel_requested"]:
            status="CANCEL_REQUESTED"
            if any(e["kind"] == "cancel_acknowledged" for e in view["events"]) and not view["reconciliation_required"]: status="CANCELLED"
        budget=view["budget"] or {}
        return {"status":status,"phase":state.get("phase","new"),"state":state,"lifecycle":view,
                "usage":{"tokens":budget.get("actual_tokens",0),"usd":budget.get("spent_usd",0.0),"usage_status":"estimated","unknown":view["reconciliation_required"] or bool(budget.get("unknown_token_calls",0))},
                "artifacts":[]}
    def cancel(self,row):
        engine=self._engine(row)
        if engine.lifecycle(row["legacy_id"])["checkpoint"]: return engine.cancel(row["legacy_id"])
        return None
    def acknowledge(self,row):
        from research_forge.wave1.lifecycle import LifecycleJournal
        # A queued alias has no external calls and can be cancelled directly.
        journal=LifecycleJournal(Path(row["workspace"]),row["legacy_id"])
        journal.cancel()
        try: journal.check_dispatch()
        except ContractDenied: pass
        return self.inspect(row)
