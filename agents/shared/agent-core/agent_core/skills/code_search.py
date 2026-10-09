"""Code Search Skill.

Provides deterministic in-repository code searching with file filtering,
directory exclusions, regex support, and line-level citations.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

DEFAULT_IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".eggs",
    "build",
    "dist",
    ".gemini",
    ".idea",
    ".vscode",
}

BINARY_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".so",
    ".dylib",
    ".dll",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".sqlite",
    ".db",
}


def search_code(
    root: Path | str,
    query: str,
    extensions: list[str] | tuple[str, ...] | None = None,
    ignore_dirs: list[str] | set[str] | None = None,
    is_regex: bool = False,
    case_insensitive: bool = False,
    max_results: int = 200,
) -> list[dict[str, Any]]:
    """Search for a query pattern across text files in a directory tree.

    Args:
        root: Directory root path to search within.
        query: String or regex pattern to search for.
        extensions: Optional list of file extensions to include (e.g. ['.py', '.md'] or ['py', 'md']).
        ignore_dirs: Optional additional directory names to ignore.
        is_regex: Whether query is a regular expression.
        case_insensitive: Whether search should ignore case.
        max_results: Maximum number of matching lines to return.

    Returns:
        List of matching dicts:
            [{"file": str(relative_path), "line": int, "content": str, "match_start": int, "match_end": int}]
    """
    if max_results <= 0:
        return []

    root_path = Path(root).resolve()
    if not root_path.exists():
        return []

    # Prepare ignored directory set
    ignored = set(DEFAULT_IGNORE_DIRS)
    if ignore_dirs:
        ignored.update(ignore_dirs)

    # Normalize extensions
    allowed_exts: set[str] | None = None
    if extensions:
        allowed_exts = {ext if ext.startswith(".") else f".{ext}" for ext in extensions}

    # Compile regex pattern
    flags = re.IGNORECASE if case_insensitive else 0
    if is_regex:
        try:
            pattern = re.compile(query, flags)
        except re.error:
            # Fall back to escaped literal pattern if regex fails to compile
            pattern = re.compile(re.escape(query), flags)
    else:
        pattern = re.compile(re.escape(query), flags)

    matches: list[dict[str, Any]] = []

    # Walk directory
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Filter directories in-place to avoid descending into ignored directories
        dirnames[:] = [d for d in dirnames if d not in ignored and not d.startswith(".")]

        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()
            if ext in BINARY_EXTENSIONS:
                continue
            if allowed_exts is not None and ext not in allowed_exts:
                continue

            filepath = Path(dirpath) / filename
            try:
                # Fast size check: skip giant files (> 2MB)
                if filepath.stat().st_size > 2 * 1024 * 1024:
                    continue

                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    for line_no, line in enumerate(f, start=1):
                        match = pattern.search(line)
                        if match:
                            rel_path = filepath.relative_to(root_path)
                            matches.append({
                                "file": str(rel_path),
                                "line": line_no,
                                "content": line.rstrip("\r\n"),
                                "match_start": match.start(),
                                "match_end": match.end(),
                            })
                            if len(matches) >= max_results:
                                return matches
            except (OSError, PermissionError):
                continue

    return matches
