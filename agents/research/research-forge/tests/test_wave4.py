from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_forge.schemas_pkg.registry import get_registry
from research_forge.wave4.dimensions import PortfolioDimensions
from research_forge.wave4.diversity import DiversityChecker
from research_forge.wave4.duplicates import NearDuplicateDetector
from research_forge.wave4.evaluation import Wave4ExitEvaluator
from research_forge.wave4.experiment import ExperimentArchitect, ExperimentPolicyError
from research_forge.wave4.fabrication import FabricationChecker
from research_forge.wave4.fusion import PortfolioFusion
from research_forge.wave4.ideator import IdeatorIsolationError, IdeatorPolicyError, IndependentIdeator
from research_forge.wave4.lineage import LineageGraph
from research_forge.wave4.orchestrator import IdeationOrchestrator
from research_forge.wave4.promotion import PromotionRules, RepairQueue
from research_forge.wave4.registry import IdeaRegistry
from research_forge.wave4.types import NO_DEFENSIBLE_IDEA, TACTICAL_OPPORTUNITY_TYPES


@pytest.fixture
def ideation_packet(repo_root: Path) -> dict:
    path = repo_root / "fixtures" / "wave4_ideation_packet.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_w4_a_ideator_isolation_bounds_and_abstention(ideation_packet: dict, repo_root: Path) -> None:
    ideator = IndependentIdeator()
    with pytest.raises(IdeatorPolicyError):
        ideator.assert_no_search("public_search")

    with pytest.raises(IdeatorIsolationError):
        ideator.validate_input({**ideation_packet, "peer_ideas": [{"idea_id": "IDEA-X"}]})

    types = {ideator.assign_opportunity_type(i) for i in range(len(TACTICAL_OPPORTUNITY_TYPES))}
    assert types == set(TACTICAL_OPPORTUNITY_TYPES)

    out0 = ideator.run(ideation_packet, ideator_index=0, draft=ideation_packet["ideator_drafts"][0])
    assert out0["candidates"]
    card = out0["candidates"][0]
    reg = get_registry(repo_root)
    reg.validate("candidate_idea", card)
    assert card["tactical_opportunity_type"] == "replace"
    assert card["evidence_ids"]

    abstain = ideator.run(ideation_packet, ideator_index=2, draft=ideation_packet["ideator_drafts"][2])
    assert abstain["outcome"] == NO_DEFENSIBLE_IDEA

    with pytest.raises(ValueError):
        ideator.enforce_bounds([card, card, card])

    diversity = json.loads(
        (repo_root / "fixtures" / "wave4_diversity_fixtures.json").read_text(encoding="utf-8")
    )
    checker = DiversityChecker()
    for pair in diversity["pairs"]:
        flags = checker.check_pair(pair["left"], pair["right"])
        for expected in pair["expect_flags"]:
            assert expected in flags


def test_w4_b_registry_lineage_duplicates_promotion(repo_root: Path) -> None:
    registry = IdeaRegistry()
    idea_a = {
        "idea_id": "IDEA-A",
        "title": "A",
        "lineage": [],
        "root_cause_model": "rc",
        "proposal": "prop A mechanism alpha",
        "evidence_ids": ["EVD-A1"],
        "assumptions": [],
        "falsification_test": "test A",
        "status": "active",
        "opportunity_type": "incremental",
        "baseline": "b",
        "lineage_hash": "sha256:1",
        "components": ["alpha", "cache"],
    }
    idea_b = {
        **idea_a,
        "idea_id": "IDEA-B",
        "title": "B",
        "proposal": "prop B mechanism alpha",
        "components": ["beta", "cache"],
    }
    registry.add(idea_a)
    registry.add(idea_b)
    registry.reject("IDEA-B", "duplicate")
    assert registry.get("IDEA-B")["status"] == "rejected"
    assert len(registry.query(include_rejected=True)) == 2

    graph = LineageGraph()
    graph.add_parent("IDEA-H", "IDEA-A")
    graph.add_component(
        "IDEA-H",
        component="alpha",
        parent_idea="IDEA-A",
        reason="inherit",
        evidence_id="EVD-A1",
        interface="api",
    )
    with pytest.raises(ValueError):
        graph.add_parent("IDEA-A", "IDEA-H")

    dupes = NearDuplicateDetector()
    clusters = dupes.cluster([idea_a, idea_b])
    assert clusters
    assert dupes.title_differs_mechanism_same(idea_a, idea_b)

    dims = PortfolioDimensions().score_batch([idea_a, idea_b])
    assert set(dims["IDEA-A"]) >= {"evidence", "distinctiveness", "compatibility"}

    promo = PromotionRules()
    repair = RepairQueue(max_attempts=2)
    evidence_index = {
        "EVD-A1": {"evidence_id": "EVD-A1", "source_id": "SRC-A", "verifier_status": "passed"}
    }
    bad = {**idea_a, "dependencies": ["UNKNOWN:vendor-api"]}
    result = promo.try_promote(bad, evidence_index=evidence_index, repair_queue=repair)
    assert not result["ok"]
    assert repair.log

    ok = promo.try_promote(idea_a, evidence_index=evidence_index, repair_queue=repair)
    assert ok["ok"]


def test_w4_c_fusion_compatibility_and_hybrid(repo_root: Path) -> None:
    fusion = PortfolioFusion()
    with pytest.raises(PermissionError):
        fusion.assert_no_search("lane_search")

    a = {
        "idea_id": "IDEA-1",
        "incompatibilities": [],
        "assumptions": ["assumption-x"],
        "proposal": "p1",
    }
    b = {
        "idea_id": "IDEA-2",
        "incompatibilities": [],
        "assumptions": ["assumption-y"],
        "proposal": "p2",
    }
    matrix = fusion.build_compatibility_matrix([a, b])
    key = "IDEA-1|IDEA-2"
    assert matrix[key]["compatible"] is True

    with pytest.raises(ValueError):
        fusion.create_hybrid(
            run_id="run",
            parents=[a, b],
            selections=[],
            baseline_idea_id="IDEA-1",
            evidence={},
            graph=LineageGraph(),
        )

    evidence = {"EVD-A1": {"evidence_id": "EVD-A1", "claim": "supports"}}
    graph = LineageGraph()
    hybrid = fusion.create_hybrid(
        run_id="run",
        parents=[a, b],
        selections=[
            {
                "component": "retry",
                "parent_idea": "IDEA-1",
                "reason": "lower incidents",
                "evidence_id": "EVD-A1",
                "interface": "middleware",
            }
        ],
        baseline_idea_id="IDEA-1",
        evidence=evidence,
        graph=graph,
    )
    get_registry(repo_root).validate("candidate_idea", hybrid)
    review = fusion.interaction_risk_review(
        {**hybrid, "components": ["retry", "cache", "dashboard"]},
        evidence,
    )
    assert review["adversarial_review_required"]


def test_w4_d_experiment_contract(repo_root: Path) -> None:
    arch = ExperimentArchitect()
    idea = {
        "idea_id": "IDEA-EXP",
        "proposal": "Canary feature",
        "baseline": "Production",
    }
    plan = arch.design_for_idea(idea)
    get_registry(repo_root).validate("experiment", plan)
    assert plan["next_steps"]["accept"]
    assert "automatic scale-up" not in plan["next_steps"]["accept"]

    with pytest.raises(ExperimentPolicyError):
        arch.design_for_idea(idea, unsafe=True)

    arch.validate_one_per_task([{"idea_id": "IDEA-1"}, {"idea_id": "IDEA-2"}])
    with pytest.raises(ExperimentPolicyError):
        arch.validate_one_per_task([{"idea_id": "IDEA-1"}, {"idea_id": "IDEA-1"}])


def test_w4_e_fabrication_checks(repo_root: Path) -> None:
    fx = json.loads(
        (repo_root / "fixtures" / "wave4_fabrication_fixtures.json").read_text(encoding="utf-8")
    )
    checker = FabricationChecker()
    index = fx["evidence_index"]
    for row in fx["ideas"]:
        audit = checker.audit_idea(row["idea"], index)
        if row.get("expect_issues"):
            assert audit["issues"] == row["expect_issues"]
        if row.get("expect_issues_prefix"):
            assert any(i.startswith(row["expect_issues_prefix"]) for i in audit["issues"])

    clone_a = {
        "idea_id": "I1",
        "proposal": "alpha mechanism shared",
        "root_cause_model": "r",
        "components": ["a"],
        "assumptions": ["x"],
        "falsification_test": "t",
    }
    clone_b = {
        **clone_a,
        "idea_id": "I2",
        "title": "different title only",
    }
    distinct = checker.check_false_diversity(
        [
            clone_a,
            clone_b,
            {
                "idea_id": "I3",
                "proposal": "beta diverge",
                "root_cause_model": "r2",
                "components": ["z"],
                "assumptions": [],
                "falsification_test": "t",
            },
        ],
        min_distinct=2,
    )
    assert distinct["distinct_count"] == 2


def test_w4_f_exit_and_orchestrator(ideation_packet: dict, repo_root: Path) -> None:
    tasks = json.loads((repo_root / "fixtures" / "wave4_exit_tasks.json").read_text(encoding="utf-8"))
    evaluator = Wave4ExitEvaluator(tasks=tasks["tasks"])
    expectations = evaluator.locked_task_expectations()
    assert len(expectations) == 5
    assert any(e.expect_abstention for e in expectations)

    orch = IdeationOrchestrator(repo_root)
    result = orch.run(ideation_packet)
    assert result["status"] == "completed"
    assert result["abstentions"]
    assert result["experiments"]
    assert result["rejected_alternatives"] is not None
    assert result["registry_events"]

    quality = evaluator.measure_quality_diversity(result["ideas"], result["dimension_scores"])
    assert quality["scalar_aggregate_forbidden"] is True

    rates = evaluator.measure_fabrication_padding(result["fabrication_audits"], ideator_outcomes=[])
    assert rates.to_dict()["generic_templates"] >= 0

    audit = evaluator.independent_wave4_audit(result)
    assert audit["passed"]

    perms = evaluator.audit_permissions()
    assert perms["passed"]
