"""Dry-run planner — no provider execution events."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from research_forge.versions import MANIFEST


def plan_dry_run(repo_root: Path) -> dict[str, Any]:
    return {
        "dry_run": True,
        "repo_root": str(repo_root),
        "phases": ["gate_check", "fixture_replay", "integrity_audit"],
        "tools": ["mock_search", "mock_reader", "mock_model"],
        "estimated_reservations_usd": 0.0,
        "provider_events": 0,
        "schema_version": MANIFEST.schema_version,
    }
