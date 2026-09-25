"""Provider registry.

`mock` is the only non-live provider. Everything else requires an explicit live opt-in
and a configured credential.
"""
from __future__ import annotations
from .mock import MockProvider
from .command import CommandProvider
from .bridge import HttpBridgeProvider
from .openai_compat import OpenAICompatibleProvider
from .anthropic import AnthropicProvider
from .gemini import GeminiProvider

PROVIDERS = ("mock", "openai", "anthropic", "gemini", "openrouter", "local", "command", "http")
LIVE_PROVIDERS = {"openai", "anthropic", "gemini", "openrouter", "local", "command", "http"}

def is_live(name: str) -> bool:
    return name in LIVE_PROVIDERS

def build_provider(name, *, config=None, secrets=None, command=None, endpoint=None, timeout=180):
    config = config or {}
    entry = (config.get("providers") or {}).get(name, {})

    def key(env_name):
        return secrets.get(env_name) if secrets else None

    if name == "mock":
        return MockProvider()
    if name == "command":
        if not command:
            raise ValueError("--provider-command is required for the command provider")
        return CommandProvider(command, timeout=timeout)
    if name == "http":
        if not endpoint:
            raise ValueError("--provider-endpoint is required for the http bridge provider")
        return HttpBridgeProvider(endpoint, token=key("BRIDGE_TOKEN"), timeout=timeout)
    if name == "openai":
        return OpenAICompatibleProvider(api_key=key("OPENAI_API_KEY"),
                                        base_url=entry.get("base_url", "https://api.openai.com/v1"),
                                        default_model=entry.get("default_model", "gpt-4o-mini"), timeout=timeout)
    if name == "openrouter":
        return OpenAICompatibleProvider(api_key=key("OPENROUTER_API_KEY"),
                                        base_url=entry.get("base_url", "https://openrouter.ai/api/v1"),
                                        default_model=entry.get("default_model", "openai/gpt-4o-mini"),
                                        timeout=timeout,
                                        extra_headers={"HTTP-Referer": "https://localhost", "X-Title": "daily-coder"})
    if name == "local":
        return OpenAICompatibleProvider(api_key=key("LOCAL_API_KEY") or "local",
                                        base_url=entry.get("base_url", "http://127.0.0.1:11434/v1"),
                                        default_model=entry.get("default_model", "qwen2.5-coder"), timeout=timeout,
                                        supports_json_response_format=False)
    if name == "anthropic":
        return AnthropicProvider(api_key=key("ANTHROPIC_API_KEY"),
                                 base_url=entry.get("base_url", "https://api.anthropic.com/v1"),
                                 default_model=entry.get("default_model", "claude-sonnet-4-5"), timeout=timeout)
    if name == "gemini":
        return GeminiProvider(api_key=key("GEMINI_API_KEY"),
                              base_url=entry.get("base_url", "https://generativelanguage.googleapis.com/v1beta"),
                              default_model=entry.get("default_model", "gemini-2.5-flash"), timeout=timeout)
    raise ValueError(f"unknown provider: {name}")
