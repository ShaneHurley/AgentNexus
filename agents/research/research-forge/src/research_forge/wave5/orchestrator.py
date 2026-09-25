"""Wave 5 orchestrator — packet, Director call, challenge (mock-by-default)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from research_forge.budget.manager import BudgetManager
from research_forge.ledger.jsonl import JsonlLedger
from research_forge.wave5.approval import ApprovalTokenStore
from research_forge.wave5.challenge import (
    ChallengeAuthorizer,
    ChallengePacketBuilder,
    ChallengeResolver,
    HighStakesClassifier,
)
from research_forge.wave5.director_role import PrincipalResearchDirector
from research_forge.wave5.eligibility import DirectorEligibility
from research_forge.wave5.fidelity import FidelityValidator
from research_forge.wave5.packet_builder import DirectorPacketBuilder
from research_forge.wave5.provider import DirectorProvider
from research_forge.wave5.repair import DirectorOutputRouter
from research_forge.wave5.validation import DirectorOutputValidator


def load_wave5_config(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "config" / "wave5.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class DirectorOrchestrator:
    def __init__(self, repo_root: Path, cfg: dict[str, Any] | None = None) -> None:
        self.repo_root = repo_root
        self.cfg = cfg or load_wave5_config(repo_root)
        pack_cfg = self.cfg.get("packet", {})
        self.builder = DirectorPacketBuilder(token_ceiling=int(pack_cfg.get("token_ceiling", 12000)))
        self.fidelity = FidelityValidator()
        self.eligibility = DirectorEligibility()
        self.director = PrincipalResearchDirector()
        self.tokens = ApprovalTokenStore()
        prov_cfg = self.cfg.get("provider", {})
        fixtures = repo_root / "fixtures" / "wave5_model"
        self.provider = DirectorProvider(
            fixtures_dir=fixtures if fixtures.is_dir() else None,
            timeout_seconds=float(prov_cfg.get("timeout_seconds", 120)),
            cost_per_1k_tokens=float(prov_cfg.get("cost_per_1k_tokens", 0.002)),
        )
        self.validator = DirectorOutputValidator(repo_root)
        self.router = DirectorOutputRouter()
        self.classifier = HighStakesClassifier()
        self.challenge_auth = ChallengeAuthorizer()
        self.challenge_builder = ChallengePacketBuilder()
        self.challenge_resolver = ChallengeResolver()
        self.budget = BudgetManager(repo_root / "config" / "budgets.yaml")

    def _ledger_event(
        self,
        ledger: JsonlLedger | None,
        *,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> None:
        if not ledger:
            return
        ledger.append(
            {
                "run_id": run_id,
                "event_type": event_type,
                "payload": payload,
            },
            idempotency_key=idempotency_key,
        )

    def build_packet(self, source: dict[str, Any]) -> dict[str, Any]:
        built = self.builder.build(source)
        if built.get("status") == "BLOCKED":
            return built
        packet = built["packet"]
        before = dict(packet)
        fidelity = self.fidelity.validate(before, packet)
        if not fidelity["passed"]:
            return {"status": "BLOCKED", "reason": "fidelity_failed", "fidelity": fidelity}
        return {"status": "ready", "packet": packet, "selection_rationale": built.get("selection_rationale")}

    def run(
        self,
        source: dict[str, Any],
        *,
        ledger: JsonlLedger | None = None,
        pre_director: dict[str, Any] | None = None,
        synthesis_need: str = "standard",
    ) -> dict[str, Any]:
        run_id = source.get("run_id", "run-w5")
        profile = source.get("profile") or source.get("budget_snapshot", {}).get("profile", "M")
        scrutiny = source.get("scrutiny") or source.get("scrutiny_result")

        self.budget.start(profile)
        budget_ok = self.budget.state is not None and self.budget.state.available > 0

        packet_result = self.build_packet(source)
        packet_ready = packet_result.get("status") == "ready"
        packet = packet_result.get("packet") or {}

        portfolio_critical = bool(source.get("portfolio_audit_critical"))
        elig = self.eligibility.assess(
            scrutiny=scrutiny,
            packet_ready=packet_ready,
            budget_ok=budget_ok,
            profile=profile,
            synthesis_need=synthesis_need,
            human_override=bool(source.get("human_override")),
            portfolio_audit_critical=portfolio_critical,
        )

        if elig.get("skip_director"):
            return {"status": "skipped", "reason": "quick_path", "eligibility": elig}

        if not elig.get("eligible"):
            return {"status": "blocked", "reason": "not_eligible", "eligibility": elig, "packet": packet_result}

        if packet_result.get("status") != "ready":
            return {"status": "blocked", "packet": packet_result, "eligibility": elig}

        self._ledger_event(
            ledger,
            run_id=run_id,
            event_type="director_packet_built",
            payload={
                "packet_hash": packet.get("packet_hash"),
                "builder_version": packet.get("builder_version"),
            },
        )

        token = self.tokens.mint(
            run_id=run_id,
            packet_hash=packet["packet_hash"],
            provider=str(self.cfg.get("provider", {}).get("name", "mock")),
            model=str(self.cfg.get("provider", {}).get("model", "mock-director")),
            max_cost_usd=float(self.cfg.get("provider", {}).get("max_cost_usd", 2.0)),
        )
        tok_check = self.tokens.validate(token, packet_hash=packet["packet_hash"], run_id=run_id)
        if not tok_check["valid"]:
            return {"status": "blocked", "reason": "approval_token_invalid", "issues": tok_check["issues"]}

        budget_err = self.budget.authorize_director_call(profile=profile)
        if budget_err:
            return {"status": "blocked", "reason": budget_err.message, "code": budget_err.code.value}

        self.tokens.consume(token)
        idem = f"{run_id}:{packet['packet_hash']}:director"
        dispatch = self.provider.dispatch(
            packet=packet,
            token_id=token.token_id,
            idempotency_key=idem,
            fixture_task_id=source.get("director_fixture_task", "director_valid"),
        )
        if dispatch.get("status") != "completed":
            return {"status": "failed", "dispatch": dispatch, "packet_hash": packet.get("packet_hash")}

        output = dispatch["output"]
        pre = pre_director or source.get("pre_director_synthesis") or {
            "format": "doctoral_synthesis",
            "conclusions": [],
            "unknowns": packet.get("unknowns", []),
        }
        validation = self.validator.validate(output, packet=packet)
        routed = self.router.route(output=output, validation=validation, pre_director=pre)
        if routed.get("status") == "repair_attempt":
            validation = self.validator.validate(routed["output"], packet=packet)
            routed = self.router.route(output=routed["output"], validation=validation, pre_director=pre)

        final_output = routed.get("output", output)
        accepted = routed.get("status") == "accepted"

        value_record = {
            **dispatch.get("record", {}),
            "validation": validation,
            "accepted": accepted,
            "director_failed": routed.get("director_failed", False),
            "packet_hash": packet.get("packet_hash"),
        }
        self._ledger_event(
            ledger,
            run_id=run_id,
            event_type="director_call_completed",
            payload=value_record,
            idempotency_key=idem,
        )

        stakes = self.classifier.classify(source)
        challenge_out: dict[str, Any] | None = None
        if stakes["high_stakes"] and source.get("xl_unresolved_conflict"):
            auth = self.challenge_auth.authorize(
                profile=profile,
                xl_conflict=True,
                approval_token=source.get("challenge_approval_token"),
                budget_ok=budget_ok,
                remaining_director_budget=profile == "XL",
            )
            if auth.get("authorized"):
                conclusion = (final_output.get("conclusions") or [{}])[0]
                c_packet = self.challenge_builder.build(
                    director_conclusion=conclusion,
                    counterevidence=list(packet.get("contradictions", []))[:3],
                    methods_flags=list(packet.get("methods_flags", [])),
                    challenge_question=source.get("challenge_question", "Stress-test the leading conclusion."),
                )
                assert self.challenge_builder.size_ok(c_packet, packet)
                c_dispatch = self.provider.dispatch(
                    packet={**packet, "challenge": c_packet},
                    token_id=token.token_id,
                    idempotency_key=f"{idem}:challenge",
                    fixture_task_id=source.get("challenge_fixture_task", "challenge_critique"),
                    challenge=True,
                    xl_approved=True,
                )
                challenge_out = self.challenge_resolver.resolve(
                    director_output=final_output,
                    challenge_output=c_dispatch.get("output") or {},
                    evidence_index={r["evidence_id"]: r for r in packet.get("fact_table", [])},
                )

        return {
            "status": "completed",
            "packet": packet,
            "director_output": final_output,
            "routing": routed,
            "value_record": value_record,
            "approval_token": token.to_dict(),
            "high_stakes": stakes,
            "challenge": challenge_out,
            "budget": self.budget.report(),
            "director_manifest": self.director.manifest(),
        }
