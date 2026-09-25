"""Director Packet construction (RF-W5-A)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from research_forge.hashing.content import hash_bytes
from research_forge.wave5.packing import TokenPacker
from research_forge.wave5.types import BUILDER_VERSION, FORBIDDEN_PACKET_KEYS


@dataclass
class SelectionLog:
    load_bearing_evidence: list[str] = field(default_factory=list)
    counterevidence: list[str] = field(default_factory=list)
    dropped_narrative: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "load_bearing_evidence": self.load_bearing_evidence,
            "counterevidence": self.counterevidence,
            "dropped_narrative": self.dropped_narrative,
        }


class DirectorPacketBuilder:
    """Build schema-approved Director packets from scrutiny + portfolio outputs."""

    def __init__(self, *, token_ceiling: int = 12000) -> None:
        self.token_ceiling = token_ceiling
        self.packer = TokenPacker(token_ceiling=token_ceiling)
        self.last_selection: SelectionLog | None = None

    def _scrub_forbidden(self, obj: dict[str, Any]) -> None:
        for key in FORBIDDEN_PACKET_KEYS:
            if key in obj:
                raise ValueError(f"forbidden_field:{key}")

    def _canonical_contradiction(self, record: dict[str, Any]) -> str:
        return json.dumps(record, sort_keys=True, separators=(",", ":"))

    def _fact_row(
        self,
        evidence_id: str,
        evidence: dict[str, Any],
        sources: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        sid = evidence.get("source_id", "")
        src = sources.get(sid, {})
        return {
            "evidence_id": evidence_id,
            "source_id": sid,
            "claim": evidence.get("claim") or evidence.get("atomic_claim", ""),
            "locator": src.get("locator") or src.get("url") or f"source:{sid}",
            "access_level": src.get("access_level", "public"),
            "claim_status": evidence.get("claim_status", "INFERENCE"),
        }

    def select_load_bearing_facts(
        self,
        *,
        evidence: dict[str, dict[str, Any]],
        sources: dict[str, dict[str, Any]],
        idea_ids: list[str],
        ideas: list[dict[str, Any]],
        leading_conclusions: list[str],
        contradictions: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], SelectionLog]:
        log = SelectionLog()
        needed: set[str] = set()
        for idea in ideas:
            if idea.get("idea_id") not in idea_ids and idea_ids:
                continue
            for eid in idea.get("evidence_ids", []):
                needed.add(eid)
                log.load_bearing_evidence.append(eid)
        for line in leading_conclusions:
            for eid, card in evidence.items():
                if eid in line or card.get("claim", "")[:24] in line:
                    needed.add(eid)
        for ctr in contradictions:
            for pos in ctr.get("positions", []):
                eid = pos.get("evidence_id")
                if eid:
                    needed.add(eid)
                    log.counterevidence.append(eid)
        if not needed:
            needed = set(evidence.keys())
            log.load_bearing_evidence.extend(sorted(needed))
        facts = [self._fact_row(eid, evidence[eid], sources) for eid in sorted(needed) if eid in evidence]
        return facts, log

    def build(
        self,
        source: dict[str, Any],
        *,
        requested_output: str = "doctoral_synthesis",
    ) -> dict[str, Any]:
        self._scrub_forbidden(source)
        run_id = source.get("run_id", "run-w5")
        charter = source.get("charter") or {}
        scrutiny = source.get("scrutiny") or source.get("scrutiny_result") or {}
        wave4 = source.get("portfolio") or source.get("wave4") or {}
        evidence = source.get("evidence") or {}
        sources = source.get("sources") or {}

        promoted = [
            i
            for i in wave4.get("ideas", [])
            if i.get("status") in ("recommended", "active", "promoted")
        ]
        idea_refs = [i["idea_id"] for i in promoted][:20]
        contradictions_raw = scrutiny.get("contradictions") or []
        facts, selection = self.select_load_bearing_facts(
            evidence=evidence,
            sources=sources,
            idea_ids=idea_refs,
            ideas=wave4.get("ideas", []),
            leading_conclusions=source.get("leading_conclusions", []),
            contradictions=contradictions_raw,
        )
        self.last_selection = selection

        ctr_strings = [self._canonical_contradiction(c) for c in contradictions_raw]
        unknowns = list(source.get("unknowns") or [])
        for ab in wave4.get("abstentions") or []:
            reason = ab.get("reason") or ab.get("outcome")
            if reason:
                unknowns.append(str(reason))
        for gap in scrutiny.get("gaps") or []:
            if gap.get("status", "open") == "open":
                unknowns.append(gap.get("gap_id", "gap"))

        packet: dict[str, Any] = {
            "packet_id": f"DP-{uuid.uuid4().hex[:12]}",
            "builder_version": BUILDER_VERSION,
            "run_id": run_id,
            "charter_ref": charter.get("charter_id") or charter.get("charter_hash") or "charter:unknown",
            "method_summary": source.get("method_summary")
            or "Frozen evidence scrutiny with adversarial review and portfolio ideation.",
            "evidence_matrix_refs": [
                scrutiny.get("evidence_matrix", {}).get("matrix_id", "MAT-aggregate")
            ],
            "fact_table": facts,
            "contradictions": ctr_strings,
            "methods_flags": list(scrutiny.get("methods_flags") or []),
            "ideas": idea_refs,
            "adversarial_cases": [
                s.get("case_id", s.get("summary", str(s)))
                for s in (scrutiny.get("skeptic", {}).get("cases") or source.get("adversarial_cases") or [])
            ],
            "experiments": [
                e.get("experiment_id", e.get("title", "exp"))
                for e in wave4.get("experiments") or []
            ],
            "unknowns": unknowns,
            "budget_snapshot": source.get("budget_snapshot") or {"profile": source.get("profile", "M")},
            "requested_output": requested_output,
            "immutable_rules": source.get("immutable_rules")
            or [
                "No new evidence IDs in Director output.",
                "Unresolved contradictions must remain open.",
            ],
            "selection_rationale": selection.to_dict(),
        }

        packed, status = self.packer.pack(packet)
        if status == "BLOCKED":
            return {"status": "BLOCKED", "reason": "token_ceiling_exceeded", "draft": packet}
        self._scrub_forbidden(packed)
        packed.pop("run_id", None)
        packed["packet_hash"] = hash_bytes(
            json.dumps(packed, sort_keys=True, separators=(",", ":")).encode()
        )
        packed["builder_version"] = BUILDER_VERSION
        return {"status": "ready", "packet": packed, "selection_rationale": selection.to_dict()}
