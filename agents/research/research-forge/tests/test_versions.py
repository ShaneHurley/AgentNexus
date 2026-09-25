from __future__ import annotations

from research_forge.versions import format_manifest


def test_manifest_deterministic() -> None:
    a = format_manifest()
    b = format_manifest()
    assert a == b
    assert "application=0.1.0+wave0" in a
