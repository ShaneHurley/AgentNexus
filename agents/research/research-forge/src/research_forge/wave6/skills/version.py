"""Skill version store and rollback (RF-W6-C-08)."""

from __future__ import annotations

from typing import Any

from research_forge.wave6.skills.manifest import SkillManifest


class SkillVersionStore:
    def __init__(self) -> None:
        self._versions: dict[str, list[SkillManifest]] = {}

    def publish(self, manifest: SkillManifest, *, held_out_passed: bool) -> dict[str, Any]:
        if not held_out_passed:
            return {"published": False, "reason": "held_out_tests_required"}
        errs = manifest.validate()
        if errs:
            return {"published": False, "reason": "invalid", "errors": errs}
        self._versions.setdefault(manifest.name, []).append(manifest)
        return {"published": True, "version": manifest.version}

    def active(self, name: str) -> SkillManifest | None:
        versions = self._versions.get(name) or []
        return versions[-1] if versions else None

    def rollback(self, name: str, to_version: str) -> dict[str, Any]:
        versions = self._versions.get(name) or []
        for m in reversed(versions):
            if m.version == to_version:
                idx = versions.index(m)
                self._versions[name] = versions[: idx + 1]
                return {"ok": True, "active_version": to_version}
        return {"ok": False, "reason": "version_not_found"}

    def replay_version(self, name: str, version: str) -> SkillManifest | None:
        for m in self._versions.get(name) or []:
            if m.version == version:
                return m
        return None
