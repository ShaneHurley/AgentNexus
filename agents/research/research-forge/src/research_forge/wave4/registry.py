"""Immutable idea registry via ledger events (RF-W4-B-01)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from research_forge.wave4.types import IDEA_EVENT_TYPES


class IdeaRegistry:
    def __init__(self) -> None:
        self._ideas: dict[str, dict[str, Any]] = {}
        self._events: list[dict[str, Any]] = []

    @property
    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def _record(self, event_type: str, idea_id: str, payload: dict[str, Any]) -> None:
        if event_type not in IDEA_EVENT_TYPES:
            raise ValueError(f"unknown idea event {event_type}")
        self._events.append({"event_type": event_type, "idea_id": idea_id, **payload})

    def get(self, idea_id: str) -> dict[str, Any] | None:
        rec = self._ideas.get(idea_id)
        return deepcopy(rec) if rec else None

    def query(self, *, include_rejected: bool = True) -> list[dict[str, Any]]:
        out = []
        for idea in self._ideas.values():
            if not include_rejected and idea.get("status") == "rejected":
                continue
            out.append(deepcopy(idea))
        return out

    def add(self, idea: dict[str, Any]) -> dict[str, Any]:
        iid = idea["idea_id"]
        if iid in self._ideas:
            raise ValueError(f"idea already exists: {iid}")
        self._ideas[iid] = deepcopy(idea)
        self._record("idea_added", iid, {"status": idea.get("status", "active")})
        return deepcopy(self._ideas[iid])

    def supersede(self, old_id: str, new_idea: dict[str, Any], reason: str) -> dict[str, Any]:
        if old_id not in self._ideas:
            raise KeyError(old_id)
        self._ideas[old_id]["status"] = "rejected"
        self._ideas[old_id]["decision_reason"] = f"superseded: {reason}"
        self._record("idea_superseded", old_id, {"successor": new_idea["idea_id"], "reason": reason})
        return self.add(new_idea)

    def repair(self, idea_id: str, patch: dict[str, Any], attempt: int) -> dict[str, Any]:
        idea = self._ideas[idea_id]
        idea.update(patch)
        idea["status"] = "repair"
        self._record("idea_repair", idea_id, {"attempt": attempt, "patch_keys": sorted(patch.keys())})
        return deepcopy(idea)

    def reject(self, idea_id: str, reason: str) -> dict[str, Any]:
        idea = self._ideas[idea_id]
        idea["status"] = "rejected"
        idea["decision_reason"] = reason
        self._record("idea_rejected", idea_id, {"reason": reason})
        return deepcopy(idea)

    def defer(self, idea_id: str, reason: str) -> dict[str, Any]:
        idea = self._ideas[idea_id]
        idea["status"] = "deferred"
        idea["decision_reason"] = reason
        self._record("idea_deferred", idea_id, {"reason": reason})
        return deepcopy(idea)

    def recommend(self, idea_id: str, reason: str) -> dict[str, Any]:
        idea = self._ideas[idea_id]
        idea["status"] = "recommended"
        idea["decision_reason"] = reason
        self._record("idea_recommended", idea_id, {"reason": reason})
        return deepcopy(idea)
