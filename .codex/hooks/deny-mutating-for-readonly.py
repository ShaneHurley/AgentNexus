#!/usr/bin/env python3
"""preToolUse / beforeShellExecution: fail-closed for readonly or unknown agents (and mutating tools)."""

from __future__ import annotations

import re
import sys
import shlex
from pathlib import Path

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


def shell_substitution(command):
    quote=None
    escaped=False
    for index,char in enumerate(command):
        if escaped:
            escaped=False
            continue
        if char=="\\" and quote!="'":
            escaped=True
            continue
        if quote:
            if char==quote:
                quote=None
            elif quote=='"' and (char=="`" or command.startswith("$(",index)):
                return True
            continue
        if char in ("'",'"'):
            quote=char
        elif char in ("`", "\n") or command.startswith("$(",index):
            return True
    return False


def trusted_bridge_command(command):
    # Only a standalone installed bridge may bypass the shell-text heuristic.
    try:
        lexer=shlex.shlex(command,posix=True,punctuation_chars=True)
        lexer.whitespace=" \t\r"
        lexer.whitespace_split=True
        lexer.commenters=""
        words=list(lexer)
    except ValueError:
        return False
    if not words:
        return None
    executable=Path(words[0])
    if not executable.is_absolute():
        return None
    root=Path(__file__).resolve().parents[2]
    trusted=root/".venv/bin/ide-bridge"
    try:
        if not trusted.is_file() or executable.resolve()!=trusted.resolve():
            return None
    except OSError:
        return False
    if shell_substitution(command):
        return False
    if any(word=="\n" or all(char in lexer.punctuation_chars for char in word) for word in words):
        return False
    return len(words) not in (0,1) and words[1] in {"daily-coder","research-forge","doctor","plan-prep"}


def is_mutating_shell(command):
    if not command.strip():
        return False
    bridge=trusted_bridge_command(command)
    if bridge is not None:
        return not bridge
    return re.search(MUTATING_SHELL_RE,command) is not None

def main() -> int:
    payload = read_stdin_json()
    if payload.get("_parse_error"):
        deny(MSG, "Malformed hook input; mutation authority unavailable.")
        return 0
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
    if tool in {"Shell", "Bash"}:
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
