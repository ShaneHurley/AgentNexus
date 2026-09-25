"""Falsification and Counterfactual Designer (RF-W3-D)."""

from __future__ import annotations

from typing import Any

from research_forge.wave3.types import FALSIFICATION_REJECT_REASONS


class FalsificationPolicyError(ValueError):
    pass


class FalsificationDesigner:
    role_id = "falsification_designer"
    allowed_tools: tuple[str, ...] = ()

    def design_tests(
        self,
        propositions: list[dict[str, Any]],
        hypotheses: list[dict[str, Any]],
        proposed_tests: list[dict[str, Any]],
    ) -> dict[str, Any]:
        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for test in proposed_tests:
            reason = self._validate_test(test, hypotheses)
            if reason:
                rejected.append({**test, "reject_reason": reason})
            else:
                accepted.append(test)

        ranked = self.rank_by_information_gain(accepted)
        disconfirming = self._disconfirming_observations(propositions)

        out = {
            "design_id": "FAL-1",
            "tests": ranked,
            "rejected_tests": rejected,
            "disconfirming_observations": disconfirming,
            "recommends_implementation": False,
        }
        if any(t.get("recommends_implementation") for t in proposed_tests):
            raise FalsificationPolicyError("Role must not recommend implementation")
        return out

    def _validate_test(self, test: dict[str, Any], hypotheses: list[dict[str, Any]]) -> str | None:
        if test.get("tautology") or test.get("predicted_outcome") == "always_true":
            return "tautology"
        if test.get("moving_target"):
            return "moving_target"
        if test.get("impossible_measurement"):
            return "impossible_measurement"
        preds = test.get("predictions") or {}
        if len(preds) < 2:
            return "confirms_only"
        outcomes = list(preds.values())
        if len(set(outcomes)) < 2:
            return "confirms_only"
        live = {h["hypothesis_id"] for h in hypotheses if h.get("status", "live") == "live"}
        covered = [hid for hid in preds if hid in live]
        if len(covered) < 2:
            return "confirms_only"
        if test.get("recommends_implementation"):
            return "confirms_only"
        return None

    def rank_by_information_gain(self, tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def score(t: dict[str, Any]) -> float:
            value = float(t.get("information_value", 0.5))
            cost = float(t.get("cost_usd", 1.0)) or 1.0
            time = float(t.get("time_days", 1.0)) or 1.0
            safety = 1.0 if t.get("safety_ok", True) else 0.1
            feasibility = float(t.get("feasibility", 0.5))
            return (value * safety * feasibility) / (cost * time)

        return sorted(tests, key=score, reverse=True)

    def _disconfirming_observations(self, propositions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in propositions:
            if p.get("unfalsifiable"):
                out.append(
                    {
                        "proposition_id": p["proposition_id"],
                        "flag": "unfalsifiable",
                        "observation": p.get("disconfirming_observation", ""),
                    }
                )
            elif p.get("disconfirming_observation"):
                out.append(
                    {
                        "proposition_id": p["proposition_id"],
                        "flag": "testable",
                        "observation": p["disconfirming_observation"],
                    }
                )
        return out

    @staticmethod
    def reject_reasons() -> tuple[str, ...]:
        return FALSIFICATION_REJECT_REASONS
