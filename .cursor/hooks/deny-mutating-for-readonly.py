#!/usr/bin/env python3
"""preToolUse / beforeShellExecution: fail-closed for readonly or unknown agents (and mutating tools)."""

from __future__ import annotations

import re
import sys

from _ide_pack_policy import (
    MUTATING_SHELL_RE,
    MUTATING_TOOLS,
    agent_name_from_payload,
    allow,
    bridge_active,
    deny,
    hook_event_name,
    mutations_blocked_for_agent,
    read_stdin_json,
    shell_command_from_payload,
    tool_name_from_payload,
)

MSG = (
    "Mutating tool/shell blocked: active agent is read-only or unknown, and IDE_BRIDGE_ACTIVE is not set. "
    "Use ide-bridge for audited writes (PolicyGateway). IDE hooks are soft least-privilege only."
)


def is_mutating_shell(command: str) -> bool:
    if not command.strip():
        return False
    return re.search(MUTATING_SHELL_RE, command) is not None


def main() -> int:
    payload = read_stdin_json()
    event = hook_event_name(payload).lower()
    agent = agent_name_from_payload(payload)

    if bridge_active():
        allow()
        return 0

    if not mutations_blocked_for_agent(agent):
        allow()
        return 0

    tool = tool_name_from_payload(payload)
    if tool and tool in MUTATING_TOOLS:
        deny(MSG, f"Blocked tool {tool} for agent {agent or 'unknown'}.")
        return 0

    if event in ("beforeshellexecution", "before_shell_execution", "") or shell_command_from_payload(payload):
        cmd = shell_command_from_payload(payload)
        if is_mutating_shell(cmd):
            deny(MSG, f"Blocked shell for agent {agent or 'unknown'}: {cmd[:200]}")
            return 0

    # preToolUse for Shell tool without beforeShellExecution split
    if tool == "Shell":
        cmd = shell_command_from_payload(payload)
        if is_mutating_shell(cmd):
            deny(MSG, f"Blocked Shell tool for agent {agent or 'unknown'}.")
            return 0

    allow()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        deny(f"deny-mutating-for-readonly hook error: {exc}", MSG)
        raise SystemExit(2) from exc
