"""Regression tests for daily_coder.context ROLE_INPUTS and truncation."""
from __future__ import annotations

import json
import unittest

from daily_coder.context import (
    DIGEST_CHARS,
    MAX_FIELD_CHARS,
    PINNED,
    ROLE_INPUTS,
    build_packet,
    diff_summary,
    implement_summary,
    plan_summary,
)


class TestRoleInputs(unittest.TestCase):
    def _fat_packet(self) -> dict:
        return {
            "ORIGINAL_REQUEST": "fix bug",
            "task_anchor": "anchor",
            "constraints": ["c1"],
            "acceptance_criteria": ["ac"],
            "file_allowlist": ["a.py"],
            "permissions": {"write": True},
            "profile": "M",
            "repo": ".",
            "request": {"text": "fix"},
            "research_digest": [{"question": "q", "observations": []}],
            "plan": {"change_units": [{"id": "u1"}], "body": "x" * 8000},
            "plan_summary": plan_summary({"change_units": [{"id": "u1"}]}),
            "plan_slice": {"units": ["u1"]},
            "plan_hash": "abc",
            "decide": {"intent": "fix"},
            "test_design": {"cases": []},
            "implement": {"changed_files": ["a.py"], "observations": ["long prose"]},
            "implement_summary": implement_summary({"changed_files": ["a.py"]}),
            "diff": {"files": ["a.py"]},
            "diff_summary": diff_summary({"files": ["a.py"]}),
            "skills": ["skill-a"],
            "brainstorm": {"options": []},
            "diagnosis": {"class": "x"},
            "frontier_advice": {"tip": "t"},
            "verification_commands": ["pytest"],
            "test_author": {"status": "ok"},
            "failure": {"msg": "err"},
            "phase": "BUILD",
            "evidence": [{"claim": "c"}],
            "decision_brief": {"summary": "b"},
            "run_summary": {"roles": []},
            "boundary": "PLAN",
        }

    def test_documenter_must_not_get_full_plan_or_research(self):
        packet = self._fat_packet()
        sliced = build_packet("documenter", packet)
        self.assertIn("decide", sliced)
        self.assertIn("implement_summary", sliced)
        self.assertIn("diff_summary", sliced)
        for forbidden in (
            "plan",
            "plan_slice",
            "plan_hash",
            "research_digest",
            "research",
            "implement",
            "diff",
            "test_design",
            "skills",
        ):
            self.assertNotIn(forbidden, sliced, msg=f"documenter must not receive {forbidden}")

    def test_roles_only_receive_declared_keys_plus_pinned(self):
        packet = self._fat_packet()
        for role, keys in ROLE_INPUTS.items():
            sliced = build_packet(role, packet)
            allowed = set(PINNED) | set(keys)
            for key in sliced:
                self.assertIn(
                    key,
                    allowed,
                    msg=f"role {role} received undeclared key {key!r}",
                )
            for key in keys:
                if key in packet:
                    self.assertIn(key, sliced, msg=f"role {role} missing declared key {key!r}")

    def test_max_field_chars_truncation_in_build_packet(self):
        blob = "z" * (MAX_FIELD_CHARS + 500)
        packet = {"ORIGINAL_REQUEST": "x", "decide": blob}
        sliced = build_packet("planner", packet)
        val = sliced["decide"]
        self.assertIsInstance(val, dict)
        self.assertTrue(val.get("_truncated"))
        self.assertEqual(val["_chars"], len(blob))
        self.assertEqual(len(val["preview"]), MAX_FIELD_CHARS)

    def test_digest_helpers_respect_digest_chars(self):
        huge_plan = {
            "change_units": [{"id": f"u{i}", "summary": "s" * 200} for i in range(50)],
            "file_allowlist": [f"f{i}.py" for i in range(50)],
            "unresolved_questions": ["q"] * 20,
            "verification_commands": ["c"] * 20,
            "rollback": "x" * 5000,
        }
        summary = plan_summary(huge_plan)
        encoded = json.dumps(summary, sort_keys=True)
        if isinstance(summary, dict) and summary.get("_truncated"):
            self.assertLessEqual(len(summary["preview"]), DIGEST_CHARS)
        else:
            self.assertLessEqual(len(encoded), DIGEST_CHARS + 200)


if __name__ == "__main__":
    unittest.main()
