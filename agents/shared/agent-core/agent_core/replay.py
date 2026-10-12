"""Offline provider-contract replay. Never builds a provider or executes tools."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .providers.base import Invocation
from .providers.codex_cli import parse_codex_jsonl, ENVELOPE_VERSION
from .providers.http import ProviderError

MAX_FIXTURE_BYTES = 2_000_000


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def replay_fixture(fixture):
    if not isinstance(fixture, dict) or set(fixture) != {"version", "id", "request", "events", "expected"} or fixture["version"] != 1:
        raise ValueError("unsupported replay fixture")
    if not isinstance(fixture["id"], str) or not fixture["id"]:
        raise ValueError("fixture ID required")
    events = fixture["events"]
    if not isinstance(events, list) or len(events) > 10_000:
        raise ValueError("bounded event array required")
    lines = [event if isinstance(event, str) else json.dumps(event, allow_nan=False) for event in events]
    request = Invocation(**fixture["request"])
    actual = {"outcome": "accepted"}
    try:
        result = parse_codex_jsonl(lines, request, model=request.model, envelope_version=ENVELOPE_VERSION)
        actual.update(output=result.output, tool_calls=[asdict(call) for call in result.tool_calls],
                      usage=asdict(result.usage), finish_reason=result.finish_reason)
    except ProviderError as error:
        actual = {"outcome": "denied", "reason": error.reason_code,
                  "remote_acceptance": error.remote_acceptance}
        receipt = getattr(error, "response", None)
        if receipt is not None:
            actual["usage"] = asdict(receipt.usage)
    expected = fixture["expected"]
    if not isinstance(expected, dict) or "outcome" not in expected:
        raise ValueError("expected outcome required")
    passed = all(actual.get(key) == value for key, value in expected.items())
    return {"id": fixture["id"], "passed": passed, "expected": expected, "actual": actual,
            "fixture_hash": _digest(fixture), "model_calls": 0, "tool_executions": 0}


def replay(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("replay input symlink denied")
    with path.open("rb") as handle:
        raw = handle.read(MAX_FIXTURE_BYTES + 1)
    if len(raw) > MAX_FIXTURE_BYTES:
        raise ValueError("replay corpus exceeds bound")
    corpus = json.loads(raw)
    if not isinstance(corpus, list) or not 1 <= len(corpus) <= 256:
        raise ValueError("bounded fixture corpus required")
    if len({row["id"] for row in corpus}) != len(corpus):
        raise ValueError("duplicate fixture ID")
    results = [replay_fixture(row) for row in corpus]
    return {"schema_version": 1, "mode": "replay", "evidence_kind": "transport_contract",
            "ok": all(row["passed"] for row in results), "corpus_hash": hashlib.sha256(raw).hexdigest(),
            "parser_hash": hashlib.sha256(Path(__import__(parse_codex_jsonl.__module__, fromlist=["__file__"]).__file__).read_bytes()).hexdigest(),
            "model_calls": 0, "tool_executions": 0, "results": results}
