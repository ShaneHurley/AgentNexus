"""Host service mirror — context projection entrypoint (RF-W2-F)."""

from __future__ import annotations

from typing import Any

from research_forge.wave2.context import ContextProjector, ContextRequest, PinnedContextStore


class ContextManagerService:
    def __init__(self, pinned: PinnedContextStore) -> None:
        self._projector = ContextProjector(pinned.as_dict())

    def project_for_role(
        self,
        role: str,
        *,
        charter_question: str,
        source_ids: list[str],
        evidence_ids: list[str],
        token_ceiling: int,
        sources: dict[str, dict[str, Any]],
        evidence: dict[str, dict[str, Any]],
        disposable: list[str] | None = None,
    ) -> dict[str, Any]:
        req = ContextRequest(
            role=role,
            charter_question=charter_question,
            source_ids=source_ids,
            evidence_ids=evidence_ids,
            token_ceiling=token_ceiling,
        )
        return self._projector.project(
            req,
            sources=sources,
            evidence=evidence,
            disposable=disposable,
        )

    def validate_dispatch(self, before_pinned: dict[str, Any], projection: dict[str, Any]) -> None:
        self._projector.block_if_invalid(before_pinned, projection)

    @property
    def telemetry(self) -> list[dict[str, Any]]:
        return [t.to_dict() for t in self._projector.telemetry]
