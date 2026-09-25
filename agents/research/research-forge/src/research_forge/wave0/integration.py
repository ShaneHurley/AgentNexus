"""Wave 0 mock run fixture builder."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from research_forge.budget.manager import BudgetManager
from research_forge.budget.wrapper import budget_wrapped_call, mark_wrapped
from research_forge.ledger.jsonl import JsonlLedger
from research_forge.ledger.reconstruct import reconstruct_run_state
from research_forge.policy.gateway import PolicyGateway
from research_forge.policy.manifest import ToolManifest
from research_forge.providers.mock_model import MockModel
from research_forge.registries.evidence import EvidenceRegistry
from research_forge.registries.source import SourceRegistry
from research_forge.settings import load_settings
from research_forge.versions import MANIFEST


def _build_default_events(run_id: str) -> list[dict[str, Any]]:
    return [
        {
            "run_id": run_id,
            "event_type": "run_manifest",
            "payload": {
                "charter_hash": "sha256:charter-fixture",
                "policy_version": MANIFEST.policy,
                "schema_version": MANIFEST.schema_version,
                "phase": "wave0_fixture",
            },
        },
        {
            "run_id": run_id,
            "event_type": "source_registered",
            "payload": {
                "source_id": "src-primary",
                "title": "Primary Source",
                "access_level": "full",
                "content_hash": "sha256:aaa",
                "primary_or_derivative": "primary",
                "identifiers": [{"type": "url", "value": "https://example.org/a"}],
            },
        },
        {
            "run_id": run_id,
            "event_type": "source_registered",
            "payload": {
                "source_id": "src-derivative",
                "title": "Derivative Summary",
                "access_level": "snippet",
                "content_hash": "sha256:bbb",
                "primary_or_derivative": "derivative",
                "provenance_parent_ids": ["src-primary"],
                "identifiers": [{"type": "url", "value": "https://example.org/mirror"}],
            },
        },
        {
            "run_id": run_id,
            "event_type": "evidence_added",
            "payload": {
                "evidence_id": "ev-1",
                "source_id": "src-primary",
                "locator": "chunk:0",
                "atomic_claim": "Effect size was 0.42",
                "access_level": "full",
                "claim_status": "VERIFIED",
                "verifier_status": "pass",
                "confidence_reason": "direct quote",
            },
        },
        {
            "run_id": run_id,
            "event_type": "evidence_added",
            "payload": {
                "evidence_id": "ev-2",
                "source_id": "src-primary",
                "locator": "chunk:1",
                "atomic_claim": "Sample size n=100",
                "access_level": "full",
                "claim_status": "CORROBORATED",
                "verifier_status": "pass",
                "confidence_reason": "table match",
            },
        },
        {
            "run_id": run_id,
            "event_type": "evidence_added",
            "payload": {
                "evidence_id": "ev-3",
                "source_id": "src-derivative",
                "locator": "snippet:0",
                "atomic_claim": "Summary repeats effect 0.42",
                "access_level": "snippet",
                "claim_status": "INFERENCE",
                "verifier_status": "pass",
                "confidence_reason": "derivative echo",
                "inference_accepted": True,
            },
        },
        {
            "run_id": run_id,
            "event_type": "audit",
            "payload": {
                "contradiction_id": "con-1",
                "proposition": "Effect size magnitude",
                "contradiction_type": "numeric_disagreement",
            },
        },
        {
            "run_id": run_id,
            "event_type": "budget_debit",
            "payload": {"amount_usd": 0.5, "role": "fixture", "lane": "default"},
        },
    ]


def run_wave0_fixture(repo_root: Path, fixture_path: Path | None) -> dict[str, Any]:
    settings = load_settings(repo_root)
    run_id = "wave0-fixture-run"
    if fixture_path and fixture_path.is_file():
        spec = json.loads(fixture_path.read_text(encoding="utf-8"))
        run_id = spec.get("run_id", run_id)

    with tempfile.TemporaryDirectory() as tmp:
        ledger_path = Path(tmp) / "ledger.jsonl"
        ledger = JsonlLedger(ledger_path)
        for ev in _build_default_events(run_id):
            ledger.append(ev)

        events = ledger.read_by_run(run_id)
        ok_chain, chain_errs = ledger.verify_chain(run_id)
        state = reconstruct_run_state(events)
        sources = SourceRegistry.from_events(events)
        evidence = EvidenceRegistry(events, state.get("sources", {}))

        gateway = PolicyGateway(repo_root / settings.policy_config, mode=settings.mode)
        for tool in (
            ToolManifest(
                "mock_search",
                {
                    "read": True,
                    "write": False,
                    "network": True,
                    "execute": False,
                    "credential": False,
                    "data_class": "public",
                },
            ),
            ToolManifest(
                "mock_model",
                {
                    "read": True,
                    "write": False,
                    "network": False,
                    "execute": False,
                    "credential": False,
                    "data_class": "public",
                },
            ),
        ):
            gateway.register_tool(tool)

        budget = BudgetManager(repo_root / settings.budget_config)
        budget.start("S")

        model = MockModel()

        @mark_wrapped
        def _model_call() -> dict[str, Any]:
            return model.complete("fixture prompt", task_id=run_id)

        wrapped = budget_wrapped_call(
            gateway,
            budget,
            cost_usd=0.1,
            auth_kwargs={
                "role": "host",
                "phase": "wave0",
                "tool_id": "mock_model",
                "operation": "model_call",
                "target": "adapter://public/mock",
            },
            fn=_model_call,
        )

        canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
        state_hash = hashlib.sha256(canonical.encode()).hexdigest()
        bundle = ledger.export_bundle(run_id)
        bundle["expected_state_hash"] = state_hash

        return {
            "run_id": run_id,
            "chain_ok": ok_chain,
            "chain_errors": chain_errs,
            "state_hash": state_hash,
            "source_count": len(sources._sources),
            "evidence_count": len(evidence.active_cards()),
            "model_response_key": wrapped.get("text", "")[:32],
            "budget": budget.report(),
            "deterministic": True,
        }
