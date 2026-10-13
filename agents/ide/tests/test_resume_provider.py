from argparse import Namespace
from unittest.mock import patch
import pytest
from ide_bridge.daily_coder import cmd_resume

def test_supervised_resume_rejects_command_provider_override():
    args=Namespace(supervisor_dir="/tmp/state",provider_command="operator command",token_limit=None,deadline_seconds=None)
    with pytest.raises(ValueError,match="native"):
        cmd_resume(args)

def test_native_resume_forwards_command_provider():
    args=Namespace(supervisor_dir=None,provider_command="operator command",provider="command",run_id="run",live=True,cwd=".")
    with patch("ide_bridge.daily_coder._run_dc",return_value=2) as execute:
        assert cmd_resume(args)==2
        execute.assert_called_once_with(["resume","run","--provider","command","--provider-command","operator command","--live"],cwd=".",mark_simulated=False)
