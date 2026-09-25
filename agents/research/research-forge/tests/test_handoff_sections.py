from __future__ import annotations

from pathlib import Path

REQUIRED_HEADINGS = [
    "## 1. Repository and folder structure",
    "## 2. State and ledger schema",
    "## 3. Source, evidence, claim, idea, experiment, and handoff schemas",
    "## 4. Seventeen-role roster and boundaries",
    "## 5. Model-tier mapping and per-role budgets",
    "## 6. First-release adapters",
    "## 7. Policy Gateway and read-only guarantees",
    "## 8. Research DAG and phase transitions",
    "## 9. Clarification, sizing, routing, early-stop",
    "## 10. Context projection and compaction",
    "## 11. Principal Director packet and escalation",
    "## 12. Human and machine output contracts",
    "## 13. Test matrix, adversarial fixtures, baselines",
    "## 14. Smallest safe prototype (Wave 1 mock slice)",
    "## 15. Open decisions and UNKNOWNs",
    "### UNKNOWN list",
]


def test_implementation_handoff_sections(repo_root: Path) -> None:
    text = (repo_root / "docs" / "implementation-handoff.md").read_text(encoding="utf-8")
    for heading in REQUIRED_HEADINGS:
        assert heading in text, f"missing section: {heading}"
