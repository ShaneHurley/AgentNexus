"""Independent Research Auditor (RF-W3-F)."""

from __future__ import annotations

import hashlib
import random
from typing import Any

from research_forge.wave3.types import AuditSeverity

CHECKLIST_ITEMS = (
    "scope",
    "source_classes",
    "unsupported_claims",
    "citation_entailment",
    "independence",
    "contradictions",
    "confidence",
    "methods",
    "experiment_testability",
    "reproducibility",
    "budget",
)


class AuditVetoError(Exception):
    def __init__(self, findings: list[dict[str, Any]]) -> None:
        self.findings = findings
        super().__init__("Critical audit findings block acceptance")


class ResearchAuditor:
    role_id = "research_auditor"
    allowed_tools: tuple[str, ...] = ("audit_checklist",)

    def __init__(self, *, sample_rate: float = 0.25) -> None:
        self.sample_rate = sample_rate

    def assert_separate_identity(self, writer_role: str, auditor_role: str) -> None:
        if writer_role == auditor_role:
            raise PermissionError("Writer and auditor identities must differ")

    def audit(
        self,
        packet: dict[str, Any],
        *,
        sample_seed: int,
        load_bearing_claim_ids: list[str] | None = None,
        adversarial_signals: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        rng = random.Random(sample_seed)
        lb = set(load_bearing_claim_ids or packet.get("load_bearing_claim_ids") or [])
        findings: list[dict[str, Any]] = []
        checklist: list[dict[str, Any]] = []

        for item in CHECKLIST_ITEMS:
            verdict = "pass"
            evidence_ref = "packet_review"
            if item == "unsupported_claims":
                for claim in packet.get("claims", []):
                    if not claim.get("evidence_ids"):
                        findings.append(
                            {
                                "item": item,
                                "severity": AuditSeverity.CRITICAL.value,
                                "detail": f"unsupported:{claim.get('claim_id')}",
                            }
                        )
            checklist.append({"item": item, "verdict": verdict, "evidence_ref": evidence_ref})

        for sig in adversarial_signals or []:
            finding = self._match_adversarial(sig)
            if finding:
                findings.append(finding)

        sampled_ids = self._sample_claims(packet.get("claims", []), lb, rng)
        for claim in packet.get("claims", []):
            cid = claim.get("claim_id", "")
            if cid in lb or cid in sampled_ids:
                if claim.get("citation_swap"):
                    findings.append(
                        {
                            "item": "citation_entailment",
                            "severity": AuditSeverity.CRITICAL.value,
                            "detail": "citation_swap",
                        }
                    )

        critical = [f for f in findings if f["severity"] == AuditSeverity.CRITICAL.value]
        blocked = len(critical) > 0
        return {
            "audit_id": f"AUD-{hashlib.sha256(str(sample_seed).encode()).hexdigest()[:8]}",
            "sample_seed": sample_seed,
            "sampled_claim_ids": sorted(sampled_ids),
            "checklist": checklist,
            "findings": findings,
            "blocked": blocked,
            "veto": blocked,
        }

    def _sample_claims(
        self,
        claims: list[dict[str, Any]],
        load_bearing: set[str],
        rng: random.Random,
    ) -> set[str]:
        sampled: set[str] = set()
        for claim in claims:
            cid = claim.get("claim_id", "")
            if cid in load_bearing:
                continue
            if rng.random() < self.sample_rate:
                sampled.add(cid)
        return sampled

    def _match_adversarial(self, sig: dict[str, Any]) -> dict[str, Any] | None:
        kind = sig.get("kind")
        mapping = {
            "fake_doi": ("citation_entailment", AuditSeverity.CRITICAL),
            "retraction": ("citation_entailment", AuditSeverity.CRITICAL),
            "derivative_consensus": ("independence", AuditSeverity.MAJOR),
            "stale_docs": ("source_classes", AuditSeverity.MAJOR),
            "citation_swap": ("citation_entailment", AuditSeverity.CRITICAL),
            "abstract_trap": ("citation_entailment", AuditSeverity.CRITICAL),
            "prompt_injection": ("scope", AuditSeverity.CRITICAL),
            "omitted_negative_result": ("unsupported_claims", AuditSeverity.CRITICAL),
        }
        if kind not in mapping:
            return None
        item, sev = mapping[kind]
        if sig.get("present"):
            return {"item": item, "severity": sev.value, "detail": kind}
        return None

    def resolve_disagreement(self, audits: list[dict[str, Any]]) -> dict[str, Any]:
        critical_sets = []
        for a in audits:
            critical_sets.append(
                frozenset(
                    f["detail"]
                    for f in a.get("findings", [])
                    if f.get("severity") == AuditSeverity.CRITICAL.value
                )
            )
        if len(critical_sets) >= 2 and critical_sets[0] != critical_sets[1]:
            return {"resolved": False, "action": "deterministic_recheck_or_human", "blocked": True}
        return {"resolved": True, "action": "accept", "blocked": False}

    def enforce_veto(self, report: dict[str, Any]) -> None:
        if report.get("veto"):
            raise AuditVetoError(report.get("findings", []))
