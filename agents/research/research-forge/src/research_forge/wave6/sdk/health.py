"""Adapter health checks (RF-W6-A-05)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from research_forge.wave6.sdk.conformance import ConformanceSuite


@dataclass
class HealthReport:
    adapter_id: str
    available: bool
    auth_ok: bool
    rate_limit_ok: bool
    schema_version: str
    last_test_at: str
    conformance_ok: bool
    issues: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return (
            self.available
            and self.auth_ok
            and self.rate_limit_ok
            and self.conformance_ok
            and not self.issues
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "available": self.available,
            "auth_ok": self.auth_ok,
            "rate_limit_ok": self.rate_limit_ok,
            "schema_version": self.schema_version,
            "last_test_at": self.last_test_at,
            "conformance_ok": self.conformance_ok,
            "healthy": self.healthy,
            "issues": self.issues,
        }


class HealthChecker:
    def __init__(self) -> None:
        self._suite = ConformanceSuite()
        self._cache: dict[str, HealthReport] = {}

    def check(self, adapter: Any) -> HealthReport:
        adapter_id = getattr(adapter, "adapter_id", "unknown")
        issues: list[str] = []
        available = True
        auth_ok = True
        rate_limit_ok = True

        if hasattr(adapter, "health_probe"):
            probe = adapter.health_probe()
            available = bool(probe.get("available", True))
            auth_ok = bool(probe.get("auth_ok", True))
            rate_limit_ok = bool(probe.get("rate_limit_ok", True))
            issues.extend(probe.get("issues") or [])

        conf = self._suite.run(adapter)
        if not conf["ok"]:
            issues.extend(conf["failures"])

        report = HealthReport(
            adapter_id=adapter_id,
            available=available,
            auth_ok=auth_ok,
            rate_limit_ok=rate_limit_ok,
            schema_version=getattr(adapter, "protocol_version", "unknown"),
            last_test_at=datetime.now(timezone.utc).isoformat(),
            conformance_ok=conf["ok"],
            issues=issues,
        )
        self._cache[adapter_id] = report
        return report

    def filter_healthy(self, adapters: list[Any]) -> list[Any]:
        out: list[Any] = []
        for ad in adapters:
            if self.check(ad).healthy:
                out.append(ad)
        return out
