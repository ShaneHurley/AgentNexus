from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_forge.adapters.search.mock import MockSearchAdapterV1
from research_forge.budget.manager import BudgetManager
from research_forge.schemas_pkg.registry import get_registry
from research_forge.wave2.context import ContextProjector, ContextRequest, PinnedContextStore
from research_forge.wave2.curator import SourceCurator, query_fingerprint
from research_forge.wave2.dashboard import DashboardBuilder
from research_forge.wave2.evaluation import FanOutEvaluator
from research_forge.wave2.fanout import FanOutOrchestrator
from research_forge.wave2.landscape import LandscapeMapper
from research_forge.wave2.saturation import SaturationConfig, SaturationEngine
from research_forge.wave2.scheduler import DuplicateLaneOwnershipError, FanOutScheduler
from research_forge.wave2.scout import ScoutLaneContract, SourceScout
from research_forge.wave2.types import DEFAULT_ANGLE_TAXONOMY, REQUIRED_SPECIAL_LANES, SchedulerLimits
from services.context_manager import ContextManagerService


@pytest.fixture
def sample_charter() -> dict:
    return {
        "charter_id": "ch-w2",
        "version": 1,
        "objective": "Evaluate fan-out coverage for widget reliability",
        "intended_use": "decision",
        "scope": "widgets",
        "non_goals": ["marketing claims"],
        "research_questions": ["RQ-001", "RQ-002"],
        "constraints": [],
        "assumptions": [],
        "access_rules": ["public_only"],
        "recency": "5y",
        "audience": "engineer",
        "depth": "standard",
        "output_contract": "packet",
        "charter_hash": "sha256:" + "a" * 64,
        "source_classes": ["scholarly", "implementation", "standards"],
    }


def test_w2_a_landscape_taxonomy_and_lanes(sample_charter: dict, repo_root: Path) -> None:
    mapper = LandscapeMapper(extra_angles=["domain_specific_x"])
    out = mapper.map_landscape(sample_charter, seed_sources=[{"title": "Seed", "source_id": "s0"}])
    reg = get_registry(repo_root)
    reg.validate("landscape_map", out)
    assert set(DEFAULT_ANGLE_TAXONOMY).issubset(set(out["angle_taxonomy"]))
    assert "domain_specific_x" in out["angle_taxonomy"]
    angles = {ln["angle"] for ln in out["lanes"]}
    for req in REQUIRED_SPECIAL_LANES:
        assert req in angles
    for term in out["terminology"]:
        assert term["maps_to"]
    for ln in out["lanes"]:
        assert ln["overlap_score"] >= 0
        assert ln["unique_queries"]
    assert mapper.role_id == "landscape_mapper"
    assert mapper.allowed_tools == ()


def test_w2_b_scout_progressive_and_caps() -> None:
    scout = SourceScout(MockSearchAdapterV1())
    contract = ScoutLaneContract(
        lane_id="LANE-TEST",
        question="widget failure modes",
        source_class="scholarly",
        query_family="failures",
        exclusions=["marketing claims"],
        budget_usd=0.2,
        stop_rule={"result_cap": 2, "duplicate_rate_stop": 0.99},
    )
    out = scout.run_lane(contract)
    assert out["lane_id"] == "LANE-TEST"
    assert out["refinements"] <= 1
    assert out["retries"] <= 2
    assert len(out["candidates"]) <= 2
    for c in out["candidates"]:
        assert len(c["relevance_reason"]) <= 280
    assert "recommendation" not in json.dumps(out).lower()


def test_w2_c_scheduler_limits_and_fan_in() -> None:
    limits = SchedulerLimits(max_active_scouts=1, max_adapter_calls_per_lane=2, max_calls_per_domain=1)
    scout = SourceScout(MockSearchAdapterV1())
    sched = FanOutScheduler(limits, scout)
    run_id = "run-sched"
    sched.claim_lane("L1", "scout-a", run_id)
    with pytest.raises(DuplicateLaneOwnershipError):
        sched.claim_lane("L1", "scout-b", run_id)
    sched.stream_candidate(
        run_id,
        "L1",
        {"candidate_id": "c1", "url": "https://example.org/a", "title": "A"},
    )
    sched.stream_candidate(
        run_id,
        "L1",
        {"candidate_id": "c2", "url": "https://example.org/a", "title": "A dup"},
    )
    snap_a = sched.deterministic_fan_in()
    snap_b = sched.deterministic_fan_in()
    assert snap_a.to_dict() == snap_b.to_dict()


def test_w2_d_curator_regression(repo_root: Path) -> None:
    data = json.loads((repo_root / "fixtures" / "wave2_curator_regression.json").read_text())
    curator = SourceCurator()
    clusters = curator.detect_derivative_clusters(data["candidates"])
    keys = [curator.canonicalize_fixture_record(c) for c in data["candidates"]]
    assert keys[0] == keys[1]
    assert keys[2] == keys[3]
    decisions = curator.triage(data["candidates"])
    assert len(decisions) == len(data["candidates"])
    assert len({d.candidate_id for d in decisions}) == len(decisions)
    fp1 = query_fingerprint(
        query_concepts=["a", "b"],
        filters={},
        source_class="scholarly",
        date_range=None,
        lane_id="L",
    )
    fp2 = query_fingerprint(
        query_concepts=["b", "a"],
        filters={},
        source_class="scholarly",
        date_range=None,
        lane_id="L",
    )
    assert fp1 == fp2
    curator.assert_no_external_search("source_registry")
    with pytest.raises(Exception):
        curator.assert_no_external_search("public_search_v1")


def test_w2_e_saturation_and_snowball() -> None:
    engine = SaturationEngine(SaturationConfig())
    engine.record_round("L1", round_index=0, new_canonical=0, new_independent=0, new_contradictions=0, new_claims=0, cost_usd=0.1)
    engine.record_round("L1", round_index=1, new_canonical=0, new_independent=0, new_contradictions=0, new_claims=0, cost_usd=0.1)
    stop, reason = engine.should_stop_lane("L1")
    assert stop and reason == "repeated_duplicates"
    assert not engine.citation_snowball_allowed({"tags": ["generic_survey"]})
    assert engine.citation_snowball_allowed({"load_bearing": True})
    follow = engine.missing_class_followup("standards", attempts=0)
    assert follow["action"] == "bounded_followup"
    gap = engine.missing_class_followup("standards", attempts=1)
    assert gap["action"] == "record_gap"
    ok, _ = engine.early_success_stop(
        {"p1": {"adequate_evidence": True, "counterevidence_attempted": True}}
    )
    assert ok


def test_w2_f_context_projection() -> None:
    pinned = PinnedContextStore(
        charter={"objective": "x", "charter_hash": "sha256:" + "b" * 64},
        budget={"limit_usd": 5},
        permissions={"network": False},
    )
    svc = ContextManagerService(pinned)
    before = pinned.as_dict()
    out = svc.project_for_role(
        "source_scout",
        charter_question="RQ-001",
        source_ids=["s1"],
        evidence_ids=["e1"],
        token_ceiling=500,
        sources={"s1": {"title": "T"}},
        evidence={"e1": {"source_id": "s1", "atomic_claim": "RQ-001 claim", "locators": []}},
        disposable=["navigation chatter", "duplicate snippet"],
    )
    svc.validate_dispatch(before, out)
    assert out["projection"]["source_refs"][0]["source_id"] == "s1"
    assert svc.telemetry[0]["pinned_tokens"] > 0


def test_w2_f_pinned_blocks_on_mutation() -> None:
    pinned = {"charter": {"k": 1}, "permissions": {}, "budget": {}, "accepted_decisions": [], "unresolved_contradictions": []}
    proj = ContextProjector(pinned)
    after = {"projection": {"pinned": {"charter": {"k": 2}}}}
    with pytest.raises(ValueError):
        proj.block_if_invalid(pinned, after)


def test_w2_g_dashboard_regression(repo_root: Path) -> None:
    events = json.loads((repo_root / "fixtures" / "wave2_dashboard_events.json").read_text())
    # out-of-order input
    shuffled = list(reversed(events))
    dash = DashboardBuilder().build("run-w2", shuffled)
    ordered = DashboardBuilder().build("run-w2", events)
    assert dash.duplicate_metrics == ordered.duplicate_metrics
    assert dash.budget["spent_usd"] == pytest.approx(0.75)
    mgr = BudgetManager(repo_root / "config" / "budgets.yaml")
    mgr.start("S")
    mgr.debit(0.75)
    report = DashboardBuilder().export_budget_report(mgr, events)
    assert report["reconciled"]["match"]


def test_w2_h_evaluation_and_audit() -> None:
    ev = FanOutEvaluator({"fanout_min_questions": 2, "trivial_max_questions": 1})
    report = ev.run_matched_experiment(
        "task-1",
        single_metrics={
            "coverage": {"source_class_coverage": 0.4, "research_questions": 1},
            "quality": {"citation_accuracy": 0.9},
            "cost_usd": 1.0,
            "latency_ms": 100,
        },
        fanout_metrics={
            "coverage": {"source_class_coverage": 0.7, "research_questions": 2},
            "quality": {"citation_accuracy": 0.92},
            "cost_usd": 1.1,
            "latency_ms": 120,
        },
        events=[],
    )
    assert report.routing_recommendation == "fan_out"
    audit = ev.wave2_audit([], budget_ok=True)
    assert audit["read_only_ok"]


def test_w2_fanout_integration(sample_charter: dict, repo_root: Path) -> None:
    orch = FanOutOrchestrator(repo_root)
    assert orch.should_fan_out(sample_charter)
    quick = dict(sample_charter)
    quick["research_questions"] = ["RQ-001"]
    assert not orch.should_fan_out(quick)
    result = orch.run(sample_charter, run_id="run-int", max_lanes=2)
    assert result["fan_in"]["canonical_source_ids"]
    assert result["triage"]
