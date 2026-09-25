"""Intake Clarifier — deterministic mock-first (RF-W1-B)."""

from __future__ import annotations

import re
from typing import Any

from research_forge.schemas_pkg.registry import SchemaRegistry
from research_forge.wave1.interfaces import WAVE1_INTERFACE_VERSION, WAVE1_ROLE_CONTRACTS, assert_conforms


class IntakeClarifier:
    role_id = "intake_clarifier"
    interface_version = WAVE1_INTERFACE_VERSION

    def __init__(self, registry: SchemaRegistry) -> None:
        assert_conforms(self, WAVE1_ROLE_CONTRACTS["intake_clarifier"])
        self._registry = registry

    @staticmethod
    def _schema_request(request: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in request.items() if not str(k).startswith("_")}

    def evaluate_completeness(self, request: dict[str, Any]) -> tuple[bool, list[str]]:
        self._registry.validate("research_request", self._schema_request(request))
        missing: list[str] = []
        topic = (request.get("topic") or "").strip()
        if not topic:
            missing.append("topic")
        if len(topic) < 3:
            missing.append("topic_too_short")
        return len(missing) == 0, missing

    def score_ambiguity(self, request: dict[str, Any]) -> float:
        """Material ambiguity: missing choices that change scope/evidence/risk/output."""
        score = 0.0
        topic = (request.get("topic") or "").lower()
        if not request.get("objective") and not request.get("intended_decision_or_use"):
            score += 0.35
        if not request.get("required_output"):
            score += 0.2
        if not request.get("desired_depth"):
            score += 0.15
        if re.search(r"\b(vs|versus|compare|either|or)\b", topic) and not request.get(
            "specific_questions"
        ):
            score += 0.4
        if request.get("domain") in ("medical", "legal", "financial") and not request.get(
            "intended_decision_or_use"
        ):
            score += 0.3
        return min(1.0, score)

    def clarify(self, request: dict[str, Any]) -> dict[str, Any]:
        ok, missing = self.evaluate_completeness(request)
        if not ok:
            raise ValueError(f"invalid request before clarify: {missing}")

        ambiguity = self.score_ambiguity(request)
        if ambiguity >= 0.5:
            result: dict[str, Any] = {
                "result_type": "questions",
                "confidence": "MEDIUM" if ambiguity < 0.75 else "LOW",
                "ambiguity_score": ambiguity,
                "questions": self._build_questions(request),
            }
        else:
            result = {
                "result_type": "ready",
                "confidence": "HIGH" if ambiguity < 0.25 else "MEDIUM",
                "ambiguity_score": ambiguity,
                "interpreted_objective": request.get("objective") or request["topic"],
                "non_goals": list(request.get("exclusions") or []),
                "assumptions": self._default_assumptions(request),
            }
        self._registry.validate("clarification_result", result)
        return result

    def _build_questions(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        questions: list[dict[str, Any]] = []
        if not request.get("intended_decision_or_use"):
            questions.append(
                {
                    "question_id": "CLQ-001",
                    "text": "What decision or use will this research support?",
                    "options": [
                        "Internal planning only",
                        "External publication or briefing",
                        "Product or architecture decision",
                    ],
                    "rationale": "Intended use changes evidence bar and scope.",
                }
            )
        if not request.get("required_output"):
            questions.append(
                {
                    "question_id": "CLQ-002",
                    "text": "Which output format do you need?",
                    "options": ["brief", "literature_review", "decision_report"],
                    "rationale": "Output contract drives depth and structure.",
                }
            )
        topic = (request.get("topic") or "").lower()
        if re.search(r"\b(vs|versus|compare)\b", topic):
            questions.append(
                {
                    "question_id": "CLQ-003",
                    "text": "Which comparison dimensions matter most?",
                    "options": [" efficacy", "cost", "risk", "implementation effort"],
                    "rationale": "Comparison scope affects search and charter questions.",
                }
            )
        return questions[:3]

    def _default_assumptions(self, request: dict[str, Any]) -> list[str]:
        assumptions = ["Public sources unless seed_sources provided."]
        if request.get("recency_requirement"):
            assumptions.append(f"Recency: {request['recency_requirement']}")
        return assumptions

    def merge_clarification(
        self,
        original: dict[str, Any],
        answers: dict[str, str],
    ) -> dict[str, Any]:
        merged = dict(original)
        merged["_clarification_provenance"] = {
            "original_request": dict(original),
            "answers": dict(answers),
        }
        for qid, answer in answers.items():
            if qid == "CLQ-001":
                merged["intended_decision_or_use"] = answer
            elif qid == "CLQ-002":
                merged["required_output"] = answer.strip().lower()
            elif qid == "CLQ-003":
                merged.setdefault("specific_questions", [])
                merged["specific_questions"] = list(merged["specific_questions"]) + [answer]
        self._registry.validate("research_request", {k: v for k, v in merged.items() if not k.startswith("_")})
        return merged
