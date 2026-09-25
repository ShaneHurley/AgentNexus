from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "schemas" / "personal"
CATALOG = ROOT / "skills" / "personal-catalog.yaml"


class RoutingTests(unittest.TestCase):
    def test_skill_route_schema_exists(self) -> None:
        path = SCHEMAS / "skill-route.schema.json"
        self.assertTrue(path.is_file())
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("selected_skill", schema["properties"])

    def test_catalog_resident_count(self) -> None:
        text = CATALOG.read_text(encoding="utf-8")
        # Count resident: true occurrences
        count = text.count("resident: true")
        self.assertLessEqual(count, 8)
        self.assertGreaterEqual(count, 1)

    def test_route_zero_or_one_shape(self) -> None:
        sample = {
            "request_id": "REQ-1",
            "selected_skill": "study-hints",
            "confidence": 0.9,
            "clarify": False,
            "escalate_to": None,
        }
        schema = json.loads((SCHEMAS / "skill-route.schema.json").read_text(encoding="utf-8"))
        for key in schema["required"]:
            self.assertIn(key, sample)


if __name__ == "__main__":
    unittest.main()
