"""Director provider call wrapper (RF-W5-B-04)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from research_forge.providers.mock_model import MockModel


@dataclass
class DirectorCallRecord:
    idempotency_key: str
    packet_hash: str
    output_hash: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        return {
            "idempotency_key": self.idempotency_key,
            "packet_hash": self.packet_hash,
            "output_hash": self.output_hash,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost_usd": self.cost_usd,
            "latency_ms": self.latency_ms,
            "status": self.status,
        }


class DirectorCallTracker:
    """Enforce one intellectual call per run (second only via challenge path)."""

    def __init__(self) -> None:
        self.intellectual_calls = 0
        self._by_key: dict[str, DirectorCallRecord] = {}

    def can_dispatch(self, *, challenge: bool = False, xl_approved: bool = False) -> bool:
        if self.intellectual_calls == 0:
            return True
        return challenge and xl_approved

    def get_idempotent(self, key: str) -> DirectorCallRecord | None:
        return self._by_key.get(key)


class DirectorProvider:
    def __init__(
        self,
        *,
        fixtures_dir: Path | None = None,
        timeout_seconds: float = 120.0,
        cost_per_1k_tokens: float = 0.002,
        complete_fn: Callable[[str, str], dict[str, Any]] | None = None,
    ) -> None:
        self.mock = MockModel(fixtures_dir)
        self.timeout_seconds = timeout_seconds
        self.cost_per_1k_tokens = cost_per_1k_tokens
        self.complete_fn = complete_fn
        self.tracker = DirectorCallTracker()

    def dispatch(
        self,
        *,
        packet: dict[str, Any],
        token_id: str,
        idempotency_key: str,
        fixture_task_id: str = "director",
        challenge: bool = False,
        xl_approved: bool = False,
    ) -> dict[str, Any]:
        existing = self.tracker.get_idempotent(idempotency_key)
        if existing and existing.status == "completed":
            return {"status": "idempotent_replay", "record": existing.to_dict()}

        if not self.tracker.can_dispatch(challenge=challenge, xl_approved=xl_approved):
            return {"status": "blocked", "reason": "one_call_limit"}

        packet_hash = packet.get("packet_hash", "")
        prompt = json.dumps(packet, sort_keys=True)
        started = time.perf_counter()
        if self.complete_fn:
            raw = self.complete_fn(prompt, fixture_task_id)
        else:
            from research_forge.wave5.mock_responses import mock_director_response

            raw = mock_director_response(fixture_task_id, prompt)
            if "structured" not in raw and self.mock.fixtures_dir:
                raw = self.mock.complete(prompt, task_id=fixture_task_id)
        latency_ms = (time.perf_counter() - started) * 1000.0
        if latency_ms > self.timeout_seconds * 1000:
            return {"status": "timeout", "latency_ms": latency_ms}

        usage = raw.get("usage") or {}
        pt = int(usage.get("prompt_tokens", 0))
        ct = int(usage.get("completion_tokens", 0))
        cost = (pt + ct) / 1000.0 * self.cost_per_1k_tokens

        output = raw.get("structured") or raw.get("text")
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                output = {"raw_text": output}

        from research_forge.hashing.content import hash_bytes

        output_hash = hash_bytes(json.dumps(output, sort_keys=True).encode())
        record = DirectorCallRecord(
            idempotency_key=idempotency_key,
            packet_hash=packet_hash,
            output_hash=output_hash,
            prompt_tokens=pt,
            completion_tokens=ct,
            cost_usd=cost,
            latency_ms=latency_ms,
            status="completed",
        )
        self.tracker._by_key[idempotency_key] = record
        if not challenge:
            self.tracker.intellectual_calls += 1

        return {
            "status": "completed",
            "output": output,
            "record": record.to_dict(),
            "provider": "mock",
        }
