"""Shared policy helpers for IDE pack Cursor hooks (soft least-privilege; not PolicyGateway)."""

from __future__ import annotations

import fnmatch
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = REPO_ROOT / "agents" / "ide" / "policy"
AUDIT_DIR = REPO_ROOT / "agents" / "ide" / ".ide-agents" / "audit"

MUTATING_TOOLS = frozenset(
    {
        "Write",
        "StrReplace",
        "Delete",
        "EditNotebook",
        "ApplyPatch",
        "NotebookEdit",
    }
)

# JavaScript-style patterns checked in Python via simple heuristics + fnmatch
MUTATING_SHELL_RE = (
    r"(?i)(\brm\b|\brmdir\b|\bdel\b|\berase\b|\bmv\b|\bmove\b|\bcp\b|\bcopy\b"
    r"|\btee\b|\btruncate\b|\bchmod\b|\bchown\b|\bmkdir\b|\btouch\b"
    r"|>\s*[^\s]|>>\s*[^\s]"
    r"|\bgit\s+(commit|push|reset\s+--hard|clean\s+-f|checkout\s+-f|rebase|merge|cherry-pick|am)\b"
    r"|\bnpm\s+(install|unpublish|publish)\b|\bpip\s+install\b|\bcargo\s+install\b"
    r"|\bpnpm\s+(add|install)\b|\byarn\s+add\b)"
)


def read_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {"_parse_error": True, "_raw": raw[:2000]}


def emit(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()


def deny(user_message: str, agent_message: str | None = None) -> None:
    payload: dict[str, Any] = {"permission": "deny", "user_message": user_message}
    if agent_message:
        payload["agent_message"] = agent_message
    emit(payload)


def allow() -> None:
    emit({"permission": "allow"})


def _load_json_list(path: Path, key: str) -> list[str]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    agents = data.get(key, [])
    if not isinstance(agents, list):
        return []
    return [str(a).strip() for a in agents if str(a).strip()]


def readonly_agents() -> frozenset[str]:
    return frozenset(_load_json_list(POLICY_DIR / "readonly-agents.json", "agents"))


def write_allowlist_agents() -> frozenset[str]:
    return frozenset(_load_json_list(POLICY_DIR / "write-allowlist-agents.json", "agents"))


def secret_deny_globs() -> list[str]:
    path = POLICY_DIR / "secret-deny-globs.json"
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    globs = data.get("globs", [])
    if not isinstance(globs, list):
        return []
    return [str(g) for g in globs]


def bridge_active() -> bool:
    return os.environ.get("IDE_BRIDGE_ACTIVE") == "1"


def agent_name_from_payload(payload: dict[str, Any]) -> str | None:
    for key in (
        "agent",
        "agentName",
        "activeAgent",
        "subagent",
        "subagentType",
        "subagent_name",
        "subagentName",
        "name",
    ):
        val = payload.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    nested = payload.get("subagentInfo") or payload.get("context")
    if isinstance(nested, dict):
        return agent_name_from_payload(nested)
    env = os.environ.get("CURSOR_AGENT") or os.environ.get("IDE_PACK_ACTIVE_AGENT")
    return env.strip() if env and env.strip() else None


# Cursor / Task built-ins — never treat as ide-agents agents (subagentStart must allow).
PLATFORM_SUBAGENT_TYPES = frozenset(
    {
        "generalPurpose",
        "explore",
        "shell",
        "browser",
        "best-of-n-runner",
        "ci-investigator",
        "cursor-guide",
        "docs-researcher",
        "doc-reader",
        "codebase-navigator",
        "enterprise-searcher",
        "meeting-analyzer",
        "people-finder",
        "plan-prep-researcher",
        "project-synthesizer",
        "skill-generator",
        "activity-analyzer",
        "work-pattern-analyzer",
        "bugbot",
        "security-review",
        "Bash",
        "Explore",
        "Browser",
        "media-review",
    }
)


def is_platform_subagent(name: str | None) -> bool:
    if not name:
        return False
    return name in PLATFORM_SUBAGENT_TYPES or name.lower() in {
        x.lower() for x in PLATFORM_SUBAGENT_TYPES
    }


def agent_authority_class(name: str | None) -> str:
    """readonly | allowlisted | platform | parent | unknown.

    - parent (no name): main Cursor agent session — writes allowed (pack development).
    - platform: Task built-ins — writes allowed unless also listed readonly (they aren't).
    - readonly: ide-agents research/master roles — mutations denied.
    - unknown named agent: fail-closed for mutations (spoof resistance).
    """
    if name and name in write_allowlist_agents():
        return "allowlisted"
    if name and name in readonly_agents():
        return "readonly"
    if not name:
        return "parent"
    if is_platform_subagent(name):
        return "platform"
    return "unknown"


def mutations_blocked_for_agent(name: str | None) -> bool:
    if bridge_active():
        return False
    auth = agent_authority_class(name)
    return auth in ("readonly", "unknown")


def normalize_path_for_match(path: str) -> str:
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if p.startswith("/"):
        p = p[1:]
    return p


def _glob_matches_path(pattern: str, norm: str, base: str) -> bool:
    pat = pattern.replace("\\", "/")
    if fnmatch.fnmatch(norm, pat) or fnmatch.fnmatch(base, pat):
        return True
    # **/foo → match any path suffix or basename
    if pat.startswith("**/"):
        suffix = pat[3:]
        if norm.endswith("/" + suffix) or norm == suffix:
            return True
        if fnmatch.fnmatch(base, suffix):
            return True
    tail = pat.split("/")[-1]
    if tail.startswith("*") and fnmatch.fnmatch(base, tail):
        return True
    return False


def path_denied_by_globs(file_path: str, globs: list[str]) -> str | None:
    norm = normalize_path_for_match(file_path)
    base = norm.split("/")[-1]
    base_lower = base.lower()
    for pattern in globs:
        if _glob_matches_path(pattern, norm, base):
            return pattern
    lowered = norm.lower()
    if base_lower == ".env" or base_lower.startswith(".env."):
        return "**/.env*"
    for fragment in ("secret", "credential", "id_rsa"):
        if fragment in lowered:
            return f"*{fragment}*"
    if base_lower.endswith(".pem"):
        return "**/*.pem"
    return None


def append_audit(record: dict[str, Any]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    line = dict(record)
    line.setdefault("ts", datetime.now(timezone.utc).isoformat())
    path = AUDIT_DIR / "sessions.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def hook_event_name(payload: dict[str, Any]) -> str:
    for key in ("hook_event", "event", "hookEvent", "type"):
        val = payload.get(key)
        if val:
            return str(val)
    return os.environ.get("CURSOR_HOOK_EVENT", "")


def tool_name_from_payload(payload: dict[str, Any]) -> str | None:
    for key in ("tool_name", "toolName", "tool", "name"):
        val = payload.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    inp = payload.get("input")
    if isinstance(inp, dict):
        for key in ("tool", "tool_name"):
            val = inp.get(key)
            if val:
                return str(val).strip()
    return None


def shell_command_from_payload(payload: dict[str, Any]) -> str:
    for key in ("command", "shellCommand", "cmd"):
        val = payload.get(key)
        if val is not None:
            return str(val)
    inp = payload.get("input")
    if isinstance(inp, dict):
        for key in ("command", "cmd"):
            if inp.get(key):
                return str(inp[key])
    return ""


def file_path_from_payload(payload: dict[str, Any]) -> str:
    for key in ("file_path", "filePath", "path", "file"):
        val = payload.get(key)
        if val is not None and str(val).strip():
            return str(val)
    inp = payload.get("input")
    if isinstance(inp, dict):
        for key in ("file_path", "path", "filePath"):
            if inp.get(key):
                return str(inp[key])
    return ""
