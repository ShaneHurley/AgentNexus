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





class TestRequiredContext(unittest.TestCase):
    def test_long_plan_and_sources_remain_structured(self):
        units=[{"id":"one","content":"x"*15000}]
        sources=[{"path":"a.py","sha256":"a"*64,"content":"x"*7000,"complete":True}]
        self.assertEqual(build_packet("implementer",{}, {"plan_slice":units})["plan_slice"],units)
        self.assertEqual(build_packet("planner",{}, {"SOURCE_SNAPSHOTS":sources})["SOURCE_SNAPSHOTS"],sources)
        self.assertEqual(build_packet("code_reviewer",{"plan":{"change_units":units}})["plan"],{"change_units":units})
    def test_required_oversize_has_structured_failure(self):
        from daily_coder.context import ContextCapacityError
        for field in ("TASK_CONTRACT","plan_slice","SOURCE_SNAPSHOTS","CANDIDATE_MANIFEST","VERIFICATION_EVIDENCE"):
            with self.subTest(field=field),self.assertRaises(ContextCapacityError) as caught:
                build_packet("implementer",{}, {field:{"body":"x"*24000}})
            self.assertEqual(caught.exception.as_dict()["reason_code"],"context_capacity")
            self.assertEqual(caught.exception.field,field)
    def test_write_feedback_compact_immutable_and_hash_bound(self):
        import hashlib
        from daily_coder.context import project_tool_results
        args={"path":"a.py","content":"x"*16000,"expected_sha256":"a"*64}
        item={"call_id":"call","operation_ref":"op","tool":"filesystem.write","ok":True,"arguments":args,"result":{"path":"a.py","sha256":"b"*64,"bytes":16000}}
        before=json.loads(json.dumps(item)); output=project_tool_results([item])
        self.assertEqual(item,before)
        self.assertLess(len(json.dumps(output)),1000)
        self.assertNotIn("arguments",output[0])
        self.assertEqual(output[0]["arguments_hash"],hashlib.sha256(json.dumps(args,sort_keys=True,default=str).encode()).hexdigest())
        self.assertEqual(output[0]["result"]["sha256"],"b"*64)
        self.assertEqual(output[0]["operation_ref"],"op")
    def test_older_source_fits_and_reduces_to_usable_metadata(self):
        from daily_coder.context import project_tool_results
        read={"call_id":"read","operation_ref":"read-op","tool":"filesystem.read","ok":True,"arguments":{"path":"a.py"},"result":{"path":"a.py","sha256":"a"*64,"start":1,"end":49,"total_lines":49,"truncated":False,"content":"x"*5000}}
        later=[{"call_id":str(i),"tool":"filesystem.list","operation_ref":str(i),"ok":True,"result":{}} for i in range(4)]
        output=project_tool_results([read]+later)
        self.assertEqual(output[0]["evidence"][0]["result"]["content"],read["result"]["content"])
        output=project_tool_results([read],max_chars=1000)
        meta=output[0]["result"]
        self.assertEqual(meta["sha256"],"a"*64)
        self.assertEqual((meta["start"],meta["end"],meta["total_lines"]),(1,49,49))
        self.assertTrue(meta["content_omitted"])
        self.assertFalse(meta["complete"])

    def test_packet_required_fields_are_selected_and_checked(self):
        from daily_coder.context import ContextCapacityError
        for role,key in (("planner","TASK_CONTRACT"),("planner","SOURCE_SNAPSHOTS"),("code_reviewer","CANDIDATE_MANIFEST"),("code_reviewer","VERIFICATION_EVIDENCE")):
            value={"body":"x"*15000}
            self.assertEqual(build_packet(role,{key:value})[key],value)
            with self.assertRaises(ContextCapacityError): build_packet(role,{key:{"body":"x"*24000}})

if __name__ == "__main__":
    unittest.main()
