"""Context projection and compaction (RF-W2-F)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

PINNED_CLASSES = (
    "charter",
    "permissions",
    "budget",
    "accepted_decisions",
    "unresolved_contradictions",
)


@dataclass
class ContextRequest:
    role: str
    charter_question: str
    source_ids: list[str]
    evidence_ids: list[str]
    token_ceiling: int


@dataclass
class ContextTelemetry:
    role: str
    requested_tokens: int
    supplied_tokens: int
    truncated_tokens: int
    pinned_tokens: int
    retrieved_tokens: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "requested_tokens": self.requested_tokens,
            "supplied_tokens": self.supplied_tokens,
            "truncated_tokens": self.truncated_tokens,
            "pinned_tokens": self.pinned_tokens,
            "retrieved_tokens": self.retrieved_tokens,
        }


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class ContextProjector:
    """Build role-specific context slices without passing raw ledger."""

    def __init__(self, pinned: dict[str, Any]) -> None:
        self.pinned = pinned
        self.telemetry: list[ContextTelemetry] = []

    def project(
        self,
        request: ContextRequest,
        *,
        sources: dict[str, dict[str, Any]],
        evidence: dict[str, dict[str, Any]],
        disposable: list[str] | None = None,
    ) -> dict[str, Any]:
        disposable = disposable or []
        pinned_slice = {k: self.pinned[k] for k in PINNED_CLASSES if k in self.pinned}
        pinned_blob = json.dumps(pinned_slice, sort_keys=True)
        pinned_tokens = _estimate_tokens(pinned_blob)

        ranked_evidence = self._rank_evidence(request, evidence)
        cards = []
        for eid in ranked_evidence:
            if eid not in request.evidence_ids:
                continue
            card = evidence[eid]
            cards.append(
                {
                    "evidence_id": eid,
                    "source_id": card.get("source_id"),
                    "atomic_claim": card.get("atomic_claim"),
                    "locators": card.get("locators", []),
                    "access": card.get("access", "unknown"),
                }
            )
        src_refs = []
        for sid in request.source_ids:
            if sid in sources:
                src_refs.append({"source_id": sid, "title": sources[sid].get("title")})

        body = {
            "role": request.role,
            "charter_question": request.charter_question,
            "pinned": pinned_slice,
            "evidence_cards": cards,
            "source_refs": src_refs,
        }
        evicted = [d for d in disposable if d not in pinned_blob]
        body["evicted_disposable_count"] = len(evicted)

        blob = json.dumps(body, sort_keys=True)
        total_tokens = _estimate_tokens(blob)
        truncated = 0
        if total_tokens > request.token_ceiling:
            truncated = total_tokens - request.token_ceiling
            while total_tokens > request.token_ceiling and len(cards) > 1:
                cards.pop()
                body["evidence_cards"] = cards
                blob = json.dumps(body, sort_keys=True)
                total_tokens = _estimate_tokens(blob)
            truncated = max(0, _estimate_tokens(json.dumps(body)) - request.token_ceiling)

        tel = ContextTelemetry(
            role=request.role,
            requested_tokens=request.token_ceiling,
            supplied_tokens=min(total_tokens, request.token_ceiling),
            truncated_tokens=truncated,
            pinned_tokens=pinned_tokens,
            retrieved_tokens=_estimate_tokens(json.dumps(cards)),
        )
        self.telemetry.append(tel)
        return {"projection": body, "telemetry": tel.to_dict()}

    def _rank_evidence(
        self,
        request: ContextRequest,
        evidence: dict[str, dict[str, Any]],
    ) -> list[str]:
        scored: list[tuple[float, str]] = []
        q = request.charter_question.lower()
        for eid, card in evidence.items():
            claim = (card.get("atomic_claim") or "").lower()
            score = 1.0 if q and q[:20] in claim else 0.5
            score += float(card.get("decision_relevance", 0))
            scored.append((score, eid))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [eid for _, eid in scored]

    def validate_pinned_fidelity(self, before: dict[str, Any], after: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        for key in PINNED_CLASSES:
            if key not in before:
                errors.append(f"missing pinned class in before: {key}")
                continue
            if before.get(key) != after.get("pinned", {}).get(key):
                errors.append(f"pinned field mutated: {key}")
        return errors

    def block_if_invalid(self, before: dict[str, Any], after: dict[str, Any]) -> None:
        errs = self.validate_pinned_fidelity(before, after.get("projection", after))
        if errs:
            raise ValueError("; ".join(errs))


@dataclass
class PinnedContextStore:
    charter: dict[str, Any]
    permissions: dict[str, Any] = field(default_factory=dict)
    budget: dict[str, Any] = field(default_factory=dict)
    accepted_decisions: list[str] = field(default_factory=list)
    unresolved_contradictions: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "charter": self.charter,
            "permissions": self.permissions,
            "budget": self.budget,
            "accepted_decisions": list(self.accepted_decisions),
            "unresolved_contradictions": list(self.unresolved_contradictions),
        }
