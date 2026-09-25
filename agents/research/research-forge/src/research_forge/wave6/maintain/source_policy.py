"""Scheduled source-policy review (RF-W6-F-01)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class SourcePolicyReviewer:
    def review_adapters(self, adapters: list[dict[str, Any]], *, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        disabled: list[str] = []
        warnings: list[str] = []
        for ad in adapters:
            exp = ad.get("license_expires")
            if exp:
                exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                if exp_dt < now:
                    disabled.append(ad["adapter_id"])
                    continue
            if ad.get("schema_version") != ad.get("required_schema_version"):
                disabled.append(ad["adapter_id"])
                warnings.append(f"schema_mismatch:{ad['adapter_id']}")
            if ad.get("security_review") == "failed":
                disabled.append(ad["adapter_id"])
        return {"disabled": disabled, "warnings": warnings, "active": [a["adapter_id"] for a in adapters if a["adapter_id"] not in disabled]}
