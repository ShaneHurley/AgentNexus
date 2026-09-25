from __future__ import annotations

from research_forge.hashing.provenance import ProvenanceValidator


def test_cycle_fixture_fails() -> None:
    sources = {
        "a": {"content_hash": "sha256:1", "provenance_parent_ids": ["b"]},
        "b": {"content_hash": "sha256:2", "provenance_parent_ids": ["a"]},
    }
    report = ProvenanceValidator(sources).validate()
    assert report.cycles
    assert not report.ok


def test_laundering_fixture_fails() -> None:
    sources = {
        "root": {"content_hash": "sha256:r", "primary_or_derivative": "primary"},
        "d1": {
            "content_hash": "sha256:1",
            "primary_or_derivative": "derivative",
            "provenance_parent_ids": ["root"],
        },
        "d2": {
            "content_hash": "sha256:2",
            "primary_or_derivative": "derivative",
            "provenance_parent_ids": ["root"],
        },
    }
    report = ProvenanceValidator(sources).validate()
    assert "derivative_cluster_single_root" in report.laundering_flags
