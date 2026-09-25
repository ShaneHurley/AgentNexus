from __future__ import annotations

from pathlib import Path

import pytest

from research_forge.policy.gateway import PolicyGateway
from research_forge.policy.manifest import ToolManifest


@pytest.fixture
def gateway(repo_root: Path) -> PolicyGateway:
    gw = PolicyGateway(repo_root / "config" / "policies.yaml", mode="mock")
    gw.register_tool(
        ToolManifest(
            "mock_search",
            {
                "read": True,
                "write": False,
                "network": True,
                "execute": False,
                "credential": False,
                "data_class": "public",
            },
        )
    )
    return gw


def test_default_deny_unknown_tool(gateway: PolicyGateway) -> None:
    allowed, dec = gateway.authorize(
        role="scout",
        phase="discovering",
        tool_id="unknown",
        operation="search",
        target="https://example.org",
    )
    assert not allowed
    assert dec["reason"] == "unknown_tool"


def test_mutating_operation_denied(gateway: PolicyGateway) -> None:
    gateway.register_tool(
        ToolManifest(
            "bad",
            {
                "read": True,
                "write": True,
                "network": True,
                "execute": True,
                "credential": False,
                "data_class": "public",
            },
        )
    )
    allowed, dec = gateway.authorize(
        role="host",
        phase="wave0",
        tool_id="bad",
        operation="write_file",
        target="/tmp/x",
    )
    assert not allowed
    assert dec["reason"] == "read_only_violation"


def test_path_traversal_blocked(gateway: PolicyGateway) -> None:
    allowed, dec = gateway.authorize(
        role="host",
        phase="wave0",
        tool_id="mock_search",
        operation="read",
        target="file:///etc/../etc/passwd",
    )
    assert not allowed
    assert dec["reason"] == "path_guard"


def test_audit_event_per_attempt(gateway: PolicyGateway) -> None:
    gateway.authorize(
        role="host",
        phase="wave0",
        tool_id="mock_search",
        operation="search",
        target="https://example.org",
    )
    assert len(gateway.audit_log) == 1


def test_restricted_confidentiality_public_adapter(gateway: PolicyGateway) -> None:
    allowed, dec = gateway.authorize(
        role="host",
        phase="wave0",
        tool_id="mock_search",
        operation="search",
        target="adapter://public/search",
        confidentiality="restricted",
    )
    assert not allowed
    assert dec["reason"] == "confidentiality_routing"
