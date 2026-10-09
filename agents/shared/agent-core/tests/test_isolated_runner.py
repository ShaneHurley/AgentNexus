from pathlib import Path
import subprocess
import pytest
from agent_core.isolation import DockerRunner, IsolationUnavailable

def test_digest_required(tmp_path):
    with pytest.raises(ValueError): DockerRunner('python:latest',tmp_path)

def test_sandbox_flags_no_secrets_and_cleanup(tmp_path,monkeypatch):
    workspace=tmp_path/'repo'; workspace.mkdir()
    (workspace/'code.py').write_text('print(1)')
    (workspace/'.env').write_text('KEY=secret')
    (workspace/'credentials.json').write_text('secret')
    outside=tmp_path/'outside'; outside.write_text('private')
    (workspace/'link').symlink_to(outside)
    seen=[]
    def run(argv,**kw):
        seen.append((argv,kw))
        if 'create' in argv:
            mount=argv[argv.index('--mount')+1]
            source=Path(mount.split('src=')[1].split(',')[0])
            assert (source/'code.py').is_file()
            assert not (source/'.env').exists()
            assert not (source/'credentials.json').exists()
            assert not (source/'link').exists()
            assert '--network=none' in argv and '--read-only' in argv and '--cap-drop=ALL' in argv
            assert '--pull=never' in argv and '--security-opt=no-new-privileges' in argv
            assert not any('OPENROUTER' in x for x in argv)
            return subprocess.CompletedProcess(argv,0,'abc123','')
        if 'start' in argv: return subprocess.CompletedProcess(argv,0,'ok','')
        return subprocess.CompletedProcess(argv,0,'','')
    monkeypatch.setenv('OPENROUTER_API_KEY','secret-value')
    monkeypatch.setattr(subprocess,'run',run)
    def attach(self, command, env, timeout, cancel_check):
        cp = run(command, env=env)
        return {'returncode':cp.returncode,'timeout':False,'stdout':cp.stdout,'stderr':cp.stderr}
    monkeypatch.setattr(DockerRunner, '_attach', attach)
    r=DockerRunner('python@sha256:'+'a'*64,workspace).run(['python','code.py'],timeout=10)
    assert r['returncode']==0
    assert seen[-1][0][-3:]==['rm','--force','abc123']
    assert all('OPENROUTER_API_KEY' not in kwargs['env'] for _,kwargs in seen)

def test_timeout_cleans_container(tmp_path,monkeypatch):
    calls=[]
    def run(argv,**kw):
        calls.append(argv)
        if 'create' in argv: return subprocess.CompletedProcess(argv,0,'id','')
        if 'start' in argv: raise subprocess.TimeoutExpired(argv,1)
        return subprocess.CompletedProcess(argv,0,'','')
    monkeypatch.setattr(subprocess,'run',run)
    def attach(self, command, env, timeout, cancel_check):
        return run(command, env=env)
    monkeypatch.setattr(DockerRunner, '_attach', attach)
    result=DockerRunner('python@sha256:'+'a'*64,tmp_path).run(['python','-V'],timeout=1)
    assert result['timeout'] and calls[-1][-1]=='id'

def test_cleanup_failure_is_not_success(tmp_path,monkeypatch):
    def run(argv,**kw):
        if 'create' in argv: return subprocess.CompletedProcess(argv,0,'id','')
        if 'start' in argv: return subprocess.CompletedProcess(argv,0,'ok','')
        return subprocess.CompletedProcess(argv,1,'','failure')
    monkeypatch.setattr(subprocess,'run',run)
    monkeypatch.setattr(DockerRunner, '_attach', lambda *args: {'returncode':0,'timeout':False,'stdout':'ok','stderr':''})
    with pytest.raises(IsolationUnavailable): DockerRunner('python@sha256:'+'a'*64,tmp_path).run(['python','-V'])


def test_without_cancellation_streams_bounded_actual_process_output(tmp_path, monkeypatch):
    import sys
    real_popen = subprocess.Popen
    children = []
    def docker(argv, **kwargs):
        assert 'start' not in argv, 'worker output must use bounded streaming'
        return subprocess.CompletedProcess(argv, 0, 'container123' if 'create' in argv else '', '')
    def start(argv, **kwargs):
        child = real_popen([sys.executable, '-c', "import sys; sys.stdout.write('o' * 100000); sys.stderr.write('e' * 100000)"], **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr('agent_core.isolation.shutil.which', lambda _: 'docker')
    monkeypatch.setattr(subprocess, 'run', docker)
    monkeypatch.setattr(subprocess, 'Popen', start)
    result = DockerRunner('python@sha256:' + 'a'*64, tmp_path).run(['python', '-V'], timeout=10)
    assert result['returncode'] == 0
    assert result['stdout'] == 'o' * 20000
    assert result['stderr'] == 'e' * 20000
    assert children[0].poll() is not None
    assert not result.get('cancelled', False)
