"""Credential indirection — reference env keys only (RF-W1-A-03)."""

from __future__ import annotations

import os
from typing import Any

# Approved provider env key names; never persist values in ledger/config.
APPROVED_CREDENTIAL_ENV_KEYS = frozenset(
    {
        "RF_PUBLIC_SEARCH_API_KEY",
        "RF_PUBLIC_READER_API_KEY",
    }
)


def credential_refs_for_live() -> dict[str, str]:
    """Map logical provider slot to env var name if set."""
    refs: dict[str, str] = {}
    for key in sorted(APPROVED_CREDENTIAL_ENV_KEYS):
        if os.environ.get(key):
            refs[key.removeprefix("RF_").lower()] = key
    return refs


def redact_for_audit(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    for k in list(out):
        if "secret" in k.lower() or "password" in k.lower() or "api_key" in k.lower():
            out[k] = "[REDACTED]"
    return out
