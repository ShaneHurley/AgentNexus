"""Typed models aligned with JSON schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str
    objective: str | None = None
    intended_decision_or_use: str | None = None
    direction_or_outline: list[str] | None = None
    seed_sources: list[str] | None = None
    specific_questions: list[str] | None = None
    audience: str | None = None
    domain: str | None = None
    time_horizon: str | None = None
    geographic_scope: str | None = None
    source_constraints: list[str] | None = None
    exclusions: list[str] | None = None
    required_output: (
        Literal[
            "brief",
            "literature_review",
            "decision_report",
            "architecture_report",
            "feasibility_study",
            "experiment_plan",
            "research_packet",
            "custom",
        ]
        | None
    ) = None
    desired_depth: Literal["quick", "standard", "deep", "thesis"] | None = None
    budget_profile: Literal["S", "M", "L", "XL"] | None = None
    recency_requirement: str | None = None
    confidentiality: Literal["public", "internal", "restricted"] | None = None
    allowed_tools: list[str] | None = None
    maximum_cost: float | None = None
    deadline: str | None = None


class LedgerEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    run_id: str
    sequence: int
    timestamp: str
    actor: str
    schema_version: str
    event_type: str
    payload: dict[str, Any]
    payload_hash: str
    previous_hash: str
    idempotency_key: str | None = None


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    canonical_title: str
    authors_or_owner: list[str]
    source_type: str
    publication_state: str
    date: str
    version: str | None = None
    canonical_url: str
    retrieved_at: str
    primary_or_derivative: str
    provenance_parent_ids: list[str] = Field(default_factory=list)
    access_level: str
    content_hash: str
    content_hash_algorithm: str
    retrieval_method: str
    registry_status: str
    license: str | None = None
    language: str | None = None
    identifiers: dict[str, str] | None = None


class EvidenceCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    source_id: str
    question_addressed: str
    claim: str
    claim_status: str
    locator: str
    access_level: str
    confidence: str
    confidence_reason: str
    verifier_status: str
    active: bool = True
