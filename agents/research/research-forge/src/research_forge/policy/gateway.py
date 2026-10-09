"""Policy Gateway — default-deny, read-only, audit events."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import yaml
from agent_core.contracts import ContractDenied
from agent_core.runtime_authority import RuntimeAuthority

from research_forge.errors import ErrorCode, ForgeError, forge_error, raise_forge
from research_forge.policy.manifest import ToolManifest


class PolicyGateway:
    def __init__(
        self,
        policy_path: Path,
        *,
        mode: str = "mock",
        workspace_root: Path | None = None,
        task_layers=None,
    ) -> None:
        with policy_path.open(encoding="utf-8") as f:
            self.policy = yaml.safe_load(f) or {}
        self.mode = mode
        self.workspace_root = (workspace_root or policy_path.parent.parent).expanduser().resolve()
        self.authority = RuntimeAuthority("rf",self.workspace_root,task_layers=task_layers)
        self._tools: dict[str, ToolManifest] = {}
        self.audit_log: list[dict[str, Any]] = []

    def register_tool(self, manifest: ToolManifest) -> ForgeError | None:
        errs = manifest.validate()
        if manifest.capabilities.get("credential") or (manifest.capabilities.get("write") and manifest.tool_id not in {"experiment.create", "experiment.pre_review", "experiment.run"}):
            errs.append("RF tools cannot acquire writes or raw credentials")
        if manifest.tool_id in self._tools:
            errs.append("registered tools cannot be replaced")
        if manifest.tool_id not in self.authority.snapshot.data["tools"]:
            errs.append("tool is not in compiled registry")
        if errs:
            return forge_error(ErrorCode.POLICY_DENIED, "Invalid tool manifest", errors=errs)
        self._tools[manifest.tool_id] = manifest
        return None

    def authorize(
        self,
        *,
        role: str,
        phase: str,
        tool_id: str,
        operation: str,
        target: str,
        confidentiality: str = "public",
        live: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        decision: dict[str, Any] = {
            "role": role,
            "phase": phase,
            "tool_id": tool_id,
            "operation": operation,
            "target_class": self._target_class(target),
            "live": live,
            "allowed": False,
            "rule": None,
            "reason": None,
        }

        if tool_id not in self._tools:
            decision["reason"] = "unknown_tool"
            self.audit_log.append(decision)
            return False, decision

        if live and self.policy.get("live_requires_flag"):
            if self.mode != "live":
                decision["reason"] = "live_requires_flag"
                self.audit_log.append(decision)
                return False, decision

        if operation.upper() in self.policy.get("blocked_http_methods", []):
            decision["reason"] = "blocked_http_method"
            self.audit_log.append(decision)
            return False, decision

        if operation in ("write_file", "delete_file", "execute", "install_package"):
            decision["reason"] = "read_only_violation"
            self.audit_log.append(decision)
            return False, decision

        if not self._path_guard(target):
            decision["reason"] = "path_guard"
            self.audit_log.append(decision)
            return False, decision

        if confidentiality == "restricted" and self._target_class(target) == "public_adapter":
            decision["reason"] = "confidentiality_routing"
            self.audit_log.append(decision)
            return False, decision

        role_tools = self.policy.get("role_tool_allowlist") or {}
        if tool_id not in role_tools.get(role, []):
            decision["reason"] = "role_not_allowed"
            self.audit_log.append(decision)
            return False, decision

        if self.policy.get("default_deny") and not self._explicit_allow(
            role, phase, tool_id, operation, confidentiality, live
        ):
            decision["reason"] = "default_deny"
            self.audit_log.append(decision)
            return False, decision

        try:
            resource = Path(unquote(urlparse(target).path)) if target.startswith("file://") else None
            self.authority.tool(role,tool_id,target=resource)
            caps = self._tools[tool_id].capabilities
            if operation in {"read", "search", "read_document"} and not caps["read"]:
                raise ContractDenied("tool does not declare reads")
            if target.startswith(("http://", "https://")) and not caps["network"]:
                raise ContractDenied("tool does not declare network")
        except ContractDenied as exc:
            decision["reason"] = "compiled_grant_denied"
            self.audit_log.append(decision)
            return False, decision
        decision["allowed"] = True
        decision["rule"] = "mock_read_only_allowlist"
        self.audit_log.append(decision)
        return True, decision

    def _explicit_allow(
        self,
        role: str,
        phase: str,
        tool_id: str,
        operation: str,
        confidentiality: str,
        live: bool,
    ) -> bool:
        allowed_mock = (
            tool_id.startswith("mock_")
            or tool_id.endswith("_v1")
            or tool_id in ("local_reader", "ledger_append", "ledger")
        )
        if operation in ("read", "search", "read_document", "model_call") and not live:
            return allowed_mock and not tool_id.startswith("public_")
        if operation in ("search", "read_document") and live:
            return tool_id.startswith("public_") or tool_id.startswith("web_") or tool_id.startswith("live_")
        if operation == "ledger_append" and tool_id == "ledger":
            return True
        if tool_id.startswith("experiment.") and phase == "local_experiment":
            if operation in (
                "experiment_create",
                "experiment_pre_review",
                "experiment_run",
                "experiment_read",
            ):
                return not live
        return False

    def _target_class(self, target: str) -> str:
        if target.startswith("adapter://public"):
            return "public_adapter"
        if target.startswith("file://"):
            return "local_file"
        return "other"

    def _path_guard(self, target: str) -> bool:
        if target.startswith("http://") or target.startswith("https://"):
            parsed = urlparse(target)
            if parsed.username or parsed.password:
                return False
            return True
        if target.startswith("file://"):
            parsed = urlparse(target)
            if parsed.netloc not in ("", "localhost"):
                return False
            raw_path = unquote(parsed.path)
            if not raw_path or ".." in Path(raw_path).as_posix().split("/"):
                return False
            try:
                Path(raw_path).expanduser().resolve().relative_to(self.workspace_root)
                return True
            except (OSError, ValueError):
                return False
        decoded = unquote(target)
        if ".." in decoded.replace("\\", "/"):
            return False
        return True

    def wrap_call(self, fn, **auth_kwargs):
        allowed, decision = self.authorize(**auth_kwargs)
        if not allowed:
            raise_forge(
                ErrorCode.POLICY_DENIED,
                decision.get("reason") or "denied",
                decision=decision,
            )
        return fn()
