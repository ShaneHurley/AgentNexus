from __future__ import annotations

from research_forge.registries.evidence import EvidenceRegistry
from research_forge.registries.normalize import canonical_key, normalize_url
from research_forge.registries.source import SourceRegistry


def test_url_normalization_equivalent() -> None:
    a = normalize_url("https://Example.org/path/?b=2&a=1")
    b = normalize_url("https://example.org/path?a=1&b=2")
    assert a == b
    assert canonical_key("url", "https://Example.org/path") == canonical_key(
        "url", "https://example.org/path/"
    )


def test_evidence_requires_source() -> None:
    reg = EvidenceRegistry([], {})
    errs = reg.validate_new_card(
        {
            "evidence_id": "e1",
            "source_id": "missing",
            "atomic_claim": "x",
            "verifier_status": "pass",
        }
    )
    assert "source_id missing or unknown" in errs[0]


def test_laundering_independent_roots() -> None:
    events = [
        {
            "sequence": 1,
            "event_type": "source_registered",
            "payload": {
                "source_id": "p",
                "identifiers": [],
                "primary_or_derivative": "primary",
            },
        },
        {
            "sequence": 2,
            "event_type": "source_registered",
            "payload": {
                "source_id": "d1",
                "provenance_parent_ids": ["p"],
                "identifiers": [],
                "primary_or_derivative": "derivative",
            },
        },
        {
            "sequence": 3,
            "event_type": "source_registered",
            "payload": {
                "source_id": "d2",
                "provenance_parent_ids": ["p"],
                "identifiers": [],
                "primary_or_derivative": "derivative",
            },
        },
    ]
    src = SourceRegistry.from_events(events)
    roots = src.independent_roots(["d1", "d2"])
    assert len(roots) == 1
