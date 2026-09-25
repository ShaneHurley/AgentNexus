"""Claim status enum and transition rules."""

from __future__ import annotations

CLAIM_STATUSES = frozenset(
    {
        "VERIFIED",
        "CORROBORATED",
        "INFERENCE",
        "ASSUMPTION",
        "CONTESTED",
        "UNKNOWN",
        "REJECTED",
    }
)

RECOMMENDATION_ELIGIBLE = frozenset({"VERIFIED", "CORROBORATED", "INFERENCE"})

LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "ASSUMPTION": frozenset({"UNKNOWN", "REJECTED", "INFERENCE"}),
    "UNKNOWN": frozenset({"ASSUMPTION", "VERIFIED", "CONTESTED", "REJECTED"}),
    "INFERENCE": frozenset({"VERIFIED", "CORROBORATED", "CONTESTED", "REJECTED"}),
    "VERIFIED": frozenset({"CONTESTED", "REJECTED"}),
    "CORROBORATED": frozenset({"CONTESTED", "REJECTED"}),
    "CONTESTED": frozenset({"VERIFIED", "CORROBORATED", "UNKNOWN", "REJECTED"}),
    "REJECTED": frozenset(),
}


def legal_claim_transitions(from_status: str, to_status: str) -> bool:
    if from_status not in CLAIM_STATUSES or to_status not in CLAIM_STATUSES:
        return False
    return to_status in LEGAL_TRANSITIONS.get(from_status, frozenset())


def assumption_may_drive_recommendation(claim_status: str) -> bool:
    return claim_status in RECOMMENDATION_ELIGIBLE
