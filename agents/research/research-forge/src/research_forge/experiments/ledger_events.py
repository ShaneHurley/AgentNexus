"""Ledger helpers for experiment lifecycle events."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from research_forge.ledger.jsonl import JsonlLedger


def experiment_ledger(workspace_root: Path) -> JsonlLedger:
    path = workspace_root / "runs" / "experiments_ledger.jsonl"
    return JsonlLedger(path)


def ledger_run_id(experiment_id: str, prefix: str = "exp-") -> str:
    return f"{prefix}{experiment_id}"


def append_event(
    ledger: JsonlLedger,
    *,
    experiment_id: str,
    event_type: str,
    payload: dict[str, Any],
    actor: str,
    prefix: str = "exp-",
) -> dict[str, Any]:
    return ledger.append(
        {
            "run_id": ledger_run_id(experiment_id, prefix),
            "event_type": event_type,
            "actor": actor,
            "payload": {"experiment_id": experiment_id, **payload},
        }
    )
