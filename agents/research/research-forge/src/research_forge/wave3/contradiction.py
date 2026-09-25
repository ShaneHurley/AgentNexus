"""Contradiction and Gap Mapper (RF-W3-B)."""

from __future__ import annotations

from typing import Any

from research_forge.wave3.propositions import PropositionRegistry
from research_forge.wave3.types import ConflictCause, GapKind, MatrixStance


class MatrixConsistencyError(ValueError):
    pass


class ContradictionMapper:
    role_id = "contradiction_mapper"
    allowed_tools: tuple[str, ...] = ("proposition_registry",)

    def __init__(self) -> None:
        self.registry = PropositionRegistry()

    def build_matrix(
        self,
        sources: dict[str, dict[str, Any]],
        evidence: dict[str, dict[str, Any]],
        cells: list[dict[str, Any]],
    ) -> dict[str, Any]:
        eid_to_prop = self.registry.register_from_evidence(evidence)
        matrix_cells: list[dict[str, Any]] = []
        for cell in cells:
            eid = cell["evidence_id"]
            sid = cell["source_id"]
            prop_id = cell.get("proposition_id") or eid_to_prop.get(eid)
            if not prop_id:
                prop_id = self.registry.register(
                    evidence[eid].get("claim", evidence[eid].get("atomic_claim", eid))
                )
            entry: dict[str, Any] = {
                "source_id": sid,
                "proposition_id": prop_id,
                "evidence_id": eid,
                "stance": cell["stance"],
            }
            if cell.get("qualification"):
                entry["qualification"] = cell["qualification"]
            if cell.get("decision_critical"):
                entry["decision_critical"] = True
            matrix_cells.append(entry)
        self.validate_matrix(matrix_cells)
        return {
            "matrix_id": "MAT-aggregate",
            "cells": matrix_cells,
            "propositions": self.registry.all_propositions(),
        }

    def validate_matrix(self, cells: list[dict[str, Any]]) -> None:
        by_key: dict[tuple[str, str, str], set[str]] = {}
        for cell in cells:
            stance = cell["stance"]
            if stance not in {s.value for s in MatrixStance}:
                raise MatrixConsistencyError(f"Invalid stance {stance}")
            key = (cell["source_id"], cell["proposition_id"], cell["evidence_id"])
            by_key.setdefault(key, set()).add(stance)
            if MatrixStance.SUPPORTS.value in by_key[key] and MatrixStance.CONTRADICTS.value in by_key[
                key
            ]:
                if cell.get("qualification") is None and stance in (
                    MatrixStance.SUPPORTS.value,
                    MatrixStance.CONTRADICTS.value,
                ):
                    raise MatrixConsistencyError(
                        "Same evidence cannot support and contradict without qualification"
                    )

    def detect_conflicts(self, matrix: dict[str, Any]) -> list[dict[str, Any]]:
        by_prop: dict[str, list[dict[str, Any]]] = {}
        for cell in matrix["cells"]:
            by_prop.setdefault(cell["proposition_id"], []).append(cell)
        conflicts: list[dict[str, Any]] = []
        for prop_id, group in by_prop.items():
            stances = {c["stance"] for c in group}
            if MatrixStance.SUPPORTS.value in stances and MatrixStance.CONTRADICTS.value in stances:
                cause = self._classify_conflict_cause(group)
                relevance = self._score_decision_relevance(prop_id, group)
                conflicts.append(
                    {
                        "contradiction_id": f"CTR-{prop_id[-8:]}",
                        "proposition": self.registry.proposition_label(prop_id),
                        "proposition_id": prop_id,
                        "positions": [
                            {
                                "source_id": c["source_id"],
                                "evidence_id": c["evidence_id"],
                                "stance": c["stance"],
                                "summary": c.get("qualification") or c["stance"],
                            }
                            for c in group
                            if c["stance"]
                            in (MatrixStance.SUPPORTS.value, MatrixStance.CONTRADICTS.value)
                        ],
                        "conflict_cause": cause,
                        "decision_relevance": relevance,
                    }
                )
        return conflicts

    def _classify_conflict_cause(self, group: list[dict[str, Any]]) -> str:
        for c in group:
            if c.get("conflict_cause"):
                return str(c["conflict_cause"])
        return ConflictCause.UNRESOLVED.value

    def _score_decision_relevance(self, prop_id: str, group: list[dict[str, Any]]) -> str:
        if any(c.get("decision_critical") for c in group):
            return "high"
        if len(group) >= 3:
            return "medium"
        return "low"

    def to_contradiction_records(self, conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for c in conflicts:
            positions = c["positions"]
            if len(positions) < 2:
                continue
            cause = c["conflict_cause"]
            ctype = "methodological" if cause == ConflictCause.METHOD.value else "factual"
            severity = "critical" if c["decision_relevance"] == "high" else "medium"
            records.append(
                {
                    "contradiction_id": c["contradiction_id"],
                    "proposition": c["proposition"],
                    "positions": positions[:10],
                    "contradiction_type": ctype,
                    "severity": severity,
                    "decision_relevance": c["decision_relevance"],
                    "resolution_status": "open",
                    "follow_up_query": f"Resolve conflict on {c['proposition_id']}",
                }
            )
        return records

    def generate_gaps(
        self,
        conflicts: list[dict[str, Any]],
        *,
        missing_evidence: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []
        for c in conflicts:
            if c["decision_relevance"] != "high":
                continue
            gaps.append(
                {
                    "gap_id": f"GAP-{c['contradiction_id'][-8:]}",
                    "kind": GapKind.UNRESOLVED_CAUSE.value,
                    "proposition_id": c["proposition_id"],
                    "decision_relevance": "high",
                    "closure_evidence_needed": "independent replication or definitional alignment",
                    "stop_rule": "close as UNKNOWN after one bounded follow-up with no gain",
                }
            )
        for item in missing_evidence or []:
            gaps.append(
                {
                    "gap_id": item.get("gap_id", "GAP-missing"),
                    "kind": item.get("kind", GapKind.MISSING_EVIDENCE.value),
                    "proposition_id": item.get("proposition_id", ""),
                    "decision_relevance": item.get("decision_relevance", "medium"),
                    "closure_evidence_needed": item.get("closure_evidence_needed", ""),
                    "stop_rule": item.get("stop_rule", "UNKNOWN after max follow-up rounds"),
                }
            )
        return gaps
