"""Packet fidelity validation (RF-W5-A-06)."""

from __future__ import annotations

from typing import Any


class FidelityValidator:
    """Ensure required IDs, unknowns, permissions survive packing."""

    def snapshot(self, packet: dict[str, Any]) -> dict[str, Any]:
        fact_ids = sorted({r["evidence_id"] for r in packet.get("fact_table", [])})
        return {
            "evidence_ids": fact_ids,
            "contradictions": list(packet.get("contradictions") or []),
            "unknowns": sorted(set(packet.get("unknowns") or [])),
            "ideas": sorted(packet.get("ideas") or []),
            "methods_flags": sorted(packet.get("methods_flags") or []),
            "experiments": sorted(packet.get("experiments") or []),
            "immutable_rules": list(packet.get("immutable_rules") or []),
        }

    def validate(self, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        snap_b = self.snapshot(before)
        snap_a = self.snapshot(after)
        missing: list[str] = []
        for eid in snap_b["evidence_ids"]:
            if eid not in snap_a["evidence_ids"]:
                missing.append(f"evidence:{eid}")
        for ctr in snap_b["contradictions"]:
            if ctr not in snap_a["contradictions"]:
                missing.append(f"contradiction:{ctr[:32]}")
        for unk in snap_b["unknowns"]:
            if unk not in snap_a["unknowns"]:
                missing.append(f"unknown:{unk}")
        for iid in snap_b["ideas"]:
            if iid not in snap_a["ideas"]:
                missing.append(f"idea:{iid}")
        blocked = len(missing) > 0
        return {"passed": not blocked, "missing": missing, "before": snap_b, "after": snap_a}
