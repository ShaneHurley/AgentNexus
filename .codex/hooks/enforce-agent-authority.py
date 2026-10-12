#!/usr/bin/env python3
"""subagentStart: block readonly subagents from write-capable delegation; inject contract reminder."""

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

    # Allow Cursor platform Task types and unnamed parent flows.
    # Readonly ide-agents agents may start (with reminder); mutation hooks still deny writes.
    # Unknown *named* custom agents: allow start but mutation hooks fail-closed on writes.
    if auth == "readonly":
        emit(
            {
                "permission": "allow",
                "user_message": REMINDER,
                "agent_message": (
                    f"Subagent '{name}' is read-only: no writes or mutating shell; "
                    "use ide-bridge for audited side effects."
                ),
            }
        )
        return 0

    allow()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # fail-closed when hooks.json sets failClosed
        deny(f"enforce-agent-authority hook error: {exc}", REMINDER)
        raise SystemExit(2) from exc
