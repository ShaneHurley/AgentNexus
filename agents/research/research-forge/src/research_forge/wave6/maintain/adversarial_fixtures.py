"""Adversarial fixture maintenance (RF-W6-F-04)."""

from __future__ import annotations

from typing import Any


class AdversarialFixtureRegistry:
    def __init__(self, fixtures: list[dict[str, Any]] | None = None) -> None:
        self.fixtures = list(fixtures or [])

    def add_escape(self, failure: dict[str, Any], *, reviewed: bool) -> dict[str, Any]:
        if not reviewed:
            return {"added": False, "reason": "review_required"}
        fid = failure.get("fixture_id") or f"adv-{failure.get('failure_id')}"
        if any(f.get("fixture_id") == fid for f in self.fixtures):
            return {"added": False, "reason": "duplicate"}
        self.fixtures.append(
            {
                "fixture_id": fid,
                "failure_id": failure.get("failure_id"),
                "pattern": failure.get("pattern"),
                "severity": failure.get("severity", "critical"),
            }
        )
        return {"added": True, "fixture_id": fid}

    def detects(self, pattern: str) -> bool:
        return any(f.get("pattern") == pattern for f in self.fixtures)
