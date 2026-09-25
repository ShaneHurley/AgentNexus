"""Human promotion for learned router (RF-W6-D-07)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_forge.wave6.routing.offline import OfflineRouterModel


@dataclass
class RouterPromotionRecord:
    version: str
    approver: str
    scope: str
    fallback_version: str
    rollback_command: str
    signed_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "approver": self.approver,
            "scope": self.scope,
            "fallback_version": self.fallback_version,
            "rollback_command": self.rollback_command,
            "signed_at": self.signed_at,
        }


class LearnedRouterRegistry:
    """Learned router cannot self-activate."""

    def __init__(self) -> None:
        self._promoted: dict[str, OfflineRouterModel] = {}
        self._records: list[RouterPromotionRecord] = []

    def promote(
        self,
        model: OfflineRouterModel,
        record: RouterPromotionRecord,
        *,
        self_activation: bool = False,
    ) -> dict[str, Any]:
        if self_activation:
            return {"promoted": False, "reason": "self_activation_forbidden"}
        if not record.approver:
            return {"promoted": False, "reason": "missing_approver"}
        self._promoted[model.version] = model
        self._records.append(record)
        return {"promoted": True, "version": model.version}

    def get_active(self, version: str) -> OfflineRouterModel | None:
        return self._promoted.get(version)

    def auto_activate_latest(self) -> dict[str, Any]:
        return {"activated": False, "reason": "human_promotion_required"}
