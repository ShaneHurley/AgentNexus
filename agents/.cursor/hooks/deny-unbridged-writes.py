#!/usr/bin/env python3
"""afterFileEdit: deny when edit was not via ide-bridge and agent is not on write allowlist."""

from __future__ import annotations

import sys

from _ide_pack_policy import (
    agent_authority_class,
    agent_name_from_payload,
    append_audit,
    bridge_active,
    deny,
    file_path_from_payload,
    read_stdin_json,
    write_allowlist_agents,
)

MSG = (
    "File edit denied: native IDE writes require IDE_BRIDGE_ACTIVE=1 (ide-bridge / PolicyGateway) "
    "or an explicit entry in ide-agents/policy/write-allowlist-agents.json (default empty)."
)


def main() -> int:
    payload = read_stdin_json()
    path = file_path_from_payload(payload)
    agent = agent_name_from_payload(payload)
    auth = agent_authority_class(agent)

    if bridge_active():
        append_audit(
            {
                "event": "afterFileEdit",
                "decision": "allow",
                "reason": "IDE_BRIDGE_ACTIVE",
                "path": path,
                "agent": agent,
            }
        )
        sys.stdout.write('{"permission":"allow"}')
        sys.stdout.flush()
        return 0

    if agent and agent in write_allowlist_agents():
        append_audit(
            {
                "event": "afterFileEdit",
                "decision": "allow",
                "reason": "write_allowlist",
                "path": path,
                "agent": agent,
            }
        )
        sys.stdout.write('{"permission":"allow"}')
        sys.stdout.flush()
        return 0

    # Parent session / platform Task agents may edit (pack development).
    # Readonly + unknown *named* ide agents: deny unbridged writes.
    if auth in ("parent", "platform", "allowlisted"):
        append_audit(
            {
                "event": "afterFileEdit",
                "decision": "allow",
                "reason": auth,
                "path": path,
                "agent": agent,
            }
        )
        sys.stdout.write('{"permission":"allow"}')
        sys.stdout.flush()
        return 0

    append_audit(
        {
            "event": "afterFileEdit",
            "decision": "deny",
            "reason": "unbridged_write",
            "path": path,
            "agent": agent,
            "authority": auth,
        }
    )
    deny(
        MSG,
        f"Unbridged edit blocked for agent {agent or 'unknown'} ({auth}) on {path or '<unknown path>'}.",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        deny(f"deny-unbridged-writes hook error: {exc}", MSG)
        raise SystemExit(2) from exc
