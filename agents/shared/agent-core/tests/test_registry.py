from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RegistryTests(unittest.TestCase):
    def test_validate_registry(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT))
        from agent_core.registry import validate_registry

        errors = validate_registry(ROOT / "registry.yaml")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
