#!/usr/bin/env python3
"""stop: append session summary JSONL under .ide-agents/audit/."""

from __future__ import annotations

import sys

from _ide_pack_policy import agent_name_from_payload, append_audit, bridge_active, read_stdin_json


def main() -> int:
    payload = read_stdin_json()
    record = {
        "event": "stop",
        "agent": agent_name_from_payload(payload),
        "bridge_active": bridge_active(),
        "payload_keys": sorted(payload.keys()),
    }
    for key in ("sessionId", "session_id", "conversationId", "status", "reason"):
        if key in payload:
            record[key] = payload[key]
    append_audit(record)
    # stop hooks may use followup_message; we only audit
    sys.stdout.write("{}")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        # Audit failure must not block session end
        raise SystemExit(0)
