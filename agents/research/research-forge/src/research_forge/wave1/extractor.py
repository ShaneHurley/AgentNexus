"""Evidence Extractor — atomic claims, no recommendations (RF-W1-F)."""

from __future__ import annotations

import re
from typing import Any

from research_forge.hashing.content import hash_normalized_text
from research_forge.schemas_pkg.registry import SchemaRegistry
from research_forge.wave1.interfaces import WAVE1_INTERFACE_VERSION, WAVE1_ROLE_CONTRACTS, assert_conforms

FORBIDDEN_KEYS = frozenset({"recommendation", "recommendations", "should_do"})


class EvidenceExtractor:
    role_id = "evidence_extractor"
    interface_version = WAVE1_INTERFACE_VERSION

    def __init__(self, registry: SchemaRegistry) -> None:
        assert_conforms(self, WAVE1_ROLE_CONTRACTS["evidence_extractor"])
        self._registry = registry

    def extract(
        self,
        *,
        source_id: str,
        read_response: dict[str, Any],
        question_addressed: str,
    ) -> list[dict[str, Any]]:
        access = read_response.get("access_level") or "metadata"
        chunks = read_response.get("chunks") or []
        text = " ".join(c.get("text", "") for c in chunks)
        cards: list[dict[str, Any]] = []
        for sentence in self._split_claims(text):
            if not sentence.strip():
                continue
            card = self._card_from_sentence(
                source_id=source_id,
                sentence=sentence,
                access=access,
                chunks=chunks,
                question=question_addressed,
            )
            self._reject_recommendations(card)
            self._registry.validate("evidence_card", card)
            cards.append(card)
        if not cards and read_response.get("metadata", {}).get("error"):
            cards.append(self._empty_source_card(source_id, question_addressed, access))
        return cards

    def _split_claims(self, text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", text)
        out: list[str] = []
        for p in parts:
            if " and " in p and len(p) > 80:
                out.extend(p.split(" and "))
            else:
                out.append(p)
        return out[:10]

    def _card_from_sentence(
        self,
        *,
        source_id: str,
        sentence: str,
        access: str,
        chunks: list[dict[str, Any]],
        question: str,
    ) -> dict[str, Any]:
        locator = chunks[0]["locator"] if chunks else "UNKNOWN"
        numerical = bool(re.search(r"\d+\s*%", sentence))
        eid = f"EVD-{hash_normalized_text(source_id + sentence)[:12].replace('sha256:', '')}"
        card: dict[str, Any] = {
            "evidence_id": eid,
            "source_id": source_id,
            "question_addressed": question,
            "claim": sentence.strip(),
            "claim_status": "UNKNOWN",
            "locator": locator,
            "supporting_passage_or_data": sentence.strip(),
            "access_level": access,
            "confidence": "LOW" if access in ("abstract", "snippet", "metadata") else "MEDIUM",
            "confidence_reason": f"Extracted at access_level={access}",
            "verifier_status": "pending",
            "limitations": [],
            "transfer_conditions": ["population: UNKNOWN", "environment: UNKNOWN"],
            "is_material_numerical": numerical,
        }
        if numerical:
            denom = re.search(r"n\s*=\s*(\d+)", sentence)
            card["units_and_denominator"] = (
                f"percent; denominator={denom.group(1) if denom else 'UNKNOWN'}"
            )
        elif access == "abstract":
            card["limitations"] = ["abstract-only; methods may be unread"]
        return card

    def _empty_source_card(self, source_id: str, question: str, access: str) -> dict[str, Any]:
        card = {
            "evidence_id": f"EVD-{hash_normalized_text(source_id + 'empty')[:12].replace('sha256:', '')}",
            "source_id": source_id,
            "question_addressed": question,
            "claim": "Source unavailable for extraction.",
            "claim_status": "UNKNOWN",
            "locator": "UNKNOWN",
            "access_level": access,
            "confidence": "UNKNOWN",
            "confidence_reason": "Reader error",
            "verifier_status": "pending",
        }
        self._registry.validate("evidence_card", card)
        return card

    def _reject_recommendations(self, card: dict[str, Any]) -> None:
        for key in FORBIDDEN_KEYS:
            if key in card:
                raise ValueError("recommendations forbidden on evidence card")
