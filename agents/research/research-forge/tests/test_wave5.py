from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import pytest

from research_forge.budget.manager import BudgetManager
from research_forge.ledger.jsonl import JsonlLedger
from research_forge.schemas_pkg.registry import get_registry
from research_forge.wave5.approval import ApprovalTokenStore
from research_forge.wave5.challenge import (
    ChallengeAuthorizer,
    ChallengePacketBuilder,
    HighStakesClassifier,
)
from research_forge.wave5.director_role import DirectorPolicyError, PrincipalResearchDirector
from research_forge.wave5.eligibility import DirectorEligibility
from research_forge.wave5.fidelity import FidelityValidator
from research_forge.wave5.handoff import HandoffTaxonomy
from research_forge.wave5.evaluation import Wave5ExitEvaluator
from research_forge.wave5.orchestrator import DirectorOrchestrator
from research_forge.wave5.packet_builder import DirectorPacketBuilder
from research_forge.wave5.provider import DirectorProvider
from research_forge.wave5.repair import DirectorOutputRouter
from research_forge.wave5.types import FORBIDDEN_PACKET_KEYS
from research_forge.wave5.validation import DirectorOutputValidator


@pytest.fixture
def synthesis_source(repo_root: Path) -> dict:
    path = repo_root / "fixtures" / "wave5_synthesis_source.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_w5_a_packet_builder_fidelity_and_schema(synthesis_source: dict, repo_root: Path) -> None:
    builder = DirectorPacketBuilder(token_ceiling=12000)
    built = builder.build(synthesis_source)
    assert built["status"] == "ready"
    packet = built["packet"]
    reg = get_registry(repo_root)
    reg.validate("director_packet", packet)

    for key in FORBIDDEN_PACKET_KEYS:
        assert key not in packet
        assert key not in synthesis_source

    before = copy.deepcopy(packet)
    fidelity = FidelityValidator()
    check = fidelity.validate(before, packet)
    assert check["passed"]

    ctr_fixture = synthesis_source["scrutiny_result"]["contradictions"][0]
    canonical = builder._canonical_contradiction(ctr_fixture)
    assert canonical in packet["contradictions"]

    for row in packet["fact_table"]:
        assert row["evidence_id"]
        assert row["source_id"]
        assert row["locator"]
        assert row["access_level"]

    assert packet["packet_hash"].startswith("sha256:")
    assert packet["builder_version"]
    assert builder.last_selection is not None
    assert builder.last_selection.load_bearing_evidence


def test_w5_a_contradiction_preservation_bytes(synthesis_source: dict) -> None:
    builder = DirectorPacketBuilder()
    built = builder.build(synthesis_source)
    packet = built["packet"]
    raw = synthesis_source["scrutiny_result"]["contradictions"]
    expected = [builder._canonical_contradiction(c) for c in raw]
    assert packet["contradictions"] == expected


def test_w5_a_token_blocked(synthesis_source: dict) -> None:
    builder = DirectorPacketBuilder(token_ceiling=50)
    built = builder.build(synthesis_source)
    assert built["status"] == "BLOCKED"


def test_w5_b_director_role_eligibility_token_and_call(synthesis_source: dict, repo_root: Path) -> None:
    director = PrincipalResearchDirector()
    with pytest.raises(DirectorPolicyError):
        director.assert_tool("search")
    assert director.manifest()["tools"] == ["structured_synthesis"]

    elig = DirectorEligibility()
    skip = elig.assess(
        scrutiny={"acceptance_blocked": False},
        packet_ready=True,
        budget_ok=True,
        profile="M",
        synthesis_need="quick_summary",
    )
    assert skip["skip_director"]

    store = ApprovalTokenStore()
    t1 = store.mint(run_id="r1", packet_hash="sha256:aaa")
    t2 = store.mint(run_id="r1", packet_hash="sha256:bbb")
    assert t1.bind_key() != t2.bind_key()
    store.consume(t1)
    assert not store.validate(t1, packet_hash="sha256:aaa", run_id="r1")["valid"]

    orch = DirectorOrchestrator(repo_root)
    with tempfile.TemporaryDirectory() as tmp:
        ledger = JsonlLedger(Path(tmp) / "ledger.jsonl")
        result = orch.run(synthesis_source, ledger=ledger)
    assert result["status"] == "completed"
    assert result["director_output"]["conclusions"]
    assert result["value_record"]["packet_hash"] == result["packet"]["packet_hash"]
    assert result["budget"]["director_calls"] == 1

    provider = DirectorProvider()
    key = "idem-1"
    packet = result["packet"]
    first = provider.dispatch(packet=packet, token_id="t", idempotency_key=key)
    second = provider.dispatch(packet=packet, token_id="t", idempotency_key=key)
    assert first["status"] == "completed"
    assert second["status"] == "idempotent_replay"
    assert provider.tracker.intellectual_calls == 1


def test_w5_b_validate_and_fallback(synthesis_source: dict, repo_root: Path) -> None:
    validator = DirectorOutputValidator(repo_root)
    builder = DirectorPacketBuilder()
    packet = builder.build(synthesis_source)["packet"]
    invalid = {
        "packet_hash": packet["packet_hash"],
        "conclusions": [{"conclusion_id": "X", "text": "bad", "evidence_ids": ["EVD-NOT-IN-PACKET"]}],
        "claim_links": [],
        "alternatives": [],
        "unfavorable_evidence": [],
        "experiments": [],
        "unknowns": [],
        "format": "doctoral_synthesis",
    }
    v = validator.validate(invalid, packet=packet)
    assert not v["valid"]

    router = DirectorOutputRouter()
    pre = synthesis_source["pre_director_synthesis"]
    routed = router.route(output=invalid, validation=v, pre_director=pre)
    assert routed["status"] == "repair_attempt"
    routed2 = router.route(output=routed["output"], validation=v, pre_director=pre)
    assert routed2["status"] == "fallback"
    assert routed2["director_failed"]


def test_w5_c_handoff_taxonomy(repo_root: Path) -> None:
    data = json.loads((repo_root / "fixtures" / "wave5_handoff_tasks.json").read_text(encoding="utf-8"))
    tax = HandoffTaxonomy(tasks=data["tasks"])
    outcomes: list = []
    for task in data["tasks"]:
        outcomes.extend(tax.run_matched_comparison(task))
    assert len(outcomes) == len(data["tasks"]) * 3
    policy = tax.select_policy(outcomes)
    assert policy.version
    assert "easy_synthesis" in policy.rules
    fp = tax.regression_fingerprint(outcomes)
    assert tax.regression_check(fp, outcomes)["passed"]


def test_w5_d_challenge_path(synthesis_source: dict, repo_root: Path) -> None:
    clf = HighStakesClassifier()
    tagged = {**synthesis_source, "domain_tags": ["medical"], "high_risk_domain": True}
    assert clf.classify(tagged)["high_stakes"]

    auth = ChallengeAuthorizer()
    assert not auth.authorize(
        profile="M", xl_conflict=True, approval_token="tok", budget_ok=True, remaining_director_budget=False
    )["authorized"]
    assert auth.authorize(
        profile="XL", xl_conflict=True, approval_token="tok", budget_ok=True, remaining_director_budget=True
    )["authorized"]

    builder = ChallengePacketBuilder()
    packet = DirectorPacketBuilder().build(synthesis_source)["packet"]
    cpack = builder.build(
        director_conclusion={"text": "lead"},
        counterevidence=packet["contradictions"][:1],
        methods_flags=packet["methods_flags"],
        challenge_question="Is the conclusion robust?",
    )
    assert builder.size_ok(cpack, packet)

    high = {
        **synthesis_source,
        "profile": "XL",
        "domain_tags": ["security"],
        "xl_unresolved_conflict": True,
        "challenge_approval_token": "challenge-approved",
    }
    orch = DirectorOrchestrator(repo_root)
    result = orch.run(high)
    assert result["status"] == "completed"
    assert result["challenge"] is not None


def test_w5_e_exit_eval_and_audit(synthesis_source: dict, repo_root: Path) -> None:
    tasks = json.loads((repo_root / "fixtures" / "wave5_exit_tasks.json").read_text(encoding="utf-8"))["tasks"]
    evaluator = Wave5ExitEvaluator(tasks=tasks)
    report = evaluator.compare_conditions(tasks[0])
    assert report.director_quality_mean > report.no_director_quality_mean
    unsup = evaluator.validate_unsupported_claim_change(report)
    assert unsup["passed"]

    orch = DirectorOrchestrator(repo_root)
    packet = orch.build_packet(synthesis_source)["packet"]
    audit = evaluator.independent_wave5_audit(
        packet=packet,
        director_manifest=PrincipalResearchDirector().manifest(),
        challenge_enabled=True,
    )
    assert audit["passed"]

    bm = BudgetManager(repo_root / "config" / "budgets.yaml")
    bm.start("M")
    assert bm.authorize_director_call(profile="M") is None
    second = bm.authorize_director_call(profile="M")
    assert second is not None
    assert second.code.value == "BUDGET_EXCEEDED"


def test_w5_e_one_call_fixtures(repo_root: Path, synthesis_source: dict) -> None:
    provider = DirectorProvider()
    packet = DirectorPacketBuilder().build(synthesis_source)["packet"]
    provider.dispatch(packet=packet, token_id="a", idempotency_key="k1")
    blocked = provider.dispatch(packet=packet, token_id="a", idempotency_key="k2")
    assert blocked["status"] == "blocked"

    fixtures = json.loads((repo_root / "fixtures" / "wave5_one_call_fixtures.json").read_text(encoding="utf-8"))
    bad = copy.deepcopy(synthesis_source)
    bad["raw_transcript"] = "secret"
    with pytest.raises(ValueError):
        DirectorPacketBuilder().build(bad)
    assert fixtures["cases"]
