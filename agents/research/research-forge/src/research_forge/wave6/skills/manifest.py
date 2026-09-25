"""Method skill manifest (RF-W6-C-01)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REQUIRED_FIELDS = (
    "name",
    "version",
    "request_types",
    "required_inputs",
    "phases",
    "output_schemas",
    "tool_budgets",
    "acceptance_criteria",
    "prohibited_behaviors",
)


@dataclass
class SkillManifest:
    name: str
    version: str
    request_types: list[str]
    required_inputs: list[str]
    phases: list[str]
    output_schemas: list[str]
    tool_budgets: dict[str, Any]
    acceptance_criteria: list[str]
    prohibited_behaviors: list[str]
    description: str = ""

    def validate(self) -> list[str]:
        errors: list[str] = []
        data = self.to_dict()
        for key in REQUIRED_FIELDS:
            if not data.get(key):
                errors.append(f"missing:{key}")
        if self.description and len(self.phases) == 0:
            errors.append("prose_only_invalid")
        if not self.request_types:
            errors.append("no_request_types")
        if not self.prohibited_behaviors:
            errors.append("missing_prohibited_behaviors")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "request_types": self.request_types,
            "required_inputs": self.required_inputs,
            "phases": self.phases,
            "output_schemas": self.output_schemas,
            "tool_budgets": self.tool_budgets,
            "acceptance_criteria": self.acceptance_criteria,
            "prohibited_behaviors": self.prohibited_behaviors,
            "description": self.description,
        }


def validate_skill_document(doc: dict[str, Any]) -> list[str]:
    """Reject generic prose-only skills."""
    if doc.get("phases") and not doc.get("output_schemas"):
        return ["prose_only_invalid"]
    try:
        manifest = SkillManifest(
            name=doc.get("name", ""),
            version=doc.get("version", ""),
            request_types=list(doc.get("request_types") or []),
            required_inputs=list(doc.get("required_inputs") or []),
            phases=list(doc.get("phases") or []),
            output_schemas=list(doc.get("output_schemas") or []),
            tool_budgets=dict(doc.get("tool_budgets") or {}),
            acceptance_criteria=list(doc.get("acceptance_criteria") or []),
            prohibited_behaviors=list(doc.get("prohibited_behaviors") or []),
            description=doc.get("description", ""),
        )
    except TypeError as exc:
        return [f"invalid_manifest:{exc}"]
    return manifest.validate()
