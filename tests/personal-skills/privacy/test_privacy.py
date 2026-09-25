from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class PrivacyTests(unittest.TestCase):
    def test_browser_handoff_persisted_false(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "personal" / "browser-handoff.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(schema["properties"]["persisted"].get("const"), False)

    def test_career_confidential_not_in_public_resume_rule(self) -> None:
        text = (ROOT / "skills" / "personal" / "career-tools" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("confidential", text.lower())
        self.assertIn("personal-store", text)

    def test_personal_store_export_purge(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "agent-core"))
        from agent_core.personal_store import (
            append_accomplishment,
            delete_store,
            export_store,
            ensure_layout,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "career"
            ensure_layout(root)
            draft = Path(tmp) / "acc.json"
            draft.write_text(
                json.dumps(
                    {
                        "id": "ACC-2026-001",
                        "context": "x",
                        "action": "y",
                        "result_status": "USER_CONFIRMED",
                        "confidentiality": "employer_confidential",
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(append_accomplishment(root, draft, confirm=True), 0)
            dest = Path(tmp) / "export"
            self.assertEqual(export_store(root, dest), 0)
            self.assertTrue((dest / "accomplishments.jsonl").is_file())
            self.assertEqual(delete_store(root, confirm=True), 0)
            self.assertFalse(root.exists())


if __name__ == "__main__":
    unittest.main()
