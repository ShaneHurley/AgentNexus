"""Schema registry with version resolution."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

from research_forge.settings import find_package_root

SCHEMA_VERSION = "1.0.0"

CANONICAL: dict[str, str] = {
    "research_request": "research_request.schema.json",
    "clarification_result": "clarification_result.schema.json",
    "research_plan": "research_plan.schema.json",
    "research_charter": "charter.schema.json",
    "claim_status": "claim_status.schema.json",
    "source_record": "source_record.schema.json",
    "evidence_card": "evidence_card.schema.json",
    "contradiction": "contradiction.schema.json",
    "candidate_idea": "idea.schema.json",
    "experiment": "experiment.schema.json",
    "local_experiment_proposal": "local_experiment_proposal.schema.json",
    "experiment_pre_review": "experiment_pre_review.schema.json",
    "experiment_run_result": "experiment_run_result.schema.json",
    "experiment_post_review": "experiment_post_review.schema.json",
    "director_packet": "director_packet.schema.json",
    "director_synthesis": "director_synthesis.schema.json",
    "research_packet": "research_packet.schema.json",
    "ledger_event": "ledger_events.schema.json",
    "landscape_map": "landscape_map.schema.json",
    "scout_result": "scout_result.schema.json",
    "methods_review": "methods_review.schema.json",
    "evidence_matrix": "evidence_matrix.schema.json",
    "follow_up_request": "follow_up_request.schema.json",
    "audit_report": "audit_report.schema.json",
}

EXPERIMENT_SCHEMAS: frozenset[str] = frozenset(
    {
        "local_experiment_proposal",
        "experiment_pre_review",
        "experiment_run_result",
        "experiment_post_review",
    }
)


class SchemaRegistry:
    def __init__(
        self,
        schema_dir: Path,
        version: str = SCHEMA_VERSION,
        *,
        names: frozenset[str] | None = None,
        lazy: bool = True,
    ) -> None:
        self.schema_dir = schema_dir
        self.version = version
        self._names = names or frozenset(CANONICAL.keys())
        self._lazy = lazy
        self._validators: dict[str, Draft202012Validator] = {}
        self._registry: Registry | None = None
        if not lazy:
            self._ensure_built(frozenset(self._names))

    def _load_schema(self, fname: str) -> dict[str, Any]:
        path = self.schema_dir / fname
        return json.loads(path.read_text(encoding="utf-8"))

    def _ensure_registry(self) -> Registry:
        if self._registry is not None:
            return self._registry
        resources: list[tuple[str, Resource]] = []
        for name in self._names:
            fname = CANONICAL[name]
            path = self.schema_dir / fname
            if not path.is_file():
                continue
            resources.append((path.name, Resource.from_contents(self._load_schema(fname))))
        self._registry = Registry().with_resources(resources)
        return self._registry

    def _ensure_built(self, needed: frozenset[str]) -> None:
        missing = needed - self._validators.keys()
        if not missing:
            return
        registry = self._ensure_registry()
        for name in missing:
            if name not in CANONICAL:
                raise KeyError(f"Unknown schema: {name}")
            fname = CANONICAL[name]
            schema = self._load_schema(fname)
            self._validators[name] = Draft202012Validator(schema, registry=registry)

    def validate(self, canonical_name: str, instance: dict[str, Any]) -> None:
        if canonical_name not in self._names:
            raise KeyError(f"Unknown schema: {canonical_name}")
        self._ensure_built(frozenset({canonical_name}))
        self._validators[canonical_name].validate(instance)

    def validate_version(self, requested: str) -> None:
        if requested != self.version:
            raise ValidationError(
                f"Schema version {requested} requires migration; current={self.version}"
            )


@lru_cache(maxsize=8)
def get_registry(repo_root: Path | None = None) -> SchemaRegistry:
    root = (repo_root or find_package_root()).resolve()
    return SchemaRegistry(root / "schemas", lazy=True)


@lru_cache(maxsize=8)
def get_experiment_registry(package_root: Path | None = None) -> SchemaRegistry:
    """Load only local-experiment schemas (faster for experiment CLI cold starts)."""
    root = (package_root or find_package_root()).resolve()
    return SchemaRegistry(root / "schemas", names=EXPERIMENT_SCHEMAS, lazy=True)