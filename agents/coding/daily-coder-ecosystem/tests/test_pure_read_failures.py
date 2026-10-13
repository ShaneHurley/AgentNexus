import uuid
import pytest
from agent_core.lifecycle import ReconciliationRequired
from daily_coder.tool_broker import ToolBroker
from daily_coder.policy import PolicyGateway
from daily_coder.state_store import StateStore

def gateway(tmp_path):
    state = StateStore(tmp_path / 'state.sqlite')
    run = str(uuid.uuid4())
    state.create(run, 'read failure regression', str(tmp_path), 'config', 'created')
    tools = {'role_allowlists': {'researcher': ['filesystem.read', 'filesystem.list'], 'implementer': ['filesystem.write']}, 'disabled_until_adapter_configured': []}
    broker = ToolBroker(tmp_path, tools, {'path_policy': {'deny': [], 'write_requires_plan_allowlist': True}})
    return PolicyGateway(broker, state, {}, False), run

@pytest.mark.parametrize('tool', ['filesystem.read', 'filesystem.list'])
def test_missing_read_is_failed_completed_receipt(tmp_path, tool):
    service, run = gateway(tmp_path)
    result = service.safe_execute(run, 'researcher', 'RESEARCH', tool, {'path': 'missing'}, operation_id='missing-read')
    assert result['ok'] is False and result['read_failed'] is True
    assert result['error'] == 'FileNotFoundError'
    assert result['message'] == 'Filesystem read unavailable'
    assert service.state.get(run)['status'] != 'RECONCILIATION_REQUIRED'
    assert service.state.pending_tool_operations(run) == []
    assert service.state.tool_operation('missing-read')['state'] == 'completed'

def test_cached_missing_read_does_not_reread_after_creation(tmp_path, monkeypatch):
    service, run = gateway(tmp_path)
    args = {'path': 'missing'}
    first = service.safe_execute(run, 'researcher', 'RESEARCH', 'filesystem.read', args, operation_id='cached-read')
    (tmp_path / 'missing').write_text('now exists')
    def forbidden(*args, **kwargs):
        pytest.fail('completed failure must replay without broker execution')
    monkeypatch.setattr(service.broker, 'execute', forbidden)
    second = service.safe_execute(run, 'researcher', 'RESEARCH', 'filesystem.read', args, operation_id='cached-read')
    assert second == first
    assert service.state.pending_tool_operations(run) == []

def test_read_permission_error_is_known_failure(tmp_path, monkeypatch):
    service, run = gateway(tmp_path)
    def denied(*args, **kwargs):
        raise PermissionError('private path must not appear')
    monkeypatch.setattr(service.broker, 'execute', denied)
    result = service.safe_execute(run, 'researcher', 'RESEARCH', 'filesystem.read', {'path': 'note'}, operation_id='permission-read')
    assert result['ok'] is False and result['error'] == 'PermissionError'
    assert 'private path' not in str(result)
    assert service.state.pending_tool_operations(run) == []

def test_write_oserror_retains_unknown_receipt(tmp_path, monkeypatch):
    service, run = gateway(tmp_path)
    def interrupted(*args, **kwargs):
        raise OSError('write outcome uncertain')
    monkeypatch.setattr(service.broker, 'execute', interrupted)
    with pytest.raises(ReconciliationRequired):
        service.safe_execute(run, 'implementer', 'IMPLEMENT', 'filesystem.write', {'path': 'new.txt', 'content': 'value'}, plan_allowlist=['new.txt'], operation_id='uncertain-write')
    assert service.state.get(run)['status'] == 'RECONCILIATION_REQUIRED'
    assert len(service.state.pending_tool_operations(run)) == 1

@pytest.mark.parametrize('error', [RuntimeError, KeyboardInterrupt])
def test_unexpected_read_exception_remains_unknown(tmp_path, monkeypatch, error):
    service, run = gateway(tmp_path)
    def unexpected(*args, **kwargs):
        raise error('unexpected')
    monkeypatch.setattr(service.broker, 'execute', unexpected)
    expected = KeyboardInterrupt if error is KeyboardInterrupt else ReconciliationRequired
    with pytest.raises(expected):
        service.safe_execute(run, 'researcher', 'RESEARCH', 'filesystem.read', {'path': 'note'}, operation_id='uncertain-read')
    assert service.state.get(run)['status'] == 'RECONCILIATION_REQUIRED'
    assert len(service.state.pending_tool_operations(run)) == 1
