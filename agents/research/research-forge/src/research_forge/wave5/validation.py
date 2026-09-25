"""Director output validation (RF-W5-B-05)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class DirectorOutputValidator:
    def __init__(self, repo_root: Path) -> None:
        schema_path = repo_root / "schemas" / "director_synthesis.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(schema)

    def validate(
        self,
        output: dict[str, Any],
        *,
        packet: dict[str, Any],
        allowed_evidence: set[str] | None = None,
    ) -> dict[str, Any]:
        issues: list[str] = []
        try:
            self.validator.validate(output)
        except Exception as exc:  # noqa: BLE001 - aggregate validation errors
            issues.append(f"schema:{exc.message if hasattr(exc, 'message') else exc}")

        if output.get("packet_hash") != packet.get("packet_hash"):
            issues.append("packet_hash_mismatch")

        allowed = allowed_evidence or {r["evidence_id"] for r in packet.get("fact_table", [])}
        for conclusion in output.get("conclusions", []):
            for eid in conclusion.get("evidence_ids", []):
                if eid not in allowed:
                    issues.append(f"unsupported_evidence:{eid}")

        new_facts = output.get("new_facts") or output.get("unsupported_claims")
        if new_facts:
            issues.append("unsupported_new_facts")

        return {"valid": len(issues) == 0, "issues": issues}
