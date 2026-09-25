"""Rebuild run projections from ledger events only."""

from __future__ import annotations

from typing import Any


def reconstruct_run_state(events: list[dict[str, Any]]) -> dict[str, Any]:
    state: dict[str, Any] = {
        "run_id": None,
        "phase": "init",
        "sources": {},
        "evidence": {},
        "budget_spent_usd": 0.0,
        "checkpoint": None,
        "charter_hash": None,
        "policy_version": None,
        "schema_version": None,
    }
    for ev in sorted(events, key=lambda e: e["sequence"]):
        if ev.get("run_id"):
            state["run_id"] = ev["run_id"]
        et = ev["event_type"]
        payload = ev["payload"]
        if et == "run_manifest":
            state["charter_hash"] = payload.get("charter_hash")
            state["policy_version"] = payload.get("policy_version")
            state["schema_version"] = payload.get("schema_version")
            state["phase"] = payload.get("phase", "init")
        elif et == "transition":
            state["phase"] = payload.get("to_phase", state["phase"])
        elif et == "source_registered":
            sid = payload["source_id"]
            state["sources"][sid] = payload
        elif et == "evidence_added":
            eid = payload["evidence_id"]
            state["evidence"][eid] = payload
        elif et == "budget_debit":
            state["budget_spent_usd"] = round(
                state["budget_spent_usd"] + float(payload.get("amount_usd", 0)), 6
            )
        elif et == "checkpoint":
            state["checkpoint"] = payload
    return state
