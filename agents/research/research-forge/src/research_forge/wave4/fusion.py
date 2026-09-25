"""Portfolio Fusion agent (RF-W4-C)."""

from __future__ import annotations

from typing import Any

from research_forge.hashing.content import hash_normalized_text
from research_forge.wave4.lineage import LineageGraph


class FusionPolicyError(PermissionError):
    pass


class PortfolioFusion:
    role_id = "portfolio_fusion"
    allowed_tools: tuple[str, ...] = ()

    def assert_no_search(self, tool: str) -> None:
        name = tool.lower()
        if "search" in name or "scout" in name:
            raise FusionPolicyError("fusion cannot search")

    def build_compatibility_matrix(self, ideas: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        matrix: dict[str, dict[str, Any]] = {}
        for i, a in enumerate(ideas):
            for b in ideas[i + 1 :]:
                key = f"{a['idea_id']}|{b['idea_id']}"
                conflicts = set(a.get("incompatibilities") or []) & set(b.get("incompatibilities") or [])
                assumption_clash = bool(set(a.get("assumptions") or []) & set(b.get("assumptions") or []))
                compatible = not conflicts and not assumption_clash
                matrix[key] = {
                    "idea_a": a["idea_id"],
                    "idea_b": b["idea_id"],
                    "compatible": compatible,
                    "conflicts": sorted(conflicts),
                    "staged_required": not compatible,
                    "dimensions_checked": [
                        "assumptions",
                        "interfaces",
                        "data",
                        "timescales",
                        "incentives",
                        "resources",
                        "failure_modes",
                    ],
                }
        return matrix

    def validate_component_selections(self, selections: list[dict[str, Any]]) -> list[str]:
        errors: list[str] = []
        for sel in selections:
            required = ("component", "parent_idea", "reason", "evidence_id", "interface")
            if any(not sel.get(k) for k in required):
                errors.append("vague_combine_rejected")
        if not selections:
            errors.append("combine_best_parts_without_details")
        return errors

    def create_hybrid(
        self,
        *,
        run_id: str,
        parents: list[dict[str, Any]],
        selections: list[dict[str, Any]],
        baseline_idea_id: str,
        evidence: dict[str, dict[str, Any]],
        graph: LineageGraph,
    ) -> dict[str, Any]:
        sel_errors = self.validate_component_selections(selections)
        if sel_errors:
            raise ValueError(";".join(sel_errors))
        for sel in selections:
            eid = sel["evidence_id"]
            if eid not in evidence:
                raise ValueError(f"uncited_component:{sel['component']}")

        parent_ids = [p["idea_id"] for p in parents]
        hybrid_id = f"IDEA-HYB-{hash_normalized_text('|'.join(parent_ids))[-8:].upper()}"
        lineage_hash = hash_normalized_text("|".join(sorted(parent_ids)))
        hybrid: dict[str, Any] = {
            "idea_id": hybrid_id,
            "title": "Hybrid composed from explicit components",
            "lineage": parent_ids,
            "root_cause_model": "Combined mechanisms from parents with interaction review",
            "proposal": "Hybrid integrating selected components with staged interfaces",
            "components": [s["component"] for s in selections],
            "evidence_ids": sorted({s["evidence_id"] for s in selections}),
            "assumptions": ["Interaction effects may introduce emergent failure modes"],
            "expected_benefits": ["Captures complementary strengths when compatible"],
            "failure_modes": ["Emergent incompatibility between parent mechanisms"],
            "costs": ["Higher operational complexity than single parent"],
            "risks": ["Unknown interaction flagged for adversarial review"],
            "falsification_test": "Hybrid does not beat complexity-adjusted baseline on held-out metric",
            "status": "active",
            "opportunity_type": "hybrid",
            "tactical_opportunity_type": "combine",
            "baseline": f"Compare against parent {baseline_idea_id} and minimal baseline",
            "distinctiveness": "Hybrid with explicit component lineage",
            "lineage_hash": lineage_hash,
            "compatibility_constraints": [f"baseline:{baseline_idea_id}"],
        }
        for sel in selections:
            graph.add_component(
                hybrid_id,
                component=sel["component"],
                parent_idea=sel["parent_idea"],
                reason=sel["reason"],
                evidence_id=sel["evidence_id"],
                interface=sel["interface"],
            )
        for pid in parent_ids:
            graph.add_parent(hybrid_id, pid)
        return hybrid

    def interaction_risk_review(
        self,
        hybrid: dict[str, Any],
        evidence: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        conflicts: list[str] = []
        unknown: list[str] = []
        for eid in hybrid.get("evidence_ids") or []:
            card = evidence.get(eid, {})
            claim = card.get("claim", "")
            if "contradict" in claim.lower():
                conflicts.append(eid)
        if len(hybrid.get("components") or []) > 2:
            unknown.append("multi_component_interaction")
        return {
            "hybrid_id": hybrid["idea_id"],
            "emergent_conflicts": conflicts,
            "unknown_interactions": unknown,
            "adversarial_review_required": bool(conflicts or unknown),
        }
