"""Provenance chain validation and integrity reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IntegrityReport:
    unverifiable_sources: list[str] = field(default_factory=list)
    changed_versions: list[str] = field(default_factory=list)
    missing_hashes: list[str] = field(default_factory=list)
    derivative_chains: list[dict[str, Any]] = field(default_factory=list)
    cycles: list[list[str]] = field(default_factory=list)
    laundering_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unverifiable_sources": self.unverifiable_sources,
            "changed_versions": self.changed_versions,
            "missing_hashes": self.missing_hashes,
            "derivative_chains": self.derivative_chains,
            "cycles": self.cycles,
            "laundering_flags": self.laundering_flags,
        }

    @property
    def ok(self) -> bool:
        return not (
            self.unverifiable_sources
            or self.cycles
            or self.laundering_flags
            or self.missing_hashes
        )


class ProvenanceValidator:
    """Detect cycles, dangling parents, and derivative corroboration laundering."""

    def __init__(self, sources: dict[str, dict[str, Any]]) -> None:
        self.sources = sources

    def validate(self) -> IntegrityReport:
        report = IntegrityReport()
        for sid, src in self.sources.items():
            if not src.get("content_hash"):
                report.missing_hashes.append(sid)
            parents = src.get("provenance_parent_ids") or []
            for pid in parents:
                if pid not in self.sources:
                    report.unverifiable_sources.append(f"{sid}:missing_parent:{pid}")

        cycles = self._find_cycles()
        report.cycles = cycles

        for sid, src in self.sources.items():
            if src.get("primary_or_derivative") == "derivative":
                chain = self._chain(sid)
                report.derivative_chains.append({"source_id": sid, "chain": chain})

        report.laundering_flags = self._detect_laundering()
        return report

    def _chain(self, sid: str) -> list[str]:
        seen = [sid]
        cur = sid
        while True:
            src = self.sources.get(cur, {})
            parents = src.get("provenance_parent_ids") or []
            if not parents:
                break
            cur = parents[0]
            if cur in seen:
                break
            seen.append(cur)
        return seen

    def _find_cycles(self) -> list[list[str]]:
        cycles: list[list[str]] = []
        visited: set[str] = set()
        stack: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> None:
            if node in stack:
                idx = path.index(node)
                cycles.append(path[idx:] + [node])
                return
            if node in visited:
                return
            visited.add(node)
            stack.add(node)
            path.append(node)
            parents = self.sources.get(node, {}).get("provenance_parent_ids") or []
            for p in parents:
                if p in self.sources:
                    dfs(p)
            path.pop()
            stack.remove(node)

        for sid in self.sources:
            dfs(sid)
        return cycles

    def _detect_laundering(self) -> list[str]:
        flags: list[str] = []
        derivatives = {
            sid
            for sid, s in self.sources.items()
            if s.get("primary_or_derivative") == "derivative"
        }
        if len(derivatives) >= 2:
            roots: set[str] = set()
            for sid in derivatives:
                chain = self._chain(sid)
                if chain:
                    roots.add(chain[-1])
            if len(roots) == 1 and len(derivatives) >= 2:
                flags.append("derivative_cluster_single_root")
        return flags

    def independent_corroboration_ok(self, source_ids: list[str]) -> bool:
        roots = set()
        for sid in source_ids:
            if sid not in self.sources:
                return False
            chain = self._chain(sid)
            roots.add(chain[-1] if chain else sid)
        return len(roots) >= 2
