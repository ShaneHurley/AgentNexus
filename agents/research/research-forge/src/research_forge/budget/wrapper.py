"""Fail-closed wrapper — unwrapped provider calls are forbidden."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from agent_core.contracts import ContractDenied
from research_forge.budget.manager import BudgetState
from collections.abc import Callable
from typing import Any, NoReturn, TypeVar

from agent_core.rate_limiter import RateLimitExceeded
from research_forge.budget.manager import BudgetManager
from research_forge.errors import ErrorCode, ForgeException, raise_forge, forge_error
from research_forge.policy.gateway import PolicyGateway

T = TypeVar("T")

_WRAPPED_MARKER = "__rf_budget_wrapped__"


def require_wrapped(fn: Callable[..., T]) -> Callable[..., T]:
    if getattr(fn, _WRAPPED_MARKER, False):
        return fn

    def _inner(*args: Any, **kwargs: Any) -> NoReturn:
        raise_forge(
            ErrorCode.POLICY_DENIED,
            "Direct provider call forbidden; use budget_wrapped_call",
        )

    return _inner  # type: ignore[return-value]


def budget_wrapped_call(
    gateway: PolicyGateway,
    budget: BudgetManager,
    *,
    cost_usd: float,
    auth_kwargs: dict[str, Any],
    fn: Callable[[], T],
    request: dict[str, Any] | None = None,
) -> T:
    journal = getattr(budget, "journal", None)
    key = hashlib.sha256(json.dumps({"authorization":auth_kwargs,"request":request},sort_keys=True).encode()).hexdigest()
    allowed, _decision = gateway.authorize(**auth_kwargs)
    if not allowed:
        raise_forge(ErrorCode.POLICY_DENIED, "Policy denied wrapped call")
    if journal:
        journal.check_dispatch()
        cached = journal.call(key)
        if cached:
            budget.state = BudgetState(**journal.view()["budget"])
            if cached["status"] != "completed":
                raise ContractDenied("RECONCILIATION_REQUIRED: provider call outcome unknown")
            return cached["result"]
    # Rate-limit gate (cheap mode)
    try:
        budget.rate_limiter.acquire()
    except RateLimitExceeded as exc:
        raise ForgeException(forge_error(
            ErrorCode.RATE_LIMITED,
            str(exc),
            rate_limit_calls=exc.calls,
            rate_limit_window=exc.window,
        ))

    err = budget.reserve(cost_usd, role=auth_kwargs.get("role", "host"))
    if err:
        raise ForgeException(err)
    row = journal.prepare(key,cost_usd,budget,auth_kwargs) if journal else None
    result = fn()
    budget.debit(cost_usd, release_reserve=cost_usd)
    if journal:
        journal.complete(row,result,budget)
        journal.check_dispatch()
    return result


def mark_wrapped(fn: Callable[..., T]) -> Callable[..., T]:
    setattr(fn, _WRAPPED_MARKER, True)
    return fn
