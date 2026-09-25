from __future__ import annotations

from pathlib import Path

from research_forge.wave1.baseline import load_baseline_tasks, run_baseline_live_report, run_baseline_mock


def test_baseline_task_count(repo_root: Path) -> None:
    tasks = load_baseline_tasks(repo_root)
    assert len(tasks) >= 25


def test_baseline_mock_runs(repo_root: Path) -> None:
    report = run_baseline_mock(repo_root)
    assert report["task_count"] >= 25
    assert report["pass_rate"] >= 0.8


def test_baseline_live_blocked(repo_root: Path) -> None:
    live = run_baseline_live_report(repo_root)
    assert live["blocked"] is True
