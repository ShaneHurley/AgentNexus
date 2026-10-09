"""Diff and Patch Tool Skill.

Provides deterministic unified diff generation and patch applicability validation
without requiring external patch binaries or git commands.
"""

from __future__ import annotations

import difflib
import re
from typing import Any

HUNK_HEADER_RE = re.compile(r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")


def generate_unified_diff(
    a: str,
    b: str,
    fromfile: str = "a",
    tofile: str = "b",
    lineterm: str = "\n",
) -> str:
    """Generate a unified diff between two text strings.

    Args:
        a: Original text.
        b: Modified text.
        fromfile: Label for original file.
        tofile: Label for modified file.
        lineterm: Line termination string.

    Returns:
        Unified diff string with headers and hunks.
    """
    a_norm = a.replace("\r\n", "\n")
    b_norm = b.replace("\r\n", "\n")
    a_lines = [line if line.endswith("\n") else line + "\n" for line in a_norm.splitlines(keepends=True)]
    b_lines = [line if line.endswith("\n") else line + "\n" for line in b_norm.splitlines(keepends=True)]

    diff = difflib.unified_diff(
        a_lines,
        b_lines,
        fromfile=fromfile,
        tofile=tofile,
        lineterm=lineterm,
    )
    return "".join(diff)


def validate_patch(original: str, patch: str) -> dict[str, Any]:
    """Validate whether a unified diff patch can apply cleanly to an original text.

    Args:
        original: Original document content.
        patch: Unified diff patch content.

    Returns:
        dict with keys:
            - applicable: bool, True if all hunks apply cleanly.
            - hunks_count: int, total number of hunks found in patch.
            - applied_hunks: int, number of hunks successfully matched.
            - failed_hunks: list of failure details per failing hunk.
            - additions: int, total added lines.
            - deletions: int, total deleted lines.
            - patched_text: str | None, resulting patched text if applicable, else None.
            - error: str | None, summary error message if any.
    """
    if not patch.strip():
        return {
            "applicable": True,
            "hunks_count": 0,
            "applied_hunks": 0,
            "failed_hunks": [],
            "additions": 0,
            "deletions": 0,
            "patched_text": original,
            "error": None,
        }

    had_crlf = "\r\n" in original
    orig_norm = original.replace("\r\n", "\n")
    patch_norm = patch.replace("\r\n", "\n")

    orig_lines = orig_norm.splitlines(keepends=True)
    # Ensure all lines end with \n for consistent comparisons
    normalized_orig = [line if line.endswith("\n") else line + "\n" for line in orig_lines]

    patch_lines = patch_norm.splitlines()

    # Parse hunks from patch
    hunks: list[dict[str, Any]] = []
    current_hunk: dict[str, Any] | None = None
    additions = 0
    deletions = 0

    for line in patch_lines:
        match = HUNK_HEADER_RE.match(line)
        if match:
            if current_hunk is not None:
                hunks.append(current_hunk)
            old_start = int(match.group(1))
            old_count = int(match.group(2)) if match.group(2) is not None else 1
            new_start = int(match.group(3))
            new_count = int(match.group(4)) if match.group(4) is not None else 1
            current_hunk = {
                "header": line,
                "old_start": old_start,
                "old_count": old_count,
                "new_start": new_start,
                "new_count": new_count,
                "lines": [],
            }
        elif current_hunk is not None:
            if line.startswith(("+", "-", " ", "\\")):
                current_hunk["lines"].append(line)
                if line.startswith("+") and not line.startswith("+++"):
                    additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    deletions += 1
            elif line == "":
                # Empty context line with leading space omitted
                current_hunk["lines"].append(" ")
            # Other lines (e.g. diff header) are ignored inside or outside hunks

    if current_hunk is not None:
        hunks.append(current_hunk)

    if not hunks:
        return {
            "applicable": False,
            "hunks_count": 0,
            "applied_hunks": 0,
            "failed_hunks": [],
            "additions": additions,
            "deletions": deletions,
            "patched_text": None,
            "error": "No valid diff hunks found in patch",
        }

    # Simulate applying hunks
    patched_lines = list(normalized_orig)
    orig_idx_offset = 0
    applied_hunks = 0
    failed_hunks: list[dict[str, Any]] = []

    for idx, hunk in enumerate(hunks):
        old_start = hunk["old_start"] - 1  # 0-indexed
        target_idx = old_start + orig_idx_offset

        # Collect old expected lines and replacement lines
        expected_old: list[str] = []
        replacement: list[str] = []
        for hline in hunk["lines"]:
            prefix = hline[:1]
            content = hline[1:] + "\n"
            if prefix == " ":
                expected_old.append(content)
                replacement.append(content)
            elif prefix == "-":
                expected_old.append(content)
            elif prefix == "+":
                replacement.append(content)
            # ignore "\\" lines

        # Verify whether target_idx matches expected_old
        match_found = False
        actual_match_idx = target_idx

        # First check exact target_idx
        if (
            0 <= target_idx
            and target_idx + len(expected_old) <= len(patched_lines)
            and patched_lines[target_idx : target_idx + len(expected_old)] == expected_old
        ):
            match_found = True
            actual_match_idx = target_idx
        else:
            # Fuzzy search within window of +/- 5 lines
            window = 5
            min_idx = max(0, target_idx - window)
            max_idx = min(len(patched_lines) - len(expected_old), target_idx + window)
            for cand_idx in range(min_idx, max_idx + 1):
                if patched_lines[cand_idx : cand_idx + len(expected_old)] == expected_old:
                    match_found = True
                    actual_match_idx = cand_idx
                    break

        if match_found:
            # Apply hunk
            patched_lines[actual_match_idx : actual_match_idx + len(expected_old)] = replacement
            # Update cumulative offset
            orig_idx_offset += (actual_match_idx - target_idx) + (len(replacement) - len(expected_old))
            applied_hunks += 1
        else:
            failed_hunks.append({
                "hunk_index": idx + 1,
                "header": hunk["header"],
                "target_line": target_idx + 1,
                "reason": "Context lines do not match target file content",
                "expected": expected_old,
            })

    if failed_hunks:
        return {
            "applicable": False,
            "hunks_count": len(hunks),
            "applied_hunks": applied_hunks,
            "failed_hunks": failed_hunks,
            "additions": additions,
            "deletions": deletions,
            "patched_text": None,
            "error": f"{len(failed_hunks)} of {len(hunks)} hunks failed to apply",
        }

    result_text = "".join(patched_lines)
    if had_crlf:
        result_text = result_text.replace("\n", "\r\n")

    return {
        "applicable": True,
        "hunks_count": len(hunks),
        "applied_hunks": applied_hunks,
        "failed_hunks": [],
        "additions": additions,
        "deletions": deletions,
        "patched_text": result_text,
        "error": None,
    }
