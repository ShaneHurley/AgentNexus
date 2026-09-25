"""Methods and Statistics Reviewer (RF-W3-A)."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from research_forge.wave3.recompute import recompute_expression
from research_forge.wave3.types import METHODS_FIXTURE_KINDS, STUDY_TYPE_CHECKLISTS, StudyType

_CAUSAL_MARKERS = re.compile(r"\b(causes?|led to|proves?|therefore|because of)\b", re.I)
_LEAKAGE_MARKERS = re.compile(
    r"\b(test set leak|data contamination|benchmark overlap|train-test overlap)\b",
    re.I,
)
_WEAK_BASELINE_MARKERS = re.compile(r"\b(weak baseline|straw man|trivial baseline)\b", re.I)


class MethodsPolicyError(PermissionError):
    pass


class MethodsReviewer:
    role_id = "methods_reviewer"
    allowed_tools: tuple[str, ...] = ("recompute_sandbox",)

    def should_activate(
        self,
        source: dict[str, Any],
        evidence_cards: list[dict[str, Any]],
        *,
        high_risk_domain: bool = False,
    ) -> bool:
        if source.get("source_class") == "documentation" and not evidence_cards:
            return False
        if high_risk_domain:
            return True
        if source.get("load_bearing") or source.get("triage_status") in (
            "DEEP_READ",
            "FOLLOW_CITATIONS",
        ):
            return True
        for card in evidence_cards:
            if card.get("is_material_numerical"):
                return True
            if card.get("methods_fixture_kind"):
                return True
        return False

    def infer_study_types(self, source: dict[str, Any], cards: list[dict[str, Any]]) -> list[str]:
        explicit = source.get("study_types") or []
        if explicit:
            return [str(s).lower() for s in explicit]
        text = " ".join(
            [source.get("title", ""), source.get("abstract", "")]
            + [c.get("method", "") or "" for c in cards]
        ).lower()
        found: list[str] = []
        if "randomized" in text or "rct" in text:
            found.append(StudyType.EXPERIMENTAL.value)
        if "benchmark" in text or "leaderboard" in text:
            found.append(StudyType.BENCHMARK.value)
        if "survey" in text or "questionnaire" in text:
            found.append(StudyType.SURVEY.value)
        if "simulation" in text or "synthetic" in text:
            found.append(StudyType.SIMULATION.value)
        if source.get("source_class") == "documentation":
            found.append(StudyType.DOCUMENTATION.value)
        if not found:
            found.append(StudyType.OBSERVATIONAL.value)
        return found

    def review(
        self,
        source: dict[str, Any],
        evidence_cards: list[dict[str, Any]],
        *,
        high_risk_domain: bool = False,
        recompute_jobs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not self.should_activate(source, evidence_cards, high_risk_domain=high_risk_domain):
            return {
                "review_id": self._review_id(source),
                "source_id": source.get("source_id", ""),
                "activated": False,
                "study_types": [StudyType.DOCUMENTATION.value],
                "checklists": {},
                "limitations": [],
                "flags": [],
                "eligibility_downgrade": False,
                "recomputations": [],
            }

        study_types = self.infer_study_types(source, evidence_cards)
        checklists = {
            st: list(STUDY_TYPE_CHECKLISTS.get(st, ()))
            for st in study_types
            if st in STUDY_TYPE_CHECKLISTS
        }
        flags: list[dict[str, Any]] = []
        limitations: list[str] = []

        comparability = self._review_comparability(source, evidence_cards)
        if comparability.get("cross_metric_comparison"):
            flags.append(
                {
                    "kind": "cross_metric_comparison",
                    "severity": "major",
                    "detail": comparability["detail"],
                }
            )

        stat_limits = self._review_statistical_support(evidence_cards)
        limitations.extend(stat_limits)

        leakage = self._review_leakage_and_selection(source, evidence_cards)
        flags.extend(leakage["flags"])
        eligibility_downgrade = leakage["eligibility_downgrade"]

        transfer = self._review_external_validity(source, evidence_cards)
        limitations.extend(transfer)

        fixture_hits = self._detect_methods_fixtures(source, evidence_cards)
        for kind in fixture_hits:
            flags.append({"kind": kind, "severity": "major", "detail": f"fixture:{kind}"})

        recomputations: list[dict[str, Any]] = []
        for job in recompute_jobs or []:
            recomputations.append(recompute_expression(job["expression"], job["inputs"]))

        return {
            "review_id": self._review_id(source),
            "source_id": source.get("source_id", ""),
            "activated": True,
            "study_types": study_types,
            "checklists": checklists,
            "comparability": comparability,
            "limitations": sorted(set(limitations)),
            "flags": flags,
            "eligibility_downgrade": eligibility_downgrade,
            "transfer_conditions": source.get("transfer_conditions") or [],
            "recomputations": recomputations,
        }

    def _review_id(self, source: dict[str, Any]) -> str:
        sid = source.get("source_id", "unknown")
        return f"MRV-{hashlib.sha256(sid.encode()).hexdigest()[:10]}"

    def _review_comparability(
        self, source: dict[str, Any], cards: list[dict[str, Any]]
    ) -> dict[str, Any]:
        metrics = {c.get("result", "") for c in cards if c.get("result")}
        harness = source.get("harness_version")
        dataset = source.get("dataset_version")
        cross = len(metrics) > 1 and not harness
        detail = ""
        if cross:
            detail = "Multiple metrics/results without pinned harness/dataset"
        if source.get("cross_metric_comparison"):
            cross = True
            detail = source.get("cross_metric_detail") or detail
        return {
            "controls_compatible": source.get("controls_compatible", True),
            "dataset_pinned": bool(dataset),
            "harness_pinned": bool(harness),
            "cross_metric_comparison": cross,
            "detail": detail,
        }

    def _review_statistical_support(self, cards: list[dict[str, Any]]) -> list[str]:
        limits: list[str] = []
        for card in cards:
            if not card.get("is_material_numerical"):
                continue
            if not card.get("units_and_denominator"):
                limits.append(f"{card.get('evidence_id')}: missing denominator/units")
            if not card.get("uncertainty"):
                limits.append(f"{card.get('evidence_id')}: no variance/uncertainty reported")
            if card.get("multiple_comparisons_unadjusted"):
                limits.append(f"{card.get('evidence_id')}: multiple comparisons unadjusted")
        return limits

    def _review_leakage_and_selection(
        self, source: dict[str, Any], cards: list[dict[str, Any]]
    ) -> dict[str, Any]:
        flags: list[dict[str, Any]] = []
        downgrade = False
        blob = " ".join(
            [source.get("abstract", "")]
            + [c.get("claim", "") for c in cards]
            + [lim for c in cards for lim in c.get("limitations", [])]
        )
        if _LEAKAGE_MARKERS.search(blob) or source.get("leakage_risk"):
            flags.append({"kind": "leakage", "severity": "critical", "detail": "leakage risk"})
            downgrade = True
        if source.get("cherry_picked") or source.get("survivorship_bias"):
            flags.append(
                {"kind": "selection_bias", "severity": "major", "detail": "selection bias signal"}
            )
            downgrade = True
        return {"flags": flags, "eligibility_downgrade": downgrade}

    def _review_external_validity(
        self, source: dict[str, Any], cards: list[dict[str, Any]]
    ) -> list[str]:
        if source.get("transfer_conditions"):
            return []
        if any(c.get("transfer_conditions") for c in cards):
            return []
        if source.get("source_class") == "documentation":
            return []
        return ["transfer_conditions_not_explicit"]

    def _detect_methods_fixtures(
        self, source: dict[str, Any], cards: list[dict[str, Any]]
    ) -> list[str]:
        hits: list[str] = []
        for card in cards:
            kind = card.get("methods_fixture_kind")
            if kind in METHODS_FIXTURE_KINDS:
                hits.append(kind)
                continue
            claim = card.get("claim", "")
            if "average" in claim.lower() and not card.get("units_and_denominator"):
                hits.append("misleading_average")
            if card.get("is_material_numerical") and not card.get("units_and_denominator"):
                hits.append("missing_denominator")
            if card.get("is_material_numerical") and not card.get("uncertainty"):
                hits.append("no_variance")
            if _WEAK_BASELINE_MARKERS.search(claim) or card.get("weak_baseline"):
                hits.append("weak_baseline")
            if _LEAKAGE_MARKERS.search(claim) or card.get("leakage_risk"):
                hits.append("leakage")
            if _CAUSAL_MARKERS.search(claim) and source.get("study_types") == ["observational"]:
                hits.append("causal_overclaim")
            if card.get("causal_overclaim"):
                hits.append("causal_overclaim")
        return sorted(set(hits))

    def assert_tool_allowed(self, tool_id: str) -> None:
        if tool_id not in self.allowed_tools and "search" in tool_id:
            raise MethodsPolicyError("Methods reviewer cannot search externally")
