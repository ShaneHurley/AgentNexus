from __future__ import annotations

from pathlib import Path

import pytest

from research_forge.schemas_pkg.registry import get_registry
from research_forge.wave1.composer import ReportComposer
from research_forge.wave1.extractor import EvidenceExtractor
from research_forge.wave1.verifier import CitationVerifier


@pytest.fixture
def registry(repo_root: Path):
    return get_registry(repo_root)


def test_extractor_rejects_recommendation_key(registry) -> None:
    ex = EvidenceExtractor(registry)
    read = {
        "access_level": "full",
        "chunks": [{"locator": "paragraph:1", "text": "Result was 50% (n=10)."}],
    }
    cards = ex.extract(source_id="SRC-0001", read_response=read, question_addressed="RQ-001")
    assert cards
    with pytest.raises(ValueError):
        bad = dict(cards[0])
        bad["recommendation"] = "buy"
        ex._reject_recommendations(bad)


def test_verifier_fake_doi(registry) -> None:
    v = CitationVerifier(registry)
    card = {
        "evidence_id": "EVD-00000001",
        "source_id": "SRC-0001",
        "question_addressed": "RQ-001",
        "claim": "Claim text here.",
        "claim_status": "UNKNOWN",
        "locator": "paragraph:1",
        "access_level": "full",
        "confidence": "MEDIUM",
        "confidence_reason": "test",
        "verifier_status": "pending",
    }
    source = {"canonical_title": "T", "canonical_url": "https://doi.org/10.0000/fake"}
    read = {"access_level": "full", "chunks": [{"locator": "paragraph:1", "text": "Claim text here."}]}
    out = v.verify(card, source=source, read_response=read)
    assert out["verifier_status"] == "failed"


def test_composer_material_claim_requires_evid(registry) -> None:
    comp = ReportComposer(registry)
    charter = {
        "objective": "o",
        "charter_id": "c",
        "version": 1,
        "intended_use": "u",
        "scope": "s",
        "non_goals": [],
        "research_questions": ["RQ-001"],
        "constraints": [],
        "assumptions": [],
        "access_rules": [],
        "recency": "r",
        "audience": "a",
        "depth": "standard",
        "output_contract": "brief",
        "charter_hash": "sha256:abc",
    }
    cards = [
        {
            "evidence_id": "BAD-001",
            "source_id": "SRC-0001",
            "claim": "x",
            "claim_status": "VERIFIED",
            "access_level": "full",
            "verifier_status": "passed",
        }
    ]
    with pytest.raises(ValueError):
        comp.compose_report(charter=charter, verified_cards=cards, unknowns=[])
