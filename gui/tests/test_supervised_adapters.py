from pathlib import Path
import pytest
from unittest.mock import Mock, patch
import tempfile

from agent_dashboard.adapters.research_forge import ResearchForgeAdapter
from agent_dashboard.adapters.daily_coder import DailyCoderAdapter


def test_research_start_executes_shared_run_and_retains_session():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        adapter = ResearchForgeAdapter("research-forge", "RF", "", {"package_root": tmp}, root / "data")
        supervisor = Mock()
        supervisor.new_session.return_value = {"session_id": "session-1"}
        supervisor.create_run.return_value = {"run_id": "shared-1"}
        supervisor.execute.return_value = {"run_id": "shared-1", "status": "WAITING_HUMAN", "engine": "research-forge"}
        with patch.object(adapter._supervisor, "supervisor", return_value=supervisor):
            result = adapter.start_run("bounded research")
            adapter.start_run("another request")
        assert result["run_id"] == "shared-1"
        assert result["status"] == "WAITING_HUMAN"
        assert result["queued"] is False
        assert supervisor.new_session.call_count == 1
        assert supervisor.create_run.call_args.args[0:2] == ("session-1", "research-forge")
        assert supervisor.execute.call_count == 2


def test_supervised_cancellation_never_claims_termination():
    with tempfile.TemporaryDirectory() as tmp:
        adapter = ResearchForgeAdapter("research-forge", "RF", "", {"package_root": tmp}, Path(tmp) / "data")
        supervisor = Mock()
        supervisor.status.return_value = {"run_id": "shared-1", "engine": "research-forge"}
        supervisor.cancel.return_value = {"run_id": "shared-1", "status": "CANCEL_REQUESTED"}
        with patch.object(adapter._supervisor, "supervisor", return_value=supervisor):
            result = adapter.cancel("shared-1")
        assert result["cancellation_requested"]
        assert not result["cancelled"]
        assert not result["acknowledged"]
        supervisor.cancel.assert_called_once_with("shared-1")


def test_daily_approval_uses_native_id_and_policy_authority():
    adapter = DailyCoderAdapter("daily-coder", "DC", "", {"supervised": True})
    supervisor = Mock()
    supervisor.status.return_value = {"engine": "daily-coder", "legacy_id": "native-1"}
    supervisor.repository = Path("/repository")
    with patch.object(adapter._supervisor, "supervisor", return_value=supervisor), patch("daily_coder.state_store.StateStore") as native_store:
        native_store.return_value.get.return_value = {"plan_hash": "plan-1"}
        adapter.approve("shared-1", note="reviewed")
    native_store.return_value.decide_approval.assert_called_once_with(
        "native-1", "plan", "plan-1", "approved", "agent-dashboard", "reviewed")


def test_rf_dashboard_note_cannot_approve_supervised_policy_gate():
    with tempfile.TemporaryDirectory() as tmp:
        adapter = ResearchForgeAdapter("research-forge", "RF", "", {"package_root": tmp}, Path(tmp) / "data")
        with patch.object(adapter._supervisor, "owns", return_value=True):
            result = adapter.approve("shared-1")
        assert not result["decided"]
        assert result["error"]["code"] == "POLICY_DENIED"
        assert not (adapter.inbox / "shared-1.decision.json").exists()


def test_real_research_supervisor_dashboard_alias_and_durable_status(tmp_path):
    adapter = ResearchForgeAdapter("research-forge", "RF", "", {
        "package_root": str(tmp_path), "supervisor_dir": str(tmp_path / "supervisor")
    }, tmp_path / "dashboard")
    out = adapter.start_run('{"topic": "bounded research topic"}')
    assert out["execution_started"]
    assert out["legacy_id"]
    assert out["status"] == "WAITING_HUMAN"
    restored = ResearchForgeAdapter("research-forge", "RF", "", {
        "package_root": str(tmp_path), "supervisor_dir": str(tmp_path / "supervisor")
    }, tmp_path / "dashboard")
    assert restored.get_run(out["run_id"])["legacy_id"] == out["legacy_id"]
    assert restored.list_runs()[0]["status"] == "WAITING_HUMAN"
    cancel = restored.cancel(out["run_id"])
    assert cancel["cancelled"] == (cancel["status"] == "CANCELLED")
    assert cancel["acknowledged"] == cancel["cancelled"]


def test_supervised_daily_health_does_not_require_http_daemon(tmp_path):
    adapter = DailyCoderAdapter("daily-coder", "DC", "", {
        "supervised": True, "supervisor_dir": str(tmp_path / "supervisor")
    })
    with patch.object(adapter, "_request", side_effect=AssertionError("HTTP must not be required")), patch.object(adapter, "_port_open", return_value=False):
        assert adapter.health()["online"]
        backend = adapter.backend_status()
    assert backend["state"] == "ready"
    assert backend["native_api_online"] is False
    assert backend["startable"] is False


def test_rf_supervised_uses_configured_workspace(tmp_path):
    workspace=tmp_path/"workspace";workspace.mkdir()
    adapter=ResearchForgeAdapter("research-forge","RF","",{"package_root":str(tmp_path),"workspace_root":str(workspace)},tmp_path/"data")
    with patch.object(adapter._supervisor,"start",return_value={}) as start:
        adapter.start_run("topic")
    assert start.call_args.args[1]==workspace

def test_auto_sessions_follow_workspace_without_widening_explicit_session(tmp_path):
    from agent_dashboard.adapters.supervised import SupervisorAccess
    service=Mock()
    service.new_session.side_effect=[{"session_id":"A"},{"session_id":"B"}]
    service.execute.return_value={}
    service.create_run.return_value={"run_id":"run"}
    access=SupervisorAccess("daily-coder",{},tmp_path)
    with patch.object(access,"supervisor",return_value=service):
        access.start("a",tmp_path/"a");access.start("b",tmp_path/"b")
    assert service.new_session.call_count==2
    assert [call.args[0] for call in service.create_run.call_args_list]==["A","B"]
    explicit=SupervisorAccess("daily-coder",{"session_id":"fixed"},tmp_path)
    with patch.object(explicit,"supervisor",return_value=service): explicit.start("b",tmp_path/"b")
    assert service.create_run.call_args.args[0]=="fixed"


def test_supervised_provider_is_pinned_to_start_request(tmp_path):
    adapter=DailyCoderAdapter("daily-coder","DC","",{"supervised":True,"provider":"anthropic"})
    with patch.object(adapter._supervisor,"start",return_value={}) as start:
        adapter.start_run("inspect",model="openai",mode="live",repo=str(tmp_path))
    assert start.call_args.kwargs["provider"]=="openai"
    assert start.call_args.kwargs["live"] is True


def test_concurrent_starts_keep_request_local_sessions(tmp_path):
    import inspect,sys,threading
    from agent_dashboard.adapters.supervised import SupervisorAccess
    access=SupervisorAccess("daily-coder",{},tmp_path)
    service=Mock();service.execute.return_value={};errors=[]
    service.new_session.side_effect=lambda **kw:{"session_id":Path(kw["project"]).name}
    def create(session,engine,request,workspace,**kw):
        if session != Path(workspace).name: raise ValueError("workspace outside session project")
        return {"run_id":"run"}
    service.create_run.side_effect=create
    lines,start=inspect.getsourcelines(SupervisorAccess.start)
    dispatch_line=start+next(i for i,line in enumerate(lines) if "row = supervisor.create_run" in line)
    paused=threading.Event();release=threading.Event()
    def trace(frame,event,arg):
        if frame.f_code is SupervisorAccess.start.__code__ and event=="line" and frame.f_lineno==dispatch_line:
            paused.set();assert release.wait(5)
        return trace
    def first():
        sys.settrace(trace)
        try: access.start("A",tmp_path/"A")
        except BaseException as exc: errors.append(exc)
        finally: sys.settrace(None)
    with patch.object(access,"supervisor",return_value=service):
        worker=threading.Thread(target=first);worker.start()
        assert paused.wait(5)
        try: access.start("B",tmp_path/"B")
        finally: release.set();worker.join(5)
    assert not errors
