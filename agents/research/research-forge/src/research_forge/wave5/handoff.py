"""Handoff taxonomy — raw vs packet vs brief (RF-W5-C)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


HANDOFF_POLICY_VERSION = "1.0.0"


@dataclass
class HandoffOutcome:
    task_id: str
    stratum: str
    condition: str
    synthesis_quality: float
    unsupported_claims: int
    contradiction_retention: float
    latency_ms: float
    tokens: int
    cost_usd: float
    audit_failures: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "stratum": self.stratum,
            "condition": self.condition,
            "synthesis_quality": self.synthesis_quality,
            "unsupported_claims": self.unsupported_claims,
            "contradiction_retention": self.contradiction_retention,
            "latency_ms": self.latency_ms,
            "tokens": self.tokens,
            "cost_usd": self.cost_usd,
            "audit_failures": self.audit_failures,
        }


@dataclass
class HandoffPolicy:
    version: str = HANDOFF_POLICY_VERSION
    rules: dict[str, str] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"version": self.version, "rules": self.rules, "confidence": self.confidence}


class HandoffTaxonomy:
    CONDITIONS = ("raw_trajectory", "director_packet", "minimal_brief")

    def __init__(self, tasks: list[dict[str, Any]] | None = None) -> None:
        self.tasks = tasks or []

    def _mock_run(self, task: dict[str, Any], condition: str) -> HandoffOutcome:
        base = task.get("expectations", {})
        q = float(base.get("quality", 0.7))
        if condition == "director_packet":
            q += float(base.get("packet_boost", 0.08))
        if condition == "raw_trajectory":
            q -= float(base.get("raw_penalty", 0.05))
        unsupported = int(base.get("unsupported_claims", {}).get(condition, 0))
        ctr = float(base.get("contradiction_retention", {}).get(condition, 1.0))
        return HandoffOutcome(
            task_id=task["task_id"],
            stratum=task["stratum"],
            condition=condition,
            synthesis_quality=max(0.0, min(1.0, q)),
            unsupported_claims=unsupported,
            contradiction_retention=ctr,
            latency_ms=float(base.get("latency_ms", {}).get(condition, 1000)),
            tokens=int(base.get("tokens", {}).get(condition, 5000)),
            cost_usd=float(base.get("cost_usd", {}).get(condition, 0.5)),
            audit_failures=int(base.get("audit_failures", {}).get(condition, 0)),
        )

    def run_matched_comparison(self, task: dict[str, Any]) -> list[HandoffOutcome]:
        return [self._mock_run(task, c) for c in self.CONDITIONS]

    def select_policy(self, outcomes: list[HandoffOutcome]) -> HandoffPolicy:
        by_stratum: dict[str, list[HandoffOutcome]] = {}
        for o in outcomes:
            by_stratum.setdefault(o.stratum, []).append(o)
        rules: dict[str, str] = {}
        confidence: dict[str, float] = {}
        for stratum, rows in by_stratum.items():
            best = max(
                rows,
                key=lambda r: (r.synthesis_quality - 0.2 * r.unsupported_claims, -r.cost_usd),
            )
            rules[stratum] = best.condition
            spread = max(r.synthesis_quality for r in rows) - min(r.synthesis_quality for r in rows)
            confidence[stratum] = round(min(0.99, 0.5 + spread), 3)
        return HandoffPolicy(rules=rules, confidence=confidence)

    def regression_fingerprint(self, outcomes: list[HandoffOutcome]) -> str:
        payload = json.dumps([o.to_dict() for o in outcomes], sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def regression_check(self, baseline_fp: str, outcomes: list[HandoffOutcome]) -> dict[str, Any]:
        current = self.regression_fingerprint(outcomes)
        return {"baseline": baseline_fp, "current": current, "passed": baseline_fp == current}
