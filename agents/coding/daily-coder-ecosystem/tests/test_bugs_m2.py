import json
import logging
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from daily_coder.acceptance import evaluate
from daily_coder.models import InvocationResult
from daily_coder.orchestrator import Orchestrator
from daily_coder.providers.mock import MockProvider
from daily_coder.schemas import SchemaError, SchemaRegistry
from daily_coder.state_store import StateStore


class BugM2TestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        source = Path(__file__).resolve().parents[1]
        self.package = self.root / "package"
        self.package.mkdir()
        for name in ("agents", "schemas", "skills", "config"):
            shutil.copytree(source / name, self.package / name)
        default_cfg_path = self.package / "config" / "default.json"
        if default_cfg_path.exists():
            cfg = json.loads(default_cfg_path.read_text(encoding="utf-8"))
            if "acceptance" in cfg and "gate_unresolved_questions" in cfg["acceptance"]:
                cfg["acceptance"].pop("gate_unresolved_questions", None)
                default_cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        self.store = StateStore(self.root / "state.sqlite")

    def tearDown(self):
        self.tmp.cleanup()

    def new_run_id(self):
        return str(uuid.uuid4())


class TestBugA_IdempotencyCycles(BugM2TestBase):
    """Bug A: Idempotency Key Collision in Repair Cycles."""

    def test_idem_key_includes_cycle_count(self):
        orch = Orchestrator(self.package, self.store, MockProvider(), live=False)
        run_id = orch.create("Fix typo", self.package)
        self.store.set_profile(run_id, "XS")

        packet = {"ORIGINAL_REQUEST": "Fix typo"}
        # Cycle 0
        orch._invoke(run_id, "master", "DECIDE", packet, 0, "XS", None)

        with self.store._connect() as c:
            keys = [r[0] for r in c.execute("SELECT idem_key FROM invocations WHERE run_id=?", (run_id,)).fetchall()]
        self.assertTrue(any(":c0" in k for k in keys), f"Expected :c0 in keys, got {keys}")

        # Bump repair cycle to 1
        self.store.bump_repair(run_id)
        orch._invoke(run_id, "master", "DECIDE", packet, 0, "XS", None)

        with self.store._connect() as c:
            keys_after = [r[0] for r in c.execute("SELECT idem_key FROM invocations WHERE run_id=?", (run_id,)).fetchall()]

        # Both c0 and c1 must be present without collision or drop
        has_c0 = any(":c0" in k for k in keys_after)
        has_c1 = any(":c1" in k for k in keys_after)
        self.assertTrue(has_c0, f"Expected :c0 in {keys_after}")
        self.assertTrue(has_c1, f"Expected :c1 in {keys_after}")
        self.assertEqual(len(keys_after), 2, f"Expected 2 invocations, got {len(keys_after)}")

    def test_error_key_includes_cycle_count(self):
        class ErrorProvider:
            name = "mock"
            def invoke(self, request):
                raise RuntimeError("simulated provider crash")

        orch = Orchestrator(self.package, self.store, ErrorProvider(), live=False)
        run_id = orch.create("Fix typo", self.package)
        self.store.set_profile(run_id, "XS")

        packet = {"ORIGINAL_REQUEST": "Fix typo"}
        # Cycle 0 error
        with self.assertRaises(RuntimeError):
            orch._invoke(run_id, "master", "DECIDE", packet, 0, "XS", None)

        # Bump to cycle 1
        self.store.bump_repair(run_id)
        # Cycle 1 error
        with self.assertRaises(RuntimeError):
            orch._invoke(run_id, "master", "DECIDE", packet, 0, "XS", None)

        with self.store._connect() as c:
            error_keys = [r[0] for r in c.execute("SELECT idem_key FROM invocations WHERE run_id=? AND status='error'", (run_id,)).fetchall()]

        self.assertIn(f"{run_id}:master:DECIDE:0:0:c0:err", error_keys)
        self.assertIn(f"{run_id}:master:DECIDE:0:0:c1:err", error_keys)
        self.assertEqual(len(error_keys), 2)

    def test_phase_transition_includes_cycle_count(self):
        run_id = self.new_run_id()
        self.store.create(run_id, "Fix typo", str(self.package), "cfg", "idem-create", live=False)
        self.store.set_profile(run_id, "XS")

        cycles_0 = self.store.get(run_id).get("repair_cycles", 0)
        self.assertEqual(cycles_0, 0)

        # Transition in cycle 0
        t0 = self.store.transition(run_id, "INTAKE", {"k": 0}, f"{run_id}:INTAKE:c{cycles_0}")
        self.assertTrue(t0)

        # Bump repair to 1
        self.store.bump_repair(run_id)
        cycles_1 = self.store.get(run_id).get("repair_cycles", 0)
        self.assertEqual(cycles_1, 1)

        # Transition in cycle 1 with :c1
        self.store.transition(run_id, "SIZE", {"k": 1}, f"{run_id}:SIZE:c{cycles_1}")

        with self.store._connect() as c:
            event_keys = [r[0] for r in c.execute("SELECT idem_key FROM events WHERE run_id=?", (run_id,)).fetchall()]

        self.assertIn(f"{run_id}:INTAKE:c0", event_keys)
        self.assertIn(f"{run_id}:SIZE:c1", event_keys)

    def test_full_repair_cycle_state_persistence(self):
        """Simulate a repair sequence and verify invocations and events across repair cycles."""
        class FailThenPass:
            name = "mock"
            def __init__(self):
                self.delegate = MockProvider()
                self.attempt = 0
            def invoke(self, request):
                if request.role == "planner" and self.attempt == 0:
                    self.attempt += 1
                    raise RuntimeError("Planner first attempt failure")
                if request.role == "failure_diagnostician":
                    return InvocationResult(output={
                        "failure_class": "plan",
                        "first_failing_signal": "Planner first attempt failure",
                        "evidence": [{"claim": "planner failed", "locator": "phase:PLAN", "label": "VERIFIED"}],
                        "recommended_action": "repair",
                        "target_phase": "PLAN",
                        "rationale": "retry planning phase"
                    }, model="mock")
                return self.delegate.invoke(request)

        orch = Orchestrator(self.package, self.store, FailThenPass(), live=False)
        res = orch.start("Fix typo", self.package)
        self.assertEqual(res["status"], "SIMULATED")
        self.assertEqual(res["repair_cycles"], 1)

        with self.store._connect() as c:
            invocations = c.execute("SELECT role, phase, idem_key, status FROM invocations WHERE run_id=?", (res["run_id"],)).fetchall()
            events = c.execute("SELECT new_phase, idem_key FROM events WHERE run_id=?", (res["run_id"],)).fetchall()

        # Invocations must include c0 and c1 keys
        c0_invs = [r for r in invocations if ":c0" in r[2]]
        c1_invs = [r for r in invocations if ":c1" in r[2]]
        self.assertTrue(len(c0_invs) > 0, "Expected cycle 0 invocations")
        self.assertTrue(len(c1_invs) > 0, "Expected cycle 1 invocations")

        # Events must include transitions for both cycles
        c0_events = [r for r in events if ":c0" in r[1]]
        c1_events = [r for r in events if ":c1" in r[1]]
        self.assertTrue(len(c0_events) > 0, "Expected cycle 0 events")
        self.assertTrue(len(c1_events) > 0, "Expected cycle 1 events")


class TestBugB_PlannerGateModeAwareness(BugM2TestBase):
    """Bug B: Planner unresolved_questions Gate Mode-Awareness."""

    def test_planner_gate_research_mode_allows_unresolved_questions(self):
        orch = Orchestrator(self.package, self.store, MockProvider(), live=False)
        run_id = self.new_run_id()
        packet = {
            "task_mode": "research",
            "file_allowlist": []
        }
        plan_value = {
            "summary": "Research findings and open design questions",
            "unresolved_questions": ["What database engine to select?", "How to handle auth?"],
            "file_allowlist": ["docs/architecture.md"]
        }
        gate_result = orch._gate(run_id, "PLAN", "planner", plan_value, packet)
        self.assertIsNone(gate_result, "Research mode must not trigger repair on unresolved questions")
        self.assertEqual(packet.get("file_allowlist"), ["docs/architecture.md"])

    def test_planner_gate_coding_mode_blocks_unresolved_questions(self):
        orch = Orchestrator(self.package, self.store, MockProvider(), live=False)
        run_id = self.new_run_id()
        packet = {
            "task_mode": "coding",
            "file_allowlist": []
        }
        plan_value = {
            "summary": "Incomplete plan",
            "unresolved_questions": ["Undecided sorting algorithm"],
            "file_allowlist": ["src/main.py"]
        }
        gate_result = orch._gate(run_id, "PLAN", "planner", plan_value, packet)
        self.assertEqual(gate_result, ("repair", "plan contains unresolved design decisions"))

    def test_planner_gate_coding_mode_default_fallback(self):
        orch = Orchestrator(self.package, self.store, MockProvider(), live=False)
        run_id = self.new_run_id()
        packet = {}  # No task_mode specified -> defaults to coding
        plan_value = {
            "summary": "Incomplete plan",
            "unresolved_questions": ["Undecided design"],
            "file_allowlist": ["src/main.py"]
        }
        gate_result = orch._gate(run_id, "PLAN", "planner", plan_value, packet)
        self.assertEqual(gate_result, ("repair", "plan contains unresolved design decisions"))

    def test_planner_gate_configurable_gate_unresolved_questions(self):
        orch = Orchestrator(self.package, self.store, MockProvider(), live=False)
        run_id = self.new_run_id()
        orch.config["acceptance"] = {"gate_unresolved_questions": False}
        packet = {"task_mode": "coding"}
        plan_value = {
            "summary": "Plan with questions, but gating is disabled",
            "unresolved_questions": ["Minor open question"],
            "file_allowlist": ["src/main.py"]
        }
        gate_result = orch._gate(run_id, "PLAN", "planner", plan_value, packet)
        self.assertIsNone(gate_result, "When gate_unresolved_questions is False, unresolved questions must not block")

    def test_acceptance_evaluate_mode_awareness(self):
        packet_research = {
            "task_mode": "research",
            "decide": {"acceptance_criteria": ["Criteria 1"]},
            "plan": {"unresolved_questions": ["Open question 1", "Open question 2"], "file_allowlist": []},
            "plan_review": {"verdict": "pass"},
            "alignment": {"verdict": "pass"}
        }
        res_research = evaluate(
            run={"revision": "rev1"},
            packet=packet_research,
            artifacts=[{"kind": "decide"}, {"kind": "plan"}, {"kind": "plan_review"}],
            approvals_ok=True,
            live=True,
            config={"acceptance": {"gate_unresolved_questions": True, "require_clean_scope": False, "require_alignment_pass": True}}
        )
        self.assertTrue(res_research["checks"].get("plan_resolved"))
        self.assertEqual(res_research["verdict"], "pass")

        packet_coding = {
            "task_mode": "coding",
            "decide": {"acceptance_criteria": ["Criteria 1"]},
            "plan": {"unresolved_questions": ["Open question 1"], "file_allowlist": []},
            "plan_review": {"verdict": "pass"},
            "alignment": {"verdict": "pass"}
        }
        res_coding = evaluate(
            run={"revision": "rev1"},
            packet=packet_coding,
            artifacts=[{"kind": "decide"}, {"kind": "plan"}, {"kind": "plan_review"}],
            approvals_ok=True,
            live=True,
            config={"acceptance": {"gate_unresolved_questions": True, "require_clean_scope": False, "require_alignment_pass": True}}
        )
        self.assertFalse(res_coding["checks"].get("plan_resolved"))
        self.assertIn("plan still contains unresolved questions", res_coding["failures"])
        self.assertEqual(res_coding["verdict"], "fail")


class TestBugC_DiagnosticianSchemaAndFallback(BugM2TestBase):
    """Bug C: Diagnostician Schema Relaxation, Exception Logging, and Fallback Diagnosis."""

    def test_diagnosis_schema_relaxation(self):
        registry = SchemaRegistry(self.package / "schemas")

        # Valid relaxed diagnosis with additionalProperties and flexible evidence
        relaxed_diagnosis = {
            "failure_class": "implementation",
            "first_failing_signal": "SyntaxError in test file",
            "evidence": [
                {"claim": "SyntaxError on line 12", "extra_evidence_detail": "Unexpected token ;"},
                "plain string evidence without object wrapper"
            ],
            "recommended_action": "retry",  # New action added to enum
            "rationale": "Model produced invalid token; retry will regenerate cleanly",
            "extra_top_level_field": "accepted because additionalProperties is true"
        }
        # Should not raise SchemaError
        registry.validate("diagnosis", relaxed_diagnosis)

    def test_diagnosis_schema_all_actions(self):
        registry = SchemaRegistry(self.package / "schemas")
        for action in ["repair", "stop", "escalate", "retry"]:
            data = {
                "failure_class": "plan",
                "first_failing_signal": "Error",
                "evidence": [{"claim": "claim 1"}],
                "recommended_action": action,
                "rationale": f"Testing action {action}"
            }
            registry.validate("diagnosis", data)

    def test_diagnosis_schema_still_rejects_missing_required(self):
        registry = SchemaRegistry(self.package / "schemas")
        with self.assertRaises(SchemaError):
            # Missing failure_class and rationale
            registry.validate("diagnosis", {"first_failing_signal": "err", "recommended_action": "repair"})

    def test_repair_logs_warning_and_synthesizes_fallback_on_diagnostician_crash(self):
        class CrashDiagnostician:
            name = "mock"
            def __init__(self):
                self.delegate = MockProvider()
            def invoke(self, request):
                if request.role == "failure_diagnostician":
                    raise RuntimeError("Diagnostician LLM failed or schema crashed")
                return self.delegate.invoke(request)

        orch = Orchestrator(self.package, self.store, CrashDiagnostician(), live=False)
        run_id = orch.create("Fix typo", self.package)
        self.store.set_profile(run_id, "XS")

        packet = {"ORIGINAL_REQUEST": "Fix typo", "plan": {"change_units": []}}

        with self.assertLogs("daily_coder", level=logging.WARNING) as cm:
            res = orch._repair(run_id, "PLAN_REVIEW", "verdict: fail", packet, depth=0)

        # 1. Warning log verified
        warning_logged = any(f"failure_diagnostician failed for run {run_id}" in m for m in cm.output)
        self.assertTrue(warning_logged, f"Expected warning log in {cm.output}")

        # 2. Fallback diagnosis synthesized in packet
        fallback = packet.get("diagnosis")
        self.assertIsNotNone(fallback)
        self.assertEqual(fallback["failure_class"], "plan")
        self.assertEqual(fallback["recommended_action"], "repair")
        self.assertIn("Fallback diagnosis generated", fallback["rationale"])

        # 3. Fallback validates against diagnosis schema
        orch.schema.validate("diagnosis", fallback)

        # 4. Fallback artifact stored
        stored = orch.artifacts.load(run_id, "diagnosis")
        self.assertIsNotNone(stored)
        self.assertEqual(stored["failure_class"], "plan")

    def test_repair_fallback_classification_for_implementation(self):
        class CrashDiagnostician:
            name = "mock"
            def __init__(self):
                self.delegate = MockProvider()
            def invoke(self, request):
                if request.role == "failure_diagnostician":
                    raise RuntimeError("Diagnostician crashed")
                return self.delegate.invoke(request)

        orch = Orchestrator(self.package, self.store, CrashDiagnostician(), live=False)
        run_id = orch.create("Fix typo", self.package)
        self.store.set_profile(run_id, "XS")

        packet = {"ORIGINAL_REQUEST": "Fix typo"}
        orch._repair(run_id, "TEST_EXECUTE", "tests failed", packet, depth=0)

        fallback = packet.get("diagnosis")
        self.assertIsNotNone(fallback)
        self.assertEqual(fallback["failure_class"], "implementation")
        self.assertEqual(fallback["target_phase"], "TEST_EXECUTE")


if __name__ == "__main__":
    unittest.main()
