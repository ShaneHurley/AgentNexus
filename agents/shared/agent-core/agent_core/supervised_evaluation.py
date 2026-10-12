"""Explicit subscription-only evaluation through the public supervised CLI."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import sqlite3

from .context_runtime import VARIANTS
from .contracts import ContractDenied
from .evaluation_io import write_report


def native_metrics(repository, run_id):
    """Read existing receipts; missing or uncertain measurements stay unknown."""
    database = Path(repository) / "agents/coding/daily-coder-ecosystem/.daily-coder/state.sqlite"
    if not database.is_file() or not run_id:
        return {"reported_tokens": None, "cached_tokens": None, "tool_calls": None, "repairs": None}
    artifact_root = database.parent / "artifacts" / run_id
    counts = []
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        rows = connection.execute("SELECT hash,path FROM artifacts WHERE run_id=? AND kind='provider_usage'", (run_id,)).fetchall()
        tool_calls = connection.execute("SELECT count(*) FROM tool_calls WHERE run_id=?", (run_id,)).fetchone()[0]
        denied = connection.execute("SELECT count(*) FROM tool_calls WHERE run_id=? AND decision!='allow'", (run_id,)).fetchone()[0]
        repairs = connection.execute("SELECT count(*) FROM invocations WHERE run_id=? AND idem_key LIKE '%:retry%'", (run_id,)).fetchone()[0]
        unknown = connection.execute("SELECT count(*) FROM invocations WHERE run_id=? AND status='remote_outcome_unknown'", (run_id,)).fetchone()[0]
        unresolved = connection.execute("SELECT count(*) FROM budget_reservations WHERE run_id=? AND (state='reserved' OR (state='settled' AND NOT EXISTS (SELECT 1 FROM invocations WHERE invocations.idem_key=budget_reservations.reservation_id)))", (run_id,)).fetchone()[0]
    for content_hash, filename in rows:
        path = Path(filename)
        if not path.is_relative_to(artifact_root) or any(p.is_symlink() for p in (path, *path.parents)):
            raise ContractDenied("usage artifact outside run evidence boundary")
        envelope = json.loads(_load(path))
        canonical = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        if hashlib.sha256(canonical.encode()).hexdigest() != content_hash:
            raise ContractDenied("usage artifact integrity mismatch")
        counts.append(envelope["payload"])
    def valid(value): return type(value) is int and value >= 0
    complete_counts = counts and all(valid(row.get(field)) for row in counts for field in ("input_tokens", "output_tokens"))
    known = sum(row[field] for row in counts for field in ("input_tokens", "output_tokens") if valid(row.get(field)))
    return {"reported_tokens": known if not unknown and not unresolved and complete_counts else None, "known_reported_tokens": known,
            "cached_tokens": sum(row["cached_tokens"] for row in counts) if counts and all(valid(row.get("cached_tokens")) for row in counts) else None,
            "tool_calls": tool_calls, "denied_tool_calls": denied, "repairs": repairs,
            "unknown_invocations": unknown, "unresolved_reservations": unresolved, "provider_calls_with_receipts": len(counts)}


def _load(path, limit=2_000_000):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("evaluation input symlink denied")
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("evaluation input exceeds bound")
    return raw


def run_suite(repository, path, *, variant="baseline", repetitions=3):
    if variant not in VARIANTS or type(repetitions) is not int or not 1 <= repetitions <= 3:
        raise ValueError("unsupported evaluation variant or repetitions")
    raw = _load(path)
    suite = json.loads(raw)
    if not isinstance(suite, dict) or set(suite) != {"version", "id", "cases"} or suite["version"] != 1:
        raise ValueError("unsupported supervised suite")
    cases = suite["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= 10:
        raise ValueError("bounded case array required")
    required = {"id", "profile", "workspace", "request_file", "request_sha256", "token_limit", "expected_status"}
    frozen_requests = {}
    for case in cases:
        if not isinstance(case, dict) or (not required <= set(case) or set(case)-required-{"reference_documents"}):
            raise ValueError("unsupported evaluation case")
        if case["profile"] not in {"Code", "Research"} or type(case["token_limit"]) is not int or not 1 <= case["token_limit"] <= 1_000_000:
            raise ValueError("invalid evaluation scope or token ceiling")
        if case["expected_status"] not in {"WAITING_HUMAN", "COMPLETE"}:
            raise ValueError("evaluation requires an acceptance state")
        request_bytes = _load(case["request_file"])
        request_bytes.decode("utf-8")
        if hashlib.sha256(request_bytes).hexdigest() != case["request_sha256"]:
            raise ValueError("request changed from frozen suite")
        frozen_requests[case["id"]] = request_bytes
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("duplicate evaluation case")
    repository = Path(repository).resolve()
    directory = repository / ".agentnexus" / "evaluations" / str(uuid.uuid4())
    directory.mkdir(parents=True)
    request_paths = {}
    for case in cases:
        destination = directory / (case["request_sha256"] + ".request.txt")
        if destination.exists():
            if _load(destination) != frozen_requests[case["id"]]:
                raise ValueError("frozen request hash collision")
        else:
            destination.write_bytes(frozen_requests[case["id"]])
            destination.chmod(0o400)
        request_paths[case["id"]] = destination
    state = directory / "state"
    command = [sys.executable, "-m", "agent_core.nexus_cli", "--repository", str(repository), "--state-dir", str(state)]
    results = []

    def public(arguments):
        # No shell, raw credentials, provider switching, or automatic approval.
        child = subprocess.Popen(command + arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 start_new_session=True)
        try:
            stdout, stderr = child.communicate(timeout=1800)
        except BaseException:
            import signal
            os.killpg(child.pid, signal.SIGTERM)
            try: child.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.communicate()
            raise
        try:
            result = json.loads(stdout)
        except (ValueError, UnicodeError):
            raise ValueError("public CLI did not return one structured result") from None
        if not isinstance(result, dict):
            raise ValueError("public CLI result must be an object")
        return result, child.returncode

    # Alternate profiles per repetition; they never receive each other's answers.
    for repetition in range(repetitions):
        for case in cases:
            if case["profile"] == "Research":
                results.append({"case_id": case["id"], "repetition": repetition + 1, "passed": False,
                                "status": "BLOCKED", "reason": "RF Wave 1 has no supervised Codex investigation adapter",
                                "model_calls": 0, "total_tokens": None})
                continue
            session, code = public(["new", "--project", case["workspace"], "--profile", case["profile"]])
            if code: raise ContractDenied("public session creation failed")
            start = time.monotonic()
            result, code = public(["run", "--session", session["session_id"], "--engine", "daily-coder",
                                   "--workspace", case["workspace"], "--request-file", str(request_paths[case["id"]]),
                                   "--provider", "codex_cli", "--live", "--budget-usd", "0",
                                   "--token-limit", str(case["token_limit"]), "--context-variant", variant,
                                   "--context-evaluation", *[value for reference in case.get("reference_documents",[]) for value in ("--reference-document",reference)]])
            accounting = result.get("accounting", {})
            snapshot = result.get("snapshot", {})
            actual_request = result.get("request")
            request_matches = isinstance(actual_request, str) and hashlib.sha256(actual_request.encode()).hexdigest() == case["request_sha256"]
            waiting = result.get("status") == "WAITING_HUMAN"
            measured = {"case_id": case["id"], "repetition": repetition + 1,
                        "passed": result.get("status") == case["expected_status"] and request_matches,
                        "task_complete": result.get("status") == "COMPLETE", "status": result.get("status", "BLOCKED"),
                        "run_id": result.get("run_id"), "session_id": session["session_id"],
                        "elapsed_seconds": round(time.monotonic() - start, 3), "exit_code": code,
                        "request_hash": case["request_sha256"], "source_hashes": snapshot.get("source_hashes", {}),
                        "request_pin_matches": request_matches,
                        "configuration_hash": snapshot.get("codex_configuration_hash"),
                        "context_policy_hash": snapshot.get("context_policy_hash"),
                        "total_tokens": accounting.get("tokens") if accounting.get("usage_status") != "unknown" else None,
                        "usage_status": accounting.get("usage_status", "unknown"), "total_cost_usd": accounting.get("total_cost_usd"),
                        "known_api_cash_usd": accounting.get("known_api_cash_usd"),
                        "pending_approvals": result.get("pending_approvals", []),
                        "artifacts": [row.get("artifact_id", row.get("id")) for row in result.get("artifacts", [])]}
            results.append(measured)
            measured.update(native_metrics(repository, result.get("run_id")))
            # Persist evidence before stopping at a gate. Human approval never
            # expires and no subsequent repetition may replay this task's writes.
            report = {"schema_version": 1, "mode": "supervised", "suite_id": suite["id"],
                      "suite_hash": hashlib.sha256(raw).hexdigest(), "variant": variant,
                      "results": results, "state_directory": str(state), "ok": False,
                      "qualification": "not_evaluated", "paused_for_approval": waiting}
            write_report(directory / "report.json", report)
            if waiting:
                report["ok"] = measured["passed"]
                write_report(directory / "report.json", report)
                return report
    report = {"schema_version": 1, "mode": "supervised", "suite_id": suite["id"],
              "suite_hash": hashlib.sha256(raw).hexdigest(), "variant": variant, "results": results,
              "state_directory": str(state), "ok": all(row["passed"] for row in results),
              "qualification": "not_evaluated", "paused_for_approval": False}
    write_report(directory / "report.json", report)
    return report
