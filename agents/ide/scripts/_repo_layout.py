"""Thin adapter: ide-agents scripts → ai_agents_repo (legacy default)."""

from __future__ import annotations

from pathlib import Path

from ai_agents_repo.bootstrap import ensure_importable

ensure_importable()

from ai_agents_repo import (  # noqa: E402
    dc_root,
    ide_pack_root,
    layout,
    repo_root,
    resolve_ref,
    rf_root,
)

REPO_ROOT = repo_root()

__all__ = [
    "REPO_ROOT",
    "dc_root",
    "rf_root",
    "ide_pack_root",
    "layout",
    "repo_root",
    "resolve_ref",
    "resolve_file_ref",
]


def resolve_file_ref(ref: str, *, root: Path | None = None) -> Path | None:
    """Resolve #file: logical ref; None when missing (audit compatibility)."""
    try:
        path = resolve_ref(ref, root=root or repo_root(), must_exist=True)
    except Exception:
        return None
    return path
