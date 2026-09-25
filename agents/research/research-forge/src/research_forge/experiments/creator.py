"""Experiment Creator — records proposals with token_budget=0."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_forge.experiments.store import ExperimentStore
from research_forge.schemas_pkg.registry import get_experiment_registry


def new_experiment_id() -> str:
    return f"EXP-{secrets.token_hex(6).upper()}"


_REQUIRED_FROM_JSON = (
    "title",
    "question",
    "why_run",
    "hypothesis",
    "expected_support",
    "expected_reject",
    "expected_inconclusive",
    "decision_impact",
    "kind",
)


class ExperimentCreator:
    role_id = "experiment_creator"

    def __init__(
        self,
        package_root: Path,
        workspace_root: Path | None = None,
        store: ExperimentStore | None = None,
    ) -> None:
        self.package_root = package_root
        self.workspace_root = (workspace_root or package_root).resolve()
        self.store = store or ExperimentStore(
            self.workspace_root, package_root=self.package_root
        )
        self.registry = get_experiment_registry(self.package_root)

    def create_from_dict(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create from a JSON proposal body (agent-friendly). Assigns id/timestamps."""
        if not isinstance(payload, dict):
            raise ValueError("proposal payload must be a JSON object")
        inputs = payload.get("inputs") or {}
        if not isinstance(inputs, dict):
            raise ValueError("inputs must be an object")

        # Accept kebab-case aliases then normalize
        normalized = dict(payload)
        aliases = {
            "why-run": "why_run",
            "expected-support": "expected_support",
            "expected-reject": "expected_reject",
            "expected-inconclusive": "expected_inconclusive",
            "decision-impact": "decision_impact",
        }
        for kebab, snake in aliases.items():
            if snake not in normalized or not normalized.get(snake):
                if kebab in normalized:
                    normalized[snake] = normalized[kebab]

        missing = [k for k in _REQUIRED_FROM_JSON if not str(normalized.get(k) or "").strip()]
        if missing:
            raise ValueError(f"Missing required proposal fields: {missing}")

        data_path = inputs.get("data_path") or normalized.get("data_path")
        if not data_path:
            raise ValueError("inputs.data_path is required")

        return self.create(
            title=str(normalized["title"]),
            question=str(normalized["question"]),
            why_run=str(normalized["why_run"]),
            hypothesis=str(normalized["hypothesis"]),
            expected_support=str(normalized["expected_support"]),
            expected_reject=str(normalized["expected_reject"]),
            expected_inconclusive=str(normalized["expected_inconclusive"]),
            decision_impact=str(normalized["decision_impact"]),
            kind=str(normalized["kind"]),
            data_path=str(data_path),
            group_column=inputs.get("group_column") or normalized.get("group_column"),
            metric_column=inputs.get("metric_column") or normalized.get("metric_column"),
            unittest_start=inputs.get("unittest_start") or normalized.get("unittest_start"),
            estimated_runtime_seconds=int(normalized.get("estimated_runtime_seconds", 30)),
            repetitions=int(normalized.get("repetitions", 1)),
            idea_id=normalized.get("idea_id"),
            parent_plan_experiment_id=normalized.get("parent_plan_experiment_id"),
            experiment_id=normalized.get("experiment_id"),
        )

    def create(
        self,
        *,
        title: str,
        question: str,
        why_run: str,
        hypothesis: str,
        expected_support: str,
        expected_reject: str,
        expected_inconclusive: str,
        decision_impact: str,
        kind: str,
        data_path: str,
        group_column: str | None = None,
        metric_column: str | None = None,
        unittest_start: str | None = None,
        estimated_runtime_seconds: int = 30,
        repetitions: int = 1,
        idea_id: str | None = None,
        parent_plan_experiment_id: str | None = None,
        experiment_id: str | None = None,
    ) -> dict[str, Any]:
        if experiment_id:
            if self.store.exists(experiment_id, "proposal.json"):
                raise ValueError(f"experiment_id already exists: {experiment_id}")
            eid = experiment_id
        else:
            eid = new_experiment_id()
            # Extremely unlikely collision; regenerate once if needed
            if self.store.exists(eid, "proposal.json"):
                eid = new_experiment_id()

        inputs: dict[str, Any] = {"data_path": data_path}
        if group_column:
            inputs["group_column"] = group_column
        if metric_column:
            inputs["metric_column"] = metric_column
        if unittest_start:
            inputs["unittest_start"] = unittest_start

        proposal: dict[str, Any] = {
            "experiment_id": eid,
            "title": title,
            "question": question,
            "why_run": why_run,
            "hypothesis": hypothesis,
            "expected_support": expected_support,
            "expected_reject": expected_reject,
            "expected_inconclusive": expected_inconclusive,
            "decision_impact": decision_impact,
            "kind": kind,
            "inputs": inputs,
            "estimated_runtime_seconds": estimated_runtime_seconds,
            "repetitions": repetitions,
            "token_budget": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if idea_id:
            proposal["idea_id"] = idea_id
        if parent_plan_experiment_id:
            proposal["parent_plan_experiment_id"] = parent_plan_experiment_id

        if kind == "group_comparison":
            if not group_column or not metric_column:
                raise ValueError("group_comparison requires --group-column and --metric-column")
        if kind == "python_unittest_benchmark" and not unittest_start:
            proposal["inputs"]["unittest_start"] = data_path

        self.registry.validate("local_experiment_proposal", proposal)
        self.store.write_json(eid, "proposal.json", proposal)
        self.store.set_status(eid, "proposed")
        return proposal
