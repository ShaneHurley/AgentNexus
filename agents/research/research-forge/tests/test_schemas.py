from __future__ import annotations

from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

from research_forge.schemas_pkg.claim_status import (
    assumption_may_drive_recommendation,
    legal_claim_transitions,
)
from research_forge.schemas_pkg.registry import get_registry


def test_research_request_valid_invalid(repo_root: Path) -> None:
    reg = get_registry(repo_root)
    reg.validate("research_request", {"topic": "quantum error correction"})
    with pytest.raises(ValidationError):
        reg.validate("research_request", {"topic": "x", "extra": True})


def test_schema_version_migration(repo_root: Path) -> None:
    reg = get_registry(repo_root)
    with pytest.raises(ValidationError):
        reg.validate_version("0.9.0")


def test_claim_transitions() -> None:
    assert legal_claim_transitions("ASSUMPTION", "INFERENCE")
    assert not assumption_may_drive_recommendation("ASSUMPTION")
