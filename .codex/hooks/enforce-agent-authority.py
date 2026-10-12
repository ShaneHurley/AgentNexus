#!/usr/bin/env python3
"""SubagentStart: inject the Codex authority reminder; never grant writes."""

from __future__ import annotations

import sys

from _ide_pack_policy import (
    agent_authority_class,
    agent_name_from_payload,
    allow,
    deny,
    emit,
    read_stdin_json,
)

REMINDER = (
    "IDE pack: this subagent is read-only. No filesystem writes, deploys, or mutating shell. "
    "Audited Daily Coder / Research Forge work must use ide-bridge (PolicyGateway), not native IDE edits. "
    "Soft hooks assist only — they are not PolicyGateway."
)


def main() -> int:
    payload = read_stdin_json()
    name = agent_name_from_payload(payload)
    auth = agent_authority_class(name)

    # Codex SubagentStart supports context injection, not blocking decisions.
    emit({"hookSpecificOutput": {"hookEventName": "SubagentStart",
         "additionalContext": REMINDER if auth != "allowlisted" else
         "Audited writes require ide-bridge and PolicyGateway approval; this hook grants no authority."}})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # fail-closed when hooks.json sets failClosed
        deny(f"enforce-agent-authority hook error: {exc}", REMINDER)
        raise SystemExit(2) from exc
