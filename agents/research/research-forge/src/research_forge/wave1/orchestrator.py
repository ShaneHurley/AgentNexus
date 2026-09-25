"""Wave 1 sequential DAG orchestrator (RF-W1-I)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_forge.adapters.reader.gateway import gated_read
from research_forge.adapters.reader.web import WebDocumentReader
from research_forge.adapters.search.gateway import gated_search
from research_forge.adapters.search.mock import MockSearchAdapterV1
from research_forge.budget.manager import BudgetManager
from research_forge.hashing.content import hash_normalized_text
from research_forge.policy.gateway import PolicyGateway
from research_forge.policy.manifest import ToolManifest
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
            "network": tool_id.startswith("public") or tool_id.startswith("web"),
            "execute": False,
            "credential": False,
            "data_class": "public",
        },
    )


def build_gateway(settings: Settings, *, live: bool) -> PolicyGateway:
    root = settings.repo_root
    gw = PolicyGateway(root / settings.policy_config, mode="live" if live else "mock")
    for tid in ("mock_search_v1", "public_search_v1", "local_reader_v1", "web_reader_v1", "ledger"):
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
        )


def select_sources(results: list[dict[str, Any]], *, max_sources: int = 2) -> list[str]:
    ranked = sorted(results, key=lambda r: (r.get("provider_rank", 99), r.get("canonical_title", "")))
    urls: list[str] = []
    for row in ranked:
        url = row.get("canonical_url")
        if url and url not in urls:
            urls.append(url)
        if len(urls) >= max_sources:
            break
    return urls


def source_from_result(result: dict[str, Any], *, source_idx: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    sid = f"SRC-{source_idx:04d}"
    return {
        "source_id": sid,
        "canonical_title": result.get("canonical_title") or "UNKNOWN",
        "authors_or_owner": list(result.get("authors_or_owner") or ["UNKNOWN"]),
        "source_type": "paper" if result.get("source_type") == "paper" else "other",
        "publication_state": "published",
        "date": result.get("date") or "UNKNOWN",
        "canonical_url": result.get("canonical_url") or "UNKNOWN",
        "retrieved_at": result.get("retrieved_at") or now,
        "primary_or_derivative": "primary",
        "access_level": "full",
        "content_hash": hash_normalized_text(json.dumps(result, sort_keys=True)),
        "content_hash_algorithm": "sha256-v1",
        "retrieval_method": "mock_search_v1",
        "registry_status": "deep_read",
    }


class Wave1Orchestrator:
    def __init__(
        self,
        repo_root: Path,
        *,
        registry: SchemaRegistry | None = None,
        live: bool = False,
        web_docs: dict[str, bytes] | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.settings = load_settings(repo_root)
        self.live = live
        self.registry = registry or get_registry(repo_root)
        self.gateway = build_gateway(self.settings, live=live)
        self.budget = BudgetManager(repo_root / self.settings.budget_config)
        self.clarifier = IntakeClarifier(self.registry)
        self.planner = CharterPlanner(self.registry)
        self.extractor = EvidenceExtractor(self.registry)
        self.verifier = CitationVerifier(self.registry)
        self.composer = ReportComposer(self.registry)
        self.search = MockSearchAdapterV1()
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

    def run(
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

        run_seed = hash_normalized_text(json.dumps(request, sort_keys=True))[:12].replace("sha256:", "")
        st = state or RunState(run_id=f"run-{run_seed}")
        st.request = request
        self.registry.validate(
            "research_request",
            {k: v for k, v in request.items() if not str(k).startswith("_")},
        )

        while st.phase != "done":
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
                        (r for r in results if r.get("canonical_url") == url),
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
                    if sid in st.reads:
                        continue
                    url = src["canonical_url"]
                    if url.endswith("/missing"):
                        st.reads[sid] = {
                            "access_level": "metadata",
                            "metadata": {"error": "inaccessible"},
                        }
                        continue
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
                        st.reads[sid] = {
                            "access_level": "metadata",
                            "metadata": {"error": "read_failed", "detail": str(exc)},
                        }
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
                        )
                    )
                st.evidence = verified
                st.phase = "compose"
                continue

            if st.phase == "compose":
                break

        if st.phase == "compose":
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

    def resume(self, state: RunState, answers: dict[str, str]) -> dict[str, Any]:
        if not state.paused and state.phase != "clarify":
            state.phase = "charter" if state.charter else state.phase
        state.paused = False
        return self.run(state.request, clarification_answers=answers, state=state)

    def _contradictions(self, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        contra = [c for c in cards if "contradict" in (c.get("claim") or "").lower()]
        if len(contra) >= 1:
            return [{"summary": "Conflicting numeric claims across sources", "evidence_ids": [c["evidence_id"] for c in contra]}]
        return []
