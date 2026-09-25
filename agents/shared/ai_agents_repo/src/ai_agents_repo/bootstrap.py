"""Checkout-only bootstrap when the package is not yet installed."""

from __future__ import annotations

import sys
from pathlib import Path

_MARKER = ".ai-agents-layout"


def _locate_checkout_src(start: Path) -> Path | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for directory in (current, *current.parents):
        src_candidates = (
            directory / "agents" / "shared" / "ai_agents_repo" / "src",
            directory / "ai_agents_repo" / "src",
        )
        for src in src_candidates:
            if not src.is_dir():
                continue
            if (directory / _MARKER).is_file():
                return src
            for anchor in (
                directory / "agents" / "ide" / "MANIFEST.yml",
                directory / "ide-pack" / "ide-agents" / "MANIFEST.yml",
            ):
                if anchor.is_file():
                    return src
    return None


def ensure_importable() -> None:
    """Add ``ai_agents_repo/src`` to ``sys.path`` when running from a checkout."""
    try:
        import ai_agents_repo  # noqa: F401
    except ImportError:
        pass
    else:
        return

    src = _locate_checkout_src(Path(__file__).resolve())
    if src is not None and str(src) not in sys.path:
        sys.path.insert(0, str(src))
