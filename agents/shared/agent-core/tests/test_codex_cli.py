import json
import sys
import time
import pytest
from agent_core.providers.base import Invocation
from agent_core.providers.http import ProviderError
from agent_core.providers.codex_cli import CodexCLIProvider,parse_codex_jsonl,CLI_VERSION,ENVELOPE_VERSION

def request(**kwargs):
    return Invocation("run","role","prompt",{},"strong",128,"idem",model="pinned-model",**kwargs)
def events(usage=None):
    result=[{"type":"thread.started","thread_id":"thread-1"},{"type":"item.completed","item":{"type":"agent_message","text":json.dumps({"version":ENVELOPE_VERSION,"output":{"ok":True},"tool_calls":[]})}},{"type":"turn.completed"}]
    if usage is not None: result[-1]["usage"]=usage
    return [json.dumps(item) for item in result]
def test_completed_and_known_zero():
    result=parse_codex_jsonl(events({"input_tokens":0,"output_tokens":0,"cached_input_tokens":0}),request(),model="pinned-model")
    assert result.output=={"ok":True} and result.usage.total_tokens==0
    assert result.usage.cached_tokens==0 and result.usage.cost_usd is None
    assert result.usage.evidence_status=="reported"
def test_missing_usage_unknown():
    result=parse_codex_jsonl(events(),request(),model="pinned-model")
    assert result.usage.total_tokens is None and result.usage.cost_usd is None
@pytest.mark.parametrize("kind",["command_execution","file_change","mcp_tool_call","web_search","unknown_native_tool"])
def test_native_execution_events_denied(kind):
    rows=events(); rows.insert(0,json.dumps({"type":"item.started","item":{"type":kind}}))
    with pytest.raises(ProviderError): parse_codex_jsonl(rows,request(),model="pinned-model")
def test_tool_envelope_only_returns_requests():
    rows=events();rows[1]=json.dumps({"type":"item.completed","item":{"type":"agent_message","text":json.dumps({"version":ENVELOPE_VERSION,"output":None,"tool_calls":[{"name":"filesystem.read","arguments":{"path":"a"},"call_id":"call-1"}]})}})
    result=parse_codex_jsonl(rows,request(tools=({"name":"filesystem.read"},)),model="pinned-model")
    assert result.tool_calls[0].call_id=="call-1" and result.output is None
    with pytest.raises(ProviderError): parse_codex_jsonl(rows,request(),model="pinned-model")
def test_incomplete_and_output_bounds():
    with pytest.raises(ProviderError): parse_codex_jsonl(events()[:-1],request(),model="pinned-model")
    with pytest.raises(ProviderError): parse_codex_jsonl(events(),request(),model="pinned-model",max_output_bytes=8)
def test_invoke_always_denies_before_subprocess(monkeypatch):
    monkeypatch.setattr("subprocess.Popen",lambda *a,**k:pytest.fail("model process launched"))
    provider=CodexCLIProvider(executable=sys.executable,expected_version=CLI_VERSION,model="pinned-model")
    with pytest.raises(ProviderError) as error: provider.invoke(request())
    assert error.value.remote_acceptance=="rejected" and not error.value.retryable
    assert provider.capabilities.tools is False

def executable(tmp_path,body):
    path=tmp_path/"fake-codex"
    path.write_text("#!"+sys.executable+"\n"+body)
    path.chmod(0o700)
    return path

def test_login_status_probe_and_version(tmp_path):
    path=executable(tmp_path,"import sys\nif sys.argv[1:]==['--version']: print('"+CLI_VERSION+"')\nelif sys.argv[1:]==['login','status']: print('Logged in using ChatGPT',file=sys.stderr)\nelse: raise SystemExit(9)\n")
    provider=CodexCLIProvider(executable=path,model="pinned-model")
    result=provider.diagnostics()
    assert result.version_matches and result.chatgpt_login and not result.supervised_ready
    assert len(result.executable_sha256)==64

def test_version_mismatch_skips_login(tmp_path):
    path=executable(tmp_path,"import sys\nif sys.argv[1:]==['--version']: print('unknown version')\nelse: raise RuntimeError('login must not run')\n")
    result=CodexCLIProvider(executable=path,model="pinned-model").diagnostics()
    assert not result.version_matches and not result.chatgpt_login

def test_probe_timeout_kills_descendant(tmp_path):
    import os
    import signal
    pidfile=tmp_path/"child.pid"
    path=executable(tmp_path,"import os,time\npid=os.fork()\nif pid==0:\n time.sleep(5)\nelse:\n open("+repr(str(pidfile))+",'w').write(str(pid))\n time.sleep(5)\n")
    provider=CodexCLIProvider(executable=path,model="pinned-model",probe_timeout=1.0)
    start=time.monotonic()
    with pytest.raises(ProviderError) as error: provider.diagnostics()
    assert error.value.category=="deadline" and time.monotonic()-start<3
    pid=int(pidfile.read_text())
    # ESRCH proves the process group was terminated; orphan zombies may briefly
    # retain a PID, so an external inspection can distinguish them from running.
    import subprocess
    state=subprocess.run(['ps','-o','stat=','-p',str(pid)],capture_output=True,text=True).stdout.strip()
    assert not state or state.startswith('Z')

def test_probe_bounded_output_and_sanitized_errors(tmp_path):
    path=executable(tmp_path,"print('private-details'*10000)")
    with pytest.raises(ProviderError) as error: CodexCLIProvider(executable=path,model="pinned-model",max_probe_bytes=100).diagnostics()
    assert "private-details" not in str(error.value)

def test_executable_digest_mismatch_before_spawn(monkeypatch):
    monkeypatch.setattr("subprocess.Popen",lambda *a,**k:pytest.fail("untrusted binary launched"))
    with pytest.raises(ProviderError): CodexCLIProvider(executable=sys.executable,model="pinned-model",expected_executable_sha256="0"*64).diagnostics()

import hashlib

def pinned(tmp_path,body):
    path=executable(tmp_path,body)
    catalog=tmp_path/"catalog.json"
    catalog.write_text(json.dumps({"models":[{"slug":"pinned-model","shell_type":"disabled","apply_patch_tool_type":None,"node_repl_disabled":True,"tool_mode":"direct","experimental_supported_tools":[],"supports_search_tool":False,"include_skills_usage_instructions":False,"include_plugin_usage_instructions":False,"include_apps_usage_instructions":False}]}))
    return CodexCLIProvider(executable=path,model="pinned-model",expected_executable_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),catalog_path=catalog,expected_catalog_sha256=hashlib.sha256(catalog.read_bytes()).hexdigest())

def test_pinned_invocation_structured_result(tmp_path):
    body="import sys,json\nif sys.argv[1:]==['--version']: print('"+CLI_VERSION+"')\nelif sys.argv[1:]==['login','status']: print('Logged in using ChatGPT')\nelse:\n " + "\n ".join("print("+repr(line)+")" for line in events({"input_tokens":2,"output_tokens":3,"cached_input_tokens":1,"cache_write_input_tokens":4,"reasoning_output_tokens":2}))+"\n"
    provider=pinned(tmp_path,body)
    assert provider.diagnostics().supervised_ready
    result=provider.invoke(request())
    assert result.output=={"ok":True} and result.usage.total_tokens==5
    assert result.usage.cached_tokens==1 and result.usage.cache_creation_tokens==4 and result.usage.reasoning_tokens==2

def test_catalog_changed_fail_closed(tmp_path):
    provider=pinned(tmp_path,"raise RuntimeError('must not launch')")
    provider.catalog_path.write_text("{}")
    with pytest.raises(ProviderError):provider.invoke(request())

def test_exact_security_settings_and_no_user_overrides(tmp_path):
    provider=pinned(tmp_path,"pass")
    settings=provider.security_settings()
    assert settings["features"]["skip_host_skill_discovery"] is True
    assert all(v is False for k,v in settings["features"].items() if k!="skip_host_skill_discovery")
    assert settings["mcp_servers"]=={} and settings["plugins"]=={}
    assert settings["web_search"]=="disabled" and settings["model_provider"]=="openai"
    assert len(provider.security_config_sha256)==64
    with pytest.raises(ProviderError): provider.invoke(request(provider_options={"sandbox":"danger-full-access"}))

def test_native_jsonl_rejected_in_pinned_invocation(tmp_path):
    rows=[json.dumps({"type":"item.started","item":{"type":"command_execution"}})]
    body="import sys\nif sys.argv[1:]==['--version']: print('"+CLI_VERSION+"')\nelif sys.argv[1:]==['login','status']: print('Logged in using ChatGPT')\nelse: print("+repr(rows[0])+")\n"
    provider=pinned(tmp_path,body)
    with pytest.raises(ProviderError) as error:provider.invoke(request())
    assert error.value.category=="security" and error.value.remote_acceptance=="unknown"

def test_cancel_active_process_remote_unknown(tmp_path):
    import threading
    provider=pinned(tmp_path,"import sys,time\nif sys.argv[1:]==['--version']: print('"+CLI_VERSION+"')\nelif sys.argv[1:]==['login','status']: print('Logged in using ChatGPT')\nelse: time.sleep(5)\n")
    errors=[]
    def invoke():
        try: provider.invoke(request())
        except ProviderError as error: errors.append(error)
    worker=threading.Thread(target=invoke);worker.start()
    stop=time.monotonic()+2
    while "idem" not in provider._active and time.monotonic()<stop:time.sleep(.01)
    assert provider.cancel("idem")=="local_terminated_remote_unknown"
    worker.join(2)
    assert not worker.is_alive() and errors[0].category=="cancelled"
    assert errors[0].remote_acceptance=="unknown"
    assert provider.cancel("missing")=="unknown"

def test_pinned_invocation_deadline_before_spawn(tmp_path,monkeypatch):
    provider=pinned(tmp_path,"pass")
    monkeypatch.setattr("subprocess.Popen",lambda *a,**k:pytest.fail("expired invocation launched"))
    with pytest.raises(ProviderError) as error:provider.invoke(request(deadline=time.time()-1))
    assert error.value.category=="deadline" and error.value.remote_acceptance=="rejected"

def test_role_schema_validation():
    req=request(output_schema={"type":"object","properties":{"ok":{"type":"string"}},"required":["ok"],"additionalProperties":False})
    with pytest.raises(ProviderError):parse_codex_jsonl(events(),req,model="pinned-model")


@pytest.mark.parametrize("diagnostic,category",[("You've hit your usage limit. PRIVATE-CREDENTIAL","account_limit"),("Invalid API key PRIVATE-CREDENTIAL","authorization"),("Invalid schema PRIVATE-CREDENTIAL","configuration"),("unexpected PRIVATE-CREDENTIAL","transport")])
def test_nonzero_exit_has_sanitized_classification(tmp_path,diagnostic,category):
    body="\n".join(["import sys", "if sys.argv[1:]==['--version']: print("+repr(CLI_VERSION)+")", "elif sys.argv[1:]==['login','status']: print('Logged in using ChatGPT')", "else:", " print("+repr(diagnostic)+",file=sys.stderr)", " raise SystemExit(1)"])
    provider=pinned(tmp_path,body)
    with pytest.raises(ProviderError) as error:provider.invoke(request())
    assert error.value.category==category
    assert error.value.remote_acceptance=="unknown" and error.value.retryable is False
    assert "PRIVATE-CREDENTIAL" not in str(error.value)
    assert len(error.value.diagnostics["output_sha256"])==64

def test_envelope_literal_fields_have_explicit_string_types(tmp_path):
    provider=pinned(tmp_path,"pass")
    schema=provider._schema(request(tools=({"name":"filesystem.read","parameters":{"type":"object","properties":{"path":{"type":"string"}},"required":["path"],"additionalProperties":False}},)))
    assert schema["properties"]["version"]["type"]=="string"
    tool=schema["properties"]["tool_calls"]["items"]["anyOf"][0]
    assert tool["properties"]["name"]["type"]=="string"
