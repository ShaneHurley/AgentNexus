"""Skill loading.

Only skills named by the approved plan are loaded, and only their front matter plus a
bounded body. The whole library is never injected.
"""
from __future__ import annotations
import re
from pathlib import Path

MAX_SKILL_CHARS = 4000
_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)

def _parse(text):
    meta, body = {}, text
    match = _FRONT.match(text)
    if match:
        body = text[match.end():]
        for line in match.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
    return meta, body

class SkillLibrary:
    def __init__(self, root):
        self.root = Path(root)

    def index(self):
        out = []
        if not self.root.exists():
            return out
        for path in sorted(self.root.glob("*/SKILL.md")):
            meta, _ = _parse(path.read_text(encoding="utf-8"))
            out.append({"name": meta.get("name", path.parent.name), "version": meta.get("version", "0"),
                        "status": meta.get("status", "active"), "description": meta.get("description", ""),
                        "path": str(path)})
        return out

    def load(self, names):
        """Return bounded skill bodies for the named, active skills only."""
        wanted = {n for n in (names or [])}
        if not wanted:
            return []
        entries = {entry["name"]: entry for entry in self.index() if entry["status"] == "active"}
        missing = sorted(wanted - set(entries))
        if missing:
            raise ValueError(f"requested skills are missing or inactive: {missing}")
        loaded = []
        for name in sorted(wanted):
            entry = entries[name]
            _, body = _parse(Path(entry["path"]).read_text(encoding="utf-8"))
            loaded.append({"name": entry["name"], "version": entry["version"], "body": body.strip()[:MAX_SKILL_CHARS]})
        return loaded
