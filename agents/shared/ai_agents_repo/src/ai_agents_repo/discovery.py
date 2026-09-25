"""Marker-based repository root discovery (never CWD-only)."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from ai_agents_repo.exceptions import LayoutError

MARKER_FILENAME = ".ai-agents-layout"
MARKER_ENV = "AI_AGENTS_REPO_ROOT"

_LEGACY_ANCHOR = Path("ide-pack") / "ide-agents" / "MANIFEST.yml"
_V2_ANCHOR = Path("agents") / "ide" / "MANIFEST.yml"
def _is_repo_root(path: Path) -> bool:
    path = path.resolve()
    if (path / MARKER_FILENAME).is_file():
        return True
    if (path / _LEGACY_ANCHOR).is_file():
        return True
    if (path / _V2_ANCHOR).is_file():
        return True
    return False


def find_repo_root(*, start: Path | None = None) -> Path:
    """Walk parents from ``start`` (or this package file) until a repo root is found."""
    env_root = os.environ.get(MARKER_ENV)
    if env_root:
        candidate = Path(env_root).expanduser().resolve()
        if not _is_repo_root(candidate):
            raise LayoutError(
                f"{MARKER_ENV}={env_root!r} is not a valid ai_agents repository root"
            )
        return candidate

    if start is None:
        start = Path(__file__).resolve()

    current = start.resolve()
    if current.is_file():
        current = current.parent

    for directory in (current, *current.parents):
        if _is_repo_root(directory):
            return directory.resolve()

    raise LayoutError(
        "Could not locate ai_agents repository root (missing "
        f"{MARKER_FILENAME} or known layout anchors). "
        f"Set {MARKER_ENV} to an absolute checkout path."
    )


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """Cached repository root for the current process."""
    return find_repo_root()


def read_marker(root: Path | None = None) -> dict:
    root = (root or repo_root()).resolve()
    marker_path = root / MARKER_FILENAME
    if not marker_path.is_file():
        return {}
    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LayoutError(f"Invalid JSON in {marker_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise LayoutError(f"{marker_path} must contain a JSON object")
    return data
