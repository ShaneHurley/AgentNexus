from __future__ import annotations

import json

from typer.testing import CliRunner

from research_forge.cli import app
from research_forge.wave0.integration import run_wave0_fixture
from research_forge.wave0.replay import replay_bundle

runner = CliRunner()


def test_wave0_fixture_deterministic(repo_root, monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(repo_root)
    a = run_wave0_fixture(repo_root, repo_root / "fixtures" / "wave0_run.json")
    b = run_wave0_fixture(repo_root, repo_root / "fixtures" / "wave0_run.json")
    assert a["state_hash"] == b["state_hash"]
    assert a["chain_ok"]


def test_live_flag_denied(repo_root, monkeypatch) -> None:
    monkeypatch.chdir(repo_root)
    result = runner.invoke(app, ["run", "--live"])
    assert result.exit_code == 2


def test_budget_stop_after_exhaustion(repo_root) -> None:
    from research_forge.budget.manager import BudgetManager

    bm = BudgetManager(repo_root / "config" / "budgets.yaml")
    bm.start("S")
    limit = bm.state.limit_usd  # type: ignore[union-attr]
    bm.debit(limit * 0.95)
    err = bm.reserve(1.0)
    assert err is not None
    assert bm.state.hard_stopped  # type: ignore[union-attr]


def test_replay_bundle(tmp_path, repo_root) -> None:
    from research_forge.ledger import JsonlLedger

    ledger = JsonlLedger(tmp_path / "l.jsonl")
    run_id = "wave0-fixture-run"
    ledger.append(
        {
            "run_id": run_id,
            "event_type": "run_manifest",
            "payload": {"charter_hash": "c", "phase": "init"},
        }
    )
    bundle = ledger.export_bundle(run_id)
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    result = replay_bundle(repo_root, path)
    assert result["ok"]
