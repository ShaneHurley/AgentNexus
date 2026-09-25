"""Director approval tokens (RF-W5-B-03)."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApprovalToken:
    token_id: str
    run_id: str
    packet_hash: str
    provider: str
    model: str
    max_cost_usd: float
    max_tokens: int
    purpose: str
    expires_at: float

    def bind_key(self) -> str:
        payload = {
            "run_id": self.run_id,
            "packet_hash": self.packet_hash,
            "provider": self.provider,
            "model": self.model,
            "purpose": self.purpose,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_id": self.token_id,
            "run_id": self.run_id,
            "packet_hash": self.packet_hash,
            "provider": self.provider,
            "model": self.model,
            "max_cost_usd": self.max_cost_usd,
            "max_tokens": self.max_tokens,
            "purpose": self.purpose,
            "expires_at": self.expires_at,
            "bind_key": self.bind_key(),
        }


class ApprovalTokenStore:
    def __init__(self) -> None:
        self._used: set[str] = set()

    def mint(
        self,
        *,
        run_id: str,
        packet_hash: str,
        provider: str = "mock",
        model: str = "mock-director",
        max_cost_usd: float = 2.0,
        max_tokens: int = 8000,
        purpose: str = "final_synthesis",
        ttl_seconds: float = 3600.0,
    ) -> ApprovalToken:
        return ApprovalToken(
            token_id=f"AT-{uuid.uuid4().hex[:16]}",
            run_id=run_id,
            packet_hash=packet_hash,
            provider=provider,
            model=model,
            max_cost_usd=max_cost_usd,
            max_tokens=max_tokens,
            purpose=purpose,
            expires_at=time.time() + ttl_seconds,
        )

    def validate(self, token: ApprovalToken, *, packet_hash: str, run_id: str) -> dict[str, Any]:
        issues: list[str] = []
        if token.packet_hash != packet_hash:
            issues.append("packet_hash_mismatch")
        if token.run_id != run_id:
            issues.append("run_id_mismatch")
        if time.time() > token.expires_at:
            issues.append("expired")
        if token.token_id in self._used:
            issues.append("token_reused")
        return {"valid": len(issues) == 0, "issues": issues}

    def consume(self, token: ApprovalToken) -> None:
        if token.token_id in self._used:
            raise ValueError("token_already_used")
        self._used.add(token.token_id)
