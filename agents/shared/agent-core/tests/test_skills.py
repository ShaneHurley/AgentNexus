"""Unit tests for agent_core.skills suite."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_core.skills import (
    compact_document,
    format_adr,
    generate_unified_diff,
    parse_adr,
    save_adr,
    scan_for_secrets,
    search_code,
    summarize_key_points,
    validate_patch,
    validate_python_code,
)


class TestAstValidator(unittest.TestCase):
    def test_valid_code(self):
        code = '''
"""Module docstring."""
import os
from sys import path

class MyClass:
    def method(self):
        return 42

async def async_worker():
    return True
'''
        res = validate_python_code(code)
        self.assertTrue(res["valid"])
        self.assertIsNone(res["syntax_error"])
        summary = res["ast_summary"]
        self.assertIn("MyClass", summary["classes"])
        self.assertIn("method", summary["functions"])
        self.assertIn("async_worker", summary["functions"])
        self.assertIn("os", summary["imports"])
        self.assertIn("sys.path", summary["imports"])
        self.assertTrue(summary["has_async"])
        self.assertEqual(summary["docstring"], "Module docstring.")
        self.assertGreater(summary["total_nodes"], 10)

    def test_syntax_error(self):
        code = "def broken_func(:\n    pass"
        res = validate_python_code(code)
        self.assertFalse(res["valid"])
        self.assertIsNotNone(res["syntax_error"])
        self.assertIn("Line 1", res["syntax_error"])
        self.assertEqual(res["ast_summary"], {})

    def test_invalid_type_input(self):
        res = validate_python_code(12345)  # type: ignore
        self.assertFalse(res["valid"])
        self.assertIn("Expected string", res["syntax_error"])


class TestDiffTool(unittest.TestCase):
    def test_generate_and_validate_patch(self):
        original = "def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n"
        modified = "def add(a, b):\n    # add docstring\n    return a + b\n\ndef sub(a, b):\n    return a - b\n"

        diff = generate_unified_diff(original, modified, fromfile="math.py", tofile="math.py")
        self.assertIn("--- math.py", diff)
        self.assertIn("+++ math.py", diff)
        self.assertIn("+    # add docstring", diff)

        patch_res = validate_patch(original, diff)
        self.assertTrue(patch_res["applicable"])
        self.assertEqual(patch_res["hunks_count"], 1)
        self.assertEqual(patch_res["applied_hunks"], 1)
        self.assertEqual(patch_res["additions"], 1)
        self.assertEqual(patch_res["deletions"], 0)
        self.assertEqual(patch_res["patched_text"], modified)

    def test_patch_mismatch(self):
        original = "line 1\nline 2\nline 3\n"
        # Patch expecting completely different content
        fake_patch = "--- a\n+++ b\n@@ -1,2 +1,2 @@\n-different line A\n+replacement\n context\n"
        patch_res = validate_patch(original, fake_patch)
        self.assertFalse(patch_res["applicable"])
        self.assertGreater(len(patch_res["failed_hunks"]), 0)
        self.assertIsNotNone(patch_res["error"])


class TestCodeSearch(unittest.TestCase):
    def test_search_code(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            f1 = tmp_path / "sample.py"
            f1.write_text("def find_me_now():\n    return 'magic_token_xyz'\n", encoding="utf-8")
            f2 = tmp_path / "ignore_dir" / "ignored.py"
            f2.parent.mkdir()
            f2.write_text("magic_token_xyz\n", encoding="utf-8")

            # Search with ignore_dirs
            results = search_code(tmp_path, "magic_token_xyz", extensions=[".py"], ignore_dirs=["ignore_dir"])
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["file"], "sample.py")
            self.assertEqual(results[0]["line"], 2)
            self.assertIn("magic_token_xyz", results[0]["content"])

    def test_regex_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            f = tmp_path / "code.py"
            f.write_text("VALUE_A = 100\nVALUE_B = 200\n", encoding="utf-8")

            results = search_code(tmp_path, r"VALUE_[A-Z]\s*=\s*\d+", is_regex=True)
            self.assertEqual(len(results), 2)


class TestSummarizer(unittest.TestCase):
    def test_short_document_unchanged(self):
        text = "Short brief note."
        res = compact_document(text, max_chars=100)
        self.assertEqual(res, text)

    def test_long_document_compaction(self):
        lines = ["# Title of Architecture", ""]
        lines.append("This is an introductory overview paragraph explaining the primary goals.")
        lines.append("")
        lines.append("## Core Features")
        for i in range(30):
            lines.append(f"- Feature item {i}: detailed description of capability and integration.")
        lines.append("")
        lines.append("## Final Conclusion")
        lines.append("This concludes the architecture document with final recommendations.")

        long_text = "\n".join(lines)
        compacted = compact_document(long_text, max_chars=500)
        self.assertLessEqual(len(compacted), 500)
        self.assertIn("Title of Architecture", compacted)

    def test_summarize_key_points(self):
        text = """
- First major point: high availability.
- Second major point: low latency routing.
- Third major point: zero trust security.
"""
        pts = summarize_key_points(text, max_points=2)
        self.assertEqual(len(pts), 2)
        self.assertIn("First major point", pts[0])
        self.assertIn("Second major point", pts[1])


class TestSecretScanner(unittest.TestCase):
    def test_openrouter_secret_detection(self):
        key = "sk-or-v1-" + ("1" * 64)
        text = f"client = OpenRouter(api_key='{key}')"
        secrets = scan_for_secrets(text)
        self.assertEqual(len(secrets), 1)
        self.assertEqual(secrets[0]["type"], "openrouter_api_key")
        self.assertTrue("..." in secrets[0]["redacted"] or "***" in secrets[0]["redacted"])
        self.assertNotIn(("1" * 64), secrets[0]["snippet"])

    def test_multiple_secrets(self):
        text = """
OPENAI_KEY = "sk-proj-123456789012345678901234567890123456789012345678"
GITHUB_PAT = "ghp_123456789012345678901234567890123456"
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
"""
        secrets = scan_for_secrets(text)
        types = [s["type"] for s in secrets]
        self.assertIn("openai_api_key", types)
        self.assertIn("github_pat", types)
        self.assertIn("aws_access_key_id", types)

    def test_no_secrets(self):
        text = "def calculate_area(width, height):\n    return width * height\n"
        secrets = scan_for_secrets(text)
        self.assertEqual(secrets, [])


class TestAdrGenerator(unittest.TestCase):
    def test_format_and_parse_adr(self):
        md = format_adr(
            title="Consolidate HTTP Transport into agent-core",
            status="Accepted",
            context="Both daily-coder and research-forge need standard HTTP transport and OpenRouter adapters.",
            decision="Move shared HTTP client and Provider models into agent_core.providers.",
            consequences="Reduces duplication, ensures unified retry and rate-limiting policies.",
            adr_id=1,
            date="2026-10-01",
            alternatives=["Duplicate provider code in both repos", "Use third-party requests library"],
        )
        self.assertIn("# ADR-1: Consolidate HTTP Transport into agent-core", md)
        self.assertIn("## Status\nAccepted", md)
        self.assertIn("## Decision", md)

        parsed = parse_adr(md)
        self.assertEqual(parsed["adr_id"], "1")
        self.assertEqual(parsed["title"], "Consolidate HTTP Transport into agent-core")
        self.assertEqual(parsed["status"], "Accepted")
        self.assertEqual(parsed["date"], "2026-10-01")
        self.assertIn("Both daily-coder and research-forge", parsed["context"])
        self.assertEqual(len(parsed["alternatives"]), 2)

    def test_save_adr(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = save_adr(
                directory=tmpdir,
                title="Use Hatchling Build Backend",
                status="Accepted",
                context="Research forge pyproject requires hatchling.",
                decision="Install hatchling in venv and configure .pth links.",
                consequences="Eliminates ModuleNotFoundError during packaging.",
                adr_id=5,
            )
            self.assertTrue(file_path.exists())
            self.assertTrue(file_path.name.startswith("0005-use-hatchling"))
            content = file_path.read_text(encoding="utf-8")
            self.assertIn("# ADR-0005: Use Hatchling Build Backend", content)


if __name__ == "__main__":
    unittest.main()
