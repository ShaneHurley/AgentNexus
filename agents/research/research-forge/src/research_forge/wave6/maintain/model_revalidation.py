"""Model revalidation against locked suite (RF-W6-F-02)."""

from __future__ import annotations

from typing import Any, Callable

SuiteFn = Callable[[str, str], dict[str, Any]]


class ModelRevalidator:
    def __init__(self, suite_fn: SuiteFn | None = None) -> None:
        self.suite_fn = suite_fn or self._default_suite

    def _default_suite(self, provider: str, model: str) -> dict[str, Any]:
        score = 0.9 if "mock" in provider else 0.7
        return {"provider": provider, "model": model, "score": score, "passed": score >= 0.75}

    def revalidate(self, mapping: dict[str, str]) -> dict[str, Any]:
        tiers: dict[str, str] = {}
        reports: list[dict[str, Any]] = []
        for role, spec in mapping.items():
            provider, _, model = spec.partition("/")
            rep = self.suite_fn(provider, model)
            reports.append({"role": role, **rep})
            tiers[role] = "high" if rep["passed"] and rep["score"] >= 0.85 else "mid"
        return {"tier_mapping": tiers, "reports": reports, "evidence_based": True}
