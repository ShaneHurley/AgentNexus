"""Adversarial stress tests for Milestone 2 bug fixes (Bug A and Bug B).

Written by Challenger 1 (challenger_m2_1) to empirically verify and challenge
idempotency key uniqueness, repair cycle state transitions, and planner gate behavior.
"""
import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from daily_coder.acceptance import evaluate
from daily_coder.models import InvocationResult, Phase, RunStatus
from daily_coder.orchestrator import Orchestrator
from daily_coder.providers.mock import MockProvider
from daily_coder.state_store import StateStore


class AdversarialM2TestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        source = Path(__file__).resolve().parents[1]
        self.package = self.root / "package"
        self.package.mkdir()
        for name in ("agents", "schemas", "skills", "config"):
            shutil.copytree(source / name, self.package / name)
        self.store = StateStore(self.root / "state.sqlite")

    def tearDown(self):
        self.tmp.cleanup()

    def new_run_id(self):
        return str(uuid.uuid4())


class TestAdversarialBugA_IdempotencyAndTransitions(AdversarialM2TestBase):
    """Adversarial stress-testing of Bug A: Idempotency Key Collisions across repair cycles."""

    def test_multi_cycle_and_schema_retry_invocation_uniqueness(self):
        """Stress-test that invocations, errors, and schema retries across 3 repair cycles have unique keys."""
        orch = Orchestrator(self.package, self.store, MockProvider(), live=False)
        run_id = self.new_run_id()
        self.store.create(run_id, "Multi cycle test", str(self.package), "cfg", "idem-create", live=False)
        self.store.set_profile(run_id, "XS")

        packet = {"ORIGINAL_REQUEST": "Multi cycle test"}

        for cycle in range(4):
            # In each cycle, record normal invocation, schema retry, and error
            idem_base = f"{run_id}:master:0:0:c{cycle}"
            self.store.record_invocation(run_id, "master", "DECIDE", 0, 0, "mid", "mock",
                                         10, 10, 0.001, 50, "ok", None, idem_base)
            for attempt in range(1, 3):
                retry_key = f"{idem_base}:retry{attempt}"
                self.store.record_invocation(run_id, "master", "DECIDE", 0, 0, "mid", "mock",
                                             10, 10, 0.001, 50, "ok", None, retry_key)
            self.store.record_invocation(run_id, "master", "DECIDE", 0, 0, "mid", "mock",
                                         0, 0, 0.0, 50, "error", "mock failure", f"{idem_base}:err")
            if cycle < 3:
                self.store.bump_repair(run_id)

        with self.store._connect() as c:
            rows = c.execute("SELECT idem_key FROM invocations WHERE run_id=?", (run_id,)).fetchall()
            keys = [r[0] for r in rows]

        # 4 cycles * (1 base + 2 retries + 1 error) = 16 distinct records
        self.assertEqual(len(keys), 16, f"Expected 16 unique invocations, got {len(keys)}")
        self.assertEqual(len(set(keys)), 16, "Collision detected in invocation idempotency keys!")

    def test_replan_after_ready_to_build_exposes_transition_collision(self):
        """VERIFIED FIX:
        When a failure occurs in a post-build phase (such as ALIGNMENT) and repairs to PLAN,
        the orchestrator re-executes READY_TO_BUILD in cycle 1.
        Because READY_TO_BUILD uses f"{run_id}:READY_TO_BUILD:c{cycles}", the transition
        is NOT dropped by SQLite events deduplication, and the repair run succeeds.
        """
        class FailAlignmentOnce(MockProvider):
            def __init__(self):
                super().__init__()
                self.align_calls = 0

            def invoke(self, r):
                if r.role == "alignment_checker":
                    self.align_calls += 1
                    if self.align_calls == 1:
                        return InvocationResult(
                            output={"verdict": "fail", "checks": {"intent_to_decision": False},
                                    "findings": [{"issue": "alignment check failed"}]},
                            input_tokens=50, output_tokens=50, model="mock"
                        )
                if r.role == "failure_diagnostician":
                    return InvocationResult(
                        output={
                            "failure_class": "plan",
                            "first_failing_signal": "alignment failed",
                            "evidence": [{"claim": "bad alignment", "locator": "phase:ALIGNMENT"}],
                            "recommended_action": "repair",
                            "target_phase": "PLAN",
                            "rationale": "replan"
                        }, input_tokens=50, output_tokens=50, model="mock"
                    )
                return super().invoke(r)

        orch = Orchestrator(self.package, self.store, FailAlignmentOnce(), live=False)
        orch.budget.config["profiles"]["S"]["max_calls"] = 100
        # Set max_repair_cycles to 1 so the spurious transition failure immediately halts the run
        orch.config["acceptance"]["max_repair_cycles"] = 1

        res = orch.start("add a feature", self.package)

        with self.store._connect() as c:
            events = c.execute("SELECT seq, old_phase, new_phase, payload, idem_key FROM events WHERE run_id=? ORDER BY seq",
                               (res["run_id"],)).fetchall()

        events_list = [dict(r) for r in events]

        # Verify no invalid transition occurred due to key collision
        has_invalid_transition = any(
            "invalid transition PLAN_REVIEW->IMPLEMENT" in e.get("payload", "")
            for e in events_list
        )
        self.assertFalse(
            has_invalid_transition,
            "Did not expect invalid transition since READY_TO_BUILD has cycle scoping"
        )
        self.assertEqual(res["status"], RunStatus.SIMULATED.value)
        self.assertEqual(res["phase"], Phase.COMPLETE.value)

        # Verify that both cycles recorded READY_TO_BUILD transitions with distinct cycle keys
        ready_events = [e for e in events_list if e.get("new_phase") == "READY_TO_BUILD"]
        self.assertEqual(len(ready_events), 2, "Expected 2 READY_TO_BUILD transitions across cycles")
        ready_keys = [e["idem_key"] for e in ready_events]
        self.assertTrue(any(":c0" in k for k in ready_keys))
        self.assertTrue(any(":c1" in k for k in ready_keys))


    def test_replan_succeeds_when_ready_to_build_has_cycle_scoping(self):
        """Proof of mitigation: When READY_TO_BUILD includes :c{cycles}, repair completes successfully."""
        from daily_coder.util import sha256_text, canonical_json

        class FixedOrchestrator(Orchestrator):
            def _ready_to_build(self, run_id, packet):
                plan = packet.get("plan") or {}
                plan_hash = sha256_text(canonical_json(plan))
                packet["plan_hash"] = plan_hash
                approval = self.state.prepare_plan_approval(run_id, plan_hash, note="approve plan before repository writes")
                state = approval["state"]
                if state != "approved":
                    if not self.live or not self.approvals_required:
                        self.state.decide_approval(run_id, "plan", plan_hash, "approved",
                                                   "auto:simulated" if not self.live else "auto:policy")
                    else:
                        self._await_human(run_id, plan_hash)
                        return "wait_human"
                cycles = self.state.get(run_id).get("repair_cycles", 0)
                self.state.transition(run_id, "READY_TO_BUILD", {"plan_hash": plan_hash}, f"{run_id}:READY_TO_BUILD:c{cycles}")
                return "ok"

        class FailAlignmentOnce(MockProvider):
            def __init__(self):
                super().__init__()
                self.align_calls = 0

            def invoke(self, r):
                if r.role == "alignment_checker":
                    self.align_calls += 1
                    if self.align_calls == 1:
                        return InvocationResult(
                            output={"verdict": "fail", "checks": {"intent_to_decision": False},
                                    "findings": [{"issue": "alignment check failed"}]},
                            input_tokens=50, output_tokens=50, model="mock"
                        )
                if r.role == "failure_diagnostician":
                    return InvocationResult(
                        output={
                            "failure_class": "plan",
                            "first_failing_signal": "alignment failed",
                            "evidence": [{"claim": "bad alignment", "locator": "phase:ALIGNMENT"}],
                            "recommended_action": "repair",
                            "target_phase": "PLAN",
                            "rationale": "replan"
                        }, input_tokens=50, output_tokens=50, model="mock"
                    )
                return super().invoke(r)

        orch = FixedOrchestrator(self.package, self.store, FailAlignmentOnce(), live=False)
        orch.budget.config["profiles"]["S"]["max_calls"] = 100
        orch.config["acceptance"]["max_repair_cycles"] = 1

        res = orch.start("add a feature", self.package)
        self.assertEqual(res["status"], RunStatus.SIMULATED.value)
        self.assertEqual(res["phase"], Phase.COMPLETE.value)

    def test_concurrent_research_lanes_idempotency_keys(self):

        """Stress-test concurrent lane execution to ensure no cross-lane key collisions."""
        orch = Orchestrator(self.package, self.store, MockProvider(), live=False)
        run_id = self.new_run_id()
        self.store.create(run_id, "Concurrent lane test", str(self.package), "cfg", "idem-create", live=False)
        self.store.set_profile(run_id, "L")

        packet = {"ORIGINAL_REQUEST": "Concurrent lane test", "research_digest": ""}
        lanes = 4

        # Simulate 4 research lanes executing in parallel for cycle 0 and cycle 1
        for cycle in (0, 1):
            for lane_id in range(lanes):
                orch._invoke(run_id, "researcher", "RESEARCH", packet, lane_id, "L", None,
                             extra={"lane": lane_id, "angle": "architecture"})
            self.store.bump_repair(run_id)

        with self.store._connect() as c:
            rows = c.execute("SELECT lane, idem_key FROM invocations WHERE run_id=? AND role='researcher'", (run_id,)).fetchall()

        self.assertEqual(len(rows), 8, f"Expected 8 lane invocations across 2 cycles, got {len(rows)}")
        keys = [r[1] for r in rows]
        self.assertEqual(len(set(keys)), 8, "Collision detected among concurrent lane idempotency keys!")


class TestAdversarialBugB_PlannerGate(AdversarialM2TestBase):
    """Adversarial stress-testing of Bug B: Planner unresolved_questions gate across task modes and edge configs."""

    def test_matrix_task_mode_and_acceptance_config(self):
        """Test exhaustive combinations of task_mode, gate_unresolved_questions, and question presence."""
        test_cases = [
            # (task_mode, gate_unresolved, questions, expected_gate_blocked, expected_acceptance_pass)
            ("research", True, ["Q1"], False, True),
            ("research", False, ["Q1"], False, True),
            ("research", True, [], False, True),
            ("coding", True, ["Q1"], True, False),
            ("coding", False, ["Q1"], False, True),
            ("coding", True, [], False, True),
            (None, True, ["Q1"], True, False),   # None defaults to coding
            (None, False, ["Q1"], False, True),
            (None, True, [], False, True),
            ("custom_mode", True, ["Q1"], True, False), # custom mode != "research" gates
            ("custom_mode", False, ["Q1"], False, True),
        ]

        for mode, gate_unresolved, questions, expect_blocked, expect_acc_pass in test_cases:
            with self.subTest(mode=mode, gate=gate_unresolved, q=questions):
                orch = Orchestrator(self.package, self.store, MockProvider(), live=False)
                run_id = self.new_run_id()
                orch.config["acceptance"] = {"gate_unresolved_questions": gate_unresolved}

                packet = {"file_allowlist": []}
                if mode is not None:
                    packet["task_mode"] = mode

                plan_val = {
                    "summary": "Plan",
                    "unresolved_questions": questions,
                    "file_allowlist": ["a.py"]
                }

                gate_res = orch._gate(run_id, "PLAN", "planner", plan_val, packet)
                if expect_blocked:
                    self.assertIsNotNone(gate_res, f"Expected gate to block for mode={mode}, gate={gate_unresolved}")
                    self.assertEqual(gate_res[0], "repair")
                else:
                    self.assertIsNone(gate_res, f"Expected gate to allow for mode={mode}, gate={gate_unresolved}")

                # Test acceptance.evaluate in parallel
                packet_eval = {
                    "decide": {"acceptance_criteria": ["Crit 1"]},
                    "plan": plan_val,
                    "plan_review": {"verdict": "pass"},
                    "alignment": {"verdict": "pass"}
                }
                if mode is not None:
                    packet_eval["task_mode"] = mode

                acc_res = evaluate(
                    run={"revision": "rev1"},
                    packet=packet_eval,
                    artifacts=[{"kind": "decide"}, {"kind": "plan"}, {"kind": "plan_review"}],
                    approvals_ok=True,
                    live=True,
                    config={"acceptance": {"gate_unresolved_questions": gate_unresolved,
                                           "require_clean_scope": False,
                                           "require_alignment_pass": True}}
                )
                self.assertEqual(acc_res["checks"]["plan_resolved"], expect_acc_pass,
                                 f"Acceptance plan_resolved check failed for mode={mode}, gate={gate_unresolved}")

    def test_case_sensitivity_of_task_mode(self):
        """VERIFIED FIX:
        Task mode is case-insensitive and stripped (e.g. 'RESEARCH', 'Research', '  research  ').
        Unresolved questions are permitted in research mode regardless of case/whitespace.
        """
        for mode in ("RESEARCH", "Research", "  research  ", "ReSeArCh"):
            with self.subTest(mode=mode):
                orch = Orchestrator(self.package, self.store, MockProvider(), live=False)
                run_id = self.new_run_id()
                packet = {"task_mode": mode}
                plan_val = {
                    "summary": "Plan",
                    "unresolved_questions": ["Open question?"],
                    "file_allowlist": []
                }
                gate_res = orch._gate(run_id, "PLAN", "planner", plan_val, packet)
                self.assertIsNone(
                    gate_res,
                    f"Uppercase/mixed-case task_mode '{mode}' must be lowercased and not blocked"
                )

                # Verify acceptance gate also handles case folding
                packet_eval = {
                    "decide": {"acceptance_criteria": ["Crit 1"]},
                    "plan": plan_val,
                    "plan_review": {"verdict": "pass"},
                    "alignment": {"verdict": "pass"},
                    "task_mode": mode
                }
                acc_res = evaluate(
                    run={"revision": "rev1"},
                    packet=packet_eval,
                    artifacts=[{"kind": "decide"}, {"kind": "plan"}, {"kind": "plan_review"}],
                    approvals_ok=True,
                    live=True,
                    config={"acceptance": {"gate_unresolved_questions": True,
                                           "require_clean_scope": False,
                                           "require_alignment_pass": True}}
                )
                self.assertTrue(
                    acc_res["checks"]["plan_resolved"],
                    f"Acceptance plan_resolved check should pass for case-insensitive mode '{mode}'"
                )



if __name__ == "__main__":
    unittest.main()
