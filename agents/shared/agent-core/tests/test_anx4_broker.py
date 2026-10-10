import time
import json
import pytest
from agent_core.secret_broker import SecretBroker, SecretBrokerError
class Backend:
    def __init__(self): self.value="dummy"+"-value"
    def get_password(self,service,account): return self.value
    def set_password(self,*args): raise RuntimeError("backend failed")
    def delete_password(self,*args): raise RuntimeError("backend failed")
class Grant:
    role_id="dc:role"
    def authorize(self, category, ref): return category=="secret_use" and ref=="provider/test"
def test_broker(tmp_path):
    broker=SecretBroker(tmp_path/"metadata.db",backend=Backend(),allow_test_backend=True)
    ref=broker.register("test","owner",["dc:role"],ref="provider/test")
    grant=broker.authorize("dc:role","run",ref,"invoke",time.time()+20,Grant())
    assert broker.use(grant,lambda value: {"echo":value})=={"echo":"[REDACTED]"}
    with pytest.raises(SecretBrokerError): broker.delete(ref)
    assert broker.available(ref)
    broker.revoke(ref)
    with pytest.raises(SecretBrokerError): broker.use(grant,lambda value:value)
def test_denied(tmp_path):
    broker=SecretBroker(tmp_path/"metadata.db",backend=Backend(),allow_test_backend=True)
    ref=broker.register("test","owner",["dc:role"])
    with pytest.raises(SecretBrokerError): broker.authorize("other","run",ref,"invoke",time.time()+20,Grant())

from dataclasses import replace

def test_failure_rotation_expiry_and_forgery(tmp_path):
    broker=SecretBroker(tmp_path/"metadata.db",backend=Backend(),allow_test_backend=True)
    ref=broker.register("test","owner",["dc:role"],ref="provider/test")
    grant=broker.authorize("dc:role","run",ref,"invoke",time.time()+20,Grant())
    assert broker.probe(grant)
    with pytest.raises(SecretBrokerError): broker.rotate(ref,"new"+"-dummy")
    assert broker.probe(grant)
    with pytest.raises(SecretBrokerError): broker.use(replace(grant,caller="other"),lambda value:True)
    with pytest.raises(SecretBrokerError): broker.authorize("dc:role","run",ref,"invoke",time.time()-1,Grant())
    with pytest.raises(SecretBrokerError): broker.authorize("dc:role","run","missing","invoke",time.time()+20,Grant())

def test_missing_locked_fail_before_callback(tmp_path):
    backend=Backend();broker=SecretBroker(tmp_path/"metadata.db",backend=backend,allow_test_backend=True)
    ref=broker.register("test","owner",["dc:role"],ref="provider/test")
    grant=broker.authorize("dc:role","run",ref,"invoke",time.time()+20,Grant())
    backend.value=None
    assert not broker.probe(grant)
    with pytest.raises(SecretBrokerError): broker.use(grant,lambda value:pytest.fail("callback invoked"))
    def locked(*args): raise RuntimeError("private"+"-details")
    backend.get_password=locked
    with pytest.raises(SecretBrokerError) as error: broker.use(grant,lambda value:True)
    assert "private" not in str(error.value)

def test_plaintext_backend_denied(tmp_path):
    with pytest.raises(SecretBrokerError): SecretBroker(tmp_path/"metadata.db",backend=Backend())

def test_supervised_provider_uses_per_invocation_grant(tmp_path,monkeypatch):
    from agent_core.providers.registry import build_provider
    from agent_core.providers.base import Invocation
    broker=SecretBroker(tmp_path/"metadata.db",backend=Backend(),allow_test_backend=True)
    ref=broker.register("test","owner",["dc:role"],ref="provider/test")
    calls=[]
    def grant(request):
        calls.append(request.run_id)
        return broker.authorize("dc:"+request.role,request.run_id,ref,"invoke",time.time()+20,Grant())
    provider=build_provider("openai",secret_broker=broker,secret_grant_factory=grant,credential_ref=ref)
    assert calls==[]
    monkeypatch.setattr("agent_core.providers.openai_compat.post_json",lambda *a,**k:{"choices":[{"message":{"content":json.dumps({"echo":"dummy"+"-value"})}}]})
    result=provider.invoke(Invocation("run","role","",{},"",1,"i",credential_ref=ref))
    assert calls==["run"] and result.output["echo"]=="[REDACTED]"

def test_authorize_void_success(tmp_path):
    class VoidGrant:
        role_id="dc:role"
        def authorize(self,category,ref):
            if category!="secret_use" or ref!="provider/test": raise PermissionError("denied")
    broker=SecretBroker(tmp_path/"metadata.db",backend=Backend(),allow_test_backend=True)
    ref=broker.register("test","owner",["dc:role"],ref="provider/test")
    grant=broker.authorize("dc:role","run",ref,"invoke",time.time()+20,VoidGrant())
    assert broker.probe(grant)

def test_actual_effective_grant(tmp_path):
    from agent_core.contracts import Grant as CoreGrant,EffectiveGrant,ContractDenied
    grant=EffectiveGrant((CoreGrant(secret_use=frozenset({"provider/test"})),)*6,"dc:role")
    broker=SecretBroker(tmp_path/"metadata.db",backend=Backend(),allow_test_backend=True)
    ref=broker.register("test","owner",["dc:role"],ref="provider/test")
    use=broker.authorize("dc:role","run",ref,"invoke",time.time()+20,grant)
    assert broker.probe(use)
    denied=EffectiveGrant((CoreGrant(secret_use=frozenset()),)*6,"dc:role")
    with pytest.raises(SecretBrokerError): broker.authorize("dc:role","run",ref,"invoke",time.time()+20,denied)

def test_bytes_redacted_and_opaque_output_denied(tmp_path):
    broker=SecretBroker(tmp_path/"metadata.db",backend=Backend(),allow_test_backend=True)
    ref=broker.register("test","owner",["dc:role"],ref="provider/test")
    grant=broker.authorize("dc:role","run",ref,"invoke",time.time()+20,Grant())
    assert broker.use(grant,lambda value:value.encode())==b"[REDACTED]"
    with pytest.raises(SecretBrokerError): broker.use(grant,lambda value:lambda:value)

def test_stream_lazy_redacted_and_closed(tmp_path):
    broker=SecretBroker(tmp_path/"metadata.db",backend=Backend(),allow_test_backend=True)
    ref=broker.register("test","owner",["dc:role"],ref="provider/test")
    grant=broker.authorize("dc:role","run",ref,"invoke",time.time()+20,Grant())
    state=[]
    def produce(value):
        try:
            yield {"echo":value}
            state.append("continued")
            yield "next"
        finally: state.append("closed")
    events=broker.stream_use(grant,produce)
    assert state==[]
    assert next(events)=={"echo":"[REDACTED]"} and state==[]
    events.close()
    assert state==["closed"]

def test_stream_revoke_between_events(tmp_path):
    broker=SecretBroker(tmp_path/"metadata.db",backend=Backend(),allow_test_backend=True)
    ref=broker.register("test","owner",["dc:role"],ref="provider/test")
    grant=broker.authorize("dc:role","run",ref,"invoke",time.time()+20,Grant())
    events=broker.stream_use(grant,lambda value:iter([value,value]))
    assert next(events)=="[REDACTED]"
    broker.revoke(ref)
    with pytest.raises(SecretBrokerError): next(events)

def test_stream_split_secret_redacted(tmp_path):
    from agent_core.providers.base import StreamEvent
    backend=Backend()
    broker=SecretBroker(tmp_path/"metadata.db",backend=backend,allow_test_backend=True)
    ref=broker.register("test","owner",["dc:role"],ref="provider/test")
    grant=broker.authorize("dc:role","run",ref,"invoke",time.time()+20,Grant())
    state=[]
    def produce(value):
        yield StreamEvent("text",text="safe "+value[:4],provider_request_id="id")
        state.append("second")
        yield StreamEvent("text",text=value[4:]+" end",provider_request_id="id")
        yield StreamEvent("finish",finish_reason="stop",provider_request_id="id")
    events=broker.stream_use(grant,produce)
    first=next(events)
    assert first.text=="safe " and state==[]
    rest=list(events)
    combined=first.text+"".join(event.text or "" for event in rest)
    assert backend.value not in combined and combined=="safe [REDACTED] end"
    assert rest[-1].finish_reason=="stop"

def test_stream_partial_secret_suffix_flushed(tmp_path):
    broker=SecretBroker(tmp_path/"metadata.db",backend=Backend(),allow_test_backend=True)
    ref=broker.register("test","owner",["dc:role"],ref="provider/test")
    grant=broker.authorize("dc:role","run",ref,"invoke",time.time()+20,Grant())
    assert "".join(broker.stream_use(grant,lambda value:iter(["safe "+value[:3]])))=="safe dum"

def test_stream_split_secret_all_boundaries(tmp_path):
    from agent_core.providers.base import StreamEvent
    backend=Backend();broker=SecretBroker(tmp_path/"metadata.db",backend=backend,allow_test_backend=True)
    ref=broker.register("test","owner",["dc:role"],ref="provider/test")
    grant=broker.authorize("dc:role","run",ref,"invoke",time.time()+20,Grant())
    for split in range(1,len(backend.value)):
        events=[StreamEvent("text",text=backend.value[:split]),StreamEvent("usage"),StreamEvent("text",text=backend.value[split:])]
        result=list(broker.stream_use(grant,lambda value:iter(events)))
        assert "".join(item.text or "" for item in result)=="[REDACTED]"
    result=list(broker.stream_use(grant,lambda value:iter(value)))
    assert "".join(result)=="[REDACTED]"
