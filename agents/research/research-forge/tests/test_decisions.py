from __future__ import annotations

from pathlib import Path

from research_forge.decisions.validator import validate_decisions_for_gate


def test_wave0_passes_with_accepted_unknowns(repo_root: Path) -> None:
    ok, msgs = validate_decisions_for_gate(repo_root, "wave_0")
    assert ok, msgs


def test_wave1_live_fails_closed(repo_root: Path) -> None:
    ok, msgs = validate_decisions_for_gate(repo_root, "wave_1_live")
    assert not ok
    assert msgs
