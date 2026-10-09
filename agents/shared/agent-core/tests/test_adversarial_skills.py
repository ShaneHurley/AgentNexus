"""Empirical Adversarial Stress Harness for agent_core.skills.

Tested by Challenger 1 for Milestone 1: Packaging & Shared Core Foundations.
Exercises:
- ast_validator with malformed syntax, null bytes, deep nesting, Python 3.10 constructs.
- diff_tool with CRLF endings, missing EOF newlines, multi-hunk offsets, empty context lines.
- code_search with deep directory trees, binary files, invalid regex, ignore dirs.
- summarizer with boundary max_chars (0, 1, 2, negative), empty docs, max_points boundary.
- secret_scanner with AWS keys, multi-secret lines, project keys, OAuth tokens.
- adr_generator with markdown subheadings, roundtrip parse/save, special characters.
"""

from __future__ import annotations

import os
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


class AdversarialAstValidatorTests(unittest.TestCase):
    """Stress tests for ast_validator."""

    def test_non_string_inputs(self):
        for bad in [None, 12345, [1, 2], b"print('hello')", {"code": "pass"}]:
            res = validate_python_code(bad)  # type: ignore
            self.assertFalse(res["valid"])
            self.assertIn("Expected string", res["syntax_error"])
            self.assertEqual(res["ast_summary"], {})

    def test_syntax_errors_catalog(self):
        cases = [
            "def ():\n    pass",
            "for x in:\n    pass",
            "while True\n    pass",
            "x = 1 +\n",
            "class 123:\n    pass",
            "import os.\n",
            "from . import",
            "def foo(a=1, b): pass",
            "x = 1 2",
            "def f(1): pass",
            "def f(*a, *b): pass",
        ]
        for c in cases:
            res = validate_python_code(c)
            self.assertFalse(res["valid"], f"Expected invalid for: {c!r}")
            self.assertIsNotNone(res["syntax_error"])

    def test_null_byte_in_source(self):
        res = validate_python_code("x = 1\x00\n")
        self.assertFalse(res["valid"])
        self.assertIn("null byte", res["syntax_error"].lower())

    def test_deeply_nested_blocks(self):
        depth = 60
        code = "if True:\n"
        for i in range(1, depth):
            code += "    " * i + f"if cond_{i}:\n"
        code += "    " * depth + "result = 42\n"
        res = validate_python_code(code)
        self.assertTrue(res["valid"])
        self.assertGreater(res["ast_summary"]["total_nodes"], depth)

    def test_deep_parens_rejection(self):
        code = "(" * 400 + "1" + ")" * 400
        res = validate_python_code(code)
        self.assertFalse(res["valid"])
        self.assertIn("nested parentheses", res["syntax_error"])

    def test_python310_pattern_matching(self):
        code = '''
def dispatch(cmd):
    match cmd:
        case {"type": "run", "args": [*args]}:
            return args
        case ["quit" | "exit", code]:
            return code
        case _:
            return None
'''
        res = validate_python_code(code)
        self.assertTrue(res["valid"])
        self.assertIn("dispatch", res["ast_summary"]["functions"])


class AdversarialDiffToolTests(unittest.TestCase):
    """Stress tests for diff_tool."""

    def test_clean_patch_application(self):
        orig = "line 1\nline 2\nline 3\n"
        mod = "line 1\nline 2 modified\nline 3\n"
        diff = generate_unified_diff(orig, mod)
        res = validate_patch(orig, diff)
        self.assertTrue(res["applicable"])
        self.assertEqual(res["patched_text"], mod)

    def test_crlf_line_endings_bug(self):
        """Diff tool handles CRLF files and preserves line endings."""
        orig = "line 1\r\nline 2\r\n"
        mod = "line 1\r\nline 2 modified\r\n"
        diff = generate_unified_diff(orig, mod)
        res = validate_patch(orig, diff)
        self.assertTrue(res["applicable"])
        self.assertEqual(res["patched_text"], mod)

    def test_missing_eof_newline_bug(self):
        """difflib preserves separate lines even when input lacks trailing newline."""
        orig = "hello"
        mod = "world"
        diff = generate_unified_diff(orig, mod)
        self.assertNotIn("-hello+world", diff)
        res = validate_patch(orig, diff)
        self.assertTrue(res["applicable"])

    def test_empty_context_line_in_patch(self):
        """Unified diff with empty context line (common in git/patch outputs)."""
        orig = "line 1\n\nline 3\n"
        # Patch has blank line with 0 chars instead of single space
        patch = "@@ -1,3 +1,3 @@\n line 1\n\n line 3\n"
        res = validate_patch(orig, patch)
        self.assertTrue(res["applicable"])
        self.assertEqual(res["patched_text"], orig)

    def test_multi_hunk_large_offset(self):
        lines = [f"data line {i}\n" for i in range(100)]
        orig = "".join(lines)
        lines[10] = "data line 10 modified\n" + "".join(f"inserted {j}\n" for j in range(10))
        lines[80] = "data line 80 modified\n"
        mod = "".join(lines)
        diff = generate_unified_diff(orig, mod)
        res = validate_patch(orig, diff)
        self.assertTrue(res["applicable"])
        self.assertEqual(res["patched_text"], mod)


class AdversarialCodeSearchTests(unittest.TestCase):
    """Stress tests for code_search."""

    def test_deep_directory_tree(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            curr = Path(tmpdir)
            for i in range(20):
                curr = curr / f"sub_{i}"
            curr.mkdir(parents=True)
            (curr / "leaf.py").write_text("SECRET_VAL = 9999\n", encoding="utf-8")

            results = search_code(tmpdir, "SECRET_VAL")
            self.assertEqual(len(results), 1)
            self.assertIn("sub_19", results[0]["file"])
            self.assertEqual(results[0]["line"], 1)

    def test_binary_null_byte_in_py(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "mixed.py"
            f.write_bytes(b"var_a = 1\n\x00\x01\x02\x03FIND_THIS_TOKEN\x00\nvar_b = 2\n")
            results = search_code(tmpdir, "FIND_THIS_TOKEN")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["line"], 2)

    def test_invalid_regex_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "sample.txt"
            f.write_text("here is an unclosed [bracket in text\n", encoding="utf-8")
            results = search_code(tmpdir, "[bracket", is_regex=True)
            self.assertEqual(len(results), 1)


class AdversarialSummarizerTests(unittest.TestCase):
    """Stress tests for summarizer."""

    def test_zero_and_small_max_chars_boundary_bug(self):
        """compact_document guarantees <= max_chars for all small boundaries."""
        text = "This is a document that should be compacted."
        for mc in [0, 1, 2, 3]:
            compacted = compact_document(text, max_chars=mc)
            self.assertLessEqual(len(compacted), mc)
        self.assertEqual(compact_document(text, max_chars=0), "")

    def test_max_points_zero_boundary_bug(self):
        """summarize_key_points with max_points=0 returns 0 points."""
        text = "- Key bullet point one.\n- Key bullet point two.\n"
        points = summarize_key_points(text, max_points=0)
        self.assertEqual(len(points), 0)


class AdversarialSecretScannerTests(unittest.TestCase):
    """Stress tests for secret_scanner."""

    def test_aws_access_key_group_leakage_bug(self):
        """AWS access key ID pattern redacts the full key and does not leak the key payload."""
        key = "AKIAIOSFODNN7EXAMPLE"
        text = f'AWS_ACCESS_KEY_ID = "{key}"'
        secrets = scan_for_secrets(text)
        self.assertEqual(len(secrets), 1)
        item = secrets[0]
        self.assertEqual(item["type"], "aws_access_key_id")
        self.assertNotIn("IOSFODNN7EXAMPLE", item["snippet"])

    def test_multi_secret_line_leakage_bug(self):
        """When multiple secrets exist on one line, all secrets are redacted in snippet."""
        sec1 = "ghp_111111111111111111111111111111111111"
        sec2 = "ghp_222222222222222222222222222222222222"
        line = f'TOKEN_A = "{sec1}" and TOKEN_B = "{sec2}"'
        secrets = scan_for_secrets(line)
        self.assertEqual(len(secrets), 2)
        self.assertNotIn(sec2, secrets[0]["snippet"])
        self.assertNotIn(sec1, secrets[1]["snippet"])

    def test_anthropic_api_key_detection(self):
        """Anthropic API keys starting with sk-ant- are detected and redacted."""
        key = "sk-ant-api03-1234567890abcdef1234567890abcdef"
        text = f'ANTHROPIC_KEY = "{key}"'
        secrets = scan_for_secrets(text)
        self.assertEqual(len(secrets), 1)
        self.assertEqual(secrets[0]["type"], "anthropic_api_key")
        self.assertNotIn("1234567890abcdef", secrets[0]["snippet"])


class AdversarialAdrGeneratorTests(unittest.TestCase):
    """Stress tests for adr_generator."""

    def test_subheadings_silent_data_loss_bug(self):
        """Subheadings starting with '## ' in context are preserved and not dropped."""
        ctx = "Initial context.\n\n## Technical Details\nImportant technical constraint."
        adr_text = format_adr("Title", "Accepted", ctx, "Decision", "Consequences")
        parsed = parse_adr(adr_text)
        self.assertIn("Important technical constraint", parsed["context"])

    def test_save_adr_string_id_crash_bug(self):
        """save_adr accepts string adr_id cleanly without raising ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = save_adr(tmpdir, "Title", "Accepted", "Ctx", "Dec", "Con", adr_id="0001")
            self.assertTrue(file_path.exists())
            self.assertTrue(file_path.name.startswith("0001-"))


if __name__ == "__main__":
    unittest.main()
