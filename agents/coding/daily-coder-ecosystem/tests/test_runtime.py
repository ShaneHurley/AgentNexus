import json
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from daily_coder.acceptance import evaluate
from daily_coder.budget import BudgetExceeded, BudgetManager
from daily_coder.context import (
    build_packet, project_tool_results, plan_summary, implement_summary,
    diff_summary, should_stop_research, research_digest, research_card_body,
)
from daily_coder.evolution import EvolutionManager
from daily_coder.models import Invocation, InvocationResult, RunStatus
from daily_coder.orchestrator import Orchestrator
from daily_coder.policy import ApprovalRequired, PolicyGateway
from daily_coder.providers.http import extract_json, json_instruction_compact, schema_field_list
from daily_coder.providers.mock import MockProvider
from daily_coder.providers.openai_compat import OpenAICompatibleProvider
from daily_coder.secrets import SecretStore
from daily_coder.state_store import StateStore
from daily_coder.tool_broker import ToolBroker, ToolDenied, redact
from daily_coder.web import NetworkDenied, WebClient, validate_url
from daily_coder.workflow import workflow_for


class RuntimeFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = StateStore(self.root / "state.sqlite")
        self.store.create("r", "fix", str(self.root), "cfg", "create", live=True)
        self.store.set_profile("r", "S")

    def tearDown(self):
        self.tmp.cleanup()


class TestBudgetReservations(RuntimeFixture):
    def test_parallel_reservations_cannot_burst_cap(self):
        config = {"profiles": {"S": {"total_tokens": 100, "max_calls": 2, "frontier_calls": 0}},
                  "thresholds": {"reserve_fraction": 0.1, "warn_fraction": 0.7,
                                 "checkpoint_fraction": 0.8, "hard_stop_fraction": 0.9}}
        budget = BudgetManager(config, self.store)
        budget.reserve("r", "S", 50)
        with self.assertRaises(BudgetExceeded):
            budget.reserve("r", "S", 41)

    def test_threshold_levels(self):
        config = {"profiles": {"S": {"total_tokens": 100, "max_calls": 10}},
                  "thresholds": {"reserve_fraction": 0.1, "warn_fraction": 0.7,
                                 "checkpoint_fraction": 0.8, "hard_stop_fraction": 0.9}}
        budget = BudgetManager(config, self.store)
        budget.reserve("r", "S", 71)
        self.assertEqual(budget.level("r", "S"), "warn")

    def test_release_removes_empty_reservation_entries(self):
        config={"profiles":{"S":{"total_tokens":1000,"max_calls":10}},"thresholds":{"reserve_fraction":0.1}}
        budget=BudgetManager(config,self.store)
        budget.reserve("r","S",100); budget.release("r",100)
        self.assertNotIn("r",budget._reserved)
        self.assertNotIn("r",budget._reserved_calls)


class TestContext(unittest.TestCase):
    def test_role_packet_excludes_irrelevant_history(self):
        packet = {"ORIGINAL_REQUEST": "fix", "repo": ".", "profile": "M", "research_digest": [],
                  "decide": {"x": 1}, "plan": {"x": 2}, "implement": {"large": "x" * 1000}}
        sliced = build_packet("planner", packet)
        self.assertIn("decide", sliced)
        self.assertNotIn("implement", sliced)
        self.assertEqual(sliced["ORIGINAL_REQUEST"], "fix")

    def test_tool_projection_is_bounded_and_keeps_recent_results(self):
        results=[{"call_id":str(i),"tool":"filesystem.read","arguments":{"path":f"src/{i}.py"},"ok":True,
                  "result":{"content":"x"*5000,"sha256":str(i)}} for i in range(10)]
        projected=project_tool_results(results,max_chars=12000,recent=2)
        self.assertTrue(projected[0]["compacted"])
        self.assertEqual(projected[0]["evidence"][0]["arguments"],{"path":"src/0.py"})
        self.assertEqual(projected[-1]["call_id"],"9")
        self.assertLessEqual(len(json.dumps(projected)),12000)

    def test_plan_and_implement_digests(self):
        plan = {
            "file_allowlist": ["a.py"],
            "change_units": [{"id": "u1", "summary": "fix"}],
            "unresolved_questions": [],
            "verification_commands": ["pytest"],
            "rollback": "git checkout",
        }
        summary = plan_summary(plan)
        self.assertEqual(summary["change_unit_count"], 1)
        self.assertEqual(summary["verification_command_count"], 1)
        implement = {
            "changed_files": ["a.py"],
            "commands": [],
            "observations": ["very long observation that must not appear in digest"],
            "blocked": False,
        }
        impl = implement_summary(implement)
        self.assertEqual(impl["changed_files"], ["a.py"])
        self.assertEqual(impl["observation_count"], 1)
        self.assertNotIn("very long observation", json.dumps(impl))

    def test_diff_summary_omits_absent(self):
        self.assertIsNone(diff_summary(None))
        self.assertEqual(diff_summary({"unavailable": True}), {"unavailable": True})

    def test_alignment_slice_receives_summaries(self):
        packet = {
            "ORIGINAL_REQUEST": "fix",
            "decide": {"intent": "x"},
            "plan_summary": {"change_unit_count": 1},
            "implement_summary": {"changed_files": ["a.py"]},
        }
        sliced = build_packet("alignment_checker", packet, {"boundary": "PLAN"})
        self.assertIn("plan_summary", sliced)
        self.assertIn("implement_summary", sliced)
        self.assertEqual(sliced["boundary"], "PLAN")

    def test_should_stop_research(self):
        self.assertFalse(should_stop_research([]))
        self.assertFalse(should_stop_research([{"unknowns": []}]))
        self.assertTrue(should_stop_research([
            {"unknowns": [], "observations": []},
            {"unknowns": [], "observations": [{"label": "VERIFIED", "claim": "x", "locator": "a:1"}]},
        ]))
        self.assertFalse(should_stop_research([{"unknowns": []}, {"unknowns": ["x"]}]))
        self.assertFalse(should_stop_research([{"observations": []}, {"unknowns": []}]))  # missing unknowns
        self.assertFalse(should_stop_research([
            {"unknowns": [], "observations": [{"label": "UNKNOWN", "claim": "?", "locator": "m:0"}]},
            {"unknowns": [], "observations": []},
        ]))
        self.assertTrue(should_stop_research([
            {"lane": 0, "angle": "implementation sites", "card": {"unknowns": [], "observations": []}},
            {"lane": 1, "angle": "callers and dependents", "card": {"unknowns": [], "observations": []}},
        ]))
        closed_pair = [
            {"unknowns": [], "observations": []},
            {"unknowns": [], "observations": [{"label": "VERIFIED", "claim": "x", "locator": "a:1"}]},
        ]
        self.assertFalse(should_stop_research(closed_pair, min_cards=3))
        self.assertTrue(should_stop_research(closed_pair, min_cards=2))

    def test_research_digest_supports_wrapper_and_flat(self):
        flat = {
            "question": "q",
            "scope": "s",
            "observations": [{"label": "VERIFIED", "claim": "c", "locator": "f:1"}],
            "unknowns": ["u"],
            "limitations": ["l1", "l2", "l3", "l4"],
        }
        dig = research_digest([flat])
        self.assertEqual(dig[0]["question"], "q")
        self.assertEqual(dig[0]["unknowns"], ["u"])
        self.assertNotIn("lane", dig[0])
        self.assertEqual(dig[0]["limitations"], ["l1", "l2", "l3"])
        wrapped = {
            "lane": 2,
            "angle": "existing tests",
            "card": {
                "question": "inner-q",
                "scope": "inner-s",
                "observations": [{"label": "INFERENCE", "claim": "x", "locator": "t:2"}],
                "unknowns": [],
                "limitations": ["lim"],
            },
        }
        dig2 = research_digest([wrapped])
        self.assertEqual(dig2[0]["lane"], 2)
        self.assertEqual(dig2[0]["angle"], "existing tests")
        self.assertEqual(dig2[0]["question"], "inner-q")
        self.assertEqual(dig2[0]["limitations"], ["lim"])
        self.assertEqual(research_card_body(wrapped)["question"], "inner-q")
        self.assertEqual(research_card_body(flat)["question"], "q")


class TestOpenAIWire(unittest.TestCase):
    def test_compact_schema_instruction(self):
        schema = {"type": "object", "required": ["verdict"], "properties": {"verdict": {"type": "string"}, "findings": {"type": "array"}}}
        text = json_instruction_compact(schema)
        self.assertIn("verdict", text)
        self.assertNotIn('"type":"object"', schema_field_list(schema) and text or "")
        self.assertIn("required", text)

    def test_tool_roles_and_json_object(self):
        provider = OpenAICompatibleProvider(supports_json_response_format=True)
        captured = {}

        def fake_post(url, payload, headers, timeout=180, retries=3):
            captured["payload"] = payload
            return {
                "choices": [{"message": {"content": '{"verdict":"pass"}'}}],
                "usage": {"prompt_tokens": 1, "output_tokens": 1},
                "model": "gpt-4o-mini",
            }

        import daily_coder.providers.openai_compat as mod
        original = mod.post_json
        mod.post_json = fake_post
        try:
            request = Invocation(
                "r", "alignment_checker", "prompt", {"ORIGINAL_REQUEST": "x"}, "lowest", 100, "id",
                tools=(),
                tool_results=(
                    {"call_id": "c1", "tool": "filesystem.read", "arguments": {"path": "a.py"}, "turn": 0, "ok": True},
                    {"call_id": "c2", "tool": "filesystem.read", "arguments": {"path": "b.py"}, "turn": 0, "ok": True},
                ),
                output_schema={"type": "object", "required": ["verdict"], "properties": {"verdict": {"type": "string"}}},
            )
            provider.invoke(request)
            messages = captured["payload"]["messages"]
            self.assertEqual(messages[2]["role"], "assistant")
            self.assertEqual(len(messages[2]["tool_calls"]), 2)
            self.assertEqual(messages[3]["role"], "tool")
            self.assertEqual(messages[3]["tool_call_id"], "c1")
            self.assertIn("response_format", captured["payload"])
            self.assertEqual(captured["payload"]["response_format"]["type"], "json_object")
        finally:
            mod.post_json = original

    def test_missing_call_id_falls_back_to_user_tool_result(self):
        provider = OpenAICompatibleProvider()
        captured = {}

        def fake_post(url, payload, headers, timeout=180, retries=3):
            captured["payload"] = payload
            return {"choices": [{"message": {"content": "{}"}}], "usage": {}, "model": "m"}

        import daily_coder.providers.openai_compat as mod
        original = mod.post_json
        mod.post_json = fake_post
        try:
            request = Invocation(
                "r", "researcher", "prompt", {}, "lowest", 50, "id",
                tools=({"name": "filesystem.read"},),
                tool_results=({"call_id": "", "tool": "filesystem.read", "arguments": {}, "turn": 0, "ok": True},),
            )
            provider.invoke(request)
            self.assertTrue(any(
                m.get("role") == "user" and str(m.get("content", "")).startswith("TOOL_RESULT")
                for m in captured["payload"]["messages"]
            ))
            self.assertNotIn("response_format", captured["payload"])
            self.assertIn("tools", captured["payload"])
        finally:
            mod.post_json = original


class TestTrivialWorkflow(unittest.TestCase):
    def _package(self, d):
        source = Path(__file__).resolve().parents[1]
        package = Path(d) / "package"
        package.mkdir()
        for name in ("agents", "schemas", "skills", "config"):
            shutil.copytree(source / name, package / name)
        return package

    def test_trivial_run_skips_author_and_documenter(self):
        with tempfile.TemporaryDirectory() as d:
            package = self._package(d)
            store = StateStore(Path(d) / "state.sqlite")
            result = Orchestrator(package, store, MockProvider(), live=False).start("Fix typo", package)
            self.assertEqual(result["status"], "SIMULATED")
            sizing = Orchestrator(package, store, MockProvider(), live=False).artifacts.load_all(result["run_id"])["sizing"]
            self.assertEqual(sizing["workflow"], "S_TRIVIAL")
            self.assertEqual(sizing["profile"], "S")
            roles = [i["role"] for i in store.invocations(result["run_id"], 1000)]
            self.assertNotIn("test_author", roles)
            self.assertNotIn("documenter", roles)
            self.assertIn("alignment_checker", roles)

    def test_nontrivial_s_still_runs_documenter(self):
        with tempfile.TemporaryDirectory() as d:
            package = self._package(d)
            store = StateStore(Path(d) / "state.sqlite")
            result = Orchestrator(package, store, MockProvider(), live=False).start("Fix off-by-one in parser", package)
            self.assertEqual(result["status"], "SIMULATED", result)
            sizing = Orchestrator(package, store, MockProvider(), live=False).artifacts.load_all(result["run_id"])["sizing"]
            self.assertEqual(sizing["workflow"], "S")
            roles = [i["role"] for i in store.invocations(result["run_id"], 1000)]
            self.assertIn("documenter", roles)
            self.assertIn("test_author", roles)


class TestMaxRetries(unittest.TestCase):
    def test_schema_retry_recovers(self):
        source = Path(__file__).resolve().parents[1]
        class Flaky:
            name = "mock"
            def __init__(self):
                self.delegate = MockProvider()
                self.fails = 0
            def invoke(self, request):
                if request.role == "master" and self.fails < 1:
                    self.fails += 1
                    return InvocationResult(output={"intent": "incomplete"}, input_tokens=1, output_tokens=1, model="mock")
                return self.delegate.invoke(request)
        with tempfile.TemporaryDirectory() as d:
            package = Path(d) / "package"
            package.mkdir()
            for name in ("agents", "schemas", "skills", "config"):
                shutil.copytree(source / name, package / name)
            store = StateStore(Path(d) / "state.sqlite")
            result = Orchestrator(package, store, Flaky(), live=False).start("Fix typo", package)
            self.assertEqual(result["status"], "SIMULATED")
            self.assertEqual(result.get("repair_cycles", 0), 0)


class TestFrontierLastChance(unittest.TestCase):
    def test_exhausted_repair_skips_frontier(self):
        source = Path(__file__).resolve().parents[1]
        frontier_calls = []
        class AlwaysFail:
            name = "mock"
            def __init__(self):
                self.delegate = MockProvider()
            def invoke(self, request):
                if request.role == "frontier_advisor":
                    frontier_calls.append(request)
                    return self.delegate.invoke(request)
                if request.role == "failure_diagnostician":
                    return InvocationResult(output={
                        "failure_class": "orchestration",
                        "first_failing_signal": "x",
                        "evidence": [{"claim": "x", "locator": "t", "label": "VERIFIED"}],
                        "recommended_action": "repair",
                        "target_phase": "DECIDE",
                        "rationale": "retry",
                    }, model="mock")
                if request.role == "master":
                    raise RuntimeError("always")
                return self.delegate.invoke(request)
        with tempfile.TemporaryDirectory() as d:
            package = Path(d) / "package"
            package.mkdir()
            for name in ("agents", "schemas", "skills", "config"):
                shutil.copytree(source / name, package / name)
            store = StateStore(Path(d) / "state.sqlite")
            # live=True would wait for approval; use live=False so frontier is skipped by _maybe_frontier
            result = Orchestrator(package, store, AlwaysFail(), live=False).start("Fix typo", package)
            self.assertEqual(result["status"], "FAILED")
            self.assertEqual(frontier_calls, [])


class TestWorkflow(unittest.TestCase):
    def test_small_route_skips_fanout_and_brainstorm(self):
        route = workflow_for("S")
        self.assertNotIn("RESEARCH", route)
        self.assertNotIn("BRAINSTORM", route)
        self.assertIn("PLAN_REVIEW", route)

    def test_workflow_version(self):
        from daily_coder.workflow import WORKFLOW_VERSION
        self.assertEqual(WORKFLOW_VERSION, "2.1")


class TestPolicy(RuntimeFixture):
    def configs(self):
        tools = {"role_allowlists": {"implementer": ["filesystem.write", "filesystem.read"]},
                 "disabled_until_adapter_configured": []}
        policy = {"path_policy": {"deny": [".git/**", "**/.env"],
                                  "write_requires_plan_allowlist": True}}
        return tools, policy

    def test_gateway_requires_plan_approval(self):
        tools, policy = self.configs()
        broker = ToolBroker(self.root, tools, policy)
        gateway = PolicyGateway(broker, self.store, policy, approvals_required=True)
        with self.assertRaises(ApprovalRequired):
            gateway.execute("r", "implementer", "IMPLEMENT", "filesystem.write",
                            {"path": "src/a.py", "content": "x"}, ["src/**"], "plan")
        self.store.request_approval("r", "plan", "plan")
        self.store.decide_approval("r", "plan", "plan", "approved", "test")
        result = gateway.execute("r", "implementer", "IMPLEMENT", "filesystem.write",
                                 {"path": "src/a.py", "content": "x"}, ["src/**"], "plan")
        self.assertTrue(result["sha256"])

    def test_compare_and_swap_blocks_stale_write(self):
        tools, policy = self.configs()
        path = self.root / "a.py"; path.write_text("old", encoding="utf-8")
        broker = ToolBroker(self.root, tools, policy)
        with self.assertRaises(ToolDenied):
            broker.execute("implementer", "filesystem.write",
                           {"path": "a.py", "content": "new", "expected_sha256": "stale"}, ["a.py"])

    def test_patch_requires_compare_and_swap_hash(self):
        tools, policy = self.configs()
        tools["role_allowlists"]["implementer"].append("patch.apply")
        path = self.root / "a.py"; path.write_text("old", encoding="utf-8")
        broker = ToolBroker(self.root, tools, policy)
        with self.assertRaisesRegex(ToolDenied, "expected_sha256 is required"):
            broker.execute("implementer", "patch.apply",
                           {"path": "a.py", "find": "old", "replace": "new"}, ["a.py"])

    def test_patch_rejects_stale_hash_and_accepts_current_hash(self):
        tools, policy = self.configs()
        tools["role_allowlists"]["implementer"].append("patch.apply")
        path = self.root / "a.py"; path.write_text("old", encoding="utf-8")
        broker = ToolBroker(self.root, tools, policy)
        arguments = {"path": "a.py", "find": "old", "replace": "new"}
        with self.assertRaisesRegex(ToolDenied, "file changed since it was read"):
            broker.execute("implementer", "patch.apply",
                           {**arguments, "expected_sha256": "stale"}, ["a.py"])
        digest = hashlib.sha256(b"old").hexdigest()
        result = broker.execute("implementer", "patch.apply",
                                {**arguments, "expected_sha256": digest}, ["a.py"])
        self.assertTrue(result["applied"])

    def test_redaction(self):
        self.assertNotIn("abc123", redact("api_key=abc123"))

    def test_executable_path_is_rejected(self):
        tools = {"role_allowlists": {"researcher": ["shell.readonly"]}, "disabled_until_adapter_configured": []}
        policy = {"path_policy": {"deny": [], "write_requires_plan_allowlist": True},
                  "command_policy": {"allow": ["python"]}}
        broker = ToolBroker(self.root, tools, policy)
        with self.assertRaises(ToolDenied):
            broker.execute("researcher", "shell.readonly", {"argv": [str(Path(__file__).parent / "python"), "-V"]})

    def test_host_interpreter_is_denied_without_isolated_runner(self):
        tools = {"role_allowlists": {"researcher": ["shell.readonly"]}, "disabled_until_adapter_configured": []}
        policy = {"path_policy": {"deny": [], "write_requires_plan_allowlist": True},
                  "command_policy": {"allow": ["python"]}}
        broker = ToolBroker(self.root, tools, policy)
        with self.assertRaises(ToolDenied):
            broker.execute("researcher", "shell.readonly", {"argv": ["python", "-c", "print('no')"]})

    def test_compatibility_test_runner_cannot_bypass_isolation(self):
        tools = {"role_allowlists": {"researcher": ["tests.run"]}, "disabled_until_adapter_configured": []}
        policy = {"path_policy": {"deny": [], "write_requires_plan_allowlist": True},
                  "command_policy": {"allow": ["python"]}}
        broker = ToolBroker(self.root, tools, policy)
        with self.assertRaises(ToolDenied):
            broker.run_tests("researcher", ["python", "-c", "print('no')"])

    def test_detached_jobs_reject_unallowlisted_executable(self):
        class JobSpy:
            started = False

            def estimate(self, repo, argv):
                return None

            def start(self, *args, **kwargs):
                self.started = True
                return {"job_id": "unexpected"}

        orchestrator = object.__new__(Orchestrator)
        orchestrator.live = True
        orchestrator.state = SimpleNamespace(get=lambda _run_id: {"repo": str(self.root)},
                                             set_status=lambda *_args: None)
        orchestrator.jobs = JobSpy()
        orchestrator.config = {"job_timeout_s": 30}
        orchestrator.artifacts = SimpleNamespace(put=lambda *_args: None)
        broker = ToolBroker(self.root,
                            {"role_allowlists": {"test_executor": ["tests.run"]},
                             "disabled_until_adapter_configured": []},
                            {"command_policy": {"allow": ["python"]}})
        packet = {"plan": {"verification_commands": [["python", "-c", "print('no')"]]}}

        with self.assertRaisesRegex(ToolDenied, "isolated execution backend"):
            orchestrator._maybe_start_job("r", packet, broker)
        self.assertFalse(orchestrator.jobs.started)


class TestAcceptance(unittest.TestCase):
    def test_mock_is_never_verified(self):
        packet = {"decide": {"acceptance_criteria": ["x"]}, "plan": {"unresolved_questions": [], "file_allowlist": []},
                  "plan_review": {"verdict": "pass"}, "implement": {"changed_files": []},
                  "alignment": {"verdict": "pass"}, "test_design": {"test_required": False}}
        result = evaluate(run={}, packet=packet,
                          artifacts=[{"kind": k} for k in ("decide", "plan", "plan_review")],
                          approvals_ok=True, live=False, config={"acceptance": {}})
        self.assertEqual(result["verdict"], "simulated")

    def test_live_blocks_missing_test_evidence(self):
        packet = {"decide": {"acceptance_criteria": ["x"]}, "plan": {"unresolved_questions": [], "file_allowlist": ["a.py"]},
                  "plan_review": {"verdict": "pass"}, "implement": {"changed_files": ["a.py"]},
                  "alignment": {"verdict": "pass"}, "code_review": {"verdict": "pass"},
                  "test_design": {"test_required": True}, "test_execute": {"verdict": "inconclusive", "commands": []}}
        result = evaluate(run={"revision": "abc"}, packet=packet,
                          artifacts=[{"kind": k} for k in ("decide", "plan", "plan_review")],
                          approvals_ok=True, live=True, config={"acceptance": {}})
        self.assertEqual(result["verdict"], "fail")
        self.assertIn("test evidence is missing or not passing", result["failures"])

    def test_live_rejects_passing_verdict_with_failed_command(self):
        packet = {"decide": {"acceptance_criteria": ["x"]}, "plan": {"unresolved_questions": [], "file_allowlist": ["a.py"]},
                  "plan_review": {"verdict": "pass"}, "implement": {"changed_files": ["a.py"]},
                  "alignment": {"verdict": "pass"}, "code_review": {"verdict": "pass"},
                  "test_design": {"test_required": True},
                  "test_execute": {"verdict": "pass", "commands": [{"argv": ["pytest"], "returncode": 0}]}}
        result = evaluate(run={"revision": "abc"}, packet=packet,
                          artifacts=[{"kind": k} for k in ("decide", "plan", "plan_review")],
                          approvals_ok=True, live=True, config={"acceptance": {}},
                          verification_results=[{"decision": "allow", "returncode": 1, "timeout": False}])
        self.assertEqual(result["verdict"], "fail")

    def test_live_rejects_passing_verdict_with_failed_detached_job(self):
        packet = {"decide": {"acceptance_criteria": ["x"]}, "plan": {"unresolved_questions": [], "file_allowlist": ["a.py"]},
                  "plan_review": {"verdict": "pass"}, "implement": {"changed_files": ["a.py"]},
                  "alignment": {"verdict": "pass"}, "code_review": {"verdict": "pass"},
                  "test_design": {"test_required": True}, "job_evidence": {"state": "failed", "exit_code": 1},
                  "test_execute": {"verdict": "pass", "commands": [{"argv": ["pytest"], "returncode": 0}]}}
        result = evaluate(run={"revision": "abc"}, packet=packet,
                          artifacts=[{"kind": k} for k in ("decide", "plan", "plan_review")],
                          approvals_ok=True, live=True, config={"acceptance": {}},
                          job_results=[{"kind": "tests", "state": "failed", "exit_code": 1}])
        self.assertEqual(result["verdict"], "fail")

    def test_live_accepts_only_recorded_successful_test_results(self):
        packet = {"decide": {"acceptance_criteria": ["x"]}, "plan": {"unresolved_questions": [], "file_allowlist": ["a.py"]},
                  "plan_review": {"verdict": "pass"}, "implement": {"changed_files": ["a.py"]},
                  "alignment": {"verdict": "pass"}, "code_review": {"verdict": "pass"},
                  "test_design": {"test_required": True},
                  "test_execute": {"verdict": "pass", "commands": [{"argv": ["pytest"], "returncode": 0}]}}
        result = evaluate(run={"revision": "abc"}, packet=packet,
                          artifacts=[{"kind": k} for k in ("decide", "plan", "plan_review")],
                          approvals_ok=True, live=True, config={"acceptance": {}},
                          verification_results=[{"decision": "allow", "returncode": 0, "timeout": False}])
        self.assertEqual(result["verdict"], "pass")


class TestRecordedVerification(RuntimeFixture):
    def test_gateway_records_test_exit_status_without_output(self):
        tools = {"role_allowlists": {"test_executor": ["tests.run"]}, "disabled_until_adapter_configured": []}
        policy = {"path_policy": {"deny": [], "write_requires_plan_allowlist": True},
                  "execution_policy": {"isolated_tools": ["tests.run"]},
                  "command_policy": {"allow": ["python"]}}
        from agent_core.isolation import DockerRunner
        from unittest.mock import patch
        runner = DockerRunner("python@sha256:" + "a" * 64, self.root)
        broker = ToolBroker(self.root, tools, policy, isolated_runner=runner)
        patched = patch.object(DockerRunner, "run", return_value={"returncode": 0, "timeout": False, "stdout": "ok", "stderr": ""})
        patched.start()
        self.addCleanup(patched.stop)
        gateway = PolicyGateway(broker, self.store, policy, approvals_required=False)
        gateway.execute("r", "test_executor", "TEST_EXECUTE", "tests.run",
                        {"argv": ["python", "-c", "print('ok')"]})
        call = self.store.tool_calls("r")[0]
        summary = json.loads(call["result_summary"])
        self.assertEqual(summary, {"returncode": 0, "timeout": False})
        self.assertNotIn("stdout", summary)


class TestSecrets(unittest.TestCase):
    def test_list_never_returns_value(self):
        with tempfile.TemporaryDirectory() as d:
            store = SecretStore(Path(d) / "secrets.json", allow_insecure_file=True)
            store._keyring = None
            store.set("OPENAI_API_KEY", "very-secret-value")
            listed = store.list()
            self.assertNotIn("value", listed[0])
            self.assertEqual(store.get("OPENAI_API_KEY"), "very-secret-value")

    def test_plaintext_fallback_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            store = SecretStore(Path(d) / "secrets.json")
            store._keyring = None
            with self.assertRaises(RuntimeError):
                store.set("OPENAI_API_KEY", "secret")


class TestProviderParsing(unittest.TestCase):
    def test_extract_json_from_fence(self):
        self.assertEqual(extract_json('```json\n{"ok": true}\n```'), {"ok": True})


class TestState(RuntimeFixture):
    def test_duplicate_invocation_is_idempotent_for_cost_and_usage(self):
        arguments = ("r", "researcher", "RESEARCH", 0, 0, "lowest", "mock",
                     10, 5, 0.02, 10, "ok", None, "same-call")
        self.store.record_invocation(*arguments)
        self.store.record_invocation(*arguments)
        self.assertEqual(self.store.get("r")["est_usd"], 0.02)
        self.assertEqual(self.store.total_usage("r"), {"calls": 1, "tokens": 15})

    def test_status_is_separate_from_phase(self):
        self.store.set_status("r", RunStatus.WAITING_HUMAN)
        row = self.store.get("r")
        self.assertEqual(row["phase"], "NEW")
        self.assertEqual(row["status"], "WAITING_HUMAN")

    def test_job_duration_history(self):
        self.store.create_job("j", "r", "tests", ["python", "-V"], self.root, self.root / "j.log", "fp", 30)
        self.store.start_job("j", 999999)
        self.store.finish_job("j", "succeeded", 0, "hash")
        estimate = self.store.duration_estimate("fp")
        self.assertEqual(estimate["samples"], 1)

    def test_job_terminal_state_is_compare_and_swap(self):
        self.store.create_job("terminal", "r", "tests", ["python", "-V"], self.root, self.root / "j.log", "fp2", 30)
        self.store.start_job("terminal", 999999)
        self.assertTrue(self.store.finish_job("terminal", "succeeded", 0, "hash"))
        self.assertFalse(self.store.finish_job("terminal", "cancelled", None, None))
        self.assertEqual(self.store.get_job("terminal")["state"], "succeeded")

    def test_metrics_aggregate_groups_roles(self):
        self.store.record_invocation("r","planner","PLAN",0,0,"mid","mock",10,5,0.0,20,"ok",None,"inv")
        result=self.store.metrics_aggregate()
        self.assertEqual(result["roles"][0]["calls"],1)

    def test_wait_transition_sets_phase_and_status_atomically(self):
        self.store.transition_status("r", "WAITING_HUMAN", "WAITING_HUMAN", {"approval": "p"}, "wait")
        row = self.store.get("r")
        self.assertEqual((row["phase"], row["status"]), ("WAITING_HUMAN", "WAITING_HUMAN"))


class TestEvolution(RuntimeFixture):
    def test_one_candidate_and_human_gated_promotion(self):
        path = self.root / "skills" / "example" / "SKILL.md"
        path.parent.mkdir(parents=True); path.write_text("old", encoding="utf-8")
        manager = EvolutionManager(self.root, self.store, self.root / "history")
        candidate = manager.propose("skill", "skills/example/SKILL.md", "new", "fix", ["run:r"])
        with self.assertRaises(RuntimeError):
            manager.propose("skill", "skills/example/SKILL.md", "other", "fix", ["run:r"])
        with self.assertRaises(PermissionError):
            manager.promote(candidate, "human")
        self.assertEqual(manager.evaluate(candidate, {"score":1,"baseline":1}, {"score":1,"baseline":1}), "eligible")
        manager.promote(candidate, "human")
        self.assertEqual(path.read_text(encoding="utf-8"), "new")

    def test_target_scope_is_enforced(self):
        manager = EvolutionManager(self.root, self.store, self.root / "history")
        with self.assertRaises(PermissionError):
            manager.propose("harness", "daily_coder/policy.py", "unsafe", "no", ["run:r"])


class TestSkills(unittest.TestCase):
    def test_missing_selected_skill_fails_closed(self):
        from daily_coder.skills import SkillLibrary
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                SkillLibrary(d).load(["missing"])


class TestNetwork(unittest.TestCase):
    def test_private_target_is_denied(self):
        with self.assertRaises(NetworkDenied):
            validate_url("http://127.0.0.1/internal", {"deny_domains": []})

    def test_web_budget_is_thread_safe(self):
        import threading
        client = WebClient({"max_calls_per_run": 10})
        denials = []
        def hammer():
            for _ in range(20):
                try:
                    client._budget()
                except NetworkDenied:
                    denials.append(1)
        threads = [threading.Thread(target=hammer) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(client.calls, 10)
        self.assertGreater(len(denials), 0)


class TestResearchFanout(unittest.TestCase):
    L_REQUEST = "Add database validation across 2 files"

    def _package(self, d):
        source = Path(__file__).resolve().parents[1]
        package = Path(d) / "package"
        package.mkdir()
        for name in ("agents", "schemas", "skills", "config"):
            shutil.copytree(source / name, package / name)
        pricing_path = package / "config" / "pricing.json"
        pricing = json.loads(pricing_path.read_text(encoding="utf-8"))
        pricing["fake"] = {"input_per_1k": 0.0, "output_per_1k": 0.0}
        pricing_path.write_text(json.dumps(pricing), encoding="utf-8")
        return package

    def test_repo_map_none_when_not_live(self):
        with tempfile.TemporaryDirectory() as d:
            package = self._package(d)
            store = StateStore(Path(d) / "state.sqlite")
            orch = Orchestrator(package, store, MockProvider(), live=False)
            self.assertIsNone(orch._build_repo_map("unused", None))

    def test_early_stop_after_closed_batch(self):
        class ClosedResearch:
            name = "mock"
            def __init__(self):
                self.delegate = MockProvider()
                self.researcher_calls = 0
            def invoke(self, request):
                if request.role != "researcher":
                    return self.delegate.invoke(request)
                self.researcher_calls += 1
                return InvocationResult(output={
                    "question": request.input_packet.get("angle", "q"),
                    "scope": request.input_packet.get("angle", "s"),
                    "observations": [{"label": "VERIFIED", "claim": "seen", "locator": "f:1"}],
                    "unknowns": [],
                }, input_tokens=1, output_tokens=1, model="fake")
        with tempfile.TemporaryDirectory() as d:
            package = self._package(d)
            store = StateStore(Path(d) / "state.sqlite")
            provider = ClosedResearch()
            result = Orchestrator(package, store, provider, live=False).start(self.L_REQUEST, package)
            self.assertEqual(result["status"], "SIMULATED",
                             {"run": result, "events": store.events(result["run_id"]),
                              "researcher_calls": provider.researcher_calls})
            self.assertEqual(result["profile"], "L")
            self.assertEqual(provider.researcher_calls, 2) # root concurrency ceiling
            research = Orchestrator(package, store, MockProvider(), live=False).artifacts.load_all(result["run_id"])["research"]
            self.assertTrue(research["early_stop"])
            self.assertEqual(len(research["cards"]), 2)
            first = research["cards"][0]
            self.assertIn("lane", first)
            self.assertIn("angle", first)
            self.assertIn("card", first)
            self.assertIn("question", first["card"])

    def test_unknown_label_blocks_early_stop(self):
        class UnknownResearch:
            name = "mock"
            def __init__(self):
                self.delegate = MockProvider()
                self.researcher_calls = 0
            def invoke(self, request):
                if request.role != "researcher":
                    return self.delegate.invoke(request)
                self.researcher_calls += 1
                return InvocationResult(output={
                    "question": request.input_packet.get("angle", "q"),
                    "scope": request.input_packet.get("angle", "s"),
                    "observations": [{"label": "UNKNOWN", "claim": "?", "locator": "m:0"}],
                    "unknowns": [],
                }, input_tokens=1, output_tokens=1, model="fake")
        with tempfile.TemporaryDirectory() as d:
            package = self._package(d)
            store = StateStore(Path(d) / "state.sqlite")
            provider = UnknownResearch()
            result = Orchestrator(package, store, provider, live=False).start(self.L_REQUEST, package)
            self.assertEqual(result["status"], "SIMULATED", result)
            self.assertEqual(provider.researcher_calls, 5)
            research = Orchestrator(package, store, MockProvider(), live=False).artifacts.load_all(result["run_id"])["research"]
            self.assertFalse(research["early_stop"])
            self.assertEqual(len(research["cards"]), 5)


class TestApprovalResume(unittest.TestCase):
    def test_approved_plan_resumes_at_build_boundary(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            package = Path(d) / "package"
            package.mkdir()
            for name in ("agents", "schemas", "skills", "config"):
                shutil.copytree(source / name, package / name)
            store = StateStore(Path(d) / "state.sqlite")
            orchestrator = Orchestrator(package, store, MockProvider(), live=True)
            first = orchestrator.start("Fix typo", package)
            self.assertEqual(first["status"], "WAITING_HUMAN")
            self.assertTrue(first["plan_hash"])
            store.decide_approval(first["run_id"], "plan", first["plan_hash"], "approved", "test")
            resumed = orchestrator.run(first["run_id"])
            self.assertNotEqual(resumed["status"], "WAITING_HUMAN")
            self.assertNotEqual(resumed["phase"], "WAITING_HUMAN")

    def test_transient_provider_failure_retries_failed_phase(self):
        source = Path(__file__).resolve().parents[1]
        class FailOnce:
            name = "mock"
            def __init__(self): self.delegate = MockProvider(); self.failed = False
            def invoke(self, request):
                if request.role == "master" and not self.failed:
                    self.failed = True
                    raise RuntimeError("transient")
                if request.role == "failure_diagnostician":
                    return InvocationResult(output={"failure_class":"orchestration","first_failing_signal":"transient",
                        "evidence":[{"claim":"provider failed once","locator":"invocation:error","label":"VERIFIED"}],
                        "recommended_action":"repair","target_phase":"DECIDE","rationale":"retry the failed phase"},model="mock")
                return self.delegate.invoke(request)
        with tempfile.TemporaryDirectory() as d:
            package = Path(d) / "package"; package.mkdir()
            for name in ("agents", "schemas", "skills", "config"):
                shutil.copytree(source / name, package / name)
            store = StateStore(Path(d) / "state.sqlite")
            result = Orchestrator(package, store, FailOnce(), live=False).start("Fix typo", package)
            self.assertEqual(result["status"], "SIMULATED")
            self.assertEqual(result["repair_cycles"], 1)


if __name__ == "__main__":
    unittest.main()
