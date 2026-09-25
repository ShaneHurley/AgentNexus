"""Experiment and Feasibility Architect (RF-W4-D)."""

from __future__ import annotations

from typing import Any


class ExperimentPolicyError(ValueError):
    pass


class ExperimentArchitect:
    role_id = "experiment_architect"
    allowed_tools: tuple[str, ...] = ()

    def design_for_idea(
        self,
        idea: dict[str, Any],
        *,
        seed_tests: list[dict[str, Any]] | None = None,
        unsafe: bool = False,
    ) -> dict[str, Any]:
        if unsafe:
            raise ExperimentPolicyError("unsafe experiment rejected; requires human approval")

        hypothesis = f"If {idea.get('proposal')} then metric improves versus baseline"
        counter = f"Baseline performance unchanged; {idea.get('baseline')} remains sufficient"
        exp_id = f"EXP-{idea['idea_id'].split('-', 1)[-1][:8]}"
        plan: dict[str, Any] = {
            "experiment_id": exp_id,
            "idea_id": idea["idea_id"],
            "hypothesis": hypothesis,
            "counter_hypothesis": counter,
            "baseline": idea.get("baseline", "Current production baseline"),
            "intervention": idea.get("proposal", "Proposed change"),
            "competing_predictions": [
                "Intervention arm: metric delta >= acceptance threshold",
                "Control arm: metric within baseline band",
            ],
            "controls": ["Hold traffic mix constant", "Pin build and config versions"],
            "variables": ["Intervention enabled vs disabled"],
            "metrics": ["Primary reliability metric", "Latency secondary"],
            "thresholds": {
                "accept": "Primary metric +2% with p<0.05 over 7 days",
                "reject": "Primary metric <= baseline +0.2%",
                "inconclusive": "Insufficient sample or overlapping CIs",
            },
            "confounders": ["Deployment coinciding with marketing event"],
            "resource_plan": [
                "Data: production traces",
                "Tools: experiment platform",
                "Expertise: SRE review",
                "Approvals: change advisory",
            ],
            "costs": ["One week shadow traffic cost"],
            "safety": ["Stop if error budget burn exceeds 2x baseline"],
            "environment_pin": "prod-region-a build 2024.09.01",
            "stop_rule": "Halt if safety threshold breached twice in 24h",
            "rollback": "Revert feature flag and drain canary within 15 minutes",
            "rejection_criterion": "Metric fails reject threshold or safety stop fires",
            "human_approval_required": False,
            "next_steps": {
                "accept": "Schedule limited rollout with continued monitoring; hold full scale until second review",
                "reject": "Archive idea with measured outcome; do not expand scope",
                "inconclusive": "Extend sample one week or redesign metric; no scale-up",
            },
        }
        if seed_tests:
            plan["seed_test_ids"] = [t.get("test_id") for t in seed_tests if t.get("test_id")]
        unavailable = [r for r in plan["resource_plan"] if r.startswith("BLOCKED:")]
        if unavailable:
            plan["human_approval_required"] = True
            plan["blockers"] = unavailable
        return plan

    def validate_one_per_task(self, tasks: list[dict[str, Any]]) -> None:
        seen: set[str] = set()
        for task in tasks:
            iid = task.get("idea_id")
            if not iid:
                raise ExperimentPolicyError("experiment task missing idea_id")
            if iid in seen:
                raise ExperimentPolicyError("multiple experiments per idea in single task")
            seen.add(iid)
