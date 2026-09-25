"""Docs API — whitelisted markdown under project docs/ (aligned with config root)."""
from __future__ import annotations

import re
from pathlib import Path

from ..paths import docs_dir
from . import common as c

_DOC_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.md$")


def _docs_dir(ctx: dict | None = None) -> Path:
    if ctx and ctx.get("docs_dir"):
        return Path(ctx["docs_dir"])
    config_dir = None
    if ctx and ctx.get("registry") is not None:
        config_dir = getattr(ctx["registry"], "config_dir", None)
    return docs_dir(config_dir=config_dir)


def _safe_doc_path(name: str, base: Path) -> Path | None:
    if not name or "/" in name or "\\" in name or ".." in name:
        return None
    if not _DOC_NAME.match(name):
        return None
    target = (base / name).resolve()
    try:
        target.relative_to(base.resolve())
    except ValueError:
        return None
    return target if target.is_file() else None


def handle_get(handler, path: str, query: dict, parts: list[str]) -> bool:
    ctx = c.ctx(handler)
    base = _docs_dir(ctx)

    if path == "/api/docs":
        if not base.is_dir():
            c.send(handler, 200, {
                "docs": [],
                "docs_dir": str(base),
                "warning": "docs directory missing — run from the agent-dashboard checkout (start.py) or set AGENT_DASHBOARD_ROOT",
            })
            return True
        docs = []
        for p in sorted(base.glob("*.md")):
            if _DOC_NAME.match(p.name):
                docs.append({"name": p.name, "title": p.stem.replace("_", " ")})
        payload = {"docs": docs, "docs_dir": str(base)}
        if not docs:
            payload["warning"] = f"No *.md files in {base}"
        c.send(handler, 200, payload)
        return True

    if len(parts) == 3 and parts[0] == "api" and parts[1] == "docs":
        name = parts[2]
        if not name.endswith(".md"):
            name = f"{name}.md"
        target = _safe_doc_path(name, base)
        if not target:
            c.send(handler, 404, {
                "error": "not found",
                "name": name,
                "docs_dir": str(base),
            })
            return True
        c.send(handler, 200, {
            "name": target.name,
            "title": target.stem.replace("_", " "),
            "content": target.read_text(encoding="utf-8", errors="replace"),
            "docs_dir": str(base),
        })
        return True
    return False
