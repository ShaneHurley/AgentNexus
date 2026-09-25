"""Replay exported bundle without network."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from research_forge.ledger.reconstruct import reconstruct_run_state


def replay_bundle(repo_root: Path, bundle_path: Path) -> dict[str, Any]:
    data = json.loads(bundle_path.read_text(encoding="utf-8"))
    events = data.get("events") or data.get("ledger_events") or []
    state = reconstruct_run_state(events)
    canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
    packet_hash = hashlib.sha256(canonical.encode()).hexdigest()
    expected = data.get("expected_state_hash")
    ok = expected is None or packet_hash == expected
    return {
        "ok": ok,
        "run_id": state.get("run_id"),
        "state_hash": packet_hash,
        "expected_state_hash": expected,
        "source_count": len(state.get("sources", {})),
        "evidence_count": len(state.get("evidence", {})),
    }
