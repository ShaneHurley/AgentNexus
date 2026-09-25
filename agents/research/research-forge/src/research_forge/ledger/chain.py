"""Hash chain helpers for ledger events."""

from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS = "sha256:0000000000000000000000000000000000000000000000000000000000000000"


def canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_hash(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def event_body_hash(event: dict[str, Any]) -> str:
    body = {
        "run_id": event["run_id"],
        "sequence": event["sequence"],
        "timestamp": event["timestamp"],
        "actor": event["actor"],
        "schema_version": event["schema_version"],
        "event_type": event["event_type"],
        "payload": event["payload"],
        "payload_hash": event["payload_hash"],
        "previous_hash": event["previous_hash"],
    }
    if "idempotency_key" in event:
        body["idempotency_key"] = event["idempotency_key"]
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"
