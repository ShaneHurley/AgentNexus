"""Evidence registry — immutable cards, supersession."""

from __future__ import annotations

from typing import Any

from research_forge.schemas_pkg.claim_status import RECOMMENDATION_ELIGIBLE


class EvidenceRegistry:
    def __init__(self, events: list[dict[str, Any]], sources: dict[str, dict[str, Any]]) -> None:
        self._cards: dict[str, dict[str, Any]] = {}
        self._superseded: dict[str, str] = {}
        for ev in sorted(events, key=lambda e: e["sequence"]):
            if ev["event_type"] != "evidence_added":
                continue
            payload = ev["payload"]
            eid = payload["evidence_id"]
            self._cards[eid] = payload
            if payload.get("supersedes"):
                self._superseded[payload["supersedes"]] = eid
        self._sources = sources

    def validate_new_card(self, card: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        sid = card.get("source_id")
        if not sid or sid not in self._sources:
            errors.append("source_id missing or unknown")
        else:
            src = self._sources[sid]
            src_access = src.get("access_level")
            card_access = card.get("access_level")
            if src_access and card_access and src_access != card_access:
                errors.append("access_level conflicts with source")
        claim = card.get("atomic_claim", "")
        if card.get("material_numerical") and not card.get("unit"):
            errors.append("material numerical claim requires unit")
        if not card.get("verifier_status"):
            errors.append("verifier_status required")
        if not claim:
            errors.append("atomic_claim required")
        return errors

    def recommendation_eligible(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for eid, card in self._cards.items():
            if eid in self._superseded.values():
                continue
            if eid in self._superseded:
                continue
            status = card.get("claim_status", "UNKNOWN")
            if status in RECOMMENDATION_ELIGIBLE and card.get("inference_accepted"):
                out.append(card)
            elif status in RECOMMENDATION_ELIGIBLE and status != "INFERENCE":
                out.append(card)
        return out

    def active_cards(self) -> dict[str, dict[str, Any]]:
        return {
            eid: card
            for eid, card in self._cards.items()
            if eid not in self._superseded and card.get("evidence_id") not in self._superseded
        }
