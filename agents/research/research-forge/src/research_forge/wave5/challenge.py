"""High-stakes challenge path (RF-W5-D)."""

from __future__ import annotations

from typing import Any

from research_forge.wave5.types import CONTESTED, HIGH_STAKES_DOMAINS


class HighStakesClassifier:
    def classify(self, source: dict[str, Any]) -> dict[str, Any]:
        tags = set(source.get("domain_tags") or [])
        user = set(source.get("user_high_stakes") or [])
        matched = sorted(tags | user & HIGH_STAKES_DOMAINS | tags & HIGH_STAKES_DOMAINS)
        if source.get("high_risk_domain"):
            matched.append("high_risk_domain")
        matched = sorted(set(matched))
        return {
            "high_stakes": len(matched) > 0,
            "matched_domains": matched,
            "conservative_default": True,
        }


class ChallengeAuthorizer:
    """Second call only with XL + token + unresolved conflict + budget."""

    def authorize(
        self,
        *,
        profile: str,
        xl_conflict: bool,
        approval_token: str | None,
        budget_ok: bool,
        remaining_director_budget: bool,
    ) -> dict[str, Any]:
        if not xl_conflict:
            return {"authorized": False, "reason": "no_unresolved_conflict"}
        if profile != "XL":
            return {"authorized": False, "reason": "profile_not_xl"}
        if not approval_token:
            return {"authorized": False, "reason": "missing_approval_token"}
        if not budget_ok or not remaining_director_budget:
            return {"authorized": False, "reason": "budget"}
        return {"authorized": True}


class ChallengePacketBuilder:
    def build(
        self,
        *,
        director_conclusion: dict[str, Any],
        counterevidence: list[str],
        methods_flags: list[str],
        challenge_question: str,
    ) -> dict[str, Any]:
        return {
            "packet_kind": "challenge",
            "director_conclusion": director_conclusion,
            "counterevidence": counterevidence,
            "methods_flags": methods_flags,
            "challenge_question": challenge_question,
        }

    def size_ok(self, challenge: dict[str, Any], director_packet: dict[str, Any]) -> bool:
        import json

        c = len(json.dumps(challenge, sort_keys=True))
        d = len(json.dumps(director_packet, sort_keys=True))
        return c < d


class ChallengeResolver:
    def resolve(
        self,
        *,
        director_output: dict[str, Any],
        challenge_output: dict[str, Any],
        evidence_index: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        critique = challenge_output.get("critique") or challenge_output.get("findings") or []
        agrees = bool(challenge_output.get("agrees_with_director", False))
        if agrees:
            return {"status": "aligned", "recommendation_blocked": False}
        critical = [c for c in critique if c.get("severity") == "critical"]
        if not critical:
            return {"status": "non_critical_disagreement", "recommendation_blocked": False}
        # Deterministic evidence check
        for item in critical:
            eid = item.get("evidence_id")
            if eid and eid in evidence_index:
                return {
                    "status": "evidence_checked",
                    "resolution": item.get("resolution", "director_retained"),
                    "recommendation_blocked": item.get("block_recommendation", False),
                }
        return {
            "status": CONTESTED,
            "recommendation_blocked": True,
            "reason": "unresolved_critical_conflict",
        }
