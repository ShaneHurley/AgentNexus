from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class WritingLintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "agent-core"))

    def test_rejects_em_dash(self) -> None:
        from agent_core.writing_lint import check_punctuation, may_complete

        findings = check_punctuation("Hello — world")
        self.assertTrue(findings)
        ok, _ = may_complete("Hello — world")
        self.assertFalse(ok)

    def test_rejects_repetition(self) -> None:
        from agent_core.writing_lint import check_repetition

        text = (
            "Please send the lab report by Friday afternoon. "
            "Please send the lab report by Friday afternoon."
        )
        self.assertTrue(check_repetition(text))

    def test_clean_text_may_complete(self) -> None:
        from agent_core.writing_lint import may_complete

        ok, findings = may_complete(
            "Hello Professor Smith. I have a question about the lab deadline on Friday."
        )
        self.assertTrue(ok, findings)

    def test_confidential_exclusion_fixture(self) -> None:
        fixture = (
            ROOT
            / "tests"
            / "writing"
            / "fixtures"
            / "confidential_must_not_appear.md"
        )
        self.assertTrue(fixture.is_file())
        public = (
            ROOT / "tests" / "writing" / "fixtures" / "public_resume_safe.md"
        ).read_text(encoding="utf-8")
        secret = "ACME_INTERNAL_REVENUE_NUMBER"
        self.assertNotIn(secret, public)

    def test_no_self_approval_rule_documented(self) -> None:
        text = (ROOT / "docs" / "shared-toolkit" / "writing-improver.md").read_text(
            encoding="utf-8"
        )
        contract = (
            ROOT
            / "agent-core"
            / "shared-agents"
            / "artifact-style-enforcer"
            / "contract.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("fail-closed", text.lower())
        self.assertIn("judge_factual_accuracy", contract)


if __name__ == "__main__":
    unittest.main()
