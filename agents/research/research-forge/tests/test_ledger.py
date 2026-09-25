from __future__ import annotations

import json
import threading
from pathlib import Path

from research_forge.ledger import JsonlLedger, reconstruct_run_state
from research_forge.ledger.resume import can_resume
from research_forge.versions import MANIFEST


def _append_manifest(ledger: JsonlLedger, run_id: str) -> None:
    ledger.append(
        {
            "run_id": run_id,
            "event_type": "run_manifest",
            "payload": {
                "charter_hash": "sha256:c",
                "policy_version": MANIFEST.policy,
                "schema_version": MANIFEST.schema_version,
                "phase": "init",
            },
        }
    )


def test_append_and_verify_chain(tmp_path: Path) -> None:
    ledger = JsonlLedger(tmp_path / "l.jsonl")
    run_id = "r1"
    _append_manifest(ledger, run_id)
    ok, errs = ledger.verify_chain(run_id)
    assert ok, errs


def test_multi_append_preserves_chain(tmp_path: Path) -> None:
    """Same-instance multi-append keeps a valid hash chain."""
    ledger = JsonlLedger(tmp_path / "l.jsonl", fsync=False)
    run_id = "r-multi"
    for i in range(5):
        ledger.append(
            {
                "run_id": run_id,
                "event_type": "audit",
                "payload": {"i": i},
            }
        )
    assert ledger.latest_sequence(run_id) == 5
    ok, errs = ledger.verify_chain(run_id)
    assert ok, errs
    ledger2 = JsonlLedger(tmp_path / "l.jsonl", fsync=False)
    ok2, errs2 = ledger2.verify_chain(run_id)
    assert ok2, errs2
    assert ledger2.latest_sequence(run_id) == 5


def test_stale_instance_after_external_append(tmp_path: Path) -> None:
    """Instance A must stay correct after instance B writes to the same file."""
    path = tmp_path / "l.jsonl"
    a = JsonlLedger(path, fsync=False)
    b = JsonlLedger(path, fsync=False)
    run_id = "r-stale"
    a.append({"run_id": run_id, "event_type": "audit", "payload": {"n": 1}})
    b.append({"run_id": run_id, "event_type": "audit", "payload": {"n": 2}})
    a.append({"run_id": run_id, "event_type": "audit", "payload": {"n": 3}})
    ok, errs = JsonlLedger(path, fsync=False).verify_chain(run_id)
    assert ok, errs
    seqs = [json.loads(line)["sequence"] for line in path.read_text(encoding="utf-8").strip().splitlines()]
    assert seqs == [1, 2, 3]


def test_idempotency(tmp_path: Path) -> None:
    ledger = JsonlLedger(tmp_path / "l.jsonl")
    run_id = "r1"
    ev = {
        "run_id": run_id,
        "event_type": "audit",
        "payload": {"k": 1},
    }
    a = ledger.append(ev, idempotency_key="idem-1")
    b = ledger.append(ev, idempotency_key="idem-1")
    assert a["event_id"] == b["event_id"]
    assert ledger.latest_sequence(run_id) == 1


def test_tamper_payload_detected(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    ledger = JsonlLedger(path)
    run_id = "r1"
    _append_manifest(ledger, run_id)
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    ev = json.loads(lines[0])
    ev["payload"]["charter_hash"] = "tampered"
    path.write_text(json.dumps(ev) + "\n", encoding="utf-8")
    ok, errs = ledger.verify_chain(run_id)
    assert not ok
    assert errs


def test_reconstruct_matches_golden(tmp_path: Path) -> None:
    ledger = JsonlLedger(tmp_path / "l.jsonl")
    run_id = "r1"
    _append_manifest(ledger, run_id)
    ledger.append(
        {
            "run_id": run_id,
            "event_type": "budget_debit",
            "payload": {"amount_usd": 1.25},
        }
    )
    state = reconstruct_run_state(ledger.read_by_run(run_id))
    assert state["budget_spent_usd"] == 1.25
    assert state["charter_hash"] == "sha256:c"


def test_resume_plan_stale_on_mismatch(tmp_path: Path) -> None:
    state = {
        "phase": "discovering",
        "charter_hash": "sha256:c",
        "policy_version": MANIFEST.policy,
        "schema_version": MANIFEST.schema_version,
    }
    err = can_resume(
        state,
        expected_charter_hash="sha256:other",
        expected_policy_version=MANIFEST.policy,
        expected_schema_version=MANIFEST.schema_version,
    )
    assert err is not None
    assert err.code.value == "PLAN_STALE"


def test_concurrent_append(tmp_path: Path) -> None:
    ledger = JsonlLedger(tmp_path / "l.jsonl")
    run_id = "r1"
    errors: list[Exception] = []

    def worker(n: int) -> None:
        try:
            ledger.append(
                {
                    "run_id": run_id,
                    "event_type": "audit",
                    "payload": {"n": n},
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    ok, _ = ledger.verify_chain(run_id)
    assert ok
    assert ledger.latest_sequence(run_id) == 5


def test_export_redaction(tmp_path: Path) -> None:
    ledger = JsonlLedger(tmp_path / "l.jsonl")
    run_id = "r1"
    ledger.append(
        {
            "run_id": run_id,
            "event_type": "audit",
            "payload": {"secret": "x", "public": "y"},
        }
    )
    bundle = ledger.export_bundle(run_id, redact_keys=frozenset({"secret"}))
    payload = bundle["events"][0]["payload"]
    assert payload["secret"] == "[REDACTED]"
    assert payload["public"] == "y"
