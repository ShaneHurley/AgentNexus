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

def test_reconcile_read_prints_actual_result_and_exit_status(monkeypatch,capsys):
    import agent_core.nexus_cli as module
    class FakeSupervisor:
        def __init__(self,*args): pass
        def reconcile_read(self,*args,**kwargs):
            return {"status":"CANCELLED","read_reconciliation":{"acknowledged":True}}
    monkeypatch.setattr(module,"Supervisor",FakeSupervisor)
    assert module.main(["reconcile-read","run","--operation-id","read","--actor","operator","--ack-result-unavailable"])==0
    assert json.loads(capsys.readouterr().out)["read_reconciliation"]["acknowledged"]

def test_reconcile_read_denial_is_controlled(monkeypatch,capsys):
    import agent_core.nexus_cli as module
    from agent_core.contracts import ContractDenied
    class FakeSupervisor:
        def __init__(self,*args): pass
        def reconcile_read(self,*args,**kwargs): raise ContractDenied("unknown effect cannot be reconciled as read")
    monkeypatch.setattr(module,"Supervisor",FakeSupervisor)
    assert module.main(["reconcile-read","run","--operation-id","write","--actor","operator","--ack-result-unavailable"])==3
    assert json.loads(capsys.readouterr().out)["error"]=="ContractDenied"
