"""Central provider registry for agent-core."""
from __future__ import annotations

import os
from typing import Any

from agent_core.providers.base import Provider
from agent_core.providers.mock import MockProvider
from agent_core.providers.openai_compat import OpenAICompatibleProvider

PROVIDERS = ("mock", "openai", "openrouter", "local")
LIVE_PROVIDERS = {"openai", "openrouter", "local"}


def is_live(name: str) -> bool:
    """Return True if provider makes real external API calls."""
    return name in LIVE_PROVIDERS


def build_provider(
    name: str = "mock",
    *,
    config: dict[str, Any] | None = None,
    secrets: dict[str, str] | None = None,
    timeout: float = 180.0,
    **kwargs: Any,
) -> Provider:
    """Build a Provider instance by name.
    
    Supports 'openrouter', 'openai', 'mock', and 'local'.
    Credentials are read from secrets dict if provided, falling back to os.environ.
    """
    config = config or {}
    provider_config = (config.get("providers") or {}).get(name, {})

    def get_secret(var_name: str) -> str | None:
        if secrets and var_name in secrets:
            return secrets[var_name]
        return os.environ.get(var_name)

    if name == "mock":
        canned = kwargs.get("canned_responses") or provider_config.get("canned_responses")
        return MockProvider(canned_responses=canned)

    if name == "openai":
        api_key = get_secret("OPENAI_API_KEY")
        base_url = provider_config.get("base_url", "https://api.openai.com/v1")
        default_model = provider_config.get("default_model", "gpt-4o-mini")
        extra_headers = provider_config.get("extra_headers")
        model_mapping = provider_config.get("model_mapping")
        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            timeout=timeout,
            extra_headers=extra_headers,
            name=name,
            model_mapping=model_mapping,
        )

    if name == "openrouter":
        api_key = get_secret("OPENROUTER_API_KEY")
        base_url = provider_config.get("base_url", "https://openrouter.ai/api/v1")
        default_model = provider_config.get("default_model", "openai/gpt-4o-mini")
        extra_headers = {
            "HTTP-Referer": "https://localhost",
            "X-Title": "AgentNexus",
            **(provider_config.get("extra_headers") or {}),
        }
        model_mapping = provider_config.get("model_mapping")
        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            timeout=timeout,
            extra_headers=extra_headers,
            name=name,
            model_mapping=model_mapping,
        )

    if name == "local":
        api_key = get_secret("LOCAL_API_KEY") or "local"
        base_url = provider_config.get("base_url", "http://127.0.0.1:11434/v1")
        default_model = provider_config.get("default_model", "qwen2.5-coder")
        return OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            timeout=timeout,
            supports_json_response_format=False,
            name=name,
        )

    raise ValueError(f"Unknown provider: {name}. Supported: {PROVIDERS}")
