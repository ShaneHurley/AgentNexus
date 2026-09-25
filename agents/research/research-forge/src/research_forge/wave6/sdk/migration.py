"""Adapter migration and compatibility (RF-W6-A-06)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MigrationPolicy:
    adapter_id: str
    min_protocol: str
    max_protocol: str
    deprecated_versions: frozenset[str]
    rollback_version: str | None = None

    def allows(self, version: str, protocol_version: str) -> tuple[bool, str | None]:
        if version in self.deprecated_versions:
            return False, "deprecated_version"
        if not _version_in_range(protocol_version, self.min_protocol, self.max_protocol):
            return False, "protocol_out_of_range"
        return True, None


def _version_in_range(v: str, lo: str, hi: str) -> bool:
    def parse(s: str) -> tuple[int, ...]:
        parts = []
        for p in s.split("."):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        return tuple(parts)

    return parse(lo) <= parse(v) <= parse(hi)


class MigrationManager:
    def __init__(self, policies: dict[str, MigrationPolicy] | None = None) -> None:
        self.policies = policies or {}
        self._activation_log: list[dict[str, Any]] = []

    def activate(self, adapter_id: str, version: str, protocol_version: str) -> dict[str, Any]:
        policy = self.policies.get(adapter_id)
        if not policy:
            entry = {"adapter_id": adapter_id, "activated": True, "reason": "no_policy"}
            self._activation_log.append(entry)
            return entry
        ok, reason = policy.allows(version, protocol_version)
        entry = {
            "adapter_id": adapter_id,
            "version": version,
            "protocol_version": protocol_version,
            "activated": ok,
            "reason": reason,
        }
        self._activation_log.append(entry)
        return entry

    def replay_fixture(self, fixture: dict[str, Any], adapter: Any) -> dict[str, Any]:
        """Replay stored request/response pairs after upgrade."""
        results: list[dict[str, Any]] = []
        for case in fixture.get("cases") or []:
            op = case.get("operation")
            if op == "search" and hasattr(adapter, "search"):
                out = adapter.search(case["query"], **case.get("kwargs", {}))
                match = out.get("results") is not None
            elif op == "read" and hasattr(adapter, "read"):
                out = adapter.read(case["locator"])
                match = "error" not in out or case.get("expect_error")
            else:
                match = False
                out = {"error": "unsupported_operation"}
            results.append({"case_id": case.get("id"), "match": match, "output_keys": list(out.keys())})
        return {"replay_ok": all(r["match"] for r in results), "results": results}
