"""Gateway-wrapped reader calls."""

from __future__ import annotations

from typing import Any

from research_forge.budget.manager import BudgetManager
from research_forge.budget.wrapper import budget_wrapped_call
from research_forge.policy.gateway import PolicyGateway


def gated_read(
    gateway: PolicyGateway,
    budget: BudgetManager,
    adapter: Any,
    *,
    role: str,
    phase: str,
    source_ref: dict[str, Any],
    live: bool,
    cost_usd: float = 0.02,
    locator: str | None = None,
) -> dict[str, Any]:
    tool_id = getattr(adapter, "adapter_id", "unknown_reader")
    url = source_ref.get("url") or source_ref.get("path") or "unknown"
    target = url if str(url).startswith("http") else f"file://{url}"

    return budget_wrapped_call(
        gateway,
        budget,
        cost_usd=cost_usd,
        auth_kwargs={
            "role": role,
            "phase": phase,
            "tool_id": tool_id,
            "operation": "read_document",
            "target": target,
            "live": live,
            "confidentiality": source_ref.get("confidentiality", "public"),
        },
        fn=lambda: adapter.read(source_ref, locator=locator),
    )
