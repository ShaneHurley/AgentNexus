"""Fan-out scheduler — lanes, limits, fan-in (RF-W2-C)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

from research_forge.registries.normalize import canonical_key, normalize_url
from research_forge.wave2.landscape import _jaccard, _tokenize
from research_forge.wave2.scout import ScoutLaneContract, SourceScout
from research_forge.wave2.types import FanInSnapshot, LaneState, ResearchLane, SchedulerLimits


class DuplicateLaneOwnershipError(ValueError):
    pass


class FanOutScheduler:
    def __init__(
        self,
        limits: SchedulerLimits,
        scout: SourceScout,
        *,
        ledger_events: list[dict[str, Any]] | None = None,
    ) -> None:
        self.limits = limits
        self.scout = scout
        self.events: list[dict[str, Any]] = list(ledger_events or [])
        self.lanes: dict[str, ResearchLane] = {}
        self.ownership: dict[str, str] = {}
        self.domain_calls: dict[str, int] = defaultdict(int)
        self.adapter_calls: dict[str, int] = defaultdict(int)
        self.registered_sources: dict[str, dict[str, Any]] = {}
        self.canceled_lanes: dict[str, dict[str, Any]] = {}

    def load_lanes(self, lanes: list[ResearchLane]) -> list[dict[str, Any]]:
        merged: list[ResearchLane] = []
        reports: list[dict[str, Any]] = []
        for lane in lanes:
            pre = self.non_overlap_precheck(lane, merged)
            reports.append(pre)
            if pre.get("action") == "merge":
                continue
            merged.append(lane)
        for lane in merged:
            self.lanes[lane.lane_id] = lane
        return reports

    def claim_lane(self, lane_id: str, owner: str, run_id: str) -> dict[str, Any]:
        if lane_id in self.ownership and self.ownership[lane_id] != owner:
            raise DuplicateLaneOwnershipError(
                f"Lane {lane_id} owned by {self.ownership[lane_id]}, not {owner}"
            )
        self.ownership[lane_id] = owner
        lane = self.lanes.get(lane_id)
        if lane:
            lane.owner = owner
            lane.state = LaneState.ACTIVE
        ev = self._audit(
            run_id,
            "lane_claim",
            {"lane_id": lane_id, "owner": owner, "namespace": f"ns/{lane_id}"},
        )
        dup = self.detect_duplicate_ownership(run_id)
        if dup:
            raise DuplicateLaneOwnershipError(dup)
        return ev

    def detect_duplicate_ownership(self, run_id: str) -> str | None:
        seen: dict[str, str] = {}
        for ev in self.events:
            if ev.get("run_id") != run_id:
                continue
            if ev.get("event_type") != "audit":
                continue
            p = ev.get("payload", {})
            if p.get("kind") != "lane_claim":
                continue
            lid = p.get("lane_id")
            owner = p.get("owner")
            if not lid or not owner:
                continue
            if lid in seen and seen[lid] != owner:
                return f"duplicate ownership for {lid}: {seen[lid]} vs {owner}"
            seen[lid] = owner
        return None

    def non_overlap_precheck(
        self,
        candidate: ResearchLane,
        active: list[ResearchLane],
    ) -> dict[str, Any]:
        best = 0.0
        twin: ResearchLane | None = None
        c_concepts = set(candidate.query_concepts) | _tokenize(" ".join(candidate.unique_queries))
        for other in active:
            if candidate.source_classes != other.source_classes:
                continue
            o_concepts = set(other.query_concepts) | _tokenize(" ".join(other.unique_queries))
            score = _jaccard(c_concepts, o_concepts)
            if score > best:
                best = score
                twin = other
        if best >= self.limits.overlap_merge_threshold and twin:
            return {
                "lane_id": candidate.lane_id,
                "action": "merge",
                "into": twin.lane_id,
                "overlap": best,
                "justification_required": best < 0.95,
            }
        return {"lane_id": candidate.lane_id, "action": "dispatch", "overlap": best}

    def dispatch_batch(self, run_id: str, lane_ids: list[str]) -> list[dict[str, Any]]:
        active = sum(1 for ln in self.lanes.values() if ln.state == LaneState.ACTIVE)
        results: list[dict[str, Any]] = []
        for lane_id in lane_ids:
            if active >= self.limits.max_active_scouts:
                break
            lane = self.lanes.get(lane_id)
            if not lane or lane.state != LaneState.PENDING:
                continue
            self.claim_lane(lane_id, f"scout-{lane_id}", run_id)
            active += 1
            contract = ScoutLaneContract(
                lane_id=lane_id,
                question=lane.unique_queries[0],
                source_class=lane.source_classes[0],
                query_family=lane.angle,
                exclusions=lane.stop_rule.get("exclusions", []),
                budget_usd=float(lane.stop_rule.get("max_cost_usd", 1.0)),
                stop_rule=lane.stop_rule,
            )
            if self.adapter_calls[lane_id] >= self.limits.max_adapter_calls_per_lane:
                self.cancel_lane(run_id, lane_id, "adapter_call_cap")
                continue
            scout_out = self.scout.run_lane(contract)
            self.adapter_calls[lane_id] += len(scout_out.get("query_events", []))
            for cand in scout_out.get("candidates", []):
                self.stream_candidate(run_id, lane_id, cand)
            lane.state = LaneState.COMPLETE
            results.append(scout_out)
        return results

    def stream_candidate(self, run_id: str, lane_id: str, candidate: dict[str, Any]) -> str:
        url = normalize_url(candidate.get("url", ""))
        key = canonical_key("url", url)
        if key in self.registered_sources:
            sid = self.registered_sources[key]["source_id"]
            self.events.append(
                self._audit(
                    run_id,
                    "candidate_dedupe",
                    {"lane_id": lane_id, "source_id": sid, "duplicate": True},
                )
            )
            return sid
        sid = f"src-{uuid.uuid4().hex[:12]}"
        payload = {
            "source_id": sid,
            "identifiers": [{"type": "url", "value": url}],
            "title": candidate.get("title"),
            "lane_id": lane_id,
            "candidate_id": candidate.get("candidate_id"),
            "primary_or_derivative": "primary",
        }
        self.registered_sources[key] = payload
        self.events.append(
            {
                "run_id": run_id,
                "event_type": "source_registered",
                "payload": payload,
            }
        )
        domain = urlparse(url).netloc or "unknown"
        self.domain_calls[domain] += 1
        if self.domain_calls[domain] > self.limits.max_calls_per_domain:
            self.cancel_lane(run_id, lane_id, "domain_rate_cap")
        return sid

    def cancel_lane(self, run_id: str, lane_id: str, reason: str) -> dict[str, Any]:
        lane = self.lanes.get(lane_id)
        preserved_cost = self.adapter_calls.get(lane_id, 0)
        preserved_sources = [
            s for s in self.registered_sources.values() if s.get("lane_id") == lane_id
        ]
        if lane:
            lane.state = LaneState.CANCELED
        record = {
            "lane_id": lane_id,
            "reason": reason,
            "preserved_source_count": len(preserved_sources),
            "preserved_adapter_calls": preserved_cost,
        }
        self.canceled_lanes[lane_id] = record
        return self._audit(run_id, "lane_canceled", record)

    def deterministic_fan_in(self) -> FanInSnapshot:
        by_lane: dict[str, list[str]] = defaultdict(list)
        for src in self.registered_sources.values():
            sid = src["source_id"]
            by_lane[src.get("lane_id", "unknown")].append(sid)
        canonical = sorted({s["source_id"] for s in self.registered_sources.values()})
        return FanInSnapshot(
            canonical_source_ids=canonical,
            lane_contributions=dict(by_lane),
        )

    def _audit(self, run_id: str, kind: str, body: dict[str, Any]) -> dict[str, Any]:
        ev = {
            "run_id": run_id,
            "event_type": "audit",
            "payload": {"kind": kind, **body},
        }
        self.events.append(ev)
        return ev
