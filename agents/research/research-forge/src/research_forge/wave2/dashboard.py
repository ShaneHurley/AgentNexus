"""Cost and duplicate dashboards from ledger events (RF-W2-G)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from research_forge.budget.manager import BudgetManager


@dataclass
class DashboardModel:
    run_id: str
    dimensions: dict[str, Any] = field(default_factory=dict)
    duplicate_metrics: dict[str, Any] = field(default_factory=dict)
    yield_metrics: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)


class DashboardBuilder:
    """All metrics derive from ledger events only."""

    def build(self, run_id: str, events: list[dict[str, Any]]) -> DashboardModel:
        run_events = [e for e in events if e.get("run_id") == run_id]
        model = DashboardModel(run_id=run_id)
        model.dimensions = self._dimensions(run_events)
        model.duplicate_metrics = self._duplicate_metrics(run_events)
        model.yield_metrics = self._yield_metrics(run_events)
        model.budget = self._budget_slice(run_events)
        return model

    def _dimensions(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        lanes: set[str] = set()
        roles: set[str] = set()
        adapters: set[str] = set()
        sources: set[str] = set()
        queries: set[str] = set()
        for ev in events:
            p = ev.get("payload", {})
            actor = ev.get("actor", "")
            if actor:
                roles.add(actor)
            if ev["event_type"] == "source_registered":
                sources.add(p.get("source_id", ""))
                lanes.add(p.get("lane_id", ""))
            if ev["event_type"] == "audit":
                lanes.add(p.get("lane_id", ""))
                if p.get("kind") == "lane_claim":
                    roles.add(p.get("owner", ""))
            if ev["event_type"] == "tool_call":
                adapters.add(p.get("adapter_id", ""))
                queries.add(p.get("query", ""))
            if ev["event_type"] == "evidence_added":
                pass
        return {
            "lane_count": len(lanes - {""}),
            "role_count": len(roles),
            "adapter_count": len(adapters - {""}),
            "source_count": len(sources - {""}),
            "query_count": len(queries - {""}),
        }

    def _duplicate_metrics(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        queries: list[str] = []
        source_ids: list[str] = []
        dedupe_hits = 0
        derivative = 0
        read_urls: list[str] = []
        for ev in events:
            p = ev.get("payload", {})
            if ev["event_type"] == "tool_call" and p.get("query"):
                queries.append(p["query"])
            if ev["event_type"] == "source_registered":
                source_ids.append(p.get("source_id", ""))
            if ev["event_type"] == "audit" and p.get("kind") == "candidate_dedupe":
                dedupe_hits += 1
            if ev["event_type"] == "audit" and p.get("kind") == "derivative_cluster":
                derivative += 1
            if ev["event_type"] == "tool_call" and p.get("tool") == "reader":
                read_urls.append(p.get("url", ""))

        q_total = len(queries) or 1
        s_total = len(source_ids) or 1
        r_total = len(read_urls) or 1
        dup_q = q_total - len(set(queries))
        dup_s = dedupe_hits
        repeated_reads = r_total - len(set(read_urls))

        return {
            "duplicate_query_rate": {"numerator": dup_q, "denominator": q_total},
            "duplicate_source_rate": {"numerator": dup_s, "denominator": s_total},
            "repeated_read_rate": {"numerator": repeated_reads, "denominator": r_total},
            "derivative_evidence_rate": {
                "numerator": derivative,
                "denominator": max(len(source_ids), 1),
            },
        }

    def _yield_metrics(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        by_lane: dict[str, dict[str, int]] = defaultdict(
            lambda: {"findings": 0, "contradictions": 0, "useful_sources": 0, "calls": 0}
        )
        verified = 0
        for ev in events:
            p = ev.get("payload", {})
            lane = p.get("lane_id", "unknown")
            if ev["event_type"] == "evidence_added":
                verified += 1
                by_lane[lane]["findings"] += 1
            if ev["event_type"] == "source_registered":
                by_lane[lane]["useful_sources"] += 1
            if ev["event_type"] == "tool_call":
                by_lane[lane]["calls"] += 1
            if ev["event_type"] == "audit" and p.get("kind") == "contradiction_found":
                by_lane[lane]["contradictions"] += 1
        zero_yield = [lid for lid, m in by_lane.items() if m["useful_sources"] == 0 and m["calls"] > 0]
        return {
            "verified_findings": verified,
            "lane_yield": dict(by_lane),
            "zero_yield_lanes": zero_yield,
        }

    def _budget_slice(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        spent = 0.0
        denials = 0
        debits: list[float] = []
        for ev in events:
            if ev["event_type"] == "budget_debit":
                amt = float(ev["payload"].get("amount_usd", 0))
                spent += amt
                debits.append(amt)
            if ev["event_type"] == "audit" and ev["payload"].get("kind") == "budget_denial":
                denials += 1
        return {
            "spent_usd": round(spent, 6),
            "debit_count": len(debits),
            "overspend_denials": denials,
            "forecast_usd": round(spent * 1.1, 6) if debits else 0.0,
        }

    def export_budget_report(
        self,
        manager: BudgetManager,
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        dash = self._budget_slice(events)
        st = manager.state
        if not st:
            return dash
        dash["reconciled"] = {
            "manager_spent": st.spent_usd,
            "ledger_spent": dash["spent_usd"],
            "match": abs(st.spent_usd - dash["spent_usd"]) < 1e-6,
            "limit_usd": st.limit_usd,
            "reserve_usd": st.reserved_usd,
            "threshold": manager.threshold_status(),
        }
        return dash
