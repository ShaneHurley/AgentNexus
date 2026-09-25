from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class IntegrityTests(unittest.TestCase):
    def test_study_hints_mentions_integrity(self) -> None:
        text = (ROOT / "skills" / "personal" / "study-hints" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Never impersonate", text)
        self.assertIn("hint", text.lower())

    def test_professor_email_calls_writing_improver(self) -> None:
        text = (ROOT / "skills" / "personal" / "professor-email" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("writing-improver", text)
        self.assertIn("F3", text)

    def test_lab_preflight_unknowns(self) -> None:
        text = (ROOT / "skills" / "personal" / "lab-preflight" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Do not invent", text)

    def test_resume_tailor_caps_and_no_documenter(self) -> None:
        text = (ROOT / "skills" / "personal" / "career-tools" / "resume-tailor.md").read_text(
            encoding="utf-8"
        ).lower()
        self.assertIn("two llm passes", text)
        self.assertIn("resume.yaml", text)
        self.assertIn("must not", text)
        self.assertIn("documenter", text)


if __name__ == "__main__":
    unittest.main()
