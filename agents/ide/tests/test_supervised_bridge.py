from argparse import Namespace
from unittest.mock import patch
from ide_bridge import research_forge


def test_mock_resume_maps_same_as_mock_run():
    args = Namespace(run_id="run-1", answer=[], live=False, cwd=".", mark_simulated=True)
    with patch.object(research_forge, "which", return_value="research-forge"), patch.object(research_forge, "run_command", return_value=0):
        assert research_forge.cmd_resume(args) == 1
        args.mark_simulated = False
        assert research_forge.cmd_resume(args) == 0
        args.live = True
        assert research_forge.cmd_resume(args) == 0


def test_supervised_bridge_delegates_run_and_resume_to_same_boundary():
    args = Namespace(supervisor_dir="/tmp/supervisor", dry_run=False)
    with patch("ide_bridge.supervised.execute", return_value=3) as execute:
        assert research_forge.cmd_run(args) == 3
        execute.assert_called_once_with(args, "research-forge")
        execute.reset_mock()
        assert research_forge.cmd_resume(args) == 3
        execute.assert_called_once_with(args, "research-forge", resume=True)


def test_real_supervised_rf_bridge_persists_shared_status(tmp_path, capsys):
    import json
    from agent_core.supervisor import Supervisor
    from ide_bridge.supervised import execute
    args = Namespace(supervisor_dir=str(tmp_path / "supervisor"),
                     cwd=str(tmp_path), session_id=None,
                     request=json.dumps({"topic": "bounded research"}), live=False,
                     mark_simulated=True)
    assert execute(args, "research-forge") == 3
    row = json.loads(capsys.readouterr().out)
    assert row["status"] == "WAITING_HUMAN"
    assert Supervisor(args.supervisor_dir).status(row["legacy_id"])["run_id"] == row["run_id"]


def test_supervised_live_resume_uses_persisted_live_pin(capsys):
    from ide_bridge.supervised import execute
    args=Namespace(supervisor_dir="/tmp/state",run_id="run",answer=[],live=False,mark_simulated=True)
    with patch("agent_core.supervisor.Supervisor") as service:
        service.return_value.status.return_value={"engine":"daily-coder"}
        service.return_value.execute.return_value={"status":"COMPLETE","live":True}
        assert execute(args,"daily-coder",resume=True)==0
