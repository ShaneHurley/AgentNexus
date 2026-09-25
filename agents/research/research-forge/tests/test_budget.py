from __future__ import annotations

from pathlib import Path

import pytest

from research_forge.budget.manager import BudgetManager
from research_forge.budget.wrapper import budget_wrapped_call, require_wrapped
from research_forge.errors import ErrorCode, ForgeException
from research_forge.policy.gateway import PolicyGateway
from research_forge.policy.manifest import ToolManifest


def test_threshold_boundaries(repo_root: Path) -> None:
    bm = BudgetManager(repo_root / "config" / "budgets.yaml")
    bm.start("S")
    limit = bm.state.limit_usd  # type: ignore[union-attr]
    bm.debit(limit * 0.69)
    assert bm.threshold_status() == "ok"
    bm.debit(limit * 0.02)
    assert bm.threshold_status() == "warn"
    bm.debit(limit * 0.09)
    assert bm.threshold_status() == "checkpoint"
    bm.debit(limit * 0.11)
    assert bm.threshold_status() == "hard_stop"


def test_reserve_blocks_before_dispatch(repo_root: Path) -> None:
    bm = BudgetManager(repo_root / "config" / "budgets.yaml")
    bm.start("S")
    err = bm.reserve(bm.state.available + 1)  # type: ignore[union-attr]
    assert err is not None
    assert err.code == ErrorCode.BUDGET_EXCEEDED


def test_direct_unwrapped_call_fails() -> None:
    def raw_provider() -> str:
        return "ok"

    wrapped_check = require_wrapped(raw_provider)
    with pytest.raises(ForgeException) as exc:
        wrapped_check()
    assert exc.value.error.code == ErrorCode.POLICY_DENIED


def test_director_second_call_denied(repo_root: Path) -> None:
    bm = BudgetManager(repo_root / "config" / "budgets.yaml")
    bm.start("S")
    assert bm.authorize_director_call(profile="S") is None
    err = bm.authorize_director_call(profile="S")
    assert err is not None


def test_wrapped_call(repo_root: Path) -> None:
    gw = PolicyGateway(repo_root / "config" / "policies.yaml", mode="mock")
    gw.register_tool(
        ToolManifest(
            "mock_model",
            {
                "read": True,
                "write": False,
                "network": False,
                "execute": False,
                "credential": False,
                "data_class": "public",
            },
        )
    )
    bm = BudgetManager(repo_root / "config" / "budgets.yaml")
    bm.start("S")

    result = budget_wrapped_call(
        gw,
        bm,
        cost_usd=0.01,
        auth_kwargs={
            "role": "host",
            "phase": "wave0",
            "tool_id": "mock_model",
            "operation": "model_call",
            "target": "adapter://public/mock",
        },
        fn=lambda: {"ok": True},
    )
    assert result["ok"]
