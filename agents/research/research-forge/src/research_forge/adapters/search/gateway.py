"""Policy-wrapped search entry (RF-W1-D-05)."""

from __future__ import annotations

import time
from typing import Any

from research_forge.budget.wrapper import budget_wrapped_call
from research_forge.budget.manager import BudgetManager
from research_forge.policy.gateway import PolicyGateway


def gated_search(
    gateway: PolicyGateway,
    budget: BudgetManager,
    adapter: Any,
    *,
    role: str,
    phase: str,
    query: str,
    live: bool,
    cost_usd: float = 0.01,
    **search_kwargs: Any,
) -> dict[str, Any]:
    tool_id = getattr(adapter, "adapter_id", "unknown_search")
    target = "adapter://public/search" if live else f"mock://{tool_id}"

    def _run() -> dict[str, Any]:
        t0 = time.perf_counter()
        out = adapter.search(query, **search_kwargs)
        out["duration_ms"] = int((time.perf_counter() - t0) * 1000)
        out["query_family"] = "initial"
        out["exact_query"] = query
        return out

    return budget_wrapped_call(
        gateway,
        budget,
        cost_usd=cost_usd,
        auth_kwargs={
            "role": role,
            "phase": phase,
            "tool_id": tool_id,
            "operation": "search",
            "target": target,
            "live": live,
        },
        fn=_run,
    )
