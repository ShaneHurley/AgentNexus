"""Append-only JSONL ledger with hash chain."""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_forge.ledger.chain import GENESIS, event_body_hash, payload_hash
from research_forge.ledger.interface import AbstractLedger

_LOCK = threading.Lock()


class JsonlLedger(AbstractLedger):
    def __init__(self, path: Path, *, fsync: bool = True) -> None:
        self.path = path
        self.fsync = fsync
        self._idempotency: dict[str, dict[str, Any]] = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def _scan_run_tail(self, run_id: str) -> tuple[int, str]:
        """Single-pass disk scan: return (latest_sequence, previous_hash for next append)."""
        latest_seq = 0
        last_event: dict[str, Any] | None = None
        if not self.path.is_file():
            return 0, GENESIS
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                ev = json.loads(line)
                if ev.get("run_id") != run_id:
                    continue
                seq = int(ev["sequence"])
                if seq >= latest_seq:
                    latest_seq = seq
                    last_event = ev
        if last_event is None:
            return 0, GENESIS
        return latest_seq, event_body_hash(last_event)

    def read_by_run(self, run_id: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                ev = json.loads(line)
                if ev.get("run_id") == run_id:
                    events.append(ev)
        return sorted(events, key=lambda e: e["sequence"])

    def read_by_sequence(self, run_id: str, sequence: int) -> dict[str, Any] | None:
        for ev in self.read_by_run(run_id):
            if ev["sequence"] == sequence:
                return ev
        return None

    def latest_sequence(self, run_id: str) -> int:
        seq, _ = self._scan_run_tail(run_id)
        return seq

    def _all_events(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if not self.path.is_file():
            return events
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events

    def verify_chain(self, run_id: str | None = None) -> tuple[bool, list[str]]:
        errors: list[str] = []
        by_run: dict[str, list[dict[str, Any]]] = {}
        for ev in self._all_events():
            rid = ev["run_id"]
            by_run.setdefault(rid, []).append(ev)

        targets = [run_id] if run_id else list(by_run.keys())
        for rid in targets:
            events = sorted(by_run.get(rid, []), key=lambda e: e["sequence"])
            prev_hash = GENESIS
            expected_seq = 1
            seen_seq: set[int] = set()
            for ev in events:
                seq = ev["sequence"]
                if seq in seen_seq:
                    errors.append(f"{rid}: duplicate sequence {seq}")
                seen_seq.add(seq)
                if seq != expected_seq:
                    errors.append(f"{rid}: sequence gap or reorder expected {expected_seq} got {seq}")
                if ev.get("previous_hash") != prev_hash:
                    errors.append(f"{rid}: wrong previous_hash at seq {seq}")
                ph = payload_hash(ev["payload"])
                if ev.get("payload_hash") != ph:
                    errors.append(f"{rid}: payload_hash mismatch at seq {seq}")
                body = event_body_hash(ev)
                prev_hash = body
                expected_seq = seq + 1
        return len(errors) == 0, errors

    def append(
        self,
        event: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        with _LOCK:
            if idempotency_key and idempotency_key in self._idempotency:
                return self._idempotency[idempotency_key]

            run_id = event["run_id"]
            latest_seq, prev_hash = self._scan_run_tail(run_id)
            seq = latest_seq + 1

            payload = event["payload"]
            envelope: dict[str, Any] = {
                "event_id": event.get("event_id") or str(uuid.uuid4()),
                "run_id": run_id,
                "sequence": seq,
                "timestamp": event.get("timestamp")
                or datetime.now(timezone.utc).isoformat(),
                "actor": event.get("actor", "host"),
                "schema_version": event.get("schema_version", "1.0.0"),
                "event_type": event["event_type"],
                "payload": payload,
                "payload_hash": payload_hash(payload),
                "previous_hash": prev_hash,
            }
            if idempotency_key:
                envelope["idempotency_key"] = idempotency_key

            line = json.dumps(envelope, sort_keys=True) + "\n"
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                if self.fsync:
                    os.fsync(f.fileno())

            if idempotency_key:
                self._idempotency[idempotency_key] = envelope
            return envelope

    def export_bundle(
        self,
        run_id: str,
        redact_keys: frozenset[str] | None = None,
    ) -> dict[str, Any]:
        redact = redact_keys or frozenset()
        events = self.read_by_run(run_id)
        redacted_events: list[dict[str, Any]] = []
        for ev in events:
            copy = json.loads(json.dumps(ev))
            if redact:
                payload = copy.get("payload", {})
                for key in redact:
                    if key in payload:
                        payload[key] = "[REDACTED]"
            redacted_events.append(copy)
        ok, chain_errors = self.verify_chain(run_id)
        return {
            "run_id": run_id,
            "events": redacted_events,
            "chain_ok": ok,
            "chain_errors": chain_errors,
            "redaction_keys": sorted(redact),
        }
