"""Map Daily Coder runtime rows to ide-bridge exit codes (plan contract)."""

from __future__ import annotations

from typing import Any

EXIT_COMPLETE = 0
EXIT_SIMULATED = 1
EXIT_PARTIAL = 2
EXIT_BLOCKED = 3
EXIT_POLICY_DENIED = 4


def exit_code_from_dc_row(row: dict[str, Any]) -> int:
    status = str(row.get("status") or "").upper()
    if status == "COMPLETE":
        return EXIT_COMPLETE
    if status == "SIMULATED":
        return EXIT_SIMULATED
    if status in ("BLOCKED", "WAITING_HUMAN", "WAITING_JOB", "CANCELLED"):
        return EXIT_BLOCKED
    if status == "FAILED":
        return EXIT_PARTIAL
    if status == "ACTIVE":
        return EXIT_PARTIAL
    return EXIT_PARTIAL


def exit_code_from_cli_failure(message: str, returncode: int | None) -> int:
    lower = message.lower()
    if "re-run with --live" in lower or "spends real credits" in lower:
        return EXIT_POLICY_DENIED
    if "tool denied" in lower or "permission" in lower or "not allowed" in lower:
        return EXIT_POLICY_DENIED
    if "daily spend cap" in lower:
        return EXIT_POLICY_DENIED
    if returncode == 4:
        return EXIT_POLICY_DENIED
    return EXIT_BLOCKED if returncode not in (None, 0) else EXIT_PARTIAL
