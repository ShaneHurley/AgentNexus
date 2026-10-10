import copy
import tempfile
import unittest
from agent_core.model_catalog import CatalogSnapshot, CatalogStore
from agent_core.model_resolver import ModelResolver
from agent_core.evaluation import evaluate


def catalog():
    model = dict(provider="local", model="fixture-model", context_tokens=10000,
                 output_tokens=2000, risks=["low"], privacy=["local"],
                 features=["tools", "json_schema"], credential_ref=None,
                 pricing=dict(input_per_million=1, output_per_million=2), latency_ms=100)
    cheap = copy.deepcopy(model)
    cheap["pricing"] = dict(input_per_million=.1, output_per_million=.2)
    return dict(schema_version=1, models={"baseline": model, "cheap": cheap})


def policy():
    return dict(schema_version=1, roles={"worker": dict(allowed_models=["baseline", "cheap"],
                default="baseline", fallback="cheap", reviewed_baseline=True,
                evaluation_class="code", qualifications={})})


def stable_policy_hash(p):
    from agent_core.model_catalog import digest
    clean=copy.deepcopy(p)
    for spec in clean["roles"].values(): spec.pop("qualifications",None)
    return digest(clean)


def records():
    return [dict(task_id=str(i), run_id=str(j), model=m, success=True,
                 critical_policy_violation=False, input_tokens=100, output_tokens=20,
                 tool_calls=1, repairs=0, escalations=0, latency_ms=10,
                 cost_usd=(1 if m == "baseline" else .1))
            for i in range(100) for j in range(2) for m in ["baseline", "cheap"]]


class RoutingTests(unittest.TestCase):
    def explain(self, c=None, p=None, req=None, env=None, override=None):
        return ModelResolver(c or catalog(), p or policy()).explain("worker", req or {},
                       env or dict(available_providers=["local"], available_credentials=[]), override)

    def test_baseline_preserved_and_unknown_quality_excluded(self):
        r=self.explain()
        self.assertEqual(r["selected_alias"], "baseline")
        self.assertIn("unqualified_quality", r["excluded"]["cheap"])

    def test_override_cannot_bypass_quality_or_features(self):
        self.assertIsNone(self.explain(override="cheap")["selected_alias"])
        r=self.explain(req=dict(features=["streaming"]), override="baseline")
        self.assertIn("unsupported_feature:streaming",r["excluded"]["baseline"])

    def test_capability_and_availability_denials(self):
        c=catalog(); c["models"]["baseline"]["credential_ref"]="opaque-1"
        r=self.explain(c=c, req=dict(risk="high",privacy="external",context_tokens=10001,
                                  output_tokens=2001,deadline_ms=1),
                       env=dict(available_providers=[],available_credentials=[]))
        self.assertEqual(set(r["excluded"]["baseline"]),set(["risk", "privacy", "context", "output", "deadline", "credential_unavailable", "provider_unavailable"]))

    def test_invalid_references_and_unknown_fields_fail_closed(self):
        p=policy(); p["roles"]["worker"]["default"]="missing"
        with self.assertRaises(ValueError): self.explain(p=p)
        c=catalog(); c["models"]["baseline"]["mystery"]=True
        with self.assertRaises(ValueError): self.explain(c=c)
        with self.assertRaises(ValueError): self.explain(req=dict(typo=True))

    def test_catalog_activation_is_explicit_and_old_pin_stable(self):
        with tempfile.TemporaryDirectory() as d:
            store=CatalogStore(d); first=store.publish(catalog())
            with self.assertRaises(ValueError): store.load()
            with self.assertRaises(ValueError): store.activate(first.hash)
            store.activate(first.hash,confirmed=True)
            c=catalog(); c["models"]["baseline"]["context_tokens"]=12000
            second=store.publish(c)
            self.assertEqual(store.load().hash,first.hash)
            self.assertEqual(store.load(first.hash).data,catalog())
            self.assertIn("baseline",store.diff(first.hash,second.hash)["changed"])
            store.activate(second.hash,confirmed=True)
            self.assertEqual(store.load(first.hash).hash,first.hash)
            detached=first.data; detached["models"].clear()
            self.assertEqual(first.data,catalog())

    def test_retry_limits_and_failure_categories(self):
        resolver=ModelResolver(catalog(),policy())
        env=dict(available_providers=["local"],available_credentials=[])
        self.assertEqual(resolver.next_attempt("worker",{},env,failure_category="quality")["action"],"repair")
        self.assertEqual(resolver.next_attempt("worker",{},env,failure_category="auth")["action"],"stop")
        self.assertEqual(resolver.next_attempt("worker",{},env,quality_repairs=1,escalations=1)["action"],"stop")
        self.assertEqual(resolver.next_attempt("worker",{},env,quality_repairs=1)["action"],"stop")


    def test_qualified_cheaper_selection_and_unknown_prices(self):
        c=catalog(); p=policy()
        report=evaluate(records(),role="worker",evaluation_class="code",catalog_hash=CatalogSnapshot.from_dict(c).hash,
                        policy_hash=stable_policy_hash(p),corpus_hash="d"*64,candidate="cheap",baseline="baseline",evidence_kind="measured")
        p["roles"]["worker"]["qualifications"]["cheap"]=report
        self.assertEqual(self.explain(c=c,p=p,req=dict(expected_input_tokens=100,expected_output_tokens=20))["selected_alias"],"cheap")
        self.assertEqual(self.explain(c=c,p=p)["selected_alias"],"baseline")
        self.assertEqual(self.explain(c=c,p=p,req=dict(expected_input_tokens=100,expected_output_tokens=20,
                         expected_escalations=1,expected_tool_cost_usd=1))["expected_task_cost_usd"]["baseline"],2.000154)
        c["models"]["baseline"]["pricing"]["input_per_million"]=None
        with self.assertRaises(ValueError): self.explain(c=c,p=p)
        self.assertIsNone(self.explain(c=c)["expected_task_cost_usd"]["baseline"])

    def test_qualification_is_bound_to_routing_policy(self):
        from agent_core.model_catalog import digest
        c=catalog(); p=policy()
        report=evaluate(records(),role="worker",evaluation_class="code",catalog_hash=CatalogSnapshot.from_dict(c).hash,
                        policy_hash=stable_policy_hash(p),corpus_hash="d"*64,candidate="cheap",baseline="baseline",evidence_kind="measured")
        from agent_core.evaluation import routing_policy_digest
        before=self.explain(c=c,p=p)
        self.assertEqual(before["routing_policy_hash"],routing_policy_digest(p))
        p["roles"]["worker"]["qualifications"]["cheap"]=report
        after=self.explain(c=c,p=p)
        self.assertEqual(before["routing_policy_hash"],after["routing_policy_hash"])
        self.assertNotEqual(before["policy_hash"],after["policy_hash"])
        req=dict(expected_input_tokens=100,expected_output_tokens=20)
        self.assertEqual(self.explain(c=c,p=p,req=req)["selected_alias"],"cheap")
        p["roles"]["worker"]["fallback"]=None
        with self.assertRaisesRegex(ValueError,"policy"):
            self.explain(c=c,p=p,req=req)
        p=policy(); report["policy_hash"]="e"*64
        report["report_hash"]=digest({k:v for k,v in report.items() if k!="report_hash"})
        p["roles"]["worker"]["qualifications"]["cheap"]=report
        with self.assertRaisesRegex(ValueError,"policy"):
            self.explain(c=c,p=p,req=req)

    def test_inconsistent_reviewed_report_fails_closed(self):
        from agent_core.model_catalog import digest
        c=catalog(); p=policy()
        report=evaluate(records(),role="worker",evaluation_class="code",catalog_hash=CatalogSnapshot.from_dict(c).hash,
                        policy_hash=stable_policy_hash(p),corpus_hash="d"*64,candidate="cheap",baseline="baseline",evidence_kind="measured")
        report["candidate_metrics"]["successful_tasks"]=1
        report["report_hash"]=digest({k:v for k,v in report.items() if k!="report_hash"})
        p["roles"]["worker"]["qualifications"]["cheap"]=report
        with self.assertRaises(ValueError): self.explain(c=c,p=p)

    def test_catalog_tamper_and_incompatible_schema_rejected(self):
        c=catalog(); c["schema_version"]=2
        with self.assertRaises(ValueError): CatalogSnapshot.from_dict(c)
        with tempfile.TemporaryDirectory() as d:
            store=CatalogStore(d); snapshot=store.publish(catalog())
            import pathlib
            pathlib.Path(d,snapshot.hash+".json").write_text("{}")
            with self.assertRaises(ValueError): store.load(snapshot.hash)

    def test_expected_escalation_must_have_eligible_configured_target(self):
        r=self.explain(req=dict(expected_input_tokens=100,expected_output_tokens=20,expected_escalations=1))
        self.assertIsNone(r["selected_alias"])
        self.assertIn("escalation_unavailable",r["excluded"]["baseline"])
        self.assertIsNone(r["expected_task_cost_usd"]["baseline"])

    def test_deadline_accounts_for_expected_repairs_and_escalation(self):
        self.assertIsNone(self.explain(req=dict(deadline_ms=150,expected_repairs=1))["selected_alias"])
        self.assertIsNone(self.explain(req=dict(deadline_ms=150,expected_escalations=1))["selected_alias"])

    def test_expected_token_counts_enforce_capacity(self):
        self.assertIsNone(self.explain(req=dict(expected_input_tokens=10001))["selected_alias"])
        self.assertIsNone(self.explain(req=dict(expected_output_tokens=2001))["selected_alias"])


class EvaluationTests(unittest.TestCase):
    def run_eval(self, rows=None, kind="measured"):
        return evaluate(records() if rows is None else rows, role="worker",evaluation_class="code",
                        catalog_hash="c"*64,policy_hash="e"*64,corpus_hash="d"*64,
                        candidate="cheap",baseline="baseline", evidence_kind=kind)

    def test_distinct_tasks_repeated_runs_and_cost_gate(self):
        r=self.run_eval()
        self.assertTrue(r["qualified"])
        self.assertEqual(r["candidate_metrics"]["distinct_tasks"],100)
        self.assertGreaterEqual(r["candidate_metrics"]["wilson_lower_95"],.9)
        self.assertEqual(r["candidate_metrics"]["tool_calls"],200)

    def test_mock_never_qualifies_and_repeats_are_not_independent(self):
        self.assertFalse(self.run_eval(kind="mock")["qualified"])
        rows=records()
        for i, row in enumerate(rows): row["task_id"]="one"; row["run_id"]=str(i//2)
        self.assertFalse(self.run_eval(rows)["qualified"])

    def test_unknown_cost_and_failed_attempts_remain_visible(self):
        rows=records(); rows[0]["cost_usd"]=None
        r=self.run_eval(rows)
        self.assertFalse(r["qualified"])
        self.assertIsNone(r["baseline_metrics"]["successful_task_cost_usd"])
        rows=records(); rows[1]["success"]=False
        r=self.run_eval(rows)
        self.assertEqual(r["candidate_metrics"]["successful_tasks"],99)
        self.assertGreater(r["candidate_metrics"]["successful_task_cost_usd"],.2)

    def test_invalid_numeric_and_duplicate_records_rejected(self):
        for value in [-1,float("nan"),float("inf")]:
            rows=records(); rows[0]["cost_usd"]=value
            with self.assertRaises(ValueError): self.run_eval(rows)
        rows=records(); rows.append(rows[0])
        with self.assertRaises(ValueError): self.run_eval(rows)

    def test_task_attempt_limits_and_pins_are_validated(self):
        rows=records(); rows[0]["repairs"]=2
        with self.assertRaises(ValueError): self.run_eval(rows)
        with self.assertRaises(ValueError):
            evaluate(records(),role="worker",evaluation_class="code",catalog_hash="bad",policy_hash="e"*64,
                     corpus_hash="d"*64,candidate="cheap",baseline="baseline",evidence_kind="measured")

    def test_critical_violation_and_missing_baseline_tasks_deny(self):
        rows=records(); rows[1]["critical_policy_violation"]=True
        self.assertFalse(self.run_eval(rows)["qualified"])
        rows=records(); rows[0]["critical_policy_violation"]=True
        self.assertFalse(self.run_eval(rows)["qualified"])
        self.assertFalse(self.run_eval([r for r in records() if r["model"]=="cheap"])["qualified"])

if __name__ == "__main__": unittest.main()
