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
    with patch("agent_core.supervisor.Supervisor") as service, patch("agent_core.coder_capacity.announce_capacity") as announce:
        instance=service.return_value
        instance.create_run.return_value={"run_id":"run","snapshot":{"execution_policy":"coder-v1"}}
        instance.execute.return_value={"status":"SIMULATED","live":False}
        assert execute(args,"daily-coder")==1
        announce.assert_called_once_with(instance,"run")
        forwarded=instance.create_run.call_args.kwargs
        assert forwarded["task_contract"]==contract
        assert forwarded["execution_policy"]=="coder-v1" and forwarded["approval_mode"]=="task"
        service.assert_called_once_with((tmp_path/"state").resolve(),repository=tmp_path)

@pytest.mark.parametrize("resume",[False,True])
@pytest.mark.parametrize("policy",["legacy","coder-v1"])
def test_bridge_capacity_notice_precedes_only_coder_dispatch(tmp_path,resume,policy):
    args=Namespace(supervisor_dir=str(tmp_path/"state"),repository=tmp_path,repo=str(tmp_path),
        session_id="session",run_id="run",request="fix",live=False,provider="mock",
        token_limit=None,deadline_seconds=None,execution_policy=None,approval_mode=None,task_contract=None,answer=[])
    events=[]
    with patch("agent_core.supervisor.Supervisor") as service, patch("agent_core.coder_capacity.announce_capacity") as announce:
        instance=service.return_value
        row={"run_id":"run","engine":"daily-coder","snapshot":{"execution_policy":policy}}
        instance.status.return_value=row
        instance.create_run.return_value=row
        announce.side_effect=lambda *args: events.append("capacity")
        def dispatch(*args,**kwargs):
            events.append("execute")
            return {"status":"SIMULATED","live":False}
        instance.execute.side_effect=dispatch
        assert execute(args,"daily-coder",resume=resume)==1
        assert events==(["capacity","execute"] if policy=="coder-v1" else ["execute"])
        if policy=="coder-v1": announce.assert_called_once_with(instance,"run")
        else: announce.assert_not_called()
