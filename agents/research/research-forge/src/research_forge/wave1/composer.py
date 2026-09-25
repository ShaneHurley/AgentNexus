"""Report Composer — evidence-linked report + packet (RF-W1-H)."""

from __future__ import annotations

from typing import Any

from research_forge.hashing.content import hash_normalized_text
from research_forge.schemas_pkg.registry import SchemaRegistry
from research_forge.wave1.interfaces import WAVE1_INTERFACE_VERSION, WAVE1_ROLE_CONTRACTS, assert_conforms


class ReportComposer:
    role_id = "report_composer"
    interface_version = WAVE1_INTERFACE_VERSION

    def __init__(self, registry: SchemaRegistry) -> None:
        assert_conforms(self, WAVE1_ROLE_CONTRACTS["report_composer"])
        self._registry = registry

    def compose_report(
        self,
        *,
        charter: dict[str, Any],
        verified_cards: list[dict[str, Any]],
        unknowns: list[str],
    ) -> tuple[str, list[dict[str, Any]]]:
        material_claims = []
        sections = [
            "# Research Report",
            f"## Objective\n{charter.get('objective')}",
            "## Key findings",
        ]
        for card in verified_cards:
            if card.get("verifier_status") != "passed":
                continue
            ref = card["evidence_id"]
            if not ref.startswith("EVD-") or len(ref) < 8:
                raise ValueError("material claim without Evidence ID")
            material_claims.append(
                {
                    "evidence_id": ref,
                    "claim": card["claim"],
                    "status": card["claim_status"],
                    "access_level": card["access_level"],
                }
            )
            sections.append(
                f"- [{ref}] ({card['claim_status']}) {card['claim']} "
                f"(source {card['source_id']}, {card['access_level']})"
            )
        if unknowns:
            sections.append("## Unknowns")
            sections.extend(f"- {u}" for u in unknowns)
        report = "\n\n".join(sections)
        return report, material_claims

    def build_packet(
        self,
        *,
        request_id: str,
        charter: dict[str, Any],
        material_claims: list[dict[str, Any]],
        contradictions: list[dict[str, Any]],
        unknowns: list[dict[str, Any]],
        report: str,
    ) -> dict[str, Any]:
        report_hash = hash_normalized_text(report)
        packet: dict[str, Any] = {
            "packet_version": "1.0.0",
            "request_id": request_id,
            "charter": charter,
            "method": {"wave": 1, "mode": "sequential_mock"},
            "source_registry_ref": "ledger://sources",
            "evidence_registry_ref": "ledger://evidence",
            "key_findings": material_claims,
            "contradictions": contradictions,
            "unknowns": unknowns,
            "audit_result": {"composer": "passed", "material_claims": len(material_claims)},
            "allowed_uses": ["internal research"],
            "prohibited_uses": ["automated execution"],
            "freshness": charter.get("recency", "UNKNOWN"),
            "expiry": "UNKNOWN",
            "report_hash": report_hash,
        }
        self._registry.validate("research_packet", packet)
        self.check_consistency(report, packet)
        return packet

    def check_consistency(self, report: str, packet: dict[str, Any]) -> None:
        for finding in packet.get("key_findings") or []:
            eid = finding.get("evidence_id")
            if eid and eid not in report:
                raise ValueError("report/packet evidence mismatch")

    def format_citation(self, source: dict[str, Any], style: str = "markdown") -> str:
        title = source.get("canonical_title") or "UNKNOWN"
        sid = source.get("source_id") or "UNKNOWN"
        if style == "markdown":
            return f"[{title}]({source.get('canonical_url', '')}) `{sid}`"
        return f"{title} ({sid})"
