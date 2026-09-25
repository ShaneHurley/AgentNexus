"""Layout selection with explicit precedence and fail-closed conflict handling."""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from ai_agents_repo.discovery import read_marker, repo_root
from ai_agents_repo.exceptions import LayoutError

LayoutName = Literal["legacy", "v2"]
_ENV_LAYOUT = "AI_AGENTS_LAYOUT"

_LEGACY_IDE = Path("ide-pack") / "ide-agents"
_V2_IDE = Path("agents") / "ide"
_LEGACY_NESTED_DC = Path("coder") / "daily-coder-ecosystem"
_V2_NESTED_DC = Path("agents") / "coding" / "daily-coder-ecosystem"
_LEGACY_DC_ROOT = Path("daily-coder-ecosystem")
class _Layout(str, Enum):
    LEGACY = "legacy"
    V2 = "v2"


def _auto_detect(root: Path) -> _Layout | None:
    legacy_ide = (root / _LEGACY_IDE / "MANIFEST.yml").is_file()
    v2_ide = (root / _V2_IDE / "MANIFEST.yml").is_file()
    legacy_nested_dc = (root / _LEGACY_NESTED_DC).is_dir()
    v2_nested_dc = (root / _V2_NESTED_DC).is_dir()
    legacy_dc_root = (root / _LEGACY_DC_ROOT).is_dir()

    if legacy_ide and v2_ide:
        raise LayoutError("Mixed layout: both legacy and v2 ide-agents hubs present")
    if legacy_nested_dc and legacy_dc_root:
        raise LayoutError("Mixed layout: both daily-coder-ecosystem and coder/daily-coder-ecosystem present")
    if legacy_nested_dc and v2_nested_dc:
        raise LayoutError("Mixed layout: both coder/ and agents/coding/ daily-coder trees present")

    if v2_ide:
        if legacy_ide or legacy_dc_root or legacy_nested_dc:
            raise LayoutError("Mixed layout: partial legacy and v2 trees detected")
        return _Layout.V2

    if legacy_ide or legacy_dc_root or legacy_nested_dc:
        return _Layout.LEGACY

    return None


def _normalize(name: str, *, source: str) -> _Layout:
    normalized = name.strip().lower()
    if normalized in ("legacy", "v1"):
        return _Layout.LEGACY
    if normalized in ("v2", "domain"):
        return _Layout.V2
    raise LayoutError(f"Unknown layout {name!r} from {source}; expected legacy or v2")


def layout(*, explicit: LayoutName | None = None, root: Path | None = None) -> LayoutName:
    """Return active layout: explicit arg > env > marker > auto-detect."""
    root = (root or repo_root()).resolve()

    env_val: _Layout | None = None
    if os.environ.get(_ENV_LAYOUT):
        env_val = _normalize(os.environ[_ENV_LAYOUT], source=_ENV_LAYOUT)

    marker_val: _Layout | None = None
    marker = read_marker(root)
    if marker.get("layout"):
        marker_val = _normalize(str(marker["layout"]), source=f"{root}/.ai-agents-layout")

    auto_val = _auto_detect(root)

    if explicit is not None:
        chosen = _normalize(explicit, source="explicit argument")
        conflicts: list[str] = []
        if env_val is not None and env_val != chosen:
            conflicts.append(f"env={env_val.value}")
        if marker_val is not None and marker_val != chosen:
            conflicts.append(f"marker={marker_val.value}")
        if auto_val is not None and auto_val != chosen:
            conflicts.append(f"auto={auto_val.value}")
        if conflicts:
            raise LayoutError(
                f"Layout explicit={chosen.value} conflicts with {', '.join(conflicts)}"
            )
        return chosen.value  # type: ignore[return-value]

    if env_val is not None:
        chosen = env_val
        conflicts = []
        if marker_val is not None and marker_val != chosen:
            conflicts.append(f"marker={marker_val.value}")
        if auto_val is not None and auto_val != chosen:
            conflicts.append(f"auto={auto_val.value}")
        if conflicts:
            raise LayoutError(
                f"Layout env={chosen.value} conflicts with {', '.join(conflicts)}"
            )
        return chosen.value  # type: ignore[return-value]

    if marker_val is not None:
        chosen = marker_val
        if auto_val is not None and auto_val != chosen:
            raise LayoutError(
                f"Layout marker={chosen.value} conflicts with auto={auto_val.value}"
            )
        return chosen.value  # type: ignore[return-value]

    if auto_val is not None:
        return auto_val.value  # type: ignore[return-value]

    raise LayoutError(
        f"No layout could be determined under {root}; "
        f"add {root / '.ai-agents-layout'} or set {_ENV_LAYOUT}"
    )


@lru_cache(maxsize=1)
def cached_layout() -> LayoutName:
    return layout()
