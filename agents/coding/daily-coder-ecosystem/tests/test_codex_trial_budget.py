"""Opt-in subscription trial limits never weaken other routes or task grants."""
import tempfile
import unittest
from pathlib import Path
from daily_coder.budget import BudgetManager,BudgetExceeded,_today
from daily_coder.state_store import StateStore


class CodexTrialBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.state=StateStore(Path(self.temp.name)/"state.sqlite")
        self.state.create("r","task",self.temp.name,"hash","create")
        self.config={"profiles":{"S":{"total_tokens":1000,"max_calls":5}},"thresholds":{"reserve_fraction":0}}

    def manager(self,override="absent",provider="codex_cli",billing="chatgpt_subscription",models=("reviewed",)):
        limits={"max_tokens_per_day":500000,"max_tokens_per_run":100,"max_spend_usd":5}
        if override!="absent": limits["codex_subscription_max_tokens_per_day"]=override
        return BudgetManager(self.config,self.state,limits=limits,subscription_models=models,provider_name=provider,billing_kind=billing,pricing={"api":{"input_per_1k":1,"output_per_1k":1}})

    def test_absent_preserves_daily_limit(self):
        budget=self.manager(); self.state.add_spend(_today(),500000,0)
        with self.assertRaises(BudgetExceeded):budget.reserve("r","S",1,model="reviewed")
        self.assertEqual(budget.limits["max_tokens_per_day"],500000)

    def test_null_removes_only_daily_cap_and_retains_run_and_call_limits(self):
        budget=self.manager(None); self.state.add_spend(_today(),900000,0)
        budget.reserve("r","S",60,model="reviewed",reservation_id="first")
        with self.assertRaises(BudgetExceeded):budget.reserve("r","S",41,model="reviewed")
        self.assertIsNone(budget.limits["max_tokens_per_day"])
        self.assertEqual(self.state.active_budget_reservations("r")["tokens"],60)
        report=budget.reservation_diagnostics("r","S",41)
        self.assertIsNone(report["daily_headroom"])
        self.assertEqual(report["run_grant_tokens"],100)
        self.assertEqual(report["daily_limit_source"],"codex_subscription_max_tokens_per_day")
        budget.config["profiles"]["S"]["max_calls"]=1
        with self.assertRaises(BudgetExceeded):budget.reserve("r","S",1,model="reviewed")

    def test_positive_limit_applies(self):
        budget=self.manager(600000); self.state.add_spend(_today(),599999,0)
        with self.assertRaises(BudgetExceeded):budget.reserve("r","S",2,model="reviewed")
        budget.reserve("r","S",1,model="reviewed")

    def test_other_routes_retain_default_even_with_subscription_metadata(self):
        for provider in ("mock","openai","local","anthropic"):
            with self.subTest(provider=provider):
                budget=self.manager(None,provider=provider)
                self.assertEqual(budget.limits["max_tokens_per_day"],500000)
                self.assertFalse(budget.codex_trial_override)

    def test_invalid_override_or_accounting_is_rejected(self):
        for value in (True,False,0,-1,1.5,"unlimited",{},[]):
            with self.subTest(value=value),self.assertRaises(ValueError):self.manager(value)
        with self.assertRaises(ValueError):self.manager(None,billing="api")
        with self.assertRaises(ValueError):self.manager(None,models=())

    def test_override_cannot_enable_api_or_missing_model_fallback(self):
        budget=self.manager(None)
        for model in ("api",None,"unreviewed"):
            with self.subTest(model=model),self.assertRaises(BudgetExceeded):budget.reserve("r","S",1,model=model)
        self.assertEqual(self.state.active_budget_reservations("r")["calls"],0)

    def test_constructor_does_not_mutate_shared_configuration(self):
        limits={"max_tokens_per_day":500000,"codex_subscription_max_tokens_per_day":None}
        BudgetManager(self.config,self.state,limits=limits,subscription_models=("reviewed",),provider_name="codex_cli",billing_kind="chatgpt_subscription")
        self.assertEqual(limits["max_tokens_per_day"],500000)


if __name__=="__main__": unittest.main()
