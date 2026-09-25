"""Physical path helpers for legacy and v2 domain layouts."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ai_agents_repo.discovery import repo_root
from ai_agents_repo.layout import LayoutName, layout

_PATH_MAP: dict[LayoutName, dict[str, tuple[str, ...]]] = {
    "legacy": {
        "ide_pack": ("ide-pack", "ide-agents"),
        "dc": ("coder", "daily-coder-ecosystem"),
        "rf": ("deep-research", "research-forge"),
        "gui": ("gui",),
        "skills": ("skills",),
        "schemas_personal": ("schemas", "personal"),
        "agent_core": ("agent-core",),
        "policy": ("ide-pack", "ide-agents", "policy"),
        "hooks": ("ide-pack", ".cursor", "hooks"),
        "browser_legacy": ("browser agent",),
    },
    "v2": {
        "ide_pack": ("agents", "ide"),
        "dc": ("agents", "coding", "daily-coder-ecosystem"),
        "rf": ("agents", "research", "research-forge"),
        "gui": ("gui",),
        "skills": ("agents", "shared", "skills"),
        "schemas_personal": ("agents", "shared", "schemas", "personal"),
        "agent_core": ("agents", "shared", "agent-core"),
        "policy": ("agents", "ide", "policy"),
        "hooks": (".cursor", "hooks"),
        "browser_daily_task": ("agents", "daily-task", "browser", "families"),
        "browser_coder": ("agents", "coding", "browser"),
        "browser_deep_research": ("agents", "research", "browser"),
        "browser_shared": ("agents", "shared", "browser"),
    },
}


def _join(root: Path, parts: tuple[str, ...]) -> Path:
    path = root
    for part in parts:
        path = path / part
    return path


def _path_for(key: str, *, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    root = (root or repo_root()).resolve()
    lay = lay or layout(root=root)
    parts = _PATH_MAP[lay].get(key)
    if parts is None:
        raise KeyError(f"No path mapping for {key!r} in layout {lay!r}")
    return _join(root, parts)


def ide_pack_root(*, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    return _path_for("ide_pack", root=root, lay=lay)


def dc_root(*, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    return _path_for("dc", root=root, lay=lay)


def rf_root(*, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    return _path_for("rf", root=root, lay=lay)


def gui_root(*, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    return _path_for("gui", root=root, lay=lay)


def skills_root(*, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    return _path_for("skills", root=root, lay=lay)


def schemas_personal_root(*, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    return _path_for("schemas_personal", root=root, lay=lay)


def agent_core_root(*, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    return _path_for("agent_core", root=root, lay=lay)


def policy_dir(*, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    return _path_for("policy", root=root, lay=lay)


def hooks_dir(*, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    return _path_for("hooks", root=root, lay=lay)


def browser_legacy_root(*, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    return _path_for("browser_legacy", root=root, lay=lay)


def browser_daily_task_root(*, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    lay = lay or layout(root=root or repo_root())
    if lay == "legacy":
        raise KeyError("browser_daily_task_root is v2-only")
    return _path_for("browser_daily_task", root=root, lay=lay)


def browser_coder_root(*, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    lay = lay or layout(root=root or repo_root())
    if lay == "legacy":
        raise KeyError("browser_coder_root is v2-only")
    return _path_for("browser_coder", root=root, lay=lay)


def browser_deep_research_root(*, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    lay = lay or layout(root=root or repo_root())
    if lay == "legacy":
        raise KeyError("browser_deep_research_root is v2-only")
    return _path_for("browser_deep_research", root=root, lay=lay)


def browser_shared_root(*, root: Path | None = None, lay: LayoutName | None = None) -> Path:
    lay = lay or layout(root=root or repo_root())
    if lay == "legacy":
        raise KeyError("browser_shared_root is v2-only")
    return _path_for("browser_shared", root=root, lay=lay)


@lru_cache(maxsize=2)
def v2_path_map_json() -> str:
    """Serialized v2 relative segments (for docs/tests)."""
    import json

    return json.dumps(_PATH_MAP["v2"], sort_keys=True)
