"""Version manifest — deterministic across runs."""

from __future__ import annotations

from pydantic import BaseModel


class VersionManifest(BaseModel):
    application: str = "0.1.0+wave0"
    schema_version: str = "1.0.0"
    prompt: str = "0.0.0-wave0"
    policy: str = "1.0.0"
    adapter_protocol: str = "1.0.0"
    ledger: str = "1.0.0"
    decision_registry: str = "1.0.0"


MANIFEST = VersionManifest()


def format_manifest() -> str:
    m = MANIFEST
    lines = [
        f"application={m.application}",
        f"schema={m.schema_version}",
        f"prompt={m.prompt}",
        f"policy={m.policy}",
        f"adapter_protocol={m.adapter_protocol}",
        f"ledger={m.ledger}",
        f"decision_registry={m.decision_registry}",
    ]
    return "\n".join(lines)
