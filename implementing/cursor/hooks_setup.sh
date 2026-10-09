#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CURSOR_DIR="$REPO_ROOT/.cursor"
HOOKS_DIR="$CURSOR_DIR/hooks"

echo "Setting up Cursor hooks in $HOOKS_DIR..."
mkdir -p "$HOOKS_DIR"
mkdir -p "$REPO_ROOT/agents/ide/.ide-agents/audit"

# 1. Helper policy module
cat << 'EOF' > "$HOOKS_DIR/_ide_pack_policy.py"
"""Cursor hook policy helpers for AgentNexus."""
from __future__ import annotations
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = REPO_ROOT / "agents" / "ide" / "policy"

PLATFORM_AGENTS = frozenset({"generalPurpose", "explore", "shell", "terminal"})

def load_json_list(filename: str) -> frozenset[str]:
    p = POLICY_DIR / filename
    if not p.is_file():
        return frozenset()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return frozenset(data)
        if isinstance(data, dict) and "agents" in data and isinstance(data["agents"], list):
            return frozenset(data["agents"])
    except Exception:
        pass
    return frozenset()

def readonly_agents() -> frozenset[str]:
    agents = set(load_json_list("readonly-agents.json"))
    if not agents:
        agents = {
            "deep-research", "research-messenger", "plan-prep", "use-master",
            "researcher", "academic-evidence-scout", "adversarial-evidence-reviewer",
            "adversarial-skeptic", "alignment-checker", "citation-verifier",
            "plan-reviewer", "planner"
        }
    return frozenset(agents)

def write_allowlist_agents() -> frozenset[str]:
    return load_json_list("write-allowlist-agents.json")

def secret_deny_globs() -> list[str]:
    p = POLICY_DIR / "secret-deny-globs.json"
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return [".env*", "*.pem", "*.key", "id_rsa*", "*credentials*"]

def bridge_active() -> bool:
    return os.environ.get("IDE_BRIDGE_ACTIVE") == "1"

def mutations_blocked_for_agent(agent: str | None) -> bool:
    if bridge_active():
        return False
    if not agent:
        return False  # Parent session allows
    if agent in PLATFORM_AGENTS:
        return False
    if agent in write_allowlist_agents():
        return False
    return True  # Readonly and unknown named agents blocked
EOF

# 2. enforce-agent-authority.py
cat << 'EOF' > "$HOOKS_DIR/enforce-agent-authority.py"
#!/usr/bin/env python3
import json
import sys
from _ide_pack_policy import readonly_agents

def main():
    try:
        raw = sys.stdin.read().strip()
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}
    
    agent = data.get("agent") or data.get("subagentName") or ""
    if agent in readonly_agents():
        out = {
            "permission": "allow",
            "user_message": f"Agent {agent} is active with read-only authority. Mutating tools are disabled."
        }
    else:
        out = {"permission": "allow"}
    print(json.dumps(out))

if __name__ == "__main__":
    main()
EOF

# 3. deny-mutating-for-readonly.py
cat << 'EOF' > "$HOOKS_DIR/deny-mutating-for-readonly.py"
#!/usr/bin/env python3
import json
import sys
from _ide_pack_policy import mutations_blocked_for_agent, bridge_active

MUTATING_TOOLS = frozenset({"Write", "Delete", "StrReplace", "EditNotebook", "Shell"})
MUTATING_SHELL_PREFIXES = ("git commit", "git push", "rm ", "mv ", "cp ", "touch ", "sed ", "awk -i")

def main():
    try:
        raw = sys.stdin.read().strip()
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}

    agent = data.get("agent") or data.get("subagentName")
    tool = data.get("tool_name")
    cmd = (data.get("command") or "").strip()

    if bridge_active() or not agent:
        print(json.dumps({"permission": "allow"}))
        return

    if mutations_blocked_for_agent(agent):
        if tool in MUTATING_TOOLS:
            print(json.dumps({"permission": "deny", "reason": f"Tool {tool} denied for agent {agent}"}))
            return
        if cmd and any(cmd.startswith(p) for p in MUTATING_SHELL_PREFIXES):
            print(json.dumps({"permission": "deny", "reason": f"Mutating shell command denied for {agent}"}))
            return

    print(json.dumps({"permission": "allow"}))

if __name__ == "__main__":
    main()
EOF

# 4. path-jail-audit.py
cat << 'EOF' > "$HOOKS_DIR/path-jail-audit.py"
#!/usr/bin/env python3
import fnmatch
import json
import sys
from pathlib import Path
from _ide_pack_policy import secret_deny_globs

def main():
    try:
        raw = sys.stdin.read().strip()
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}

    file_path = data.get("file_path") or ""
    filename = Path(file_path).name

    for pattern in secret_deny_globs():
        if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(file_path, pattern):
            print(json.dumps({"permission": "deny", "reason": f"Path {file_path} matches protected secret pattern"}))
            return

    print(json.dumps({"permission": "allow"}))

if __name__ == "__main__":
    main()
EOF

# 5. deny-unbridged-writes.py
cat << 'EOF' > "$HOOKS_DIR/deny-unbridged-writes.py"
#!/usr/bin/env python3
import json
import sys
from _ide_pack_policy import mutations_blocked_for_agent, bridge_active

def main():
    try:
        raw = sys.stdin.read().strip()
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}

    agent = data.get("agent") or data.get("subagentName")
    if bridge_active() or not agent:
        print(json.dumps({"permission": "allow"}))
        return

    if mutations_blocked_for_agent(agent):
        print(json.dumps({"permission": "deny", "reason": f"Unbridged file write denied for agent {agent}"}))
        return

    print(json.dumps({"permission": "allow"}))

if __name__ == "__main__":
    main()
EOF

# 6. session-audit.py
cat << 'EOF' > "$HOOKS_DIR/session-audit.py"
#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path
from _ide_pack_policy import REPO_ROOT

AUDIT_DIR = REPO_ROOT / "agents" / "ide" / ".ide-agents" / "audit"

def main():
    try:
        raw = sys.stdin.read().strip()
        data = json.loads(raw) if raw else {}
    except Exception:
        data = {}

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_file = AUDIT_DIR / "cursor_sessions.jsonl"
    record = {
        "timestamp": time.time(),
        "event": "stop",
        "data": data
    }
    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    print(json.dumps({"permission": "allow"}))

if __name__ == "__main__":
    main()
EOF

# 7. Write .cursor/hooks.json
cat << 'EOF' > "$CURSOR_DIR/hooks.json"
{
  "version": 1,
  "hooks": {
    "subagentStart": [
      {
        "command": "python3 .cursor/hooks/enforce-agent-authority.py",
        "failClosed": true
      }
    ],
    "preToolUse": [
      {
        "command": "python3 .cursor/hooks/deny-mutating-for-readonly.py",
        "failClosed": true
      }
    ],
    "beforeReadFile": [
      {
        "command": "python3 .cursor/hooks/path-jail-audit.py",
        "failClosed": true
      }
    ],
    "afterFileEdit": [
      {
        "command": "python3 .cursor/hooks/deny-unbridged-writes.py",
        "failClosed": true
      }
    ],
    "stop": [
      {
        "command": "python3 .cursor/hooks/session-audit.py",
        "failClosed": false
      }
    ]
  }
}
EOF

chmod +x "$HOOKS_DIR"/*.py
echo "Cursor hooks successfully installed and configured."
