"""Skill routing with logged rationale (RF-W6-C-07)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_forge.wave6.skills.builtin import ALL_SKILLS


@dataclass
class SkillRoutingDecision:
    request_type: str
    selected: list[str]
    rationale: str
    conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_type": self.request_type,
            "selected": self.selected,
            "rationale": self.rationale,
            "conflicts": self.conflicts,
        }


class SkillRouter:
    def __init__(self, skills: dict[str, Any] | None = None) -> None:
        self.skills = skills or ALL_SKILLS
        self.log: list[dict[str, Any]] = []

    def route(self, request: dict[str, Any]) -> SkillRoutingDecision:
        req_type = request.get("request_type", "")
        applicable = [s.name for s in self.skills.values() if req_type in s.request_types]
        conflicts: list[str] = []
        if len(applicable) > 1 and req_type == "experiment_plan":
            conflicts = applicable
        if not applicable:
            decision = SkillRoutingDecision(req_type, [], "no_applicable_skill")
        elif len(applicable) == 1:
            decision = SkillRoutingDecision(req_type, applicable, f"single_match:{applicable[0]}")
        elif conflicts:
            decision = SkillRoutingDecision(
                req_type, [], "conflicting_skills", conflicts=conflicts
            )
        else:
            decision = SkillRoutingDecision(
                req_type, [applicable[0]], f"priority_order:{applicable[0]}"
            )
        self.log.append(decision.to_dict())
        return decision
