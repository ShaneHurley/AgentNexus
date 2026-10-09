import importlib.util
import json
import pytest


def main():
    assert importlib.util.find_spec("agent_core.nexus_cli") is not None, "unified CLI missing"
    from agent_core.nexus_cli import main
    return main


def test_cli_creates_and_lists_persistent_identity(tmp_path, capsys):
    cli=main()
    assert cli(["--state-dir",str(tmp_path),"new","--identity","daily-user","--project",str(tmp_path)]) == 0
    created=json.loads(capsys.readouterr().out)
    assert cli(["--state-dir",str(tmp_path),"sessions"]) == 0
    sessions=json.loads(capsys.readouterr().out)
    assert sessions[0]["session_id"] == created["session_id"]
    assert sessions[0]["identity"] == "daily-user"


def test_cli_denies_unknown_resume_without_dispatch(tmp_path,capsys):
    cli=main()
    assert cli(["--state-dir",str(tmp_path),"resume","missing-id"]) == 3
    result=json.loads(capsys.readouterr().out)
    assert result["ok"] is False
