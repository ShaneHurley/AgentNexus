"""Unit tests for Cursor IDE pack hooks (stdin JSON fixtures)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / ".cursor" / "hooks"


def run_hook(script: str, payload: dict, *, env: dict | None = None) -> dict:
    proc_env = os.environ.copy()
    # Fail-closed tests must not inherit live bridge or agent context from the parent shell.
    for key in ("IDE_BRIDGE_ACTIVE", "CURSOR_AGENT", "IDE_PACK_ACTIVE_AGENT", "CURSOR_HOOK_EVENT"):
        proc_env.pop(key, None)
    if env:
        proc_env.update(env)
    proc = subprocess.run(
        [sys.executable, str(HOOKS_DIR / script)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=str(HOOKS_DIR),
        env=proc_env,
        check=False,
    )
    if proc.stderr.strip():
        # Hooks should not write stderr on success paths
        pass
    out = proc.stdout.strip()
    if not out:
        return {"permission": "missing", "stderr": proc.stderr}
    return json.loads(out)


class TestEnforceAgentAuthority(unittest.TestCase):
    def test_unknown_subagent_allowed_at_start(self) -> None:
        out = run_hook("enforce-agent-authority.py", {"subagentName": "mystery-agent"})
        self.assertEqual(out.get("permission"), "allow")

    def test_readonly_subagent_allowed_with_reminder(self) -> None:
        out = run_hook("enforce-agent-authority.py", {"agent": "deep-research"})
        self.assertEqual(out.get("permission"), "allow")
        self.assertIn("read-only", (out.get("user_message") or "").lower())


class TestDenyMutatingForReadonly(unittest.TestCase):
    def test_parent_session_allows_write_tool(self) -> None:
        out = run_hook("deny-mutating-for-readonly.py", {"tool_name": "Write"})
        self.assertEqual(out.get("permission"), "allow")

    def test_write_tool_blocked_for_research(self) -> None:
        out = run_hook(
            "deny-mutating-for-readonly.py",
            {"agent": "deep-research", "tool_name": "Write"},
        )
        self.assertEqual(out.get("permission"), "deny")

    def test_mutating_shell_blocked_for_unknown(self) -> None:
        out = run_hook(
            "deny-mutating-for-readonly.py",
            {"agent": "not-in-roster", "command": "git commit -m x"},
        )
        self.assertEqual(out.get("permission"), "deny")

    def test_bridge_active_allows(self) -> None:
        out = run_hook(
            "deny-mutating-for-readonly.py",
            {"agent": "deep-research", "tool_name": "Write"},
            env={"IDE_BRIDGE_ACTIVE": "1"},
        )
        self.assertEqual(out.get("permission"), "allow")


class TestDenyUnbridgedWrites(unittest.TestCase):
    def test_unbridged_edit_denied_for_unknown_named(self) -> None:
        out = run_hook(
            "deny-unbridged-writes.py",
            {"agent": "implementer", "file_path": "src/foo.py"},
        )
        self.assertEqual(out.get("permission"), "deny")

    def test_unbridged_edit_denied_for_readonly(self) -> None:
        out = run_hook(
            "deny-unbridged-writes.py",
            {"agent": "deep-research", "file_path": "src/foo.py"},
        )
        self.assertEqual(out.get("permission"), "deny")

    def test_parent_session_allows_unbridged_edit(self) -> None:
        out = run_hook("deny-unbridged-writes.py", {"file_path": "ide-agents/README.md"})
        self.assertEqual(out.get("permission"), "allow")

    def test_platform_subagent_allows_unbridged_edit(self) -> None:
        out = run_hook(
            "deny-unbridged-writes.py",
            {"subagentName": "generalPurpose", "file_path": "ide-agents/README.md"},
        )
        self.assertEqual(out.get("permission"), "allow")

    def test_bridge_active_allows_edit(self) -> None:
        out = run_hook(
            "deny-unbridged-writes.py",
            {"agent": "implementer", "file_path": "src/foo.py"},
            env={"IDE_BRIDGE_ACTIVE": "1"},
        )
        self.assertEqual(out.get("permission"), "allow")


class TestPathJailAudit(unittest.TestCase):
    def test_env_file_denied(self) -> None:
        out = run_hook("path-jail-audit.py", {"file_path": ".env"})
        self.assertEqual(out.get("permission"), "deny")

    def test_normal_source_allowed(self) -> None:
        out = run_hook("path-jail-audit.py", {"file_path": "ide-agents/README.md"})
        self.assertEqual(out.get("permission"), "allow")


class TestIdePackPolicy(unittest.TestCase):
    def test_policy_module_import(self) -> None:
        sys.path.insert(0, str(HOOKS_DIR))
        try:
            import _ide_pack_policy as pol  # noqa: PLC0415

            self.assertIn("deep-research", pol.readonly_agents())
            self.assertTrue(pol.mutations_blocked_for_agent("unknown-agent"))
            self.assertFalse(pol.mutations_blocked_for_agent("unknown-agent") and pol.bridge_active())
        finally:
            sys.path.remove(str(HOOKS_DIR))


if __name__ == "__main__":
    unittest.main()
