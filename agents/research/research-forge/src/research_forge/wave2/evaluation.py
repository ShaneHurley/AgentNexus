"""Fan-out evaluation, routing, audit (RF-W2-H)."""

from __future__ import annotations

import hashlib
import statistics
from dataclasses import dataclass, field
from typing import Any


COORDINATION_FAILURE_LABELS = (
    "duplicate_work",
    "missed_lane",
    "state_conflict",
    "cancellation_error",
    "context_loss",
)


@dataclass
class MatchedRun:
    mode: str
    task_id: str
    coverage: dict[str, Any]
    quality: dict[str, Any]
    cost_usd: float
    latency_ms: float
    blind_token: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "task_id": self.task_id,
            "coverage": self.coverage,
            "quality": self.quality,
            "cost_usd": self.cost_usd,
            "latency_ms": self.latency_ms,
            "blind_token": self.blind_token,
        }


@dataclass
class ExperimentReport:
    task_id: str
    single_agent: MatchedRun
    fan_out: MatchedRun
    coordination_failures: list[dict[str, Any]] = field(default_factory=list)
    routing_recommendation: str = "single_agent"

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "single_agent": self.single_agent.to_dict(),
            "fan_out": self.fan_out.to_dict(),
            "coordination_failures": self.coordination_failures,
            "routing_recommendation": self.routing_recommendation,
            "distributions": self._distributions(),
        }

    def _distributions(self) -> dict[str, Any]:
        def spread(a: float, b: float) -> dict[str, float]:
            vals = [a, b]
            return {
                "mean": statistics.mean(vals),
                "stdev": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
            }

        return {
            "cost_usd": spread(self.single_agent.cost_usd, self.fan_out.cost_usd),
            "latency_ms": spread(self.single_agent.latency_ms, self.fan_out.latency_ms),
            "independent_evidence": spread(
                float(self.single_agent.coverage.get("independent_evidence", 0)),
                float(self.fan_out.coverage.get("independent_evidence", 0)),
            ),
        }


class FanOutEvaluator:
    def __init__(self, routing_config: dict[str, Any] | None = None) -> None:
        self.routing_config = routing_config or {}

    def blind_assignment(self, task_id: str) -> str:
        h = hashlib.sha256(task_id.encode()).hexdigest()
        return h[:8]

    def run_matched_experiment(
        self,
        task_id: str,
        *,
        single_metrics: dict[str, Any],
        fanout_metrics: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> ExperimentReport:
        single = MatchedRun(
            mode="single_agent",
            task_id=task_id,
            coverage=single_metrics.get("coverage", {}),
            quality=single_metrics.get("quality", {}),
            cost_usd=float(single_metrics.get("cost_usd", 0)),
            latency_ms=float(single_metrics.get("latency_ms", 0)),
            blind_token=self.blind_assignment(task_id),
        )
        fan = MatchedRun(
            mode="fan_out",
            task_id=task_id,
            coverage=fanout_metrics.get("coverage", {}),
            quality=fanout_metrics.get("quality", {}),
            cost_usd=float(fanout_metrics.get("cost_usd", 0)),
            latency_ms=float(fanout_metrics.get("latency_ms", 0)),
            blind_token=self.blind_assignment(task_id + ":fan"),
        )
        failures = self.inspect_coordination_failures(events)
        route = self.routing_rule(task_id, single, fan, failures)
        return ExperimentReport(
            task_id=task_id,
            single_agent=single,
            fan_out=fan,
            coordination_failures=failures,
            routing_recommendation=route,
        )

    def inspect_coordination_failures(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        failures: list[dict[str, Any]] = []
        owners: dict[str, str] = {}
        for ev in events:
            p = ev.get("payload", {})
            if ev.get("event_type") == "audit" and p.get("kind") == "lane_claim":
                lid = p.get("lane_id")
                if lid in owners and owners[lid] != p.get("owner"):
                    failures.append(
                        {"label": "state_conflict", "lane_id": lid, "detail": "dual owner"}
                    )
                owners[lid] = p.get("owner", "")
            if ev.get("event_type") == "audit" and p.get("kind") == "candidate_dedupe":
                failures.append(
                    {"label": "duplicate_work", "source_id": p.get("source_id"), "detail": "dedupe"}
                )
            if ev.get("event_type") == "audit" and p.get("kind") == "lane_canceled":
                if p.get("preserved_source_count", 0) < 0:
                    failures.append(
                        {"label": "cancellation_error", "lane_id": p.get("lane_id")}
                    )
            if ev.get("event_type") == "audit" and p.get("kind") == "context_loss":
                failures.append({"label": "context_loss", "detail": p.get("detail")})
        for ev in events:
            p = ev.get("payload", {})
            if ev.get("event_type") == "audit" and p.get("kind") == "missed_lane":
                failures.append({"label": "missed_lane", "lane_id": p.get("lane_id")})
        return failures

    def routing_rule(
        self,
        task_id: str,
        single: MatchedRun,
        fan: MatchedRun,
        failures: list[dict[str, Any]],
    ) -> str:
        cfg = self.routing_config
        min_questions = int(cfg.get("fanout_min_questions", 2))
        questions = int(fan.coverage.get("research_questions", 1))
        if questions <= int(cfg.get("trivial_max_questions", 1)):
            return "single_agent"
        if questions < min_questions:
            return "single_agent"
        critical = [f for f in failures if f["label"] in ("state_conflict", "context_loss")]
        if critical:
            return "single_agent"
        fan_cov = float(fan.coverage.get("source_class_coverage", 0))
        single_cov = float(single.coverage.get("source_class_coverage", 0))
        if fan_cov > single_cov and fan.cost_usd <= single.cost_usd * 1.25:
            return "fan_out"
        if fan.quality.get("citation_accuracy", 0) >= single.quality.get("citation_accuracy", 0):
            if fan_cov >= single_cov:
                return "fan_out"
        return "single_agent"

    def wave2_audit(self, events: list[dict[str, Any]], *, budget_ok: bool) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        for ev in events:
            if ev.get("event_type") == "tool_call":
                caps = ev.get("payload", {}).get("capabilities", {})
                if caps.get("write"):
                    findings.append(
                        {"severity": "critical", "code": "mutating_tool", "event": ev.get("sequence")}
                    )
        stop_ok = any(
            ev.get("payload", {}).get("stopped_reason")
            for ev in events
            if ev.get("event_type") == "audit" and ev.get("payload", {}).get("kind") == "scout_complete"
        )
        if not budget_ok:
            findings.append({"severity": "major", "code": "budget_divergence"})
        return {
            "critical_open": [f for f in findings if f["severity"] == "critical"],
            "stop_rules_observed": stop_ok,
            "read_only_ok": not any(f["code"] == "mutating_tool" for f in findings),
            "findings": findings,
        }
