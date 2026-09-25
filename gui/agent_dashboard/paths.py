"""Runtime paths — keep secrets and identity out of the project tree."""
from __future__ import annotations
import os
import tempfile
from pathlib import Path


def _looks_like_project(root: Path) -> bool:
    return (root / "config" / "agents.json").is_file() or (root / "docs").is_dir()


def project_root(*, config_path: Path | None = None) -> Path:
    """Resolve the agent-dashboard checkout / install project root.

    Prefer explicit env / config location so docs and config stay aligned when
    launched via start.py, ``python -m agent_dashboard``, or an editable install.
    """
    env = (os.environ.get("AGENT_DASHBOARD_ROOT") or "").strip()
    if env:
        return Path(env).expanduser().resolve()

    if config_path is not None:
        cfg = Path(config_path).expanduser().resolve()
        if cfg.name == "agents.json" and cfg.parent.name == "config":
            return cfg.parent.parent
        if cfg.is_file():
            return cfg.parent

    here = Path(__file__).resolve().parent  # .../agent_dashboard
    for candidate in (here.parent, Path.cwd(), *Path.cwd().resolve().parents):
        if _looks_like_project(candidate):
            return candidate.resolve()

    return here.parent


def docs_dir(*, config_dir: Path | None = None, project: Path | None = None) -> Path:
    """Locate markdown docs; try checkout next to config, then packaged fallback."""
    candidates: list[Path] = []
    if config_dir is not None:
        candidates.append(Path(config_dir).resolve().parent / "docs")
    root = project or project_root()
    candidates.append(root / "docs")
    # Packaged / in-tree fallback under the Python package (see package-data).
    candidates.append(Path(__file__).resolve().parent / "docs")
    for path in candidates:
        if path.is_dir():
            return path.resolve()
    return candidates[0].resolve()


def default_data_dir() -> Path:
    """Ephemeral OS temp dir outside the repo. Never under gui/.

    Override with AGENT_DASHBOARD_DATA if you want a custom location.
    Tokens/credentials must never be written here (or anywhere on disk).
    """
    override = os.environ.get("AGENT_DASHBOARD_DATA", "").strip()
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            path = Path(tempfile.gettempdir()) / path
        return path.resolve()
    return (Path(tempfile.gettempdir()) / "agent-orchestration-dashboard").resolve()


def resolve_data_dir(configured: str | None, *, project: Path | None = None) -> Path:
    """Resolve data_dir; never place it inside the project checkout."""
    root = (project or project_root()).resolve()
    if not configured or configured in (".", "./", ".agent-dashboard"):
        path = default_data_dir()
    else:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = default_data_dir()
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        pass
    else:
        # Would live inside the project — force outside.
        path = default_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_under_project(path: Path, *, project: Path | None = None) -> bool:
    root = (project or project_root()).resolve()
    try:
        path.resolve().relative_to(root)
        return True
    except ValueError:
        return False
