"""Idea lineage graph (RF-W4-B-02)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LineageGraph:
    parent_edges: dict[str, list[str]] = field(default_factory=dict)
    component_edges: dict[str, list[dict[str, str]]] = field(default_factory=dict)

    def add_parent(self, child_id: str, parent_id: str) -> None:
        if child_id == parent_id:
            raise ValueError("self-parent forbidden")
        if self._would_cycle(child_id, parent_id):
            raise ValueError("lineage cycle detected")
        self.parent_edges.setdefault(child_id, [])
        if parent_id not in self.parent_edges[child_id]:
            self.parent_edges[child_id].append(parent_id)

    def add_component(
        self,
        hybrid_id: str,
        *,
        component: str,
        parent_idea: str,
        reason: str,
        evidence_id: str,
        interface: str,
    ) -> None:
        self.component_edges.setdefault(hybrid_id, [])
        self.component_edges[hybrid_id].append(
            {
                "component": component,
                "parent_idea": parent_idea,
                "reason": reason,
                "evidence_id": evidence_id,
                "interface": interface,
            }
        )

    def _would_cycle(self, child_id: str, parent_id: str) -> bool:
        seen: set[str] = set()
        stack = [parent_id]
        while stack:
            cur = stack.pop()
            if cur == child_id:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(self.parent_edges.get(cur, []))
        return False

    def trace_components(self, hybrid_id: str) -> list[dict[str, str]]:
        return list(self.component_edges.get(hybrid_id, []))

    def validate_hybrid(self, hybrid: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        iid = hybrid["idea_id"]
        parents = hybrid.get("lineage") or []
        for pid in parents:
            try:
                self.add_parent(iid, pid)
            except ValueError as exc:
                errors.append(str(exc))
        traced = self.trace_components(iid)
        if hybrid.get("opportunity_type") == "hybrid" and not traced:
            errors.append("hybrid missing component trace")
        return errors
