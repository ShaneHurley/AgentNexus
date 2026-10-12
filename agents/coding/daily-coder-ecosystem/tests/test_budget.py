"""Budget reserve, threshold levels, and orchestrator provider-path coverage."""
from __future__ import annotations

import shutil
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from daily_coder.budget import BudgetExceeded, BudgetManager, DailyCapExceeded, DEFAULT_THRESHOLDS
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


class TestSubscriptionAccounting(unittest.TestCase):
    MODEL = "codex/reviewed-model"

    def test_exact_trusted_membership_is_required_and_api_pricing_stays_strict(self):
        budget = BudgetManager(_profile_config(), _StaticUsageStore(), subscription_models=[self.MODEL])
        accounting = budget.validate_model_accounting(self.MODEL)
        self.assertEqual(accounting["accounting_mode"], "subscription")
        self.assertEqual(accounting["known_api_cash_usd"], 0.0)
        self.assertIsNone(accounting["total_cost_usd"])
        with self.assertRaises(BudgetExceeded):
            budget.validate_model_pricing(self.MODEL)
        with self.assertRaises(BudgetExceeded):
            budget.price(self.MODEL, 1, 1)
        for model in ("codex/other-model", "codex/reviewed-model-extra", "reviewed-model"):
            with self.subTest(model=model), self.assertRaises(BudgetExceeded):
                budget.validate_model_accounting(model)
        with self.assertRaises(BudgetExceeded):
            BudgetManager(_profile_config(), _StaticUsageStore()).validate_model_accounting(self.MODEL)

    def test_malformed_trusted_allowlists_fail_closed(self):
        for models in (None, self.MODEL, {self.MODEL: True}, [None], [""], [" model"], ["codex/*"], [42], [True]):
            with self.subTest(models=models), self.assertRaises(ValueError):
                BudgetManager(_profile_config(), _StaticUsageStore(), subscription_models=models)

    def test_pricing_mode_metadata_cannot_grant_subscription(self):
        budget = BudgetManager(_profile_config(), _StaticUsageStore(), pricing={self.MODEL: {"accounting_mode": "subscription"}})
        with self.assertRaises(BudgetExceeded):
            budget.validate_model_accounting(self.MODEL)
        with self.assertRaises(BudgetExceeded):
            budget.reserve("r", "S", 1, model=self.MODEL, estimated_usd=0)
        with self.assertRaises(BudgetExceeded):
            budget.settle("r", 1, self.MODEL, 1, 0, reported_usd=0)

    def test_subscription_reserves_tokens_and_retains_token_caps(self):
        budget = BudgetManager(_profile_config(), _StaticUsageStore(), subscription_models=[self.MODEL])
        result = budget.reserve("r", "S", 60, model=self.MODEL)
        self.assertEqual(result["reserved"], 60)
        self.assertEqual(result["known_api_cash_usd"], 0)
        self.assertIsNone(result["total_cost_usd"])
        self.assertEqual(result["total_cost_status"], "unknown")
        with self.assertRaises(BudgetExceeded):
            budget.reserve("r", "S", 31, model=self.MODEL)
        self.assertEqual(budget._used("r")["tokens"], 60)

    def test_subscription_persistent_cash_is_zero_total_dollar_value_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "state.sqlite")
            store.create("r", "task", temp, "cfg", "create", live=True)
            store.set_profile("r", "S")
            budget = BudgetManager(_profile_config(), store, limits={"max_tokens_per_day": 1000, "max_spend_usd": 0.0}, subscription_models=[self.MODEL])
            reservation = budget.reserve("r", "S", 30, model=self.MODEL, reservation_id="subscription")
            self.assertEqual(store.active_budget_reservations("r")["tokens"], 30)
            self.assertEqual(reservation["known_api_cash_usd"], 0)
            result = budget.settle("r", 30, self.MODEL, 10, 5, "subscription")
            self.assertEqual(result["known_api_cash_usd"], 0)
            self.assertIsNone(result["total_cost_usd"])
            self.assertEqual(result["accounting_mode"], "subscription")
            self.assertEqual(store.spend(__import__("datetime").date.today().isoformat())["tokens"], 15)
            self.assertEqual(store.spend(__import__("datetime").date.today().isoformat())["est_usd"], 0)
            # Until its invocation receipt is committed, settlement itself is authoritative usage.
            report = budget.report("r", "S")
            self.assertEqual(report["tokens"], 15)
            self.assertEqual(report["known_api_cash_usd"], 0)
            self.assertIsNone(report["est_usd"])
            self.assertIsNone(report["total_cost_usd"])
            self.assertIsNone(report["cost_per_verified_pass"])
            self.assertIsNone(report["today"]["est_usd"])
            self.assertEqual(report["total_cost_status"], "unknown")

    def test_subscription_nonzero_or_malformed_cash_cannot_be_silently_discarded(self):
        budget = BudgetManager(_profile_config(), _StaticUsageStore(), subscription_models=[self.MODEL])
        for amount in (1.0, -1, float("inf"), float("nan"), "unknown"):
            with self.subTest(amount=amount), self.assertRaises((BudgetExceeded, ValueError)):
                budget.reserve("r", "S", 10, model=self.MODEL, estimated_usd=amount)
        reservation = budget.reserve("r", "S", 10, model=self.MODEL)
        for amount in (1.0, -1, float("inf"), float("nan"), "unknown"):
            with self.subTest(amount=amount), self.assertRaises((BudgetExceeded, ValueError)):
                budget.settle("r", 10, self.MODEL, 1, 0, reservation["reservation_id"], reported_usd=amount)
        self.assertEqual(budget._used("r")["tokens"], 10)

    def test_zero_daily_cash_cap_allows_trusted_subscription_startup_only(self):
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "state.sqlite")
            limits = {"max_spend_usd": 0.0}
            subscription = BudgetManager(_profile_config(), store, limits=limits, subscription_models=[self.MODEL])
            self.assertEqual(subscription.check_daily()["est_usd"], 0)
            with self.assertRaises(DailyCapExceeded):
                BudgetManager(_profile_config(), store, limits=limits).check_daily()
            store.add_spend(__import__("datetime").date.today().isoformat(), 1, 0.01)
            with self.assertRaises(DailyCapExceeded):
                subscription.check_daily()

    def test_trusted_membership_is_snapshotted_before_caller_changes_allowlist(self):
        models = [self.MODEL]
        budget = BudgetManager(_profile_config(), _StaticUsageStore(), subscription_models=models)
        models.append("codex/unreviewed")
        with self.assertRaises(BudgetExceeded):
            budget.validate_model_accounting("codex/unreviewed")

    def test_api_accounting_retains_float_settlement_and_cash_report(self):
        with tempfile.TemporaryDirectory() as temp:
            store = StateStore(Path(temp) / "state.sqlite")
            store.create("r", "task", temp, "cfg", "create", live=True)
            store.set_profile("r", "S")
            budget = BudgetManager(_profile_config(), store, pricing={"api/model": {"input_per_1k": 2, "output_per_1k": 3}})
            accounting = budget.validate_model_accounting("api/model")
            self.assertEqual(accounting["accounting_mode"], "api")
            budget.reserve("r", "S", 30, model="api/model", reservation_id="api")
            self.assertEqual(budget.settle("r", 30, "api/model", 10, 5, "api"), 0.035)
            self.assertIsInstance(budget.report("r", "S")["est_usd"], float)


class TestBudgetThresholds(unittest.TestCase):
    def test_unlisted_model_is_not_assumed_free(self):
        cfg = _profile_config()
        pricing = {"default": {"input_per_1k": 0.0, "output_per_1k": 0.0}}
        budget = BudgetManager(cfg, _StaticUsageStore(), pricing=pricing)
        with self.assertRaises(BudgetExceeded):
            budget.price("unlisted-provider/model", 1000, 1000)

    def test_explicit_zero_rate_model_is_free(self):
        cfg = _profile_config()
        pricing = {"free/provider-model": {"input_per_1k": 0.0, "output_per_1k": 0.0}}
        budget = BudgetManager(cfg, _StaticUsageStore(), pricing=pricing)
        self.assertEqual(budget.price("free/provider-model", 1000, 1000), 0.0)

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


class TestPersistentBudgetReservations(unittest.TestCase):
    def test_separate_managers_share_per_run_reservations(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.sqlite"
            first_store = StateStore(path)
            first_store.create("r", "task", temp, "cfg", "create", live=True)
            first_store.set_profile("r", "S")
            second_store = StateStore(path)
            first = BudgetManager(_profile_config(100), first_store)
            second = BudgetManager(_profile_config(100), second_store)

            first.reserve("r", "S", 60, reservation_id="first-call")
            with self.assertRaises(BudgetExceeded):
                second.reserve("r", "S", 31, reservation_id="second-call")

    def test_separate_managers_share_daily_usd_reservations(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.sqlite"
            first_store = StateStore(path)
            first_store.create("r1", "task", temp, "cfg", "create-1", live=True)
            first_store.set_profile("r1", "S")
            first_store.create("r2", "task", temp, "cfg", "create-2", live=True)
            first_store.set_profile("r2", "S")
            second_store = StateStore(path)
            config = _profile_config(100)
            limits = {"max_tokens_per_day": 1000, "max_spend_usd": 1.0}
            pricing = {"priced/model": {"input_per_1k": 1.0, "output_per_1k": 1.0}}
            first = BudgetManager(config, first_store, pricing=pricing, limits=limits)
            second = BudgetManager(config, second_store, pricing=pricing, limits=limits)

            first.reserve("r1", "S", 10, model="priced/model", estimated_usd=0.6,
                          reservation_id="first-call")
            with self.assertRaises(BudgetExceeded):
                second.reserve("r2", "S", 10, model="priced/model", estimated_usd=0.6,
                               reservation_id="second-call")


class TestOrchestratorBudgetPath(unittest.TestCase):
    def test_unpriced_selected_model_is_rejected_before_provider_call(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            package = Path(d) / "package"
            package.mkdir()
            for name in ("agents", "schemas", "skills", "config"):
                shutil.copytree(source / name, package / name)
            (package / "config" / "pricing.json").write_text(
                '{"default":{"input_per_1k":0,"output_per_1k":0}}', encoding="utf-8")

            class ProviderSpy:
                name = "mock"

                def __init__(self):
                    self.calls = 0

                def invoke(self, request):
                    self.calls += 1
                    return MockProvider().invoke(request)

            provider = ProviderSpy()
            store = StateStore(Path(d) / "state.sqlite")
            orch = Orchestrator(package, store, provider, live=False)
            run_id = "r"
            store.create(run_id, "research", str(package), "cfg", "create")
            store.set_profile(run_id, "S")
            with self.assertRaises(BudgetExceeded):
                orch._invoke(run_id, "researcher", "RESEARCH", {"request": "inspect"}, 0, "S", None)
            self.assertEqual(provider.calls, 0)

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

            def tracking_reserve(run_id, profile, estimated_tokens, **kwargs):
                order.append("reserve")
                return original_reserve(run_id, profile, estimated_tokens, **kwargs)

            orch.budget.reserve = tracking_reserve  # type: ignore[method-assign]
            orch.start("Fix typo", package)
            self.assertGreater(len(order), 0)
            for i in range(0, len(order), 2):
                self.assertEqual(order[i], "reserve")
                if i + 1 < len(order):
                    self.assertEqual(order[i + 1], "invoke")


if __name__ == "__main__":
    unittest.main()
