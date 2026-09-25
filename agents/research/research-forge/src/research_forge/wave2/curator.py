"""Triage Curator — registry-only dedupe and scoring (RF-W2-D)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from research_forge.registries.normalize import canonical_key, normalize_url
from research_forge.registries.source import SourceRegistry
from research_forge.wave2.types import CuratorDecision, TriageStatus

TRIAGE_STATUSES = tuple(s.value for s in TriageStatus)


class CuratorPolicyError(ValueError):
    pass


def query_fingerprint(
    *,
    query_concepts: list[str],
    filters: dict[str, Any] | None,
    source_class: str,
    date_range: str | None,
    lane_id: str,
) -> str:
    payload = {
        "concepts": sorted(c.lower().strip() for c in query_concepts),
        "filters": filters or {},
        "source_class": source_class.lower(),
        "date_range": date_range or "",
        "lane_id": lane_id,
    }
    blob = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class SourceCurator:
    role_id = "source_curator"
    allowed_tools: tuple[str, ...] = ("source_registry",)

    def __init__(
        self,
        registry: SourceRegistry | None = None,
        *,
        class_floors: dict[str, int] | None = None,
    ) -> None:
        self.registry = registry
        self.class_floors = class_floors or {
            "scholarly": 1,
            "standards": 1,
            "implementation": 1,
        }
        self._fingerprints: set[str] = set()
        self._class_attempts: dict[str, dict[str, Any]] = {}

    def assert_no_external_search(self, tool_id: str) -> None:
        if tool_id not in self.allowed_tools and "search" in tool_id:
            raise CuratorPolicyError("Curator cannot invoke external search")

    def flag_duplicate_query(self, fingerprint: str) -> bool:
        if fingerprint in self._fingerprints:
            return True
        self._fingerprints.add(fingerprint)
        return False

    def score_candidate(self, candidate: dict[str, Any]) -> dict[str, float]:
        recency = 0.5
        if candidate.get("date"):
            recency = 0.8
        access = 1.0 if candidate.get("access") == "open" else 0.3
        return {
            "relevance": 0.7,
            "authority": 0.6 if candidate.get("source_type") == "paper" else 0.4,
            "independence": 0.5,
            "uniqueness": 0.6,
            "access": access,
            "recency": recency,
            "contradiction_value": 0.4,
            "expected_information_gain": 0.55,
        }

    def triage(
        self,
        candidates: list[dict[str, Any]],
        *,
        lane_id: str = "default",
    ) -> list[CuratorDecision]:
        clusters = self.detect_derivative_clusters(candidates)
        cluster_rank: dict[str, int] = {}
        decisions: list[CuratorDecision] = []
        for cand in candidates:
            fp = query_fingerprint(
                query_concepts=[cand.get("title", ""), cand.get("url", "")],
                filters={},
                source_class=cand.get("source_type", "unknown"),
                date_range=None,
                lane_id=lane_id,
            )
            if self.flag_duplicate_query(fp):
                decisions.append(
                    CuratorDecision(
                        candidate_id=cand["candidate_id"],
                        status=TriageStatus.REJECT,
                        reason="duplicate_query_fingerprint",
                        scores=self.score_candidate(cand),
                    )
                )
                continue
            cid = clusters.get(cand["candidate_id"])
            if cid:
                cluster_rank[cid] = cluster_rank.get(cid, 0) + 1
                if cluster_rank[cid] > 1:
                    status = TriageStatus.REFERENCE_ONLY
                    reason = "derivative_cluster_member"
                else:
                    status = TriageStatus.DEEP_READ
                    reason = "canonical_cluster_root"
            elif cand.get("follow_citations"):
                status = TriageStatus.FOLLOW_CITATIONS
                reason = "citation_expansion"
            else:
                status = TriageStatus.SCREEN
                reason = "initial_screen"
            decisions.append(
                CuratorDecision(
                    candidate_id=cand["candidate_id"],
                    status=status,
                    reason=reason,
                    scores=self.score_candidate(cand),
                    cluster_id=cid,
                )
            )
        self._ensure_single_status(decisions)
        return decisions

    def detect_derivative_clusters(
        self,
        candidates: list[dict[str, Any]],
    ) -> dict[str, str | None]:
        """Map candidate_id -> cluster_id (None if independent)."""
        roots: dict[str, str] = {}
        assignment: dict[str, str | None] = {}
        for cand in candidates:
            cid = cand["candidate_id"]
            canonical = cand.get("canonical_reference") or cand.get("doi")
            content_hash = cand.get("content_hash")
            original = cand.get("original_url") or cand.get("url")
            cluster_key = None
            if canonical:
                cluster_key = f"canon:{canonical}"
            elif content_hash:
                cluster_key = f"hash:{content_hash}"
            elif original:
                cluster_key = f"url:{normalize_url(original)}"
            if cluster_key and cluster_key in roots:
                assignment[cid] = roots[cluster_key]
            elif cluster_key:
                cluster_id = f"cluster-{hashlib.sha256(cluster_key.encode()).hexdigest()[:8]}"
                roots[cluster_key] = cluster_id
                assignment[cid] = cluster_id
            else:
                assignment[cid] = None
        return assignment

    def canonicalize_fixture_record(self, record: dict[str, Any]) -> str:
        """Return canonical cluster key for regression fixtures."""
        kind = record.get("fixture_kind")
        if kind == "preprint_published":
            return record.get("doi", record.get("canonical_reference", ""))
        if kind == "mirror":
            return normalize_url(record.get("original_url", record.get("url", "")))
        if kind == "news_summary":
            return record.get("original_url", "")
        if kind == "vendor_repost":
            return record.get("content_hash", "")
        if kind == "same_dataset":
            return record.get("dataset_id", "")
        return normalize_url(record.get("url", ""))

    def enforce_class_floors(
        self,
        candidates_by_class: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        report: dict[str, Any] = {"attempts": [], "gaps": []}
        for cls, floor in self.class_floors.items():
            have = len(candidates_by_class.get(cls, []))
            attempt = {
                "source_class": cls,
                "floor": floor,
                "found": have,
                "met": have >= floor,
            }
            report["attempts"].append(attempt)
            if have < floor:
                report["gaps"].append(
                    {
                        "source_class": cls,
                        "reason": "floor_not_met",
                        "forced_into_conclusions": False,
                    }
                )
            self._class_attempts[cls] = attempt
        return report

    def register_from_events(self, events: list[dict[str, Any]]) -> None:
        self.registry = SourceRegistry.from_events(events)

    def _ensure_single_status(self, decisions: list[CuratorDecision]) -> None:
        seen: set[str] = set()
        for d in decisions:
            if d.candidate_id in seen:
                raise ValueError(f"Duplicate triage for {d.candidate_id}")
            seen.add(d.candidate_id)
            if d.status.value not in TRIAGE_STATUSES:
                raise ValueError(f"Invalid status {d.status}")
