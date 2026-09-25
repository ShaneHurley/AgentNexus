from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class RegressionTests(unittest.TestCase):
    def test_six_uf_agents_still_listed(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for name in (
            "deep-research",
            "research-messenger",
            "plan-prep",
            "use-master",
            "daily-coder",
            "researcher",
        ):
            self.assertIn(name, text)

    def test_ide_pack_exists(self) -> None:
        self.assertTrue((ROOT / "ide-pack" / "ide-agents").is_dir())

    def test_no_personal_orchestrator_package(self) -> None:
        self.assertFalse((ROOT / "personal-orchestrator").exists())


if __name__ == "__main__":
    unittest.main()
