"""Proposition registry (RF-W3-B-01)."""

from __future__ import annotations

import hashlib
import re
from typing import Any


def normalize_proposition_text(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


class PropositionRegistry:
    def __init__(self) -> None:
        self._by_norm: dict[str, str] = {}
        self._labels: dict[str, str] = {}

    def register(self, claim_text: str, *, alias: str | None = None) -> str:
        norm = normalize_proposition_text(claim_text)
        if norm in self._by_norm:
            return self._by_norm[norm]
        prop_id = f"PROP-{hashlib.sha256(norm.encode()).hexdigest()[:10]}"
        self._by_norm[norm] = prop_id
        self._labels[prop_id] = alias or claim_text.strip()
        return prop_id

    def register_from_evidence(self, evidence: dict[str, dict[str, Any]]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for eid, card in evidence.items():
            claim = card.get("claim") or card.get("atomic_claim") or ""
            if not claim:
                continue
            prop_id = self.register(claim)
            mapping[eid] = prop_id
        return mapping

    def proposition_label(self, prop_id: str) -> str:
        return self._labels.get(prop_id, prop_id)

    def all_propositions(self) -> dict[str, str]:
        return dict(self._labels)
