"""Frozen Wave 1 role and adapter contracts (RF-W1-A-04)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

WAVE1_INTERFACE_VERSION = "1.0.0"


@dataclass(frozen=True)
class RoleContract:
    role_id: str
    interface_version: str
    input_schema: str
    output_schema: str
    allowed_operations: frozenset[str]


WAVE1_ROLE_CONTRACTS: dict[str, RoleContract] = {
    "intake_clarifier": RoleContract(
        role_id="intake_clarifier",
        interface_version=WAVE1_INTERFACE_VERSION,
        input_schema="research_request",
        output_schema="clarification_result",
        allowed_operations=frozenset({"evaluate", "clarify", "merge"}),
    ),
    "charter_planner": RoleContract(
        role_id="charter_planner",
        interface_version=WAVE1_INTERFACE_VERSION,
        input_schema="research_request",
        output_schema="research_charter",
        allowed_operations=frozenset({"plan", "freeze"}),
    ),
    "evidence_extractor": RoleContract(
        role_id="evidence_extractor",
        interface_version=WAVE1_INTERFACE_VERSION,
        input_schema="source_record",
        output_schema="evidence_card",
        allowed_operations=frozenset({"extract"}),
    ),
    "citation_verifier": RoleContract(
        role_id="citation_verifier",
        interface_version=WAVE1_INTERFACE_VERSION,
        input_schema="evidence_card",
        output_schema="evidence_card",
        allowed_operations=frozenset({"verify"}),
    ),
    "report_composer": RoleContract(
        role_id="report_composer",
        interface_version=WAVE1_INTERFACE_VERSION,
        input_schema="research_packet",
        output_schema="research_packet",
        allowed_operations=frozenset({"compose", "serialize"}),
    ),
}


@dataclass(frozen=True)
class AdapterContract:
    adapter_kind: str
    interface_version: str
    adapter_id: str


@runtime_checkable
class SearchAdapterProtocol(Protocol):
    adapter_id: str

    def search(
        self,
        query: str,
        *,
        page_size: int = 10,
        cursor: str | int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


@runtime_checkable
class ReaderAdapterProtocol(Protocol):
    adapter_id: str

    def read(
        self,
        source_ref: dict[str, Any],
        *,
        locator: str | None = None,
    ) -> dict[str, Any]: ...


def assert_conforms(role_or_adapter: Any, contract: RoleContract | AdapterContract) -> None:
    if isinstance(contract, RoleContract):
        if getattr(role_or_adapter, "role_id", None) != contract.role_id:
            raise ValueError(f"role_id mismatch: expected {contract.role_id}")
        if getattr(role_or_adapter, "interface_version", None) != contract.interface_version:
            raise ValueError("interface_version mismatch")
    elif isinstance(contract, AdapterContract):
        if getattr(role_or_adapter, "adapter_id", None) != contract.adapter_id:
            raise ValueError(f"adapter_id mismatch: expected {contract.adapter_id}")
