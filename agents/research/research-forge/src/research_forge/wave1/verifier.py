"""Citation Verifier — fail closed on identity/entailment (RF-W1-G)."""

from __future__ import annotations

import re
import hashlib
from typing import Any

from research_forge.schemas_pkg.claim_status import legal_claim_transitions
from research_forge.schemas_pkg.registry import SchemaRegistry
from research_forge.wave1.interfaces import WAVE1_INTERFACE_VERSION, WAVE1_ROLE_CONTRACTS, assert_conforms


class CitationVerifier:
    role_id = "citation_verifier"
    interface_version = WAVE1_INTERFACE_VERSION

    def __init__(self, registry: SchemaRegistry, *, entailment_checker=None) -> None:
        assert_conforms(self, WAVE1_ROLE_CONTRACTS["citation_verifier"])
        self._registry = registry
        self._entailment_checker = entailment_checker

    def verify(
        self,
        card: dict[str, Any],
        *,
        source: dict[str, Any],
        read_response: dict[str, Any],
        provenance_graph: dict[str, list[str]] | None = None,
        live: bool = False,
    ) -> dict[str, Any]:
        verified = dict(card)
        notes: list[str] = []
        passed = True

        retrieval = read_response.get("metadata") or {}
        if live and (
            source.get("source_authenticity") == "synthetic_fixture"
            or retrieval.get("synthetic")
            or retrieval.get("retrieval_status") == "fixture"
        ):
            passed = False
            notes.append("synthetic_source")
        elif retrieval.get("retrieval_status") in ("unavailable", "failed", "empty"):
            passed = False
            notes.append("source_unavailable")

        if live:
            corpus = read_response.get("content")
            if corpus is None: corpus = " ".join(c.get("text", "") for c in read_response.get("chunks") or [])
            expected = "sha256:" + hashlib.sha256(corpus.encode()).hexdigest()
            if retrieval.get("retrieval_status") != "retrieved" or retrieval.get("synthetic") is not False or retrieval.get("content_hash") != expected or not read_response.get("canonical_url"):
                passed = False
                notes.append("missing_or_invalid_provenance")
        if source.get("publication_state") == "retracted":
            passed = False
            notes.append("retracted_source")

        if self._fake_doi(source):
            passed = False
            notes.append("fake_doi")

        if not self._identity_match(source, read_response):
            passed = False
            notes.append("identity_mismatch")

        if not self._locator_retrievable(card, read_response):
            passed = False
            notes.append("locator_not_retrievable")

        entail = (self._entailment_checker(card, source, read_response) if self._entailment_checker else
                  ("not_supported" if live else self._entailment(card, read_response)))
        if entail != "supports":
            passed = False
            notes.append("entailment_fail")

        if card.get("is_material_numerical") and not self._numeric_fidelity(card, read_response):
            passed = False
            notes.append("numeric_mismatch")

        if provenance_graph and self._laundering(card, provenance_graph):
            passed = False
            notes.append("source_laundering")

        verified["verifier_status"] = "passed" if passed else "failed"
        verified["verifier_notes"] = "; ".join(notes) if notes else "ok"
        if passed:
            new_status = "VERIFIED" if entail == "supports" else "INFERENCE"
            if legal_claim_transitions(card["claim_status"], new_status):
                verified["claim_status"] = new_status
        else:
            verified["claim_status"] = "REJECTED"
            verified["active"] = False
        self._registry.validate("evidence_card", verified)
        return verified

    def _fake_doi(self, source: dict[str, Any]) -> bool:
        url = source.get("canonical_url") or ""
        return "10.0000/fake" in url or url.endswith("/fake-doi")

    def _identity_match(self, source: dict[str, Any], read_response: dict[str, Any]) -> bool:
        meta = read_response.get("metadata") or {}
        if meta.get("error") == "inaccessible":
            return False
        source_url = source.get("canonical_url") or source.get("url")
        read_url = read_response.get("canonical_url")
        if source_url and read_url and source_url != read_url:
            return False
        return bool(source_url or source.get("canonical_title"))

    def _locator_retrievable(self, card: dict[str, Any], read_response: dict[str, Any]) -> bool:
        loc = card.get("locator")
        if loc == "UNKNOWN":
            return read_response.get("access_level") == "metadata"
        for ch in read_response.get("chunks") or []:
            if ch.get("locator") == loc and ch.get("text"):
                return True
        return False

    def _entailment(self, card: dict[str, Any], read_response: dict[str, Any]) -> str:
        claim = (card.get("claim") or "").lower()
        corpus = " ".join(c.get("text", "") for c in read_response.get("chunks") or []).lower()
        if not corpus.strip():
            return "not_supported"
        tokens = [t for t in re.findall(r"[a-z0-9%]+", claim) if len(t) > 3][:5]
        # Offline fixtures can verify exact paragraph attribution only. A substring
        # inside a negation is never entailment; live acceptance requires a reviewed checker.
        if claim.strip() and any(claim.strip() == c.get("text", "").strip().lower() for c in read_response.get("chunks") or []):
            return "supports"
        # Similar wording is a lead for human review, not evidence of entailment.
        if tokens and sum(1 for t in tokens if t in corpus) >= max(1, len(tokens) // 2):
            return "inference"
        if "contradict" in claim and "contradict" in corpus:
            return "contradicts"
        return "not_supported"

    def _numeric_fidelity(self, card: dict[str, Any], read_response: dict[str, Any]) -> bool:
        claim = card.get("claim") or ""
        corpus = " ".join(c.get("text", "") for c in read_response.get("chunks") or [])
        nums = re.findall(r"\d+\.?\d*\s*%", claim)
        if not nums:
            return True
        return nums[0].replace(" ", "") in corpus.replace(" ", "")

    def _laundering(self, card: dict[str, Any], graph: dict[str, list[str]]) -> bool:
        sid = card.get("source_id")
        parents = graph.get(sid or "", [])
        return len(parents) > 2
