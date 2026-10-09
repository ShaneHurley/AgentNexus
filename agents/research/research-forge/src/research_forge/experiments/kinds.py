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


def run_python_unittest_benchmark(start_dir: Path, *, repetitions: int = 1, raw_tail: int = 4000, image: str | None = None) -> dict[str, Any]:
    """Arbitrary Python executes only inside a reviewed, digest-pinned worker."""
    from agent_core.isolation import DockerRunner, IsolationUnavailable
    if not image: raise IsolationUnavailable("code experiments require a reviewed isolated_image")
    if not 1 <= repetitions <= 10: raise ValueError("experiment repetitions exceed ceiling")
    runner = DockerRunner(image,start_dir)
    durations=[]; last={"returncode":None,"stdout":"","stderr":""}
    for _ in range(repetitions):
        last=runner.run(["python","-m","unittest","discover","-s","/workspace","-q"])
        durations.append(last["duration_s"])
        if last["returncode"] != 0: break
    return {"exit_code":last["returncode"] if last["returncode"] is not None else 1,
            "duration_seconds":sum(durations),"metrics":{"repetitions_run":len(durations),"durations_seconds":durations,"mean_duration_seconds":statistics.fmean(durations),"sandbox_mode":"docker","sandbox_warning":"digest_pinned_isolated_worker"},
            "raw_stdout_tail":_tail(last["stdout"],raw_tail),"raw_stderr_tail":_tail(last["stderr"],raw_tail)}
