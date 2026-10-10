"""Provider construction with explicit reference-based supervision."""
from __future__ import annotations
import os
from agent_core.providers.mock import MockProvider
from agent_core.providers.openai_compat import OpenAICompatibleProvider
from agent_core.providers.anthropic import AnthropicProvider
PROVIDERS=("mock","openai","openrouter","local","anthropic")
LIVE_PROVIDERS=set(PROVIDERS)-{"mock"}
def is_live(name): return name in LIVE_PROVIDERS

def build_provider(name="mock",*,config=None,secrets=None,timeout=180.0,secret_broker=None,secret_grant_factory=None,credential_ref=None,allow_development_environment=False,development_secret_grant=None,**kwargs):
    pc=((config or {}).get("providers") or {}).get(name,{})
    if name=="mock": return MockProvider(canned_responses=kwargs.get("canned_responses") or pc.get("canned_responses"))
    if name not in LIVE_PROVIDERS: raise ValueError("Unknown provider")
    ref=credential_ref or pc.get("credential_ref")
    variables={"openai":"OPENAI_API_KEY","openrouter":"OPENROUTER_API_KEY","anthropic":"ANTHROPIC_API_KEY","local":"LOCAL_API_KEY"}
    key=None
    if secrets:
        raise ValueError("raw registry secrets are unsupported; use SecretBroker")
    if allow_development_environment:
        if secret_broker is not None or not ref or development_secret_grant is None:
            raise ValueError("development environment override requires narrow secret grant")
        try:
            if development_secret_grant.authorize("secret_use",ref) is False:
                raise ValueError("development secret capability denied")
        except Exception:
            raise ValueError("development secret capability denied") from None
        key=os.environ.get(variables[name])
    urls={"openai":"https://api.openai.com/v1","openrouter":"https://openrouter.ai/api/v1","anthropic":"https://api.anthropic.com/v1","local":"http://127.0.0.1:11434/v1"}
    models={"openai":"gpt-4o-mini","openrouter":"openai/gpt-4o-mini","anthropic":"claude-sonnet-4-5","local":"qwen2.5-coder"}
    args=dict(api_key=key,base_url=pc.get("base_url",urls[name]),default_model=pc.get("default_model",models[name]),timeout=timeout,secret_broker=secret_broker,secret_grant_factory=secret_grant_factory,credential_ref=ref)
    if name=="anthropic": return AnthropicProvider(**args)
    return OpenAICompatibleProvider(**args,name=name,extra_headers=pc.get("extra_headers"),model_mapping=pc.get("model_mapping"),supports_json_response_format=name!="local")
