"""Director eligibility (RF-W5-B-02)."""

from __future__ import annotations

from typing import Any


class DirectorEligibility:
    """Routine quick requests may skip Director."""

    def assess(
        self,
        *,
        scrutiny: dict[str, Any] | None,
        packet_ready: bool,
        budget_ok: bool,
        profile: str,
        synthesis_need: str = "standard",
        human_override: bool = False,
        portfolio_audit_critical: bool = False,
    ) -> dict[str, Any]:
        reasons: list[str] = []
        if scrutiny and scrutiny.get("acceptance_blocked") and not human_override:
            reasons.append("scrutiny_not_cleared")
        if not packet_ready:
            reasons.append("packet_not_verified")
        if not budget_ok:
            reasons.append("budget_reserve_unavailable")
        if profile not in ("S", "M", "L", "XL"):
            reasons.append("profile_not_permitted")
        if portfolio_audit_critical:
            reasons.append("portfolio_critical_findings")
        if synthesis_need == "none":
            reasons.append("no_synthesis_need")
        skip = synthesis_need in ("quick_summary", "none") and not reasons
        eligible = len(reasons) == 0 and not skip
        return {
            "eligible": eligible,
            "skip_director": skip,
            "reasons": reasons,
        }
