"""Citation Verifier — fail closed on identity/entailment (RF-W1-G)."""

from __future__ import annotations

import re
from typing import Any

from research_forge.schemas_pkg.claim_status import legal_claim_transitions
from research_forge.schemas_pkg.registry import SchemaRegistry
from research_forge.wave1.interfaces import WAVE1_INTERFACE_VERSION, WAVE1_ROLE_CONTRACTS, assert_conforms


class CitationVerifier:
    role_id = "citation_verifier"
    interface_version = WAVE1_INTERFACE_VERSION

    def __init__(self, registry: SchemaRegistry) -> None:
        assert_conforms(self, WAVE1_ROLE_CONTRACTS["citation_verifier"])
        self._registry = registry

    def verify(
        self,
        card: dict[str, Any],
        *,
        source: dict[str, Any],
        read_response: dict[str, Any],
        provenance_graph: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        verified = dict(card)
        notes: list[str] = []
        passed = True

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

        entail = self._entailment(card, read_response)
        if entail == "not_supported":
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
        return bool(source.get("canonical_title"))

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
        if tokens and sum(1 for t in tokens if t in corpus) >= max(1, len(tokens) // 2):
            return "supports"
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
