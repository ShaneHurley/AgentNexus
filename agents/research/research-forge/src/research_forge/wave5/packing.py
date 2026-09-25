"""Token packing for Director packets (RF-W5-A-05)."""

from __future__ import annotations

import json
from typing import Any


def _approx_tokens(obj: Any) -> int:
    if isinstance(obj, str):
        return max(1, len(obj.split()))
    if isinstance(obj, dict):
        return sum(_approx_tokens(v) for v in obj.values()) + len(obj)
    if isinstance(obj, list):
        return sum(_approx_tokens(v) for v in obj) + 1
    return 1


class TokenPacker:
    """Drop redundant narrative only; never merge contradictions."""

    PRIORITY_KEYS = (
        "immutable_rules",
        "charter_ref",
        "requested_output",
        "contradictions",
        "fact_table",
        "experiments",
        "unknowns",
        "methods_flags",
        "ideas",
        "adversarial_cases",
        "method_summary",
        "evidence_matrix_refs",
        "budget_snapshot",
        "selection_rationale",
    )

    def __init__(self, *, token_ceiling: int) -> None:
        self.token_ceiling = token_ceiling

    def pack(self, packet: dict[str, Any]) -> tuple[dict[str, Any], str]:
        if _approx_tokens(packet) <= self.token_ceiling:
            return dict(packet), "ok"
        trimmed = dict(packet)
        dropped: list[str] = []
        summary = trimmed.get("method_summary", "")
        if len(summary.split()) > 40:
            trimmed["method_summary"] = " ".join(summary.split()[:40])
            dropped.append("method_summary_tail")
        rationale = trimmed.get("selection_rationale") or {}
        if isinstance(rationale, dict) and rationale.get("dropped_narrative") is not None:
            rationale["dropped_narrative"] = list(rationale.get("dropped_narrative", [])) + dropped
            trimmed["selection_rationale"] = rationale
        if _approx_tokens(trimmed) <= self.token_ceiling:
            return trimmed, "ok"
        # Last resort: shrink fact claim text but keep IDs/locators
        facts = []
        for row in trimmed.get("fact_table", []):
            claim = row.get("claim", "")
            if len(claim.split()) > 30:
                row = {**row, "claim": " ".join(claim.split()[:30])}
            facts.append(row)
        trimmed["fact_table"] = facts
        if _approx_tokens(trimmed) <= self.token_ceiling:
            return trimmed, "ok"
        if json.dumps(trimmed, sort_keys=True) == json.dumps(packet, sort_keys=True):
            return packet, "BLOCKED"
        return trimmed, "BLOCKED" if _approx_tokens(trimmed) > self.token_ceiling else "ok"
