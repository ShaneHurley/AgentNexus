"""Filesystem jail for IDE workspace API."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 1 << 20  # 1 MiB

SKIP_DIR_NAMES = frozenset({".git", "node_modules"})


def skip_dir_name(name: str) -> bool:
    if name in SKIP_DIR_NAMES:
        return True
    return name.startswith(".venv")


def resolve_root(roots: list[dict[str, Any]], root_id: str) -> Path | None:
    for r in roots:
        if r.get("id") == root_id:
            p = Path(str(r["path"])).resolve()
            if p.is_dir():
                return p
            return None
    return None


def resolve_in_root(root: Path, rel_path: str) -> Path:
    """Resolve rel_path under root; raises PermissionError on escape."""
    rel = (rel_path or "").replace("\\", "/").strip("/")
    if ".." in rel.split("/"):
        raise PermissionError("path traversal denied")
    target = (root / rel).resolve() if rel else root.resolve()
    root_res = root.resolve()
    try:
        target.relative_to(root_res)
    except ValueError as exc:
        raise PermissionError("path outside workspace root") from exc
    return target


def list_tree(root: Path, rel_path: str, *, depth: int = 1) -> dict[str, Any]:
    base = resolve_in_root(root, rel_path)
    if not base.is_dir():
        raise FileNotFoundError("not a directory")
    entries: list[dict[str, Any]] = []
    try:
        names = sorted(os.listdir(base))
    except OSError as exc:
        raise PermissionError(str(exc)) from exc
    for name in names:
        if skip_dir_name(name):
            continue
        p = base / name
        try:
            p = p.resolve()
            p.relative_to(root.resolve())
        except (ValueError, OSError):
            continue
        if p.is_dir():
            node: dict[str, Any] = {"name": name, "type": "dir"}
            if depth > 1:
                node["children"] = list_tree(root, str(Path(rel_path) / name) if rel_path else name, depth=depth - 1).get(
                    "entries", []
                )
            entries.append(node)
        elif p.is_file():
            entries.append({"name": name, "type": "file", "size": p.stat().st_size})
    return {"path": rel_path.replace("\\", "/"), "entries": entries}


def read_file(root: Path, rel_path: str) -> dict[str, Any]:
    target = resolve_in_root(root, rel_path)
    if not target.is_file():
        raise FileNotFoundError("not a file")
    size = target.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError("file exceeds 1 MiB limit")
    text = target.read_text(encoding="utf-8", errors="replace")
    mtime = target.stat().st_mtime
    return {"path": rel_path, "content": text, "size": size, "mtime": mtime}


def write_file(root: Path, rel_path: str, content: str) -> dict[str, Any]:
    if len(content.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("content exceeds 1 MiB limit")
    target = resolve_in_root(root, rel_path)
    if target.is_dir():
        raise ValueError("cannot write directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": rel_path, "size": target.stat().st_size, "mtime": target.stat().st_mtime}
