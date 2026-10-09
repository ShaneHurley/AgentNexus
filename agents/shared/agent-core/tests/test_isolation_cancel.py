import subprocess
import sys
import time
from unittest.mock import patch
import pytest
from agent_core.isolation import DockerRunner
from agent_core.lifecycle import ReconciliationRequired


def test_cancel_stops_actual_client_process_and_confirms_container_removal(tmp_path):
    runner=DockerRunner("python@sha256:"+"a"*64,tmp_path)
    children=[]; original=subprocess.Popen
    def start(*args,**kwargs):
        child=original([sys.executable,"-c","import time; time.sleep(60)"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        children.append(child); return child
    def docker(command,**kwargs):
        return subprocess.CompletedProcess(command,0,"container123" if "create" in command else "","")
    with patch("agent_core.isolation.shutil.which",return_value="docker"), patch("agent_core.isolation.subprocess.run",side_effect=docker), patch("agent_core.isolation.subprocess.Popen",side_effect=start):
        try:
            result=runner.run(["python","-V"],cancel_check=lambda:bool(children))
            assert result["cancelled"] and result["cancellation_confirmed"]
            assert children[0].poll() is not None
        finally:
            for child in children:
                if child.poll() is None: child.kill(); child.wait(timeout=5)


def test_unconfirmed_container_removal_is_reconciliation(tmp_path):
    runner=DockerRunner("python@sha256:"+"a"*64,tmp_path)
    calls=0
    def cancel():
        nonlocal calls
        calls+=1
        return calls > 1
    def docker(command,**kwargs):
        return subprocess.CompletedProcess(command,1 if "rm" in command else 0,"container123" if "create" in command else "","")
    with patch("agent_core.isolation.shutil.which",return_value="docker"),patch("agent_core.isolation.subprocess.run",side_effect=docker):
        with pytest.raises(ReconciliationRequired,match="termination unconfirmed"):
            runner.run(["python","-V"],cancel_check=cancel)
