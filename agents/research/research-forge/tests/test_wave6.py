from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_forge.registries.normalize import normalize_arxiv, normalize_doi
from research_forge.wave6.adapters import (
    MockCodeRepositoryAdapter,
    MockDatasetArtifactAdapter,
    MockInternalKnowledgeAdapter,
    MockPatentAdapter,
    MockScholarlySearchAdapter,
    MockStandardsAdapter,
    merge_retrieval_records,
)
from research_forge.wave6.maintain import (
    AdversarialFixtureRegistry,
    DeprecationReviewer,
    DisasterRecovery,
    DriftMonitor,
    ModelRevalidator,
    SourcePolicyReviewer,
)
from research_forge.wave6.proposals import (
    CanaryController,
    ImprovementProposal,
    ProposalChangelog,
    ProposalGenerator,
    ProposalReplay,
    ProposalWorkflow,
)
from research_forge.wave6.proposals.workflow import MergeApproval
from research_forge.wave6.routing import (
    LearnedRouterRegistry,
    OfflineTrainer,
    RoutingDataQualityFilter,
    RoutingGuardrails,
    ShadowRouter,
    StaticRoutingBaseline,
)
from research_forge.wave6.routing.promotion import RouterPromotionRecord
from research_forge.wave6.sdk import (
    AdapterCapabilityManifest,
    ConformanceSuite,
    HealthChecker,
    MigrationManager,
    MigrationPolicy,
    PluginRegistry,
)
from research_forge.wave6.sdk.bad_adapter import BadAdapter
from research_forge.wave6.skills import ALL_SKILLS, SkillRouter, SkillRunner, SkillVersionStore, validate_skill_document
from research_forge.wave6.skills.manifest import SkillManifest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


# --- W6-A SDK ---


def test_unknown_capability_denied() -> None:
    manifest = AdapterCapabilityManifest(
        adapter_id="x",
        version="1.0.0",
        protocol_version="1.0.0",
        capabilities={"teleport": True},
        allowed_operations=["search"],
    )
    assert any("unknown_capability" in e for e in manifest.validate())


def test_bad_adapter_fails_conformance() -> None:
    report = ConformanceSuite().run(BadAdapter())
    assert not report["ok"]
    assert report["failures"]


def test_unapproved_plugin_cannot_load(repo_root: Path) -> None:
    reg = PluginRegistry({"approved_signatures": ["only-this"]})
    manifest = AdapterCapabilityManifest(
        adapter_id=" rogue ",
        version="1.0.0",
        protocol_version="1.0.0",
        capabilities={"read": True, "data_class": "public"},
        allowed_operations=["search"],
    )
    from research_forge.wave6.sdk.registry import PluginRecord

    out = reg.register_plugin(
        PluginRecord("rogue", "entry", "not-approved", approved=False, manifest=manifest)
    )
    assert out["loaded"] is False


def test_health_excludes_unhealthy() -> None:
    hc = HealthChecker()
    healthy = hc.filter_healthy([MockScholarlySearchAdapter(), BadAdapter()])
    assert len(healthy) == 1


def test_migration_blocks_deprecated() -> None:
    mgr = MigrationManager(
        {
            "mock_scholarly": MigrationPolicy(
                "mock_scholarly", "1.0.0", "1.0.0", frozenset({"0.9.0"})
            )
        }
    )
    out = mgr.activate("mock_scholarly", "0.9.0", "1.0.0")
    assert out["activated"] is False


def test_plugin_registry_from_config(repo_root: Path) -> None:
    reg = PluginRegistry({"approved_signatures": ["a1b2c3d4e5f67890"]})
    results = reg.discover_from_config(repo_root / "config" / "wave6_plugins.yaml")
    assert any(r.get("loaded") for r in results)


# --- W6-B Adapters ---


def test_scholarly_mapping_no_guessed_metadata() -> None:
    ad = MockScholarlySearchAdapter()
    out = ad.search("Example Study Alpha", page_size=5, cursor=0)
    for r in out["results"]:
        assert r["guessed_fields"] == []
        assert r["metadata_provenance"] == "provider_mapped"


def test_scholarly_doi_arxiv_alias() -> None:
    ad = MockScholarlySearchAdapter()
    results = ad.search("Example Study Alpha", page_size=10)["results"]
    groups = {r.get("alias_group") for r in results}
    arxiv = {normalize_arxiv(r["canonical_arxiv"]) for r in results if r.get("canonical_arxiv")}
    assert len(groups) == 1
    assert "arxiv:2301.00001" in arxiv


def test_scholarly_conformance() -> None:
    assert ConformanceSuite().run(MockScholarlySearchAdapter())["ok"]


def test_code_repo_write_blocked() -> None:
    ad = MockCodeRepositoryAdapter()
    with pytest.raises(PermissionError):
        ad.write_file("x", "y")


def test_standards_superseded_flagged() -> None:
    ad = MockStandardsAdapter()
    hit = ad.search("HTTP", page_size=5)["results"]
    assert any(r["superseded"] for r in hit)
    read = ad.read({"standard_id": "RFC2616"})
    assert read["superseded"] is True


def test_internal_cross_user_leakage_fails() -> None:
    alice = MockInternalKnowledgeAdapter(acting_user="alice")
    bob = MockInternalKnowledgeAdapter(acting_user="bob")
    assert alice.read({"doc_id": "doc-bob-1"}).get("error") == "permission_denied"
    assert bob.read({"doc_id": "doc-bob-1"}).get("access_level") == "full"


def test_patent_status_uncertainty_explicit() -> None:
    ad = MockPatentAdapter()
    r = ad.read({"publication_number": "EP3000000A1"})
    assert r["status_certainty"] == "uncertain"


def test_dataset_not_executed() -> None:
    ad = MockDatasetArtifactAdapter()
    out = ad.read({"artifact_id": "ds-001"})
    assert out["executed"] is False
    with pytest.raises(PermissionError):
        ad.execute()


def test_cross_adapter_dedup() -> None:
    merged = merge_retrieval_records(
        [
            {
                "provider": "scholarly_a",
                "identifiers": [{"type": "doi", "value": "10.1000/x"}],
                "alias_group": "doi:10.1000/x",
            },
            {
                "provider": "scholarly_b",
                "identifiers": [{"type": "doi", "value": "10.1000/x"}],
                "alias_group": "doi:10.1000/x",
            },
        ]
    )
    assert merged["independence_count"] == 1
    assert len(merged["retrievals"]) == 2


# --- W6-C Skills ---


def test_prose_only_skill_invalid() -> None:
    errs = validate_skill_document({"name": "x", "description": "just prose", "phases": ["a"]})
    assert "prose_only_invalid" in errs


def test_systematic_review_mock_run() -> None:
    skill = ALL_SKILLS["systematic_review"]
    out = SkillRunner().run(skill, {"research_charter": {"topic": "t"}})
    assert "search_log" in out["phases"]


def test_experiment_design_unfalsifiable_fails() -> None:
    skill = ALL_SKILLS["experiment_design"]
    out = SkillRunner().run(
        skill, {"research_charter": {}, "hypothesis": "always true under all conditions"}
    )
    assert out.get("error") == "unfalsifiable_plan"


def test_skill_routing_logged() -> None:
    router = SkillRouter()
    d = router.route({"request_type": "literature_review"})
    assert d.selected == ["systematic_review"]
    assert router.log


def test_skill_version_rollback() -> None:
    store = SkillVersionStore()
    m1 = SkillManifest(
        name="systematic_review",
        version="1.0.0",
        request_types=["literature_review"],
        required_inputs=["research_charter"],
        phases=["a"],
        output_schemas=["s"],
        tool_budgets={"search": 1},
        acceptance_criteria=["x"],
        prohibited_behaviors=["y"],
    )
    m2 = SkillManifest(
        name="systematic_review",
        version="2.0.0",
        request_types=["literature_review"],
        required_inputs=["research_charter"],
        phases=["a", "b"],
        output_schemas=["s"],
        tool_budgets={"search": 2},
        acceptance_criteria=["x"],
        prohibited_behaviors=["y"],
    )
    store.publish(m1, held_out_passed=True)
    store.publish(m2, held_out_passed=True)
    store.rollback("systematic_review", "1.0.0")
    assert store.active("systematic_review").version == "1.0.0"


# --- W6-D Routing ---


def test_routing_quality_filter(repo_root: Path) -> None:
    events = json.loads((repo_root / "fixtures" / "wave6_routing_events.json").read_text())
    clean = RoutingDataQualityFilter().filter(events)
    assert len(clean) == 2


def test_offline_train_no_live_tools() -> None:
    def guard() -> None:
        raise RuntimeError("training_cannot_call_live_research_tools")

    trainer = OfflineTrainer(live_tool_guard=guard)
    with pytest.raises(RuntimeError):
        trainer.train([])
    model = OfflineTrainer().train(
        [{"route": "fan_out", "expert_verdict": "good", "request_features": {"lane_count": 4}}]
    )
    assert model.trained_on == 1


def test_shadow_mode_logs_proposal() -> None:
    model = OfflineTrainer().train(
        [
            {
                "route": "fan_out",
                "expert_verdict": "good",
                "request_features": {"lane_count": 5, "complexity": "high"},
            }
        ]
    )
    shadow = ShadowRouter(model)
    shadow.execute({"lane_count": 5, "complexity": "high", "budget_profile": "M"})
    assert shadow.shadow_log[0]["proposed_route"]


def test_learned_router_cannot_self_activate() -> None:
    reg = LearnedRouterRegistry()
    assert reg.auto_activate_latest()["activated"] is False


def test_router_human_promotion() -> None:
    reg = LearnedRouterRegistry()
    model = OfflineTrainer().train([])
    rec = RouterPromotionRecord("offline-v1", "alice", "routing", "wave2-static-v1", "rf rollback", "now")
    assert reg.promote(model, rec)["promoted"] is True
    assert reg.promote(model, rec, self_activation=True)["promoted"] is False


def test_guardrails_override_adversarial() -> None:
    model = OfflineTrainer().train([])
    out = RoutingGuardrails().route_with_model(
        model, {"lane_count": 9, "adversarial_probe": True, "budget_remaining_usd": 10}
    )
    assert out["route"] == "single_agent"
    assert out["overridden"] is True


def test_static_baseline_frozen() -> None:
    b = StaticRoutingBaseline()
    assert b.FROZEN
    assert b.decide({"lane_count": 5, "complexity": "high"}) == "fan_out"


# --- W6-E Proposals ---


def test_vague_prompt_proposal_invalid() -> None:
    p = ImprovementProposal(
        proposal_id="p1",
        observed_failure="bad",
        evidence_refs=["e1"],
        affected_component="prompt",
        proposed_change={"kind": "vague_prompt_tweak"},
        expected_benefit="better",
        risks=["r"],
        test_cases=["t"],
        rollback_plan="rb",
        failure_ids=["f1"],
    )
    assert "vague_improve_prompt_invalid" in p.validate()


def test_proposal_generator_verified_only(repo_root: Path) -> None:
    failures = json.loads((repo_root / "fixtures" / "wave6_proposal_failures.json").read_text())
    props = ProposalGenerator().from_failures(failures)
    assert len(props) == 1
    assert props[0].failure_ids == ["fail-001"]


def test_no_automatic_merge() -> None:
    wf = ProposalWorkflow()
    p = ProposalGenerator().from_failures(
        [
            {
                "failure_id": "f",
                "verified": True,
                "component": "tool",
                "evidence_refs": ["e"],
                "test_cases": ["t"],
            }
        ]
    )[0]
    assert wf.attempt_auto_merge(p)["merged"] is False


def test_human_merge_and_canary_rollback() -> None:
    wf = ProposalWorkflow()
    p = ProposalGenerator().from_failures(
        [
            {
                "failure_id": "f2",
                "verified": True,
                "component": "verifier",
                "evidence_refs": ["e"],
                "test_cases": ["t"],
            }
        ]
    )[0]
    approval = MergeApproval("f2", "bob", True, True, True, True, "sig")
    assert wf.human_merge(p, approval)["merged"] is True
    canary = CanaryController()
    canary.activate("f2", "v2")
    assert canary.rollback("f2", "v1")["ok"] is True


def test_proposal_replay_bundle() -> None:
    def run(case: dict, cfg: dict) -> dict:
        return {"passed": cfg.get("patched"), "case": case["id"]}

    replay = ProposalReplay(run)
    bundle = replay.replay("p", [{"id": "c1"}], baseline_config={}, proposed_config={"patched": True})
    assert len(bundle.baseline_results) == 1


def test_changelog_reconstruct() -> None:
    from research_forge.wave6.proposals.changelog import ChangelogEntry

    log = ProposalChangelog()
    log.record(ChangelogEntry("p1", "approved", "alice", "tests green", ["t1"], "v2"))
    assert len(log.reconstruct("p1")) == 1


# --- W6-F Maintain ---


def test_source_policy_disables_expired() -> None:
    out = SourcePolicyReviewer().review_adapters(
        [{"adapter_id": "a1", "license_expires": "2020-01-01T00:00:00+00:00", "schema_version": "1", "required_schema_version": "1"}]
    )
    assert "a1" in out["disabled"]


def test_model_revalidation_tiers() -> None:
    out = ModelRevalidator().revalidate({"extractor": "mock/mid"})
    assert out["evidence_based"] is True
    assert "extractor" in out["tier_mapping"]


def test_drift_alerts_configured() -> None:
    alerts = DriftMonitor().evaluate({"unsupported_claim_rate": 0.2})
    assert alerts


def test_adversarial_fixture_after_escape() -> None:
    reg = AdversarialFixtureRegistry()
    assert reg.add_escape({"failure_id": "e1", "pattern": "fake-doi"}, reviewed=True)["added"]
    assert reg.detects("fake-doi")


def test_disaster_recovery_replay(tmp_path: Path, repo_root: Path) -> None:
    dr = DisasterRecovery()
    bundle = dr.export_bundle(repo_root, tmp_path / "bundle.json")
    bundle["components"]["config"] = []
    bundle["components"]["ledger"] = []
    bundle["components"]["registries"] = []
    bundle["components"]["prompts"] = []
    bundle["components"]["schemas"] = []
    bundle["components"]["adapters"] = []
    assert dr.restore_and_replay(bundle, "abc")["replay_match"] is True


def test_deprecation_requires_review() -> None:
    out = DeprecationReviewer().review({"usage_30d": 0, "dependents": ["x"], "replay_review_passed": True})
    assert out["decision"] == "retain"
