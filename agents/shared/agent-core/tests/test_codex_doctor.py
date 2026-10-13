import hashlib
import json
import pytest
from agent_core.codex_doctor import doctor
from agent_core.providers.codex_cli import CLI_VERSION, SUPPORTED_VERSIONS
from agent_core.providers.http import ProviderError

class Fake:
    version=CLI_VERSION
    login=(0,b"",b"Logged in using ChatGPT")
    pin_error=False
    probe_error=False
    version_code=0
    security_config_sha256="c"*64
    probes=[]
    def __init__(self,**kwargs): self.kwargs=kwargs
    def invoke(self,*args,**kwargs): pytest.fail("doctor must not invoke model")
    def _pins(self):
        if self.pin_error: raise ProviderError("private catalog details",category="configuration",remote_acceptance="rejected")
        return b"catalog"
    def _probe(self,args):
        self.probes.append(args)
        if self.probe_error: raise ProviderError("private probe details",category="transport",remote_acceptance="rejected")
        return (self.version_code,self.version.encode(),b"") if args==("--version",) else self.login

@pytest.fixture
def configured(tmp_path):
    executable=tmp_path/"fake-codex"
    executable.write_bytes(b"local fake binary")
    value={"version":CLI_VERSION,"model":"reviewed-test-model","reasoning_effort":"medium","executable":str(executable),"executable_sha256":hashlib.sha256(executable.read_bytes()).hexdigest(),"catalog_path":str(tmp_path/"catalog.json"),"catalog_sha256":"b"*64,"security_config_sha256":"c"*64}
    path=tmp_path/".agentnexus/codex.json"
    path.parent.mkdir()
    path.write_text(json.dumps(value))
    return tmp_path,path,value

def check(configured,**overrides):
    root,path,value=configured
    Provider=type("LocalFake",(Fake,),{"probes":[],**overrides})
    result=doctor(root,provider_factory=Provider)
    assert "private" not in json.dumps(result)
    assert str(root) not in json.dumps(result)
    return result,Provider.probes

@pytest.mark.parametrize("version",SUPPORTED_VERSIONS)
@pytest.mark.parametrize("login",[(0,b"Logged in using ChatGPT",b""),(0,b"",b"Logged in using ChatGPT\n")])
def test_ready_supported_version_and_stream_variants(configured,version,login):
    root,path,value=configured
    value["version"]=version
    path.write_text(json.dumps(value))
    result,probes=check(configured,version=version,login=login)
    assert result["ready"] and result["status"]=="ready"
    assert probes==[("--version",),("login","status")]
    assert result["model"]==value["model"]

@pytest.mark.parametrize("login,status",[((1,b"",b"Not logged in"),"signed_out"),((0,b"private unknown text",b""),"status_unrecognized"),((2,b"private error",b""),"authentication_unavailable")])
def test_login_failures_are_distinct_and_sanitized(configured,login,status):
    result,_=check(configured,login=login)
    assert result["status"]==status and not result["ready"]

@pytest.mark.parametrize("field,value,status",[("executable","/missing-doctor-executable","executable_missing"),("executable_sha256","0"*64,"pin_mismatch"),("version","future","unsupported_version"),("security_config_sha256","d"*64,"invalid_security_configuration")])
def test_independent_configuration_failures(configured,field,value,status):
    root,path,pins=configured
    pins[field]=value
    path.write_text(json.dumps(pins))
    result,_=check(configured)
    assert result["status"]==status and not result["ready"]

def test_version_and_catalog_failures_skip_login(configured):
    result,probes=check(configured,version="different")
    assert result["status"]=="unsupported_version" and probes==[("--version",)]
    result,probes=check(configured,pin_error=True)
    assert result["status"]=="pin_mismatch" and probes==[("--version",)]
    result,probes=check(configured,version_code=2)
    assert result["status"]=="probe_unavailable" and probes==[("--version",)]

def test_probe_failure_is_not_authentication_failure(configured):
    result,_=check(configured,probe_error=True)
    assert result["status"]=="probe_unavailable"

def test_missing_and_symlink_config(tmp_path):
    assert doctor(tmp_path)["status"]=="configuration_missing"
    directory=tmp_path/".agentnexus"
    directory.mkdir()
    (directory/"codex.json").symlink_to(tmp_path/"outside")
    assert doctor(tmp_path)["status"]=="invalid_security_configuration"

def test_constructor_failure_is_typed_and_private(configured):
    root,_,_=configured
    def invalid(**kwargs): raise ValueError("private constructor details")
    result=doctor(root,provider_factory=invalid)
    assert result["status"]=="invalid_security_configuration" and "private" not in json.dumps(result)

def test_public_cli_doctor_exit_code(tmp_path,capsys,monkeypatch):
    import agent_core.codex_doctor as module
    from agent_core.nexus_cli import main
    monkeypatch.setattr(module,"doctor",lambda root:{"ready":True,"status":"ready"})
    assert main(["--repository",str(tmp_path),"codex","doctor","--json"])==0
    assert json.loads(capsys.readouterr().out)["status"]=="ready"
    monkeypatch.setattr(module,"doctor",lambda root:{"ready":False,"status":"signed_out"})
    assert main(["--repository",str(tmp_path),"codex","doctor","--json"])==3
