"""Wave 1 baseline protocol and runner (RF-W1-J)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research_forge.wave1.orchestrator import Wave1Orchestrator


def load_baseline_tasks(repo_root: Path) -> list[dict[str, Any]]:
    path = repo_root / "baseline" / "tasks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    tasks = data.get("tasks") or []
    if len(tasks) < 25:
        raise ValueError(f"baseline requires >=25 tasks, got {len(tasks)}")
    return tasks


def run_baseline_mock(repo_root: Path) -> dict[str, Any]:
    tasks = load_baseline_tasks(repo_root)
    orch = Wave1Orchestrator(repo_root, live=False)
    results: list[dict[str, Any]] = []
    passed = 0
    for task in tasks:
        req = task["request"]
        web_docs = task.get("web_docs") or {}
        if web_docs:
            orch = Wave1Orchestrator(repo_root, live=False, web_docs=_decode_docs(web_docs))
        out = orch.run(req, clarification_answers=task.get("clarification_answers"))
        ok = bool(out.get("ok")) and not out.get("paused")
        if ok and task.get("expect_report_hash"):
            ok = out.get("report_hash") == task["expect_report_hash"]
        if ok:
            passed += 1
        results.append(
            {
                "task_id": task["task_id"],
                "ok": ok,
                "report_hash": out.get("report_hash"),
                "checks": task.get("checks", []),
            }
        )
    return {
        "protocol_version": "1.0.0",
        "mode": "mock",
        "task_count": len(tasks),
        "passed": passed,
        "pass_rate": passed / len(tasks),
        "results": results,
        "comparison_targets": {
            "min_pass_rate": 0.8,
            "wave2_uses_same_tasks": True,
        },
    }


def run_baseline_live_report(repo_root: Path) -> dict[str, Any]:
    """Live baseline is fail-closed unless gate passes; returns blocked report."""
    from research_forge.wave1.live_gate import build_live_contract, validate_live_contract
    from research_forge.settings import load_settings

    settings = load_settings(repo_root)
    contract = build_live_contract(
        cli_live=True,
        settings=settings,
        approval_record_id=None,
    )
    ok, msgs, err = validate_live_contract(repo_root, contract)
    return {
        "protocol_version": "1.0.0",
        "mode": "live",
        "blocked": not ok,
        "messages": msgs,
        "error": err,
    }


def _decode_docs(raw: dict[str, str]) -> dict[str, bytes]:
    return {url: text.encode("utf-8") for url, text in raw.items()}
