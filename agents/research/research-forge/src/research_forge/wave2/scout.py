"""Source Scout — lane-bounded progressive search (RF-W2-B)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from research_forge.wave2.types import (
    MAX_SCOUT_PROSE_CHARS,
    MAX_SCOUT_REFINEMENTS,
    MAX_SCOUT_RETRIES,
    ScoutCandidate,
)

SearchFn = Callable[..., dict[str, Any]]


def _result_url(res: dict[str, Any]) -> str:
    return res.get("url") or res.get("canonical_url") or ""


def _result_title(res: dict[str, Any]) -> str:
    return res.get("title") or res.get("canonical_title") or ""


@dataclass
class ScoutLaneContract:
    lane_id: str
    question: str
    source_class: str
    query_family: str
    exclusions: list[str]
    budget_usd: float
    stop_rule: dict[str, Any]

    def validate_cross_lane(self, other_lane_id: str) -> None:
        if other_lane_id != self.lane_id:
            raise ValueError("Scout contract is single-lane; cross-lane search prohibited")

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane_id": self.lane_id,
            "question": self.question,
            "source_class": self.source_class,
            "query_family": self.query_family,
            "exclusions": self.exclusions,
            "budget_usd": self.budget_usd,
            "stop_rule": self.stop_rule,
        }


@dataclass
class ScoutRunState:
    queries_executed: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[ScoutCandidate] = field(default_factory=list)
    spent_usd: float = 0.0
    refinements: int = 0
    retries: int = 0
    duplicate_hits: int = 0
    rounds_without_new: int = 0
    stopped_reason: str | None = None


class SourceScout:
    role_id = "source_scout"
    allowed_tools = ("mock_search_v1",)

    def __init__(
        self,
        search: SearchFn | Any,
        *,
        cost_per_query_usd: float = 0.05,
    ) -> None:
        if hasattr(search, "search"):
            self._search = search.search  # type: ignore[assignment]
        else:
            self._search = search
        self.cost_per_query = cost_per_query_usd

    def run_lane(self, contract: ScoutLaneContract) -> dict[str, Any]:
        state = ScoutRunState()
        seen_urls: set[str] = set()
        result_cap = int(contract.stop_rule.get("result_cap", 8))
        dup_rate_stop = float(contract.stop_rule.get("duplicate_rate_stop", 0.75))
        no_new_stop = int(contract.stop_rule.get("no_new_source_rounds", 2))

        broad_q = f"{contract.query_family} {contract.question}"[:200]
        self._execute_query(contract, broad_q, state, seen_urls, result_cap)

        if state.stopped_reason:
            return self._package(contract, state)

        gap = self._observed_gap(state)
        if gap and state.refinements < MAX_SCOUT_REFINEMENTS:
            state.refinements += 1
            refined = f"{broad_q} {gap}"[:200]
            self._execute_query(contract, refined, state, seen_urls, result_cap)

        if self._should_stop(state, contract, dup_rate_stop, no_new_stop):
            return self._package(contract, state)

        return self._package(contract, state)

    def _execute_query(
        self,
        contract: ScoutLaneContract,
        query: str,
        state: ScoutRunState,
        seen_urls: set[str],
        result_cap: int,
    ) -> None:
        if state.spent_usd + self.cost_per_query > contract.budget_usd:
            state.stopped_reason = "budget_cap"
            return
        if len(state.candidates) >= result_cap:
            state.stopped_reason = "result_cap"
            return

        qid = f"q-{uuid.uuid4().hex[:10]}"
        attempt = 0
        page: dict[str, Any] = {"results": []}
        while attempt <= MAX_SCOUT_RETRIES:
            try:
                page = self._search(
                    query,
                    filters={"source_class": contract.source_class},
                )
                break
            except Exception:
                attempt += 1
                state.retries += 1
                if state.retries > MAX_SCOUT_RETRIES:
                    state.stopped_reason = "retry_cap"
                    return
        state.spent_usd += self.cost_per_query
        state.queries_executed.append(
            {"query_event_id": qid, "query": query, "adapter": "mock_search_v1"}
        )

        new_in_round = 0
        for res in page.get("results", []):
            if len(state.candidates) >= result_cap:
                state.stopped_reason = "result_cap"
                break
            url = _result_url(res)
            if any(ex.lower() in _result_title(res).lower() for ex in contract.exclusions):
                continue
            if url in seen_urls:
                state.duplicate_hits += 1
                continue
            seen_urls.add(url)
            new_in_round += 1
            cand = ScoutCandidate(
                candidate_id=f"cand-{uuid.uuid4().hex[:10]}",
                lane_id=contract.lane_id,
                url=url,
                title=_result_title(res)[:200],
                relevance_reason=self._relevance(res, contract)[:MAX_SCOUT_PROSE_CHARS],
                source_type=res.get("source_type") or contract.source_class,
                access="open",
                uniqueness_hypothesis="distinct url",
                follow_citations=bool(res.get("source_type") == "paper"),
                query_event_id=qid,
            )
            state.candidates.append(cand)

        if new_in_round == 0:
            state.rounds_without_new += 1
        else:
            state.rounds_without_new = 0

    def _observed_gap(self, state: ScoutRunState) -> str:
        if not state.candidates:
            return "primary evidence"
        types = {c.source_type for c in state.candidates}
        if len(types) == 1:
            return "alternative source type"
        return ""

    def _should_stop(
        self,
        state: ScoutRunState,
        contract: ScoutLaneContract,
        dup_rate_stop: float,
        no_new_stop: int,
    ) -> bool:
        if state.stopped_reason:
            return True
        total = state.duplicate_hits + len(state.candidates)
        if total and state.duplicate_hits / total >= dup_rate_stop:
            state.stopped_reason = "duplicate_rate"
            return True
        if state.rounds_without_new >= no_new_stop:
            state.stopped_reason = "no_new_source_window"
            return True
        if state.spent_usd >= contract.budget_usd:
            state.stopped_reason = "budget_cap"
            return True
        if contract.stop_rule.get("lane_saturated"):
            state.stopped_reason = "lane_saturation"
            return True
        return False

    def _relevance(self, res: dict[str, Any], contract: ScoutLaneContract) -> str:
        snippet = (res.get("snippet") or "")[:120]
        return f"Matches {contract.source_class}: {snippet}"

    def _package(self, contract: ScoutLaneContract, state: ScoutRunState) -> dict[str, Any]:
        return {
            "lane_id": contract.lane_id,
            "contract": contract.to_dict(),
            "query_events": state.queries_executed,
            "candidates": [c.to_dict() for c in state.candidates],
            "spent_usd": round(state.spent_usd, 4),
            "stopped_reason": state.stopped_reason or "complete",
            "refinements": state.refinements,
            "retries": state.retries,
        }
