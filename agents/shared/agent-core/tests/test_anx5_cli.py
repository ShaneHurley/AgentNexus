from agent_core.nexus_cli import main

def test_memory_help_does_not_initialize_execution_state(tmp_path):
    import pytest
    with pytest.raises(SystemExit) as e:main(['--state-dir',str(tmp_path/'state'),'memory','--help'])
    assert e.value.code==0
    assert not (tmp_path/'state').exists()

def test_memory_denied_input_does_not_initialize_execution_state(tmp_path,capsys):
    assert main(['--state-dir',str(tmp_path/'state'),'memory','search','--store',str(tmp_path/'missing.sqlite'),'--workspace',str(tmp_path),'--grant-file',str(tmp_path/'missing.json'),'--query','hello'])==3
    assert not (tmp_path/'state').exists()
