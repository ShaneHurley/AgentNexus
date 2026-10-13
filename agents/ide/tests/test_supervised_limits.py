import argparse
from argparse import Namespace
from unittest.mock import patch
import pytest
from ide_bridge import daily_coder, research_forge
from ide_bridge.supervised import add_options,execute

@pytest.mark.parametrize("flag,value",[("--token-limit","0"),("--token-limit","-1"),("--token-limit","1.2"),("--deadline-seconds","0"),("--deadline-seconds","-1"),("--deadline-seconds","nan"),("--deadline-seconds","inf")])
def test_invalid_cli_limits_rejected(flag,value):
    parser=argparse.ArgumentParser()
    add_options(parser)
    with pytest.raises(SystemExit): parser.parse_args([flag,value])

@pytest.mark.parametrize("limit,seconds,expected",[(None,None,80000),(221411,1800.0,221411)])
def test_supervisor_forwards_limits_once(tmp_path,capsys,limit,seconds,expected):
    args=Namespace(supervisor_dir=str(tmp_path/"state"),repo=str(tmp_path),session_id="existing",request="contained task",live=False,mark_simulated=True,token_limit=limit,deadline_seconds=seconds)
    with patch("agent_core.supervisor.Supervisor") as Service,patch("ide_bridge.supervised.time.time",return_value=1000):
        service=Service.return_value
        service.create_run.return_value={"run_id":"run"}
        service.execute.return_value={"status":"SIMULATED","live":False}
        assert execute(args,"daily-coder")==1
        service.create_run.assert_called_once_with("existing","daily-coder","contained task",str(tmp_path.resolve()),live=False,provider="mock",limit_tokens=expected,deadline=None if seconds is None else 2800.0)
        service.execute.assert_called_once_with("run")
        service.new_session.assert_not_called()

@pytest.mark.parametrize("module",[daily_coder,research_forge])
@pytest.mark.parametrize("field,value",[("token_limit",1),("deadline_seconds",1.0)])
def test_native_limits_are_not_silently_ignored(module,field,value):
    args=Namespace(supervisor_dir=None,token_limit=None,deadline_seconds=None)
    setattr(args,field,value)
    with pytest.raises(ValueError,match="supervisor"): module.cmd_run(args)
    with pytest.raises(ValueError,match="pinned"): module.cmd_resume(args)

def test_resume_cannot_amend_pinned_limits():
    args=Namespace(supervisor_dir="/tmp/state",token_limit=1,deadline_seconds=None)
    with pytest.raises(ValueError,match="pinned"): execute(args,"daily-coder",resume=True)
