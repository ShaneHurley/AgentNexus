import time
import pytest
from agent_core.providers.base import Invocation, TokenUsage
from agent_core.providers.http import post_json, ProviderError

def test_unknown_usage():
    assert TokenUsage().cost_usd is None
    assert TokenUsage().input_tokens is None

def test_invocation_deadline():
    request=Invocation("r","role","",{},"",1,"i",deadline=time.time()+1)
    assert request.max_transport_retries == 0

def test_unknown_acceptance_not_retried(monkeypatch):
    calls=[]
    def fail(*args,**kwargs):
        calls.append(1)
        raise OSError("untrusted upstream message")
    monkeypatch.setattr("urllib.request.urlopen",fail)
    with pytest.raises(ProviderError) as error:
        post_json("https://example.org",{},retries=2)
    assert len(calls)==1
    assert error.value.remote_acceptance=="unknown"
    assert "untrusted" not in str(error.value)

from agent_core.providers.openai_compat import OpenAICompatibleProvider
from agent_core.providers.registry import build_provider

def test_registry_no_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY","dummy"+"-value")
    assert build_provider("openai").api_key is None

def test_reported_zero_and_missing(monkeypatch):
    responses=iter([{"choices":[{"message":{"content":"{}"}}]}, {"id":"request-id","choices":[{"finish_reason":"stop","message":{"content":"{}"}}],"usage":{"prompt_tokens":0,"completion_tokens":0,"cost":0}}])
    monkeypatch.setattr("agent_core.providers.openai_compat.post_json",lambda *a,**k:next(responses))
    provider=OpenAICompatibleProvider(api_key="dummy"+"-value")
    request=Invocation("r","role","",{},"",1,"i")
    unknown=provider.invoke(request)
    assert unknown.usage.input_tokens is None and unknown.usage.cost_usd is None
    zero=provider.invoke(request)
    assert zero.usage.cost_usd==0 and zero.usage.evidence_status=="reported"
    assert zero.provider_request_id=="request-id"

def test_openrouter_privacy(monkeypatch):
    payloads=[]
    def transport(url,payload,*a,**k):
        payloads.append(payload)
        return {"choices":[{"message":{"content":"{}"}}]}
    monkeypatch.setattr("agent_core.providers.openai_compat.post_json",transport)
    OpenAICompatibleProvider(api_key="dummy"+"-value",name="openrouter").invoke(Invocation("r","role","",{},"",1,"i",provider_options={"provider":{"allow_fallbacks":True,"zdr":False}}))
    assert payloads[0]["provider"]=={"allow_fallbacks":True,"zdr":True,"data_collection":"deny","require_parameters":True}

import io
import json
import urllib.error
from agent_core.providers.anthropic import AnthropicProvider

def test_rejected_throttling_bounded(monkeypatch):
    calls=[]
    def fail(request,**kwargs):
        calls.append(1)
        raise urllib.error.HTTPError(request.full_url,429,"no",{},io.BytesIO(b"untrusted"))
    monkeypatch.setattr("urllib.request.urlopen",fail)
    with pytest.raises(ProviderError) as error:
        post_json("https://example.org",{},retries=2,backoff_factor=0)
    assert len(calls)==3
    assert error.value.remote_acceptance=="rejected" and error.value.retryable

def test_server_failure_unknown_not_replayed(monkeypatch):
    calls=[]
    def fail(request,**kwargs):
        calls.append(1)
        raise urllib.error.HTTPError(request.full_url,503,"no",{},io.BytesIO(b"untrusted"))
    monkeypatch.setattr("urllib.request.urlopen",fail)
    with pytest.raises(ProviderError) as error:
        post_json("https://example.org",{},retries=2)
    assert len(calls)==1 and error.value.remote_acceptance=="unknown"

def test_deadline_before_network(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",lambda *a,**k:pytest.fail("network invoked"))
    with pytest.raises(ProviderError): post_json("https://example.org",{},deadline=time.time()-1)

def test_native_tools_and_cache(monkeypatch):
    payloads=[]
    def transport(url,payload,*a,**k):
        payloads.append(payload)
        return {"id":"native-id","stop_reason":"tool_use","content":[{"type":"tool_use","id":"call-id","name":"filesystem.read","input":{"path":"a"}}],"usage":{"input_tokens":12,"output_tokens":3,"cache_read_input_tokens":8}}
    monkeypatch.setattr("agent_core.providers.anthropic.post_json",transport)
    result=AnthropicProvider(api_key="dummy"+"-value").invoke(Invocation("r","role","",{},"",1,"i",tool_results=({"call_id":"previous","tool":"filesystem.read","arguments":{},"result":"ok"},)))
    assert payloads[0]["messages"][1]["content"][0]["id"]=="previous"
    assert payloads[0]["messages"][2]["content"][0]["tool_use_id"]=="previous"
    assert result.tool_calls[0].call_id=="call-id" and result.usage.cached_tokens==8
    assert result.usage.cost_usd is None and result.finish_reason=="tool_use"

def test_openai_tool_stream(monkeypatch):
    events=[{"id":"stream-id","choices":[{"delta":{"tool_calls":[{"index":0,"id":"call-id","function":{"name":"filesystem_read","arguments":"{\"p\":"}}]}}]}, {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"1}"}}]},"finish_reason":"tool_calls"}]}, {"usage":{"prompt_tokens":0,"completion_tokens":0,"cost":0},"choices":[]}]
    monkeypatch.setattr("agent_core.providers.openai_compat.post_stream",lambda *a,**k:iter(map(json.dumps,events)))
    provider=OpenAICompatibleProvider(api_key="dummy"+"-value")
    result=list(provider.stream_events(Invocation("r","role","",{},"",1,"i",tools=({"name":"filesystem.read","parameters":{}},))))
    assert result[0].tool_call.call_id=="call-id" and result[0].tool_call.arguments=={"p":1}
    assert result[-1].usage.cost_usd==0

def test_native_stream(monkeypatch):
    events=[{"type":"message_start","message":{"id":"native-id","usage":{"input_tokens":2,"cache_read_input_tokens":1}}},{"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"call-id","name":"read","input":{}}},{"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"{\"p\":1}"}},{"type":"content_block_stop","index":0},{"type":"message_delta","delta":{"stop_reason":"tool_use"},"usage":{"output_tokens":3}}]
    monkeypatch.setattr("agent_core.providers.anthropic.post_stream",lambda *a,**k:iter(map(json.dumps,events)))
    result=list(AnthropicProvider(api_key="dummy"+"-value").stream_events(Invocation("r","role","",{},"",1,"i")))
    assert result[0].tool_call.call_id=="call-id" and result[0].provider_request_id=="native-id"
    assert result[1].usage.input_tokens==3 and result[1].usage.output_tokens==3
    assert result[-1].finish_reason=="tool_use"

def test_actual_development_grant(monkeypatch):
    from agent_core.contracts import Grant,EffectiveGrant
    monkeypatch.setenv("OPENAI_API_KEY","dummy"+"-value")
    grant=EffectiveGrant((Grant(secret_use=frozenset({"provider/test"})),)*6,"developer")
    provider=build_provider("openai",credential_ref="provider/test",allow_development_environment=True,development_secret_grant=grant)
    assert provider.api_key=="dummy"+"-value"
    with pytest.raises(ValueError): build_provider("openai",credential_ref="provider/other",allow_development_environment=True,development_secret_grant=grant)

def test_native_cache_creation_total():
    usage=AnthropicProvider()._usage({"input_tokens":12,"cache_read_input_tokens":8,"cache_creation_input_tokens":4,"output_tokens":3})
    assert usage.input_tokens==24 and usage.total_tokens==27
    assert usage.cached_tokens==8 and usage.cache_creation_tokens==4
