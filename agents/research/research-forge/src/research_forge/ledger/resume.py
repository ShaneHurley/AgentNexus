"""Resume rules — version mismatch returns PLAN_STALE."""

from __future__ import annotations

from typing import Any

from research_forge.errors import ErrorCode, ForgeError, forge_error
from research_forge.versions import MANIFEST

TERMINAL_PHASES = frozenset({"completed", "failed", "cancelled"})


def can_resume(
    state: dict[str, Any],
    *,
    expected_charter_hash: str,
    expected_policy_version: str,
    expected_schema_version: str,
) -> ForgeError | None:
    phase = state.get("phase", "init")
    if phase in TERMINAL_PHASES:
        return forge_error(ErrorCode.PLAN_STALE, f"Cannot resume terminal phase {phase}")
    if state.get("charter_hash") != expected_charter_hash:
        return forge_error(ErrorCode.PLAN_STALE, "Charter hash mismatch")
    if state.get("policy_version") != expected_policy_version:
        return forge_error(ErrorCode.PLAN_STALE, "Policy version mismatch")
    if state.get("schema_version") != expected_schema_version:
        return forge_error(ErrorCode.PLAN_STALE, "Schema version mismatch")
    if state.get("schema_version") != MANIFEST.schema_version:
        return forge_error(ErrorCode.PLAN_STALE, "Schema manifest mismatch")
    return None
