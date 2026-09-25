from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ToolkitTests(unittest.TestCase):
    def test_adr_stages_documented(self) -> None:
        adr = (ROOT / "docs" / "decisions" / "0002-split-data-workflow.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("extraction", adr.lower())
        self.assertIn("visualization", adr.lower())

    def test_toolkit_skills_exist(self) -> None:
        for name in (
            "datasheet-extractor",
            "structured-data-evaluator",
            "claim-auditor",
            "visualization-specifier",
        ):
            path = ROOT / "skills" / "shared" / name / "SKILL.md"
            self.assertTrue(path.is_file(), name)

    def test_structured_data_forbids_mental_math(self) -> None:
        text = (
            ROOT / "skills" / "shared" / "structured-data-evaluator" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("mental math", text.lower())


if __name__ == "__main__":
    unittest.main()
