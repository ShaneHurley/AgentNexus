"""Wave 1 sequential DAG orchestrator (RF-W1-I)."""

from __future__ import annotations

import json
import hashlib
import os
import math
import time
from dataclasses import asdict
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from agent_core.contracts import ContractDenied
from agent_core.registry_snapshot import compile_repository
from agent_core.runtime_authority import repository_root, runtime_snapshot
from typing import Any

from research_forge.adapters.reader.gateway import gated_read
from research_forge.adapters.reader.web import WebDocumentReader
from research_forge.adapters.search.gateway import gated_search
from research_forge.adapters.search.mock import MockSearchAdapterV1
from research_forge.budget.manager import BudgetManager, BudgetState
from research_forge.errors import ErrorCode, ForgeException, forge_error
from research_forge.hashing.content import hash_normalized_text
from research_forge.policy.gateway import PolicyGateway
from research_forge.policy.manifest import ToolManifest
from research_forge.providers.live_model import LiveModel
from research_forge.providers.live_reader import LiveReaderAdapter
from research_forge.providers.live_search import LiveSearchAdapter
from research_forge.schemas_pkg.registry import SchemaRegistry, get_registry
from research_forge.settings import Settings, load_settings
from research_forge.wave1.charter import CharterPlanner
from research_forge.wave1.clarifier import IntakeClarifier
from research_forge.wave1.composer import ReportComposer
from research_forge.wave1.extractor import EvidenceExtractor
from research_forge.wave1.live_gate import build_live_contract, effective_mode, validate_live_contract
from research_forge.wave1.verifier import CitationVerifier

PHASES = (
    "clarify",
    "charter",
    "search",
    "select",
    "read",
    "extract",
    "verify",
    "compose",
    "done",
)


def _tool_manifest(tool_id: str) -> ToolManifest:
    return ToolManifest(
        tool_id=tool_id,
        capabilities={
            "read": True,
            "write": False,
            "network": tool_id.startswith(("public", "web", "live")),
            "execute": False,
            "credential": False,
            "data_class": "public",
        },
    )


def build_gateway(settings: Settings, *, live: bool) -> PolicyGateway:
    root = settings.repo_root
    workspace_root = (root / settings.run_workspace).resolve()
    gw = PolicyGateway(
        root / settings.policy_config,
        mode="live" if live else "mock",
        workspace_root=workspace_root,
    )
    for tid in (
        "mock_search_v1",
        "public_search_v1",
        "live_search_v1",
        "local_reader_v1",
        "web_reader_v1",
        "live_reader_v1",
        "ledger",
    ):
        gw.register_tool(_tool_manifest(tid))
    return gw


@dataclass
class RunState:
    run_id: str
    phase: str = "clarify"
    request: dict[str, Any] = field(default_factory=dict)
    clarification: dict[str, Any] | None = None
    charter: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    search_log: list[dict[str, Any]] = field(default_factory=list)
    selected_urls: list[str] = field(default_factory=list)
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    reads: dict[str, dict[str, Any]] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    paused: bool = False
    resume_token: str | None = None
    search_completed: bool = False
    registry_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "phase": self.phase,
            "request": self.request,
            "clarification": self.clarification,
            "charter": self.charter,
            "plan": self.plan,
            "search_log": self.search_log,
            "selected_urls": self.selected_urls,
            "sources": self.sources,
            "reads": self.reads,
            "evidence": self.evidence,
            "paused": self.paused,
            "resume_token": self.resume_token,
            "search_completed": self.search_completed,
            "registry_hash": self.registry_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunState":
        return cls(
            run_id=str(data.get("run_id") or ""),
            phase=str(data.get("phase") or "clarify"),
            request=dict(data.get("request") or {}),
            clarification=data.get("clarification"),
            charter=data.get("charter"),
            plan=data.get("plan"),
            search_log=list(data.get("search_log") or []),
            selected_urls=list(data.get("selected_urls") or []),
            sources=dict(data.get("sources") or {}),
            reads=dict(data.get("reads") or {}),
            evidence=list(data.get("evidence") or []),
            paused=bool(data.get("paused")),
            resume_token=data.get("resume_token"),
            search_completed=bool(data.get("search_completed")),
            registry_hash=data.get("registry_hash"),
        )


def select_sources(results: list[dict[str, Any]], *, max_sources: int = 2) -> list[str]:
    ranked = sorted(
        results,
        key=lambda r: (
            r.get("provider_rank", 99),
            r.get("canonical_title") or r.get("title") or "",
        ),
    )
    urls: list[str] = []
    for row in ranked:
        url = row.get("canonical_url") or row.get("url")
        if url and url not in urls:
            urls.append(url)
        if len(urls) >= max_sources:
            break
    return urls


def source_from_result(result: dict[str, Any], *, source_idx: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    sid = f"SRC-{source_idx:04d}"
    canonical_url = result.get("canonical_url") or result.get("url") or "UNKNOWN"
    title = result.get("canonical_title") or result.get("title") or "UNKNOWN"
    return {
        "source_id": sid,
        "canonical_title": title,
        "authors_or_owner": list(result.get("authors_or_owner") or result.get("authors") or ["UNKNOWN"]),
        "source_type": "paper" if result.get("source_type") == "paper" else "other",
        "publication_state": "published",
        "date": result.get("date") or "UNKNOWN",
        "canonical_url": canonical_url,
        "retrieved_at": result.get("retrieved_at") or now,
        "primary_or_derivative": "primary",
        "access_level": "metadata",
        "content_hash": hash_normalized_text(json.dumps(result, sort_keys=True)),
        "content_hash_algorithm": "sha256-v1",
        "retrieval_method": result.get("retrieval_method") or result.get("adapter_id") or "mock_search_v1",
        "registry_status": "deep_read",
        "source_authenticity": (
            result.get("source_authenticity")
            if result.get("source_authenticity") in ("unverified", "synthetic_fixture")
            else "unverified"
        ),
        "content_availability": "not_read",
    }


class Wave1Orchestrator:
    def __init__(
        self,
        repo_root: Path,
        *,
        registry: SchemaRegistry | None = None,
        live: bool = False,
        web_docs: dict[str, bytes] | None = None,
        search_adapter: Any | None = None,
        reader_adapter: Any | None = None,
        model: Any | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
        workspace: Path | None = None,
        resource_limits: dict[str, Any] | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.workspace = workspace or Path(os.environ.get("RF_RUNTIME_ROOT", str(repo_root)))
        self._journal = None
        self._pins = None
        self.resource_limits = dict(resource_limits) if resource_limits is not None else None
        if self.resource_limits is not None:
            from agent_core.sessions import resources
            resources(self.resource_limits["tokens"],self.resource_limits["usd"])
            deadline=self.resource_limits.get("deadline")
            if deadline is not None and (isinstance(deadline,bool) or not isinstance(deadline,(int,float)) or not math.isfinite(deadline)):
                raise ValueError("deadline must be a finite timestamp")
        self.settings = load_settings(repo_root)
        self.live = live
        self.registry = registry or get_registry(repo_root)
        self.gateway = build_gateway(self.settings, live=live)
        if workspace is not None:
            self.gateway.workspace_root = workspace.resolve()
        self.budget = BudgetManager(repo_root / self.settings.budget_config)
        self.budget.resource_limits = self.resource_limits
        self.clarifier = IntakeClarifier(self.registry)
        self.planner = CharterPlanner(self.registry)
        self.extractor = EvidenceExtractor(self.registry)
        self.verifier = CitationVerifier(self.registry)
        self.composer = ReportComposer(self.registry)

        if model is not None:
            self.model = model
        elif self.live:
            self.model = LiveModel(model=model_name, api_key=api_key)
        else:
            self.model = None

        if search_adapter is not None:
            self.search = search_adapter
        elif self.live:
            self.search = LiveSearchAdapter(model=self.model if isinstance(self.model, LiveModel) else None)
        else:
            self.search = MockSearchAdapterV1()

        if reader_adapter is not None:
            self.reader = reader_adapter
        elif self.live:
            self.reader = LiveReaderAdapter()
        else:
            default_docs = {
                "https://example.org/a": (
                    b"Alpha Paper body. Alpha claims 42% improvement (n=100). Methods described."
                ),
                "https://example.org/b": (
                    b"Beta Paper body. Beta contradicts alpha at 38% in a separate cohort."
                ),
            }
            merged_docs = {**default_docs, **(web_docs or {})}
            self.reader = WebDocumentReader(merged_docs)

        self.max_sources = 2

    def lifecycle(self, run_id: str) -> dict[str, Any]:
        from research_forge.wave1.lifecycle import LifecycleJournal
        return LifecycleJournal(self.workspace,run_id).view()

    def cancel(self, run_id: str) -> dict[str, Any]:
        from research_forge.wave1.lifecycle import LifecycleJournal
        journal = LifecycleJournal(self.workspace,run_id)
        if journal.load() is None:
            raise ContractDenied("unknown RF run")
        journal.cancel()
        return journal.view()

    def _configuration_pins(self) -> dict[str, Any]:
        files = {}
        for directory in ("config", "schemas"):
            for path in sorted((self.repo_root / directory).rglob("*")):
                if path.is_file():
                    files[str(path.relative_to(self.repo_root))] = hashlib.sha256(path.read_bytes()).hexdigest()
        return {"live":self.live,"registry_hash":self.gateway.authority.snapshot.snapshot_id,
                "settings":self.settings.model_dump(mode="json"),"files":files,
                "search":type(self.search).__module__ + "." + type(self.search).__qualname__,
                "reader":type(self.reader).__module__ + "." + type(self.reader).__qualname__,
                "model":getattr(self.model,"model",None),"max_sources":self.max_sources,"resource_limits":self.resource_limits}

    def _check_resource_limits(self):
        if self.resource_limits is None:
            return
        if self.resource_limits["usd"] <= 0 or self.resource_limits["tokens"] <= 0:
            raise ForgeException(forge_error(ErrorCode.BUDGET_EXCEEDED,"Run resource ceiling exhausted"))
        deadline=self.resource_limits.get("deadline")
        if deadline is not None and time.time() >= deadline:
            raise ForgeException(forge_error(ErrorCode.BUDGET_EXCEEDED,"Run deadline exhausted"))

    def run(self, request: dict[str, Any], *, clarification_answers: dict[str,str] | None = None,
            state: RunState | None = None, run_id: str | None = None) -> dict[str, Any]:
        from research_forge.wave1.lifecycle import LifecycleJournal
        if state is not None and run_id is not None:
            raise ContractDenied("run_id may only be supplied for a new RF run")
        st = state or RunState(run_id=run_id or f"run-{uuid.uuid4()}")
        journal = LifecycleJournal(self.workspace,st.run_id)
        with journal.lock():
            pins = self._configuration_pins()
            saved = journal.load()
            if state is not None and saved is None:
                raise ContractDenied("legacy incomplete RF state has no durable checkpoint; start a new run")
            if saved:
                if state is not None and state.registry_hash != pins["registry_hash"]:
                    raise ContractDenied("registry changed or legacy RF run is unpinned; start a new run")
                if saved["pins"] != pins:
                    raise ContractDenied("RF configuration, live mode, or registry changed; start a new run")
                st = RunState.from_dict(saved["state"])
                if request != st.request:
                    raise ContractDenied("RF restart request changed; start a new run")
                if saved["budget"]:
                    self.budget.start(saved["budget"]["profile"])
                    self.budget.state = BudgetState(**saved["budget"])
                journal.check_dispatch()
                if journal.incomplete():
                    raise ContractDenied("RECONCILIATION_REQUIRED: incomplete provider call cannot be replayed")
                if saved.get("result"):
                    return saved["result"]
            else:
                self.budget.state = None
                st.request = request
                st.registry_hash = pins["registry_hash"]
                journal.checkpoint(st,self.budget,pins)
            self._check_resource_limits()
            self._journal, self._pins = journal,pins
            self.budget.journal = journal
            try:
                result = self._execute(request,clarification_answers=clarification_answers,state=st)
                self._check_resource_limits()
                journal.checkpoint(st,self.budget,pins,result=result if st.phase == "done" else None)
                journal.check_dispatch()
                return result
            finally:
                self._journal = None
                self.budget.journal = None

    def _execute(
        self,
        request: dict[str, Any],
        *,
        clarification_answers: dict[str, str] | None = None,
        state: RunState | None = None,
    ) -> dict[str, Any]:
        contract = build_live_contract(cli_live=self.live, settings=self.settings)
        ok, msgs, _ = validate_live_contract(self.repo_root, contract)
        if self.live and not ok:
            return {"ok": False, "errors": msgs}

        st = state or RunState(run_id=f"run-{uuid.uuid4()}")
        snapshot = self.gateway.authority.snapshot
        if state is not None and st.registry_hash != snapshot.snapshot_id:
            raise ContractDenied("registry changed or legacy RF run is unpinned; start a new run")
        if runtime_snapshot().snapshot_id != snapshot.snapshot_id:
            raise ContractDenied("registry changed during execution")
        st.registry_hash = self.gateway.authority.pin(self.repo_root / self.settings.run_workspace / "registry")
        self.gateway.authority.dispatch("orchestrator","ide:deep-research")
        st.request = request
        self.registry.validate(
            "research_request",
            {k: v for k, v in request.items() if not str(k).startswith("_")},
        )

        while st.phase != "done":
            self._journal.checkpoint(st,self.budget,self._pins)
            self._journal.check_dispatch()
            self._check_resource_limits()
            role = {"clarify":"intake_clarifier", "charter":"charter_planner", "extract":"evidence_extractor", "verify":"citation_verifier", "compose":"report_composer"}.get(st.phase)
            if role: self.gateway.authority.dispatch(role,"rf:orchestrator")
            if st.phase == "clarify":
                clar = self.clarifier.clarify(st.request)
                st.clarification = clar
                if clar["result_type"] == "questions" and not clarification_answers:
                    st.paused = True
                    st.resume_token = f"pause-{uuid.uuid4().hex[:8]}"
                    return {
                        "ok": True,
                        "paused": True,
                        "clarification": clar,
                        "state": st.to_dict(),
                    }
                if clarification_answers:
                    st.request = self.clarifier.merge_clarification(
                        st.request, clarification_answers
                    )
                    st.clarification = self.clarifier.clarify(st.request)
                st.paused = False
                st.resume_token = None
                st.phase = "charter"
                continue

            if st.phase == "charter":
                plan = self.planner.build_plan(st.request)
                charter = self.planner.draft_charter(st.request, plan)
                charter = self.planner.freeze_charter(charter)
                st.plan = plan
                st.charter = charter
                self.budget.start(plan.get("budget_profile") or "S")
                st.phase = "search"
                continue

            if st.phase == "search":
                if st.search_completed:
                    st.phase = "read"
                    continue
                query = st.plan["initial_queries"][0] if st.plan else st.request["topic"]
                page = gated_search(
                    self.gateway,
                    self.budget,
                    self.search,
                    role="orchestrator",
                    phase="search",
                    query=query,
                    live=self.live,
                )
                st.search_log.append(page)
                results = page.get("results") or []
                st.selected_urls = select_sources(results, max_sources=self.max_sources)
                for i, url in enumerate(st.selected_urls, start=1):
                    row = next(
                        (r for r in results if (r.get("canonical_url") == url or r.get("url") == url)),
                        results[min(i - 1, len(results) - 1)],
                    )
                    src = source_from_result(row, source_idx=i)
                    self.registry.validate("source_record", src)
                    st.sources[src["source_id"]] = src
                st.search_completed = True
                st.phase = "read"
                continue

            if st.phase == "read":
                for sid, src in st.sources.items():
                    if sid not in st.reads:
                        url = src["canonical_url"]
                        if url.endswith("/missing"):
                            st.reads[sid] = {
                                "access_level": "metadata",
                                "metadata": {"error": "inaccessible"},
                            }
                        else:
                            ref = {"url": url, "mime": "text/plain"}
                            try:
                                st.reads[sid] = gated_read(
                                    self.gateway,
                                    self.budget,
                                    self.reader,
                                    role="orchestrator",
                                    phase="read",
                                    source_ref=ref,
                                    live=self.live,
                                )
                            except Exception as exc:  # noqa: BLE001 — partial path
                                if isinstance(exc, (ContractDenied, ForgeException)) or self._journal.incomplete():
                                    raise
                                st.reads[sid] = {
                                    "access_level": "metadata",
                                    "metadata": {"error": "read_failed", "detail": str(exc)},
                                }

                    read_response = st.reads[sid]
                    read_meta = read_response.get("metadata") or {}
                    retrieval_status = read_meta.get("retrieval_status")
                    if read_meta.get("synthetic") or retrieval_status == "fixture":
                        src["source_authenticity"] = "synthetic_fixture"
                    if retrieval_status == "failed" or read_meta.get("error") == "read_failed":
                        src["content_availability"] = "failed"
                    elif read_meta.get("error"):
                        src["content_availability"] = "unavailable"
                    elif not any(chunk.get("text") for chunk in read_response.get("chunks") or []):
                        src["content_availability"] = "empty"
                    else:
                        src["content_availability"] = "available"
                    src["access_level"] = read_response.get("access_level", "metadata")
                    body = " ".join(
                        chunk.get("text", "") for chunk in read_response.get("chunks") or []
                    ).strip()
                    if body:
                        src["content_hash"] = hash_normalized_text(body)
                    self.registry.validate("source_record", src)
                st.phase = "extract"
                continue

            if st.phase == "extract":
                rq = (st.charter or {}).get("research_questions") or ["RQ-001"]
                question = rq[0]
                for sid in st.sources:
                    read_resp = st.reads.get(sid) or {"access_level": "metadata", "chunks": []}
                    st.evidence.extend(
                        self.extractor.extract(
                            source_id=sid,
                            read_response=read_resp,
                            question_addressed=question,
                        )
                    )
                st.phase = "verify"
                continue

            if st.phase == "verify":
                verified: list[dict[str, Any]] = []
                for card in st.evidence:
                    src = st.sources.get(card["source_id"], {})
                    read_resp = st.reads.get(card["source_id"], {})
                    verified.append(
                        self.verifier.verify(
                            card,
                            source=src,
                            read_response=read_resp,
                            provenance_graph={},
                            live=self.live,
                        )
                    )
                st.evidence = verified
                st.phase = "compose"
                continue

            if st.phase == "compose":
                break

        if st.phase == "compose":
            self.gateway.authority.dispatch("report_composer","rf:orchestrator")
            passed = [c for c in st.evidence if c.get("verifier_status") == "passed"]
            unknowns = [
                u
                for u in [
                    "Negative evidence lane attempted in mock",
                    *(r.get("metadata", {}).get("error", "") for r in st.reads.values() if r.get("metadata")),
                ]
                if u
            ]
            report, findings = self.composer.compose_report(
                charter=st.charter or {},
                verified_cards=passed,
                unknowns=unknowns,
            )
            contradictions = self._contradictions(passed)
            packet = self.composer.build_packet(
                request_id=st.run_id,
                charter=st.charter or {},
                material_claims=findings,
                contradictions=contradictions,
                unknowns=[{"topic": u} for u in unknowns if u],
                report=report,
            )
            st.phase = "done"
            return {
                "ok": True,
                "run_id": st.run_id,
                "mode": effective_mode(self.settings, self.live),
                "report": report,
                "report_hash": hash_normalized_text(report),
                "packet": packet,
                "packet_hash": hash_normalized_text(json.dumps(packet, sort_keys=True)),
                "state": st.to_dict(),
                "audit_count": len(self.gateway.audit_log),
            }
        return {"ok": False, "state": st.to_dict()}

    def resume(self, state: RunState, answers: dict[str, str] | None = None) -> dict[str, Any]:
        return self.run(state.request,clarification_answers=answers,state=state)

    def _contradictions(self, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        contra = [c for c in cards if "contradict" in (c.get("claim") or "").lower()]
        if len(contra) >= 1:
            return [{"summary": "Conflicting numeric claims across sources", "evidence_ids": [c["evidence_id"] for c in contra]}]
        return []
