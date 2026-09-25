"""Resolve logical references (e.g. ide-agents/...) to safe physical paths."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from urllib.parse import unquote

from ai_agents_repo.discovery import repo_root
from ai_agents_repo.exceptions import RefResolutionError
from ai_agents_repo.paths import (
    agent_core_root,
    dc_root,
    ide_pack_root,
    rf_root,
    schemas_personal_root,
    skills_root,
)

# Logical prefix -> resolver returning path relative to repo root anchor
_PREFIX_HANDLERS: dict[str, Callable[[str, Path], Path]] = {}


def _register(prefix: str, handler) -> None:
    _PREFIX_HANDLERS[prefix.rstrip("/") + "/"] = handler


def _hub_relative(rest: str, *, root: Path) -> Path:
    hub = ide_pack_root(root=root)
    return hub / rest


def _repo_relative(rest: str, *, root: Path) -> Path:
    return root / rest


_register("ide-agents/", lambda rest, root: _hub_relative(rest, root=root))
_register("skills/", lambda rest, root: skills_root(root=root) / rest)
_register("schemas/personal/", lambda rest, root: schemas_personal_root(root=root) / rest)
_register("agent-core/", lambda rest, root: agent_core_root(root=root) / rest)
_register("daily-coder-ecosystem/", lambda rest, root: dc_root(root=root) / rest)
_register("research-forge/", lambda rest, root: rf_root(root=root) / rest)
_register("docs/", lambda rest, root: _repo_relative(Path("docs") / rest, root=root))

ACCEPTED_PREFIXES = tuple(sorted(_PREFIX_HANDLERS.keys()))


def _normalize_ref(ref: str) -> str:
    ref = unquote(ref.strip()).replace("\\", "/").lstrip("/")
    ref = ref.rstrip(".,;")
    if not ref:
        raise RefResolutionError("Empty logical reference")
    if ref.startswith("/") or (len(ref) > 1 and ref[1] == ":"):
        raise RefResolutionError(f"Absolute paths are rejected: {ref!r}")
    if ".." in ref.split("/"):
        raise RefResolutionError(f"Parent segments are rejected: {ref!r}")
    return ref


def resolve_ref(logical: str, *, root: Path | None = None, must_exist: bool = False) -> Path:
    """Map a logical repo reference to a physical path under ``root``.

    Symlink policy: the returned path is ``candidate.resolve(strict=False)`` and
    must remain under ``root.resolve()`` (fail closed on escape).
    """
    root = (root or repo_root()).resolve()
    normalized = _normalize_ref(logical)

    handler = None
    rest = normalized
    for prefix in ACCEPTED_PREFIXES:
        if normalized.startswith(prefix):
            handler = _PREFIX_HANDLERS[prefix]
            rest = normalized[len(prefix) :]
            break

    if handler is None:
        raise RefResolutionError(
            f"Unknown logical prefix in {logical!r}; accepted: {', '.join(ACCEPTED_PREFIXES)}"
        )

    candidate = handler(rest, root)
    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise RefResolutionError(f"Could not resolve {logical!r}: {exc}") from exc

    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise RefResolutionError(
            f"Reference {logical!r} escapes repository root after resolution"
        ) from exc

    if must_exist and not resolved.is_file():
        raise RefResolutionError(f"Reference {logical!r} does not resolve to an existing file")

    return resolved
