"""Runtime config overlay under data_dir (never mutates repo config/agents.json)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

# host / port / auth_required are forbidden (edit agents.json + restart instead).
OVERLAY_ALLOWLIST = frozenset({"workspace_roots"})


def overlay_path(data_dir: Path) -> Path:
    return data_dir / "config_overlay.json"


def load_overlay(data_dir: Path) -> dict[str, Any]:
    path = overlay_path(data_dir)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def filtered_overlay(raw: dict[str, Any]) -> dict[str, Any]:
    return {k: raw[k] for k in raw if k in OVERLAY_ALLOWLIST}


def validate_overlay_payload(body: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    unknown = [k for k in body if k not in OVERLAY_ALLOWLIST]
    clean = filtered_overlay(body)
    if "workspace_roots" in clean and not isinstance(clean["workspace_roots"], list):
        raise ValueError("workspace_roots must be a list")
    return clean, unknown


def write_overlay(data_dir: Path, payload: dict[str, Any]) -> Path:
    path = overlay_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".overlay-", suffix=".json")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.is_file():
            try:
                tmp.unlink()
            except OSError:
                pass
    return path


def merge_workspace_roots(base: dict[str, Any], overlay: dict[str, Any], *, config_dir: Path) -> list[dict[str, Any]]:
    """Effective workspace roots: overlay wins, else config, else derived from agents."""
    if overlay.get("workspace_roots"):
        return _normalize_roots(overlay["workspace_roots"], config_dir)
    if base.get("workspace_roots"):
        return _normalize_roots(base["workspace_roots"], config_dir)
    return _derive_roots_from_agents(base, config_dir)


def _normalize_roots(entries: list[Any], config_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    root = config_dir.parent
    for i, item in enumerate(entries):
        if isinstance(item, str):
            p = Path(item)
            if not p.is_absolute():
                p = (root / p).resolve()
            out.append({"id": f"root-{i}", "label": p.name, "path": str(p)})
        elif isinstance(item, dict) and item.get("path"):
            p = Path(str(item["path"]))
            if not p.is_absolute():
                p = (root / p).resolve()
            out.append({
                "id": str(item.get("id") or f"root-{i}"),
                "label": str(item.get("label") or p.name),
                "path": str(p),
            })
    return out


def _derive_roots_from_agents(config: dict[str, Any], config_dir: Path) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    root = config_dir.parent
    for entry in config.get("agents", []):
        for key in ("repo_root", "package_root", "workspace_root"):
            val = (entry.get("options") or {}).get(key)
            if not val:
                continue
            p = Path(val)
            if not p.is_absolute():
                p = (root / p).resolve()
            s = str(p)
            if s in seen or not p.is_dir():
                continue
            seen.add(s)
            out.append({
                "id": f"{entry.get('id', 'agent')}-{key}",
                "label": f"{entry.get('name', entry.get('id', 'root'))} ({key})",
                "path": s,
            })
    docs = (root / "docs").resolve()
    if docs.is_dir() and str(docs) not in seen:
        out.append({"id": "docs", "label": "Documentation", "path": str(docs)})
    return out
