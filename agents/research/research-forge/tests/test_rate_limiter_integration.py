"""Integration: Research Forge BudgetManager + rate limiter."""
from __future__ import annotations

from pathlib import Path

import pytest

from research_forge.budget.manager import BudgetManager


def test_budget_manager_xs_profile_has_rate_limiter(repo_root: Path) -> None:
    bm = BudgetManager(repo_root / "config" / "budgets.yaml")
    bm.start("XS")
    assert bm.rate_limiter.config.enabled
    assert bm.rate_limiter.config.max_calls == 10
    report = bm.report()
    assert "rate_limiter" in report
    assert report["rate_limiter"]["remaining"] == 10


def test_s_profile_rate_limiter_enabled(repo_root: Path) -> None:
    bm = BudgetManager(repo_root / "config" / "budgets.yaml")
    bm.start("S")
    assert bm.rate_limiter.config.enabled
    assert bm.rate_limiter.config.max_calls == 15


def test_l_profile_rate_limiter_disabled(repo_root: Path) -> None:
    bm = BudgetManager(repo_root / "config" / "budgets.yaml")
    bm.start("L")
    assert not bm.rate_limiter.config.enabled
