"""Fabrication and template-default checks (RF-W4-E)."""

from __future__ import annotations

import re
from typing import Any

from research_forge.wave4.diversity import DiversityChecker
from research_forge.wave4.duplicates import NearDuplicateDetector
from research_forge.wave4.types import TEMPLATE_DEFAULT_MARKERS

_NOVELTY = re.compile(r"\b(first|novel|unique|never been done)\b", re.I)


class FabricationChecker:
    def __init__(self) -> None:
        self._dupes = NearDuplicateDetector()
        self._diversity = DiversityChecker()

    def verify_source_ids(
        self,
        idea: dict[str, Any],
        evidence_index: dict[str, dict[str, Any]],
    ) -> list[str]:
        errors: list[str] = []
        for eid in idea.get("evidence_ids") or []:
            if eid not in evidence_index:
                errors.append(f"invented_source:{eid}")
            elif evidence_index[eid].get("verifier_status") == "failed":
                errors.append(f"failed_evidence:{eid}")
        return errors

    def check_unsupported_novelty(self, idea: dict[str, Any]) -> list[str]:
        text = " ".join(
            [
                idea.get("proposal", ""),
                idea.get("distinctiveness", ""),
                idea.get("novelty_check", "") or "",
            ]
        )
        if _NOVELTY.search(text) and not idea.get("novelty_check"):
            return ["unsupported_novelty_language"]
        return []

    def check_template_defaults(self, idea: dict[str, Any]) -> list[str]:
        blob = (idea.get("proposal", "") + " " + " ".join(idea.get("components") or [])).lower()
        hits = [m for m in TEMPLATE_DEFAULT_MARKERS if m in blob]
        if not hits:
            return []
        if idea.get("root_cause_model") and idea.get("falsification_test"):
            return []  # mechanism + test established
        return [f"template_default:{h}" for h in hits]

    def check_false_diversity(self, ideas: list[dict[str, Any]], min_distinct: int = 3) -> dict[str, Any]:
        clusters = self._dupes.cluster(ideas)
        distinct_count = len(ideas) - sum(len(c) - 1 for c in clusters)
        return {
            "distinct_count": distinct_count,
            "required_min": min_distinct,
            "clusters": clusters,
            "passed": distinct_count >= min_distinct,
        }

    def check_complexity_inflation(self, idea: dict[str, Any]) -> dict[str, Any]:
        components = idea.get("components") or []
        simpler = {
            "variant": "removal",
            "description": f"Remove optional components leaving baseline {idea.get('baseline')}",
            "unnecessary": components[1:] if len(components) > 1 else [],
        }
        return {
            "idea_id": idea["idea_id"],
            "component_count": len(components),
            "simpler_baseline": simpler,
        }

    def check_evidence_to_action_leap(self, idea: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        steps = idea.get("recommendation_steps") or []
        for step in steps:
            basis = step.get("basis")
            if basis not in ("evidence", "inference", "assumption"):
                errors.append(f"unsupported_leap:{step.get('step_id', 'unknown')}")
        return errors

    def audit_idea(
        self,
        idea: dict[str, Any],
        evidence_index: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        issues: list[str] = []
        issues.extend(self.verify_source_ids(idea, evidence_index))
        issues.extend(self.check_unsupported_novelty(idea))
        issues.extend(self.check_template_defaults(idea))
        issues.extend(self.check_evidence_to_action_leap(idea))
        return {"idea_id": idea["idea_id"], "issues": issues, "blocks_promotion": bool(issues)}
