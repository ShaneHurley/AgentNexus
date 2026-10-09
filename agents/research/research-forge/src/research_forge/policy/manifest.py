"""Tool capability manifest — undeclared capability blocks registration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REQUIRED_CAPS = frozenset({"read", "write", "network", "execute", "credential", "data_class"})


@dataclass
class ToolManifest:
    tool_id: str
    capabilities: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        for cap in REQUIRED_CAPS:
            if cap not in self.capabilities:
                errors.append(f"{self.tool_id}: missing capability {cap}")
        for cap in ("read", "write", "network", "execute", "credential"):
            if cap in self.capabilities and type(self.capabilities[cap]) is not bool:
                errors.append(f"{self.tool_id}: {cap} must be a boolean")
        if self.capabilities.get("data_class") not in {"public","local","internal","confidential","restricted"}:
            errors.append(f"{self.tool_id}: invalid data class")
        return errors
