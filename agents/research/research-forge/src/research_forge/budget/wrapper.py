"""Fail-closed wrapper — unwrapped provider calls are forbidden."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NoReturn, TypeVar

from research_forge.budget.manager import BudgetManager
from research_forge.errors import ErrorCode, ForgeException, raise_forge
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
) -> T:
    err = budget.reserve(cost_usd, role=auth_kwargs.get("role", "host"))
    if err:
        raise ForgeException(err)
    allowed, _decision = gateway.authorize(**auth_kwargs)
    if not allowed:
        raise_forge(ErrorCode.POLICY_DENIED, "Policy denied wrapped call")
    result = fn()
    budget.debit(cost_usd, release_reserve=cost_usd)
    return result


def mark_wrapped(fn: Callable[..., T]) -> Callable[..., T]:
    setattr(fn, _WRAPPED_MARKER, True)
    return fn
