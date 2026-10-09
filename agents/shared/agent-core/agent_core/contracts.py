"""Fail-closed task grants. A registry describes capability; it never grants authority."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import math
from typing import Any, Mapping

LAYERS = ("user", "role", "profile", "parent", "runtime", "approval")
ACTIONS = ("tools", "skills", "delegation", "memory_read", "memory_write")


class ContractDenied(PermissionError):
    pass


@dataclass(frozen=True)
class Grant:
    tools: frozenset[str] = frozenset()
    skills: frozenset[str] = frozenset()
    delegation: frozenset[str] = frozenset()
    memory_read: frozenset[str] = frozenset()
    memory_write: frozenset[str] = frozenset()
    workspace_roots: tuple[str, ...] = ()
    write_roots: tuple[str, ...] = ()
    resources: Mapping[str, int | float] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Grant":
        if not isinstance(value, Mapping):
            raise ContractDenied("grant must be an explicit mapping")
        unknown = set(value) - set(ACTIONS) - {"workspace_roots", "write_roots", "resources"}
        if unknown:
            raise ContractDenied(f"unknown grant fields: {sorted(unknown)}")
        data = {}
        for key in ACTIONS:
            entries = value.get(key, [])
            if not isinstance(entries, (list, tuple, set, frozenset)) or any(not isinstance(x, str) or not x or x == "*" for x in entries):
                raise ContractDenied(f"{key} requires explicit capability IDs")
            data[key] = frozenset(entries)
        for key in ("workspace_roots", "write_roots"):
            entries = value.get(key, [])
            if not isinstance(entries, (list, tuple)) or any(not isinstance(x, str) or not Path(x).is_absolute() for x in entries):
                raise ContractDenied(f"{key} requires absolute paths")
            data[key] = tuple(str(Path(x).resolve()) for x in entries)
        resources = value.get("resources", {})
        if not isinstance(resources, Mapping) or any(not isinstance(x, (int, float)) or isinstance(x, bool) or not math.isfinite(x) or x < 0 for x in resources.values()):
            raise ContractDenied("resource ceilings must be non-negative numbers")
        data["resources"] = dict(resources)
        return cls(**data)

    def as_mapping(self) -> dict[str, Any]:
        return {**{k: sorted(getattr(self, k)) for k in ACTIONS},
                "workspace_roots": list(self.workspace_roots), "write_roots": list(self.write_roots),
                "resources": dict(self.resources)}

    def permits_path(self, path: str | Path, *, write: bool = False) -> bool:
        target = Path(path).resolve()
        return any(target == Path(root) or Path(root) in target.parents for root in (self.write_roots if write else self.workspace_roots))


@dataclass(frozen=True)
class EffectiveGrant:
    """Retains every layer so path intersection cannot accidentally union permissions."""
    layers: tuple[Grant, ...]
    role_id: str
    revoked: frozenset[str] = frozenset()

    @classmethod
    def evaluate(cls, contract: Mapping[str, Any], layers: Mapping[str, Grant | Mapping[str, Any]], *, revoked=()) -> "EffectiveGrant":
        if set(layers) != set(LAYERS):
            raise ContractDenied("all six grant layers are required")
        if not contract.get("id") or contract.get("active") is not True:
            raise ContractDenied("unknown or inactive role")
        values = tuple(v if isinstance(v, Grant) else Grant.from_mapping(v) for v in (layers[k] for k in LAYERS))
        role = Grant.from_mapping(contract.get("grant", {}))
        # Caller-supplied role layer may narrow the registry, never broaden it.
        values += (role,)
        if contract.get("leaf", True) and any(values[-1].delegation):
            raise ContractDenied("leaf roles cannot delegate")
        return cls(values, contract["id"], frozenset(revoked))

    def capabilities(self, action: str) -> frozenset[str]:
        if action not in ACTIONS:
            raise ContractDenied("unknown action")
        return frozenset.intersection(*(getattr(g, action) for g in self.layers)) - self.revoked

    def authorize(self, action: str, capability: str, target: str | Path | None = None, *, write: bool = False) -> None:
        if capability not in self.capabilities(action):
            raise ContractDenied(f"{self.role_id} denied {action}:{capability}")
        if target is not None and not all(g.permits_path(target, write=write) for g in self.layers):
            raise ContractDenied("target escapes effective workspace scope")

    def ceiling(self, name: str) -> int | float:
        # Missing ceilings deny consumption instead of treating missing as unlimited.
        return min(g.resources.get(name, 0) for g in self.layers)

    def narrow(self, grant: Grant) -> "EffectiveGrant":
        return EffectiveGrant(self.layers + (grant,), self.role_id, self.revoked)

    def authorize_delegation(self, child: str, *, depth: int, active_children: int, task_key: str, ancestor_keys=()) -> None:
        self.authorize("delegation", child)
        if depth >= min(2, self.ceiling("delegation_depth")) or active_children >= min(2, self.ceiling("concurrency")):
            raise ContractDenied("delegation ceiling reached")
        if not task_key or task_key in ancestor_keys:
            raise ContractDenied("duplicate or recursive task key")
