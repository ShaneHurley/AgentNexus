"""Deterministic policy gateway.

Every role-originated tool call passes through here. The gateway authorizes the role,
applies path/network/write policy, enforces human approval for repository writes,
executes through the broker, redacts output, and records immutable evidence.
"""
from __future__ import annotations
import time
from .tool_broker import ToolDenied
from .util import canonical_json, sha256_text

class ApprovalRequired(RuntimeError):
    def __init__(self, kind, subject_hash, detail=None):
        super().__init__(f"approval required: {kind}")
        self.kind = kind; self.subject_hash = subject_hash; self.detail = detail or {}

WRITE_TOOLS = {"filesystem.write", "patch.apply"}

class PolicyGateway:
    def __init__(self, broker, state, policies, approvals_required=True):
        self.broker = broker
        self.state = state
        self.policies = policies
        self.approvals_required = approvals_required

    def execute(self, run_id, role, phase, tool, arguments, plan_allowlist=None, plan_hash=None):
        started = time.time()
        try:
            self.broker.authorize(role, tool)
            if tool in WRITE_TOOLS and self.approvals_required:
                state = self.state.approval_state(run_id, "plan", plan_hash)
                if state != "approved":
                    raise ApprovalRequired("plan", plan_hash, {"tool": tool})
            result = self.broker.execute(role, tool, arguments, plan_allowlist=plan_allowlist)
            digest = sha256_text(canonical_json(result))
            self.state.record_tool_call(run_id, role, phase, tool, arguments, "allow", None, digest,
                                        int((time.time() - started) * 1000))
            return result
        except ApprovalRequired as exc:
            self.state.record_tool_call(run_id, role, phase, tool, arguments, "blocked", str(exc), None,
                                        int((time.time() - started) * 1000))
            raise
        except ToolDenied as exc:
            self.state.record_tool_call(run_id, role, phase, tool, arguments, "deny", str(exc), None,
                                        int((time.time() - started) * 1000))
            raise
        except Exception as exc:
            self.state.record_tool_call(run_id, role, phase, tool, arguments, "error", f"{type(exc).__name__}: {exc}",
                                        None, int((time.time() - started) * 1000))
            raise

    def safe_execute(self, run_id, role, phase, tool, arguments, plan_allowlist=None, plan_hash=None):
        """Return a structured error instead of raising, so a model turn can recover."""
        try:
            return {"ok": True, "result": self.execute(run_id, role, phase, tool, arguments, plan_allowlist, plan_hash)}
        except ApprovalRequired as exc:
            return {"ok": False, "error": "approval_required", "message": str(exc), "kind": exc.kind}
        except ToolDenied as exc:
            return {"ok": False, "error": "denied", "message": str(exc)}
        except Exception as exc:
            return {"ok": False, "error": type(exc).__name__, "message": str(exc)[:2000]}
