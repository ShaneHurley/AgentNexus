"""Charter Planner — freeze immutable charter (RF-W1-C)."""

from __future__ import annotations

import json
from typing import Any

from research_forge.hashing.content import hash_normalized_text
from research_forge.schemas_pkg.registry import SchemaRegistry
from research_forge.wave1.interfaces import WAVE1_INTERFACE_VERSION, WAVE1_ROLE_CONTRACTS, assert_conforms

PROFILE_ORDER = ("S", "M", "L", "XL")


class CharterPlanner:
    role_id = "charter_planner"
    interface_version = WAVE1_INTERFACE_VERSION

    def __init__(self, registry: SchemaRegistry) -> None:
        assert_conforms(self, WAVE1_ROLE_CONTRACTS["charter_planner"])
        self._registry = registry

    def build_plan(self, request: dict[str, Any]) -> dict[str, Any]:
        questions = request.get("specific_questions") or []
        rq_ids = [f"RQ-{i+1:03d}" for i in range(max(1, len(questions)))]
        if not questions:
            questions = [f"Answer: {request['topic']}"]
            rq_ids = ["RQ-001"]

        plan = {
            "plan_id": f"plan-{hash_normalized_text(request['topic'])[:12].replace('sha256:', '')}",
            "charter_question_map": {rq_ids[i]: [questions[i]] for i in range(len(questions))},
            "source_classes": ["scholarly", "official", "technical"],
            "inclusion_rules": ["peer-reviewed or primary where available"],
            "exclusion_rules": list(request.get("exclusions") or []),
            "recency": request.get("recency_requirement") or "last 5 years unless historical",
            "initial_queries": [request["topic"], *questions[:2]],
            "negative_evidence_lane": {
                "lane_id": "NEG-001",
                "query_templates": [
                    f"limitations {request['topic']}",
                    f"failed replication {request['topic']}",
                ],
            },
            "budget_profile": self._assign_profile(request),
            "budget_profile_reason": "deterministic sizing from depth and question count",
        }
        self._registry.validate("research_plan", plan)
        self._validate_plan_coherence(plan, rq_ids)
        return plan

    def draft_charter(self, request: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
        rq_ids = list(plan["charter_question_map"].keys())
        charter_body = {
            "charter_id": f"chr-{hash_normalized_text(request.get('objective') or request['topic'])[:12].replace('sha256:', '')}",
            "version": 1,
            "objective": request.get("objective") or request["topic"],
            "intended_use": request.get("intended_decision_or_use") or "general research",
            "scope": request.get("topic", ""),
            "non_goals": list(request.get("exclusions") or ["implementation execution"]),
            "research_questions": rq_ids,
            "constraints": list(request.get("source_constraints") or []),
            "assumptions": ["Mock-first Wave 1; access levels honored."],
            "access_rules": ["read-only discovery", "no credential URLs in queries"],
            "recency": plan["recency"],
            "audience": request.get("audience") or "researcher",
            "depth": request.get("desired_depth") or "standard",
            "output_contract": request.get("required_output") or "brief",
            "charter_hash": "sha256:pending",
        }
        charter_body["charter_hash"] = self._charter_hash(charter_body)
        self._registry.validate("research_charter", charter_body)
        return charter_body

    def freeze_charter(self, charter: dict[str, Any]) -> dict[str, Any]:
        frozen = dict(charter)
        if frozen.get("charter_hash") == "sha256:pending":
            frozen["charter_hash"] = self._charter_hash(frozen)
        self._registry.validate("research_charter", frozen)
        return frozen

    def _charter_hash(self, charter: dict[str, Any]) -> str:
        payload = {k: v for k, v in charter.items() if k != "charter_hash"}
        return hash_normalized_text(json.dumps(payload, sort_keys=True))

    def _assign_profile(self, request: dict[str, Any]) -> str:
        user = request.get("budget_profile")
        if user in PROFILE_ORDER:
            return user
        depth = request.get("desired_depth") or "standard"
        mapping = {"quick": "S", "standard": "S", "deep": "M", "thesis": "L"}
        return mapping.get(depth, "S")

    def _validate_plan_coherence(self, plan: dict[str, Any], rq_ids: list[str]) -> None:
        if not plan.get("negative_evidence_lane", {}).get("query_templates"):
            raise ValueError("missing negative evidence lane")
        for rq in rq_ids:
            if rq not in plan["charter_question_map"]:
                raise ValueError(f"lane missing charter question map for {rq}")
        user_max = plan.get("budget_profile")
        if user_max and user_max not in PROFILE_ORDER:
            raise ValueError("invalid budget profile")
