#!/usr/bin/env python3
"""Generate personal and agent-core JSON schemas."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    print("wrote", path.relative_to(REPO))


def main() -> None:
    base = {"$schema": "https://json-schema.org/draft/2020-12/schema"}
    personal = REPO / "schemas" / "personal"
    schemas = {
        "skill-route.schema.json": {
            **base,
            "title": "skill_route",
            "type": "object",
            "required": ["request_id", "selected_skill", "confidence"],
            "properties": {
                "request_id": {"type": "string"},
                "selected_skill": {"type": ["string", "null"]},
                "mode": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "clarify": {"type": "boolean"},
                "escalate_to": {"type": ["string", "null"]},
                "rationale": {"type": "string"},
            },
        },
        "study-session.schema.json": {
            **base,
            "title": "study_session",
            "type": "object",
            "required": ["session_id", "objective", "hint_level", "status"],
            "properties": {
                "session_id": {"type": "string"},
                "objective": {"type": "string"},
                "user_attempt": {"type": "string"},
                "hint_level": {"type": "integer", "minimum": 1, "maximum": 5},
                "status": {"enum": ["COMPLETE", "PARTIAL", "BLOCKED"]},
                "integrity_ok": {"type": "boolean"},
            },
        },
        "lab-preflight.schema.json": {
            **base,
            "title": "lab_preflight",
            "type": "object",
            "required": ["lab_id", "ready", "unknowns", "status"],
            "properties": {
                "lab_id": {"type": "string"},
                "ready": {"type": "boolean"},
                "missing_prerequisites": {"type": "array", "items": {"type": "string"}},
                "materials": {"type": "array", "items": {"type": "string"}},
                "safety": {"type": "array", "items": {"type": "string"}},
                "unknowns": {"type": "array", "items": {"type": "string"}},
                "status": {"enum": ["COMPLETE", "PARTIAL", "BLOCKED", "NOT_APPLICABLE"]},
            },
        },
        "deadline-triage.schema.json": {
            **base,
            "title": "deadline_triage",
            "type": "object",
            "required": ["items", "status"],
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["title", "due", "priority"],
                        "properties": {
                            "title": {"type": "string"},
                            "due": {"type": "string"},
                            "priority": {"enum": ["P0", "P1", "P2", "P3"]},
                            "source": {"type": "string"},
                        },
                    },
                },
                "status": {"enum": ["COMPLETE", "PARTIAL", "BLOCKED"]},
                "beats_baseline": {"type": ["boolean", "null"]},
            },
        },
        "career-profile.schema.json": {
            **base,
            "title": "career_profile",
            "type": "object",
            "required": ["version", "identity"],
            "properties": {
                "version": {"type": "string"},
                "identity": {"type": "object"},
                "skills": {"type": "array", "items": {"type": "string"}},
                "education": {"type": "array"},
                "experience_ids": {"type": "array", "items": {"type": "string"}},
                "public_summary": {"type": "string"},
            },
        },
        "accomplishment.schema.json": {
            **base,
            "title": "accomplishment",
            "type": "object",
            "required": ["id", "context", "action", "result_status", "confidentiality"],
            "properties": {
                "id": {"type": "string", "pattern": "^ACC-"},
                "context": {"type": "string"},
                "action": {"type": "string"},
                "result": {"type": "string"},
                "technologies": {"type": "array", "items": {"type": "string"}},
                "competencies": {"type": "array", "items": {"type": "string"}},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
                "result_status": {"enum": ["VERIFIED", "USER_CONFIRMED", "UNKNOWN"]},
                "confidentiality": {"enum": ["public", "private", "employer_confidential"]},
                "resume_safe_summary": {"type": "string"},
                "interview_story_outline": {"type": "string"},
            },
        },
        "opportunity-review.schema.json": {
            **base,
            "title": "opportunity_review",
            "type": "object",
            "required": ["opportunity_id", "recommendation", "status"],
            "properties": {
                "opportunity_id": {"type": "string"},
                "requirements": {"type": "array", "items": {"type": "string"}},
                "matched_evidence": {"type": "array", "items": {"type": "string"}},
                "gaps": {"type": "array", "items": {"type": "string"}},
                "recommendation": {"enum": ["APPLY", "INVESTIGATE", "DEFER"]},
                "status": {"enum": ["COMPLETE", "PARTIAL", "BLOCKED"]},
            },
        },
        "browser-handoff.schema.json": {
            **base,
            "title": "browser_handoff",
            "type": "object",
            "required": ["role_id", "status", "persisted"],
            "properties": {
                "role_id": {"type": "string"},
                "status": {"enum": ["COMPLETE", "PARTIAL", "BLOCKED", "NOT_APPLICABLE"]},
                "persisted": {"type": "boolean", "const": False},
                "draft": {"type": "string"},
                "evidence_refs": {"type": "array", "items": {"type": "string"}},
            },
        },
    }
    for name, schema in schemas.items():
        write(personal / name, schema)

    write(
        REPO / "agent-core" / "schemas" / "writing" / "writing_task.schema.json",
        {
            **base,
            "title": "writing_task",
            "type": "object",
            "required": ["task_id", "mode", "purpose"],
            "properties": {
                "task_id": {"type": "string"},
                "mode": {
                    "enum": [
                        "email",
                        "discussion_post",
                        "message",
                        "small_rewrite",
                        "page_review",
                        "technical_documentation",
                        "code_comment",
                        "readme",
                        "design_document",
                        "change_summary",
                        "style_review",
                    ]
                },
                "audience": {"type": "object"},
                "purpose": {"type": "string"},
                "source_text": {"type": "string"},
                "formality": {"enum": ["F1", "F2", "F3", "F4", "auto"]},
                "rewrite_scope": {
                    "enum": [
                        "correct_only",
                        "minimal",
                        "moderate",
                        "substantial",
                        "new_from_context",
                        "review_only",
                    ]
                },
                "required_facts": {"type": "array", "items": {"type": "string"}},
                "prohibited_claims": {"type": "array", "items": {"type": "string"}},
            },
        },
    )
    write(
        REPO / "agent-core" / "schemas" / "writing" / "writing_result.schema.json",
        {
            **base,
            "title": "writing_result",
            "type": "object",
            "required": ["task_id", "status", "mode", "formality_applied", "validation"],
            "properties": {
                "task_id": {"type": "string"},
                "status": {"enum": ["COMPLETE", "PARTIAL", "BLOCKED"]},
                "mode": {"type": "string"},
                "formality_applied": {"enum": ["F1", "F2", "F3", "F4"]},
                "revised_artifact": {"type": "string"},
                "change_summary": {"type": "object"},
                "unsupported_claims_removed": {"type": "array", "items": {"type": "string"}},
                "validation": {
                    "type": "object",
                    "required": ["no_em_dash", "repetition_check"],
                    "properties": {
                        "no_em_dash": {"type": "boolean"},
                        "repetition_check": {"type": "boolean"},
                        "tone_consistency": {"type": "boolean"},
                        "semantic_preservation": {"type": "boolean"},
                        "audience_fit": {"type": "boolean"},
                    },
                },
            },
        },
    )
    write(
        REPO / "agent-core" / "schemas" / "shared" / "shared_task.schema.json",
        {
            **base,
            "title": "shared_task",
            "type": "object",
            "required": ["task_id", "caller_id", "role_id", "role_version", "output_schema", "budget"],
            "properties": {
                "task_id": {"type": "string"},
                "task_anchor": {"type": "string"},
                "caller_id": {"type": "string"},
                "role_id": {"type": "string"},
                "role_version": {"type": "string"},
                "mode": {"type": "string"},
                "input_refs": {"type": "array"},
                "profile_refs": {"type": "array"},
                "permissions": {"type": "array"},
                "forbidden_actions": {"type": "array"},
                "output_schema": {"type": "string"},
                "budget": {"type": "object"},
            },
        },
    )
    write(
        REPO / "agent-core" / "schemas" / "shared" / "shared_result.schema.json",
        {
            **base,
            "title": "shared_result",
            "type": "object",
            "required": ["task_id", "role_id", "role_version", "status"],
            "properties": {
                "task_id": {"type": "string"},
                "role_id": {"type": "string"},
                "role_version": {"type": "string"},
                "status": {"enum": ["COMPLETE", "PARTIAL", "BLOCKED", "NOT_APPLICABLE"]},
                "claims": {"type": "array"},
                "evidence_refs": {"type": "array"},
                "artifacts": {"type": "array"},
                "unknowns": {"type": "array"},
                "limitations": {"type": "array"},
            },
        },
    )
    write(
        REPO / "agent-core" / "schemas" / "writing" / "style_task.schema.json",
        {
            **base,
            "title": "style_task",
            "type": "object",
            "required": ["task_id", "profile_id", "artifact"],
            "properties": {
                "task_id": {"type": "string"},
                "profile_id": {"type": "string"},
                "artifact": {"type": "string"},
                "formality": {"enum": ["F1", "F2", "F3", "F4"]},
            },
        },
    )
    write(
        REPO / "agent-core" / "schemas" / "writing" / "style_result.schema.json",
        {
            **base,
            "title": "style_result",
            "type": "object",
            "required": ["task_id", "status", "semantic_risk"],
            "properties": {
                "task_id": {"type": "string"},
                "status": {"enum": ["COMPLETE", "PARTIAL", "BLOCKED"]},
                "findings": {"type": "array"},
                "patch_proposal": {"type": "string"},
                "semantic_risk": {"enum": ["none", "low", "medium", "high"]},
                "needs_domain_review": {"type": "boolean"},
            },
        },
    )
    write(
        REPO / "agent-core" / "schemas" / "toolkit" / "claim_audit.schema.json",
        {
            **base,
            "title": "claim_audit",
            "type": "object",
            "required": ["claims"],
            "properties": {
                "claims": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["text", "tag"],
                        "properties": {
                            "text": {"type": "string"},
                            "tag": {
                                "enum": [
                                    "VERIFIED",
                                    "USER_CONFIRMED",
                                    "UNKNOWN",
                                    "UNSUPPORTED",
                                ]
                            },
                            "evidence_refs": {"type": "array", "items": {"type": "string"}},
                            "freshness": {
                                "enum": ["fresh", "stale", "expired", "unknown"]
                            },
                        },
                    },
                }
            },
        },
    )


if __name__ == "__main__":
    main()
