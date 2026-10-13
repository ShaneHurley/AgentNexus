from argparse import Namespace
from unittest.mock import Mock, patch
import pytest
from ide_bridge.supervised import execute, add_options
import argparse

def test_task_policy_options_parse_with_explicit_repository(tmp_path):
    parser=argparse.ArgumentParser(); add_options(parser)
    args=parser.parse_args(["--execution-policy","coder-v1","--approval-mode","task","--task-contract",str(tmp_path/"contract.json"),"--repository",str(tmp_path)])
    assert args.execution_policy=="coder-v1" and args.approval_mode=="task"
    assert args.task_contract==tmp_path/"contract.json" and args.repository==tmp_path

@pytest.mark.parametrize("key",["execution_policy","approval_mode","task_contract"])
def test_resume_cannot_change_task_authority(key):
    args=Namespace(token_limit=None,deadline_seconds=None,execution_policy=None,approval_mode=None,task_contract=None)
    setattr(args,key,"changed")
    with pytest.raises(ValueError,match="pinned"):
        execute(args,"daily-coder",resume=True)

def test_supervisor_receives_exact_task_contract(tmp_path):
    import json
    path=tmp_path/"contract.json"; contract={"task":"test"}; path.write_text(json.dumps(contract))
    args=Namespace(supervisor_dir=str(tmp_path/"state"),repository=tmp_path,repo=str(tmp_path),session_id="session",request="fix",live=False,provider="mock",token_limit=99,deadline_seconds=None,execution_policy="coder-v1",approval_mode="task",task_contract=path)
    with patch("agent_core.supervisor.Supervisor") as service:
        instance=service.return_value
        instance.create_run.return_value={"run_id":"run"}
        instance.execute.return_value={"status":"SIMULATED","live":False}
        assert execute(args,"daily-coder")==1
        forwarded=instance.create_run.call_args.kwargs
        assert forwarded["task_contract"]==contract
        assert forwarded["execution_policy"]=="coder-v1" and forwarded["approval_mode"]=="task"
        service.assert_called_once_with((tmp_path/"state").resolve(),repository=tmp_path)
