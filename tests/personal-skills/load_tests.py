"""Load tests from nested personal-skills suites."""

from __future__ import annotations

import unittest
from pathlib import Path


def load_tests(loader, tests, pattern):  # noqa: ANN001
    suite = unittest.TestSuite()
    root = Path(__file__).resolve().parent
    for sub in ("routing", "contract", "integrity", "privacy", "regression"):
        suite.addTests(loader.discover(str(root / sub), pattern="test*.py"))
    return suite
