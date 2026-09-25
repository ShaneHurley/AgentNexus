"""Typed experiment kind runners (stdlib only, no shell)."""

from __future__ import annotations

import csv
import json
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


def _tail(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def run_dataset_profile(data_path: Path, *, raw_tail: int = 4000) -> dict[str, Any]:
    t0 = time.perf_counter()
    rows: list[dict[str, Any]] = []
    columns: list[str] = []
    if data_path.suffix.lower() == ".jsonl":
        with data_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if isinstance(obj, dict):
                    rows.append(obj)
        if rows:
            columns = sorted({k for r in rows for k in r})
    else:
        with data_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            columns = list(reader.fieldnames or [])
            rows = list(reader)

    missing: dict[str, int] = {c: 0 for c in columns}
    numeric: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        for c in columns:
            val = row.get(c, "")
            if val is None or str(val).strip() == "":
                missing[c] = missing.get(c, 0) + 1
                continue
            try:
                numeric[c].append(float(val))
            except (TypeError, ValueError):
                pass

    summaries: dict[str, Any] = {}
    for c, vals in numeric.items():
        if vals:
            summaries[c] = {
                "count": len(vals),
                "min": min(vals),
                "max": max(vals),
                "mean": statistics.fmean(vals),
            }

    metrics = {
        "row_count": len(rows),
        "columns": columns,
        "missing": missing,
        "numeric_summaries": summaries,
    }
    duration = time.perf_counter() - t0
    # metrics already structured in result; avoid duplicating into raw_stdout_tail
    _ = raw_tail
    return {
        "exit_code": 0,
        "duration_seconds": duration,
        "metrics": metrics,
        "raw_stdout_tail": "",
        "raw_stderr_tail": "",
    }


def run_group_comparison(
    data_path: Path,
    *,
    group_column: str,
    metric_column: str,
    min_group_n: int = 2,
    raw_tail: int = 4000,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    with data_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        g = str(row.get(group_column, "")).strip()
        raw = row.get(metric_column, "")
        if not g or raw is None or str(raw).strip() == "":
            continue
        try:
            groups[g].append(float(raw))
        except (TypeError, ValueError):
            continue

    means = {g: statistics.fmean(vals) for g, vals in groups.items() if vals}
    counts = {g: len(vals) for g, vals in groups.items()}
    usable = {g: n for g, n in counts.items() if n >= min_group_n}
    inconclusive = len(usable) < 2

    metrics: dict[str, Any] = {
        "group_means": means,
        "group_counts": counts,
        "usable_groups": sorted(usable),
        "inconclusive": inconclusive,
        "largest_mean_group": max(means, key=means.get) if means else None,
    }
    duration = time.perf_counter() - t0
    _ = raw_tail
    return {
        "exit_code": 0,
        "duration_seconds": duration,
        "metrics": metrics,
        "raw_stdout_tail": "",
        "raw_stderr_tail": "",
    }


def run_python_unittest_benchmark(
    start_dir: Path,
    *,
    repetitions: int = 1,
    raw_tail: int = 4000,
) -> dict[str, Any]:
    """Run unittest discovery via argv list (no shell).

    Set ``RF_EXPERIMENT_SANDBOX=docker`` to wrap discovery in
    ``docker run --rm --network=none`` (REC-04 experiment). Default remains
    in-process subprocess and is **not** a secure sandbox.
    """
    import os

    durations: list[float] = []
    last_out = ""
    last_err = ""
    exit_code = 0
    sandbox = (os.environ.get("RF_EXPERIMENT_SANDBOX") or "").strip().lower()
    start_dir = start_dir.resolve()
    for _ in range(repetitions):
        t0 = time.perf_counter()
        if sandbox == "docker":
            cmd = [
                "docker",
                "run",
                "--rm",
                "--network=none",
                "-v",
                f"{start_dir}:/work:ro",
                "-w",
                "/work",
                "python:3.11-slim",
                "python",
                "-m",
                "unittest",
                "discover",
                "-s",
                "/work",
                "-q",
            ]
        else:
            cmd = [sys.executable, "-m", "unittest", "discover", "-s", str(start_dir), "-q"]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        durations.append(time.perf_counter() - t0)
        last_out = proc.stdout or ""
        last_err = proc.stderr or ""
        exit_code = proc.returncode
        if exit_code != 0:
            break

    metrics = {
        "repetitions_run": len(durations),
        "durations_seconds": durations,
        "mean_duration_seconds": statistics.fmean(durations) if durations else 0.0,
        "start_dir": str(start_dir),
        "sandbox_mode": sandbox or "in_process",
        "sandbox_warning": (
            "docker_network_none" if sandbox == "docker" else "not_a_secure_sandbox"
        ),
    }
    return {
        "exit_code": exit_code,
        "duration_seconds": sum(durations),
        "metrics": metrics,
        "raw_stdout_tail": _tail(last_out, raw_tail),
        "raw_stderr_tail": _tail(last_err, raw_tail),
    }
