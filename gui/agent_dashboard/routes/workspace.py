"""Workspace FS jail API."""
from __future__ import annotations

from .. import workspace_jail as jail
from ..config_overlay import load_overlay, merge_workspace_roots
from . import common as c


def _roots(ctx: dict) -> list[dict]:
    reg = ctx["registry"]
    overlay = load_overlay(reg.data_dir)
    return merge_workspace_roots(reg.config, overlay, config_dir=reg.config_dir)


def handle_get(handler, path: str, query: dict, parts: list[str]) -> bool:
    if path == "/api/workspace/roots":
        c.send(handler, 200, {"roots": _roots(c.ctx(handler))})
        return True

    if path == "/api/workspace/tree":
        root_id = query.get("root", [""])[0]
        rel = query.get("path", [""])[0]
        roots = _roots(c.ctx(handler))
        root = jail.resolve_root(roots, root_id)
        if not root:
            c.send(handler, 404, {"error": "unknown root"})
            return True
        try:
            depth = int(query.get("depth", ["1"])[0])
        except ValueError:
            depth = 1
        depth = max(1, min(4, depth))
        try:
            tree = jail.list_tree(root, rel, depth=depth)
        except PermissionError as exc:
            c.send(handler, 403, {"error": str(exc)})
            return True
        except FileNotFoundError:
            c.send(handler, 404, {"error": "not found"})
            return True
        c.send(handler, 200, {"root": root_id, **tree})
        return True

    if path == "/api/workspace/file":
        root_id = query.get("root", [""])[0]
        rel = query.get("path", [""])[0]
        if not rel:
            c.send(handler, 400, {"error": "path is required"})
            return True
        roots = _roots(c.ctx(handler))
        root = jail.resolve_root(roots, root_id)
        if not root:
            c.send(handler, 404, {"error": "unknown root"})
            return True
        try:
            payload = jail.read_file(root, rel)
        except PermissionError as exc:
            c.send(handler, 403, {"error": str(exc)})
            return True
        except FileNotFoundError:
            c.send(handler, 404, {"error": "not found"})
            return True
        except ValueError as exc:
            c.send(handler, 413, {"error": str(exc)})
            return True
        c.send(handler, 200, {"root": root_id, **payload})
        return True
    return False


def handle_put(handler, path: str, query: dict, body: dict, parts: list[str]) -> bool:
    if path != "/api/workspace/file":
        return False
    root_id = query.get("root", [""])[0]
    rel = query.get("path", [""])[0]
    if not root_id or not rel:
        c.send(handler, 400, {"error": "root and path are required"})
        return True
    content = body.get("content")
    if content is None:
        c.send(handler, 400, {"error": "content is required"})
        return True
    if not isinstance(content, str):
        c.send(handler, 400, {"error": "content must be a string"})
        return True
    roots = _roots(c.ctx(handler))
    root = jail.resolve_root(roots, root_id)
    if not root:
        c.send(handler, 404, {"error": "unknown root"})
        return True
    try:
        payload = jail.write_file(root, rel, content)
    except PermissionError as exc:
        c.send(handler, 403, {"error": str(exc)})
        return True
    except ValueError as exc:
        c.send(handler, 400, {"error": str(exc)})
        return True
    c.send(handler, 200, {"root": root_id, **payload})
    return True
