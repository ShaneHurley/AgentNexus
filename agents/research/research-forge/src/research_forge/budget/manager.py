"""Budget Manager — profiles, reserve/debit, thresholds, Director counter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from research_forge.errors import ErrorCode, ForgeError, forge_error


@dataclass
class BudgetState:
    profile: str
    limit_usd: float
    spent_usd: float = 0.0
    reserved_usd: float = 0.0
    director_calls: int = 0
    role_spent: dict[str, float] = field(default_factory=dict)
    lane_spent: dict[str, float] = field(default_factory=dict)
    hard_stopped: bool = False

    @property
    def available(self) -> float:
        audit_reserve = self.limit_usd * self.audit_fraction
        return max(0.0, self.limit_usd - self.spent_usd - self.reserved_usd - audit_reserve)

    audit_fraction: float = 0.10


class BudgetManager:
    def __init__(self, config_path: Path) -> None:
        with config_path.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        self.profiles = cfg["profiles"]
        self.thresholds = cfg["thresholds"]
        self.state: BudgetState | None = None
        self.events: list[dict[str, Any]] = []

    def start(self, profile: str) -> BudgetState:
        if profile not in self.profiles:
            raise ValueError(f"Unknown profile {profile}")
        p = self.profiles[profile]
        self.state = BudgetState(
            profile=profile,
            limit_usd=float(p["cost_usd"]),
            audit_fraction=float(p.get("reserve_audit_fraction", 0.10)),
        )
        return self.state

    def reserve(self, amount_usd: float, *, role: str = "host", lane: str = "default") -> ForgeError | None:
        if not self.state or self.state.hard_stopped:
            return forge_error(ErrorCode.BUDGET_EXCEEDED, "Budget hard stopped")
        if amount_usd > self.state.available:
            return forge_error(ErrorCode.BUDGET_EXCEEDED, "Insufficient reserve")
        self.state.reserved_usd += amount_usd
        self.events.append({"type": "reserve", "amount_usd": amount_usd, "role": role, "lane": lane})
        return None

    def debit(
        self,
        amount_usd: float,
        *,
        role: str = "host",
        lane: str = "default",
        release_reserve: float | None = None,
    ) -> ForgeError | None:
        if not self.state or self.state.hard_stopped:
            return forge_error(ErrorCode.BUDGET_EXCEEDED, "Budget hard stopped")
        if release_reserve:
            self.state.reserved_usd = max(0.0, self.state.reserved_usd - release_reserve)
        self.state.spent_usd += amount_usd
        self.state.role_spent[role] = self.state.role_spent.get(role, 0.0) + amount_usd
        self.state.lane_spent[lane] = self.state.lane_spent.get(lane, 0.0) + amount_usd
        self.events.append({"type": "debit", "amount_usd": amount_usd, "role": role, "lane": lane})
        frac = self.state.spent_usd / self.state.limit_usd
        if frac >= self.thresholds["hard_stop_fraction"]:
            self.state.hard_stopped = True
        return None

    def threshold_status(self) -> str:
        if not self.state:
            return "none"
        frac = self.state.spent_usd / self.state.limit_usd
        if frac >= self.thresholds["hard_stop_fraction"]:
            return "hard_stop"
        if frac >= self.thresholds["checkpoint_fraction"]:
            return "checkpoint"
        if frac >= self.thresholds["warn_fraction"]:
            return "warn"
        return "ok"

    def authorize_director_call(
        self,
        *,
        profile: str,
        xl_conflict: bool = False,
        approval_token: str | None = None,
    ) -> ForgeError | None:
        if not self.state:
            return forge_error(ErrorCode.BUDGET_EXCEEDED, "Budget not started")
        max_calls = int(self.profiles[profile]["director_calls"])
        if self.state.director_calls >= max_calls:
            if not (profile == "XL" and xl_conflict and approval_token):
                return forge_error(ErrorCode.BUDGET_EXCEEDED, "Director call limit")
        if profile == "XL" and self.state.director_calls >= 1:
            if not (xl_conflict and approval_token):
                return forge_error(ErrorCode.BUDGET_EXCEEDED, "Second Director call denied")
        reserve_err = self.reserve(1.0, role="director")
        if reserve_err:
            return reserve_err
        self.state.director_calls += 1
        return None

    def report(self) -> dict[str, Any]:
        if not self.state:
            return {}
        return {
            "profile": self.state.profile,
            "limit_usd": self.state.limit_usd,
            "spent_usd": self.state.spent_usd,
            "reserved_usd": self.state.reserved_usd,
            "director_calls": self.state.director_calls,
            "role_spent": dict(self.state.role_spent),
            "lane_spent": dict(self.state.lane_spent),
            "threshold": self.threshold_status(),
            "hard_stopped": self.state.hard_stopped,
        }
