"""Deterministic mock model keyed by prompt hash."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class MockModel:
    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self.fixtures_dir = fixtures_dir
        self.call_count = 0

    def complete(self, prompt: str, task_id: str = "default") -> dict[str, Any]:
        self.call_count += 1
        key = hashlib.sha256(f"{task_id}:{prompt}".encode()).hexdigest()[:16]
        if self.fixtures_dir:
            path = self.fixtures_dir / f"model_{key}.json"
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
        return {
            "text": f"mock-response:{key}",
            "usage": {"prompt_tokens": len(prompt.split()), "completion_tokens": 8},
            "model_tier": "mock",
        }
