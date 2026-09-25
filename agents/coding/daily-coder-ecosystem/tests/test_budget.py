"""Budget reserve, threshold levels, and orchestrator provider-path coverage."""
from __future__ import annotations

import shutil
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from daily_coder.budget import BudgetExceeded, BudgetManager, DEFAULT_THRESHOLDS
from daily_coder.orchestrator import Orchestrator
from daily_coder.providers.mock import MockProvider
from daily_coder.state_store import StateStore


class _StaticUsageStore:
    """Minimal store for unit tests that only need total_usage."""

    def __init__(self, tokens: int = 0, calls: int = 0):
        self._tokens = tokens
        self._calls = calls

    def total_usage(self, _run_id: str) -> dict:
        return {"tokens": self._tokens, "calls": self._calls}


def _profile_config(total_tokens: int = 100, max_calls: int = 20) -> dict:
    return {
        "profiles": {"S": {"total_tokens": total_tokens, "max_calls": max_calls, "frontier_calls": 0}},
        "thresholds": dict(DEFAULT_THRESHOLDS),
    }


class TestBudgetThresholds(unittest.TestCase):
    def test_usable_tokens_matches_ninety_percent_hard_stop(self):
        cfg = _profile_config(100)
        budget = BudgetManager(cfg, _StaticUsageStore())
        self.assertEqual(budget.usable_tokens("S"), 90)
        self.assertEqual(
            budget.usable_tokens("S"),
            int(100 * (1 - DEFAULT_THRESHOLDS["reserve_fraction"])),
        )
        self.assertEqual(
            int(100 * DEFAULT_THRESHOLDS["hard_stop_fraction"]),
            budget.usable_tokens("S"),
        )

    def test_check_raises_at_usable_ceiling(self):
        cfg = _profile_config(100, max_calls=2)
        cfg["thresholds"] = {"reserve_fraction": 0.1}
        with self.assertRaises(BudgetExceeded):
            BudgetManager(cfg, _StaticUsageStore(tokens=90, calls=1)).check("r", "S")

    def test_level_warn_checkpoint_hard_stop(self):
        cfg = _profile_config(100)
        budget = BudgetManager(cfg, _StaticUsageStore())
        budget.reserve("r", "S", 70)
        self.assertEqual(budget.level("r", "S"), "warn")
        budget.release("r", 70)
        budget.reserve("r", "S", 80)
        self.assertEqual(budget.level("r", "S"), "checkpoint")
        budget.release("r", 80)
        budget.reserve("r", "S", 90)
        self.assertEqual(budget.level("r", "S"), "hard_stop")

    def test_reserve_emits_event_when_not_ok(self):
        cfg = _profile_config(100)
        budget = BudgetManager(cfg, _StaticUsageStore())
        out = budget.reserve("r", "S", 75)
        self.assertEqual(out["level"], "warn")
        self.assertTrue(budget.events)
        self.assertEqual(budget.events[-1]["level"], "warn")


class TestBudgetParallelReserve(unittest.TestCase):
    def test_parallel_lanes_cannot_burst_past_usable_cap(self):
        cfg = _profile_config(100, max_calls=10)
        store = _StaticUsageStore()
        budget = BudgetManager(cfg, store)
        chunk = 30
        usable = budget.usable_tokens("S")

        def attempt():
            try:
                budget.reserve("r", "S", chunk)
                return "ok"
            except BudgetExceeded:
                return "denied"

        with ThreadPoolExecutor(max_workers=6) as pool:
            outcomes = [f.result() for f in [pool.submit(attempt) for _ in range(6)]]

        ok = outcomes.count("ok")
        denied = outcomes.count("denied")
        self.assertEqual(ok * chunk, usable)
        self.assertGreater(denied, 0)
        self.assertLessEqual(budget._used("r")["tokens"], usable)

    def test_reserve_is_thread_safe_under_contention(self):
        cfg = _profile_config(1000, max_calls=50)
        budget = BudgetManager(cfg, _StaticUsageStore())
        errors: list[Exception] = []

        def worker():
            try:
                for _ in range(5):
                    budget.reserve("r", "S", 10)
                    budget.release("r", 10)
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertNotIn("r", budget._reserved)


class TestOrchestratorBudgetPath(unittest.TestCase):
    def test_invoke_reserves_before_provider(self):
        source = Path(__file__).resolve().parents[1]
        order: list[str] = []

        class OrderProvider:
            name = "mock"

            def invoke(self, request):
                order.append("invoke")
                return MockProvider().invoke(request)

        with tempfile.TemporaryDirectory() as d:
            package = Path(d) / "package"
            package.mkdir()
            for name in ("agents", "schemas", "skills", "config"):
                shutil.copytree(source / name, package / name)
            store = StateStore(Path(d) / "state.sqlite")
            orch = Orchestrator(package, store, OrderProvider(), live=False)
            original_reserve = orch.budget.reserve

            def tracking_reserve(run_id, profile, estimated_tokens):
                order.append("reserve")
                return original_reserve(run_id, profile, estimated_tokens)

            orch.budget.reserve = tracking_reserve  # type: ignore[method-assign]
            orch.start("Fix typo", package)
            self.assertGreater(len(order), 0)
            for i in range(0, len(order), 2):
                self.assertEqual(order[i], "reserve")
                if i + 1 < len(order):
                    self.assertEqual(order[i + 1], "invoke")


if __name__ == "__main__":
    unittest.main()
