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
        role="unlisted_worker",
        phase="discovering",
        tool_id="unknown",
        operation="search",
        target="https://example.org",
    )
    assert not allowed
    assert dec["reason"] == "unknown_tool"


def test_registered_tool_denied_to_unlisted_role(gateway: PolicyGateway) -> None:
    allowed, dec = gateway.authorize(
        role="unlisted_worker",
        phase="discovering",
        tool_id="mock_search",
        operation="search",
        target="https://example.org",
    )
    assert not allowed
    assert dec["reason"] == "role_not_allowed"


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
    assert dec["reason"] == "unknown_tool" # registration itself rejected privilege expansion


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


def test_file_target_must_resolve_within_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside.txt"
    workspace.mkdir()
    outside.write_text("private", encoding="utf-8")
    (workspace / "escape.txt").symlink_to(outside)
    config = Path(__file__).resolve().parents[1] / "config" / "policies.yaml"
    gw = PolicyGateway(config, mode="mock", workspace_root=workspace)
    gw.register_tool(ToolManifest("mock_search", {
        "read": True, "write": False, "network": False, "execute": False,
        "credential": False, "data_class": "public",
    }))
    allowed, decision = gw.authorize(
        role="orchestrator", phase="read", tool_id="mock_search", operation="read",
        target=f"file://{workspace / 'escape.txt'}",
    )
    assert not allowed
    assert decision["reason"] == "path_guard"


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
