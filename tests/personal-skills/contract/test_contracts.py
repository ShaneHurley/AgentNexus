from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "schemas" / "personal"


class ContractTests(unittest.TestCase):
    def test_all_personal_schemas_parse(self) -> None:
        files = list(SCHEMAS.glob("*.schema.json"))
        self.assertGreaterEqual(len(files), 8)
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data.get("type"), "object")
            self.assertIn("title", data)

    def test_accomplishment_sample(self) -> None:
        sample = {
            "id": "ACC-2026-001",
            "context": "lab project",
            "action": "implemented logger",
            "result": "reduced debug time",
            "result_status": "USER_CONFIRMED",
            "confidentiality": "public",
        }
        schema = json.loads((SCHEMAS / "accomplishment.schema.json").read_text(encoding="utf-8"))
        for key in schema["required"]:
            self.assertIn(key, sample)


if __name__ == "__main__":
    unittest.main()
