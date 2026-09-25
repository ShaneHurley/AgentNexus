from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_forge.schemas_pkg.registry import get_registry
from research_forge.wave3.auditor import AuditVetoError, ResearchAuditor
from research_forge.wave3.contradiction import ContradictionMapper, MatrixConsistencyError
from research_forge.wave3.evaluation import ScrutinyMetrics, Wave3ExitEvaluator
from research_forge.wave3.falsify import FalsificationDesigner
from research_forge.wave3.followup import FollowUpCoordinator, FollowUpPolicyError
from research_forge.wave3.methods import MethodsPolicyError, MethodsReviewer
from research_forge.wave3.orchestrator import ScrutinyOrchestrator
from research_forge.wave3.propositions import PropositionRegistry
from research_forge.wave3.recompute import recompute_expression
from research_forge.wave3.skeptic import AdversarialSkeptic, SkepticPolicyError
from research_forge.wave3.types import METHODS_FIXTURE_KINDS


@pytest.fixture
def scrutiny_packet(repo_root: Path) -> dict:
    path = repo_root / "fixtures" / "wave3_scrutiny_packet.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_w3_a_methods_activation_and_fixtures(repo_root: Path) -> None:
    reviewer = MethodsReviewer()
    doc_source = {"source_id": "SRC-DOC", "source_class": "documentation"}
    assert not reviewer.should_activate(doc_source, [])

    fixtures = json.loads(
        (repo_root / "fixtures" / "wave3_methods_fixtures.json").read_text(encoding="utf-8")
    )
    detected: set[str] = set()
    for fx in fixtures:
        src = {
            "source_id": fx["source_id"],
            "study_types": fx.get("study_types", ["benchmark"]),
            "load_bearing": True,
            "triage_status": "DEEP_READ",
        }
        card = dict(fx["evidence"])
        card.setdefault("verifier_status", "passed")
        out = reviewer.review(src, [card])
        reg = get_registry(repo_root)
        reg.validate("methods_review", out)
        for f in out["flags"]:
            if f["kind"] in METHODS_FIXTURE_KINDS:
                detected.add(f["kind"])
        assert out["activated"]
        assert out["checklists"]
    assert detected == set(METHODS_FIXTURE_KINDS)

    recomp = recompute_expression("(a + b) / n", {"a": 90.0, "b": 10.0, "n": 2.0})
    assert recomp["result"] == 50.0

    with pytest.raises(MethodsPolicyError):
        reviewer.assert_tool_allowed("public_search")


def test_w3_b_contradiction_matrix_and_gaps(scrutiny_packet: dict, repo_root: Path) -> None:
    mapper = ContradictionMapper()
    matrix = mapper.build_matrix(
        scrutiny_packet["sources"],
        scrutiny_packet["evidence"],
        scrutiny_packet["matrix_cells"],
    )
    get_registry(repo_root).validate("evidence_matrix", matrix)

    reg = PropositionRegistry()
    pid1 = reg.register("Method M improves reliability")
    pid2 = reg.register("method m improves reliability")
    assert pid1 == pid2

    conflicts = mapper.detect_conflicts(matrix)
    assert conflicts
    records = mapper.to_contradiction_records(conflicts)
    get_registry(repo_root).validate("contradiction", records[0])
    gaps = mapper.generate_gaps(conflicts)
    assert gaps[0]["stop_rule"]

    with pytest.raises(MatrixConsistencyError):
        mapper.validate_matrix(
            [
                {
                    "source_id": "SRC-A",
                    "proposition_id": "P1",
                    "evidence_id": "EVD-1",
                    "stance": "supports",
                },
                {
                    "source_id": "SRC-A",
                    "proposition_id": "P1",
                    "evidence_id": "EVD-1",
                    "stance": "contradicts",
                },
            ]
        )


def test_w3_c_skeptic_frozen_and_round_cap(scrutiny_packet: dict) -> None:
    skeptic = AdversarialSkeptic(max_rounds=3)
    with pytest.raises(SkepticPolicyError):
        skeptic.assert_no_search("scout_lane")

    out = skeptic.run_review(
        leading_conclusions=scrutiny_packet["leading_conclusions"],
        evidence=scrutiny_packet["evidence"],
        objections=scrutiny_packet["objections"],
        charter_frozen=scrutiny_packet["charter"],
    )
    assert out["rounds_used"] <= 3
    gated = {o.get("summary", o.get("category")): o["status"] for o in out["objections"]}
    assert gated["noise without evidence"] == "bounded_gap"
    assert out["strongest_unfavorable"] is not None
    assert out["checks_performed"]


def test_w3_d_falsification_rejects_bad_tests() -> None:
    designer = FalsificationDesigner()
    hyps = [{"hypothesis_id": "H1", "status": "live"}, {"hypothesis_id": "H2", "status": "live"}]
    proposed = [
        {"test_id": "taut", "tautology": True, "predicted_outcome": "always_true"},
        {"test_id": "move", "moving_target": True, "predictions": {"H1": "a", "H2": "b"}},
        {"test_id": "imp", "impossible_measurement": True, "predictions": {"H1": "a", "H2": "b"}},
        {
            "test_id": "same",
            "predictions": {"H1": "same", "H2": "same"},
            "information_value": 0.5,
            "cost_usd": 1,
            "time_days": 1,
        },
        {
            "test_id": "good",
            "predictions": {"H1": "low", "H2": "high"},
            "information_value": 0.9,
            "cost_usd": 0.5,
            "time_days": 1,
            "feasibility": 0.9,
        },
    ]
    out = designer.design_tests([], hyps, proposed)
    reasons = {t["test_id"]: t["reject_reason"] for t in out["rejected_tests"]}
    assert reasons["taut"] == "tautology"
    assert reasons["move"] == "moving_target"
    assert reasons["imp"] == "impossible_measurement"
    assert reasons["same"] == "confirms_only"
    assert out["tests"][0]["test_id"] == "good"
    assert out["recommends_implementation"] is False


def test_w3_e_followup_bounded_and_schema(repo_root: Path) -> None:
    coord = FollowUpCoordinator(max_rounds=1)
    bad = coord.validate_request({"gap_id": "GAP-1", "query": "research more"})
    assert "generic_query_forbidden" in bad

    req = {
        "gap_id": "GAP-1",
        "decision_relevance": "high",
        "inspected_evidence_ids": ["EVD-A1"],
        "desired_source_type": "scholarly",
        "query": "independent replication widget reliability",
        "budget_usd": 0.25,
        "stop_condition": "close UNKNOWN if no new evidence",
    }
    get_registry(repo_root).validate("follow_up_request", req)

    with pytest.raises(FollowUpPolicyError):
        coord.authorize(req, orchestrator_approved=True, budget_approved=True, self_spawn=True)

    no_gain = coord.execute_lane(
        req,
        scout_run={"candidates": [], "forced_no_gain": True},
        curator_decisions=[],
    )
    assert no_gain["status"] == "completed"
    assert no_gain.get("gap_resolution") == "UNKNOWN"

    denied = coord.authorize(req, orchestrator_approved=True, budget_approved=True)
    assert denied["authorized"] is False
    assert "max_rounds_exceeded" in denied["errors"]

    with pytest.raises(FollowUpPolicyError):
        coord.assert_no_bypass("custom_scraper_workflow")


def test_w3_f_auditor_veto_and_adversarial(scrutiny_packet: dict, repo_root: Path) -> None:
    auditor = ResearchAuditor()
    auditor.assert_separate_identity("report_composer", "research_auditor")
    with pytest.raises(PermissionError):
        auditor.assert_separate_identity("research_auditor", "research_auditor")

    kinds = [
        "fake_doi",
        "retraction",
        "derivative_consensus",
        "stale_docs",
        "citation_swap",
        "abstract_trap",
        "prompt_injection",
        "omitted_negative_result",
    ]
    signals = [{"kind": k, "present": True} for k in kinds]
    report = auditor.audit(scrutiny_packet, sample_seed=7, adversarial_signals=signals)
    get_registry(repo_root).validate("audit_report", report)
    critical = [f for f in report["findings"] if f["severity"] == "critical"]
    assert len(critical) >= 3
    assert report["sample_seed"] == 7

    with pytest.raises(AuditVetoError):
        auditor.enforce_veto(report)

    alt = auditor.audit(
        {"claims": [{"claim_id": "C1", "evidence_ids": ["EVD-A1"]}]},
        sample_seed=1,
        adversarial_signals=[],
    )
    disagree = auditor.resolve_disagreement([report, alt])
    assert disagree["blocked"] is True or disagree["resolved"] is False


def test_w3_g_exit_suite_and_orchestrator(scrutiny_packet: dict, repo_root: Path) -> None:
    orch = ScrutinyOrchestrator(repo_root)
    result = orch.run(scrutiny_packet, sample_seed=99)
    assert result["methods_flags"]
    assert result["contradictions"]
    assert result["acceptance_blocked"] is True

    evaluator = Wave3ExitEvaluator()
    baseline = ScrutinyMetrics(methods_flags=0, contradictions_found=0, audit_critical=0, cost_usd=0.1)
    comparison = evaluator.run_locked_scrutiny_suite(
        "w3-exit-001",
        scrutiny_packet,
        wave2_baseline=baseline,
        wave3_result=result,
    )
    assert comparison.improved
    noise = evaluator.calibrate_reviewer_noise(
        [
            {"predicted_critical": True, "actual_critical": True},
            {"predicted_critical": True, "actual_critical": False},
        ]
    )
    assert "precision" in noise
    bounded = evaluator.validate_bounded_followup(FollowUpCoordinator(max_rounds=1), attempts=2)
    assert bounded["passed"]
    self_audit = evaluator.audit_wave3_permissions()
    assert self_audit["passed"]
