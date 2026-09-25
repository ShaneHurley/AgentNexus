from __future__ import annotations

import json

from typer.testing import CliRunner

from research_forge.cli import app
from research_forge.wave1.orchestrator import RunState, Wave1Orchestrator
from research_forge.wave1.persistence import load_run_state, save_run_state, status_payload

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "validate" in result.stdout


def test_validate_wave0(repo_root, monkeypatch) -> None:
    monkeypatch.chdir(repo_root)
    result = runner.invoke(app, ["validate", "--gate", "wave_0"])
    assert result.exit_code == 0
    assert '"ok":true' in result.stdout.replace(" ", "")


def test_doctor(repo_root, monkeypatch) -> None:
    monkeypatch.chdir(repo_root)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0


def test_run_not_implemented_without_fixture(repo_root, monkeypatch) -> None:
    monkeypatch.chdir(repo_root)
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 2


def test_dry_run_no_providers(repo_root, monkeypatch) -> None:
    monkeypatch.chdir(repo_root)
    result = runner.invoke(app, ["run", "--dry-run"])
    assert result.exit_code == 0
    assert "provider_events" in result.stdout
    assert '"provider_events":0' in result.stdout.replace(" ", "")


def test_resume_missing_run_not_found(repo_root, monkeypatch) -> None:
    monkeypatch.chdir(repo_root)
    result = runner.invoke(app, ["resume", "run-deadbeef"])
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["code"] == "NOT_FOUND"
    assert "run-deadbeef" in payload["message"]


def test_status_missing_run_exit_2(repo_root, monkeypatch) -> None:
    monkeypatch.chdir(repo_root)
    result = runner.invoke(app, ["status", "run-deadbeef"])
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["found"] is False


def test_persist_and_cli_resume_status(repo_root, monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(repo_root)
    orch = Wave1Orchestrator(repo_root, live=False)
    req = {"topic": "Redis vs Memcached for sessions"}
    paused = orch.run(req)
    assert paused.get("paused")
    save_run_state(repo_root, paused["state"], live=False)
    run_id = paused["state"]["run_id"]

    st_result = runner.invoke(app, ["status", run_id])
    assert st_result.exit_code == 0
    status = json.loads(st_result.stdout)
    assert status["found"] is True
    assert status["paused"] is True

    result = runner.invoke(
        app,
        [
            "resume",
            run_id,
            "-a",
            "CLQ-001=product decision",
            "-a",
            "CLQ-002=brief",
            "-a",
            "CLQ-003=cost",
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload.get("persisted") is True
    loaded, _ = load_run_state(repo_root, run_id)
    assert loaded.phase == "done"
    assert loaded.paused is False

    listed = status_payload(repo_root, None)
    assert listed["latest"] == run_id


def test_runstate_roundtrip() -> None:
    original = RunState(
        run_id="run-abc",
        phase="clarify",
        request={"topic": "t"},
        paused=True,
        resume_token="pause-1",
    )
    restored = RunState.from_dict(original.to_dict())
    assert restored.to_dict() == original.to_dict()
