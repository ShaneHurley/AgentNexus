from __future__ import annotations

from pathlib import Path

import pytest

from research_forge.decisions.validator import validate_decisions_for_gate
from research_forge.settings import load_settings
from research_forge.wave1.interfaces import WAVE1_INTERFACE_VERSION, WAVE1_ROLE_CONTRACTS
from research_forge.wave1.live_gate import build_live_contract, effective_mode, validate_live_contract


def test_wave1_mock_gate_passes(repo_root: Path) -> None:
    ok, msgs = validate_decisions_for_gate(repo_root, "wave_1_mock")
    assert ok, msgs


def test_unauthorized_live_blocked(repo_root: Path) -> None:
    settings = load_settings(repo_root)
    contract = build_live_contract(cli_live=True, settings=settings, approval_record_id=None)
    ok, msgs, err = validate_live_contract(repo_root, contract)
    assert not ok
    assert any("approval" in m for m in msgs)
    assert err is not None


def test_env_live_without_cli_stays_mock(repo_root: Path) -> None:
    settings = load_settings(repo_root, cli_overrides={"mode": "live"})
    assert effective_mode(settings, cli_live=False) == "mock"


@pytest.mark.parametrize("role_id", list(WAVE1_ROLE_CONTRACTS))
def test_role_contract_version(role_id: str) -> None:
    c = WAVE1_ROLE_CONTRACTS[role_id]
    assert c.interface_version == WAVE1_INTERFACE_VERSION
