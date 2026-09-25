"""Adapter capability manifest validation (RF-W6-A-03)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

KNOWN_CAPABILITIES = frozenset(
    {
        "network",
        "credential",
        "read",
        "write",
        "execute",
        "pagination",
        "rate_limit",
        "retry",
        "hash_content",
        "locator",
        "access_disclosure",
        "data_class",
    }
)

KNOWN_DATA_CLASSES = frozenset({"public", "internal", "confidential", "restricted"})
KNOWN_OPERATIONS = frozenset({"search", "read", "metadata", "list"})


@dataclass
class AdapterCapabilityManifest:
    adapter_id: str
    version: str
    protocol_version: str
    capabilities: dict[str, Any] = field(default_factory=dict)
    allowed_operations: list[str] = field(default_factory=list)
    network: bool = False
    credential: bool = False
    data_class: str = "public"

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.adapter_id:
            errors.append("missing_adapter_id")
        if not self.version:
            errors.append("missing_version")
        for key in self.capabilities:
            if key not in KNOWN_CAPABILITIES:
                errors.append(f"unknown_capability:{key}")
        if self.data_class not in KNOWN_DATA_CLASSES:
            errors.append(f"invalid_data_class:{self.data_class}")
        for op in self.allowed_operations:
            if op not in KNOWN_OPERATIONS:
                errors.append(f"unknown_operation:{op}")
        if self.capabilities.get("write"):
            errors.append("write_not_permitted")
        if self.capabilities.get("execute"):
            errors.append("execute_not_permitted")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "version": self.version,
            "protocol_version": self.protocol_version,
            "capabilities": self.capabilities,
            "allowed_operations": self.allowed_operations,
            "network": self.network,
            "credential": self.credential,
            "data_class": self.data_class,
        }
