"""Live model provider wrapping agent_core.providers for OpenRouter / OpenAI-compatible endpoints."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from agent_core.providers.base import Invocation, Provider
from agent_core.providers.http import extract_json
from agent_core.providers.openai_compat import OpenAICompatibleProvider


class LiveModel:
    """Wraps agent_core OpenRouter/OpenAI-compatible provider with standard complete/generate API."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        api_key: str | None = None,
        model: str | None = None,
        provider: Provider | None = None,
        default_model: str = "openai/gpt-4o-mini",
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> None:
        self.config = dict(config or {})
        self.api_key = api_key
        self.model = model or default_model
        self.model_tier = self.model
        self.timeout = timeout
        self.call_count = 0

        if provider is not None:
            self.provider = provider
        else:
            pc=(self.config.get("providers") or {}).get("openrouter",{})
            self.provider = OpenAICompatibleProvider(api_key=self.api_key,base_url=pc.get("base_url","https://openrouter.ai/api/v1"),default_model=self.model,timeout=self.timeout,name="openrouter")

    def complete(self, prompt: str, task_id: str = "default", **kwargs: Any) -> dict[str, Any]:
        """Invoke provider and return standard response dictionary."""
        self.call_count += 1
        key_hash = hashlib.sha256(f"{task_id}:{prompt}".encode()).hexdigest()[:16]
        max_tokens = int(kwargs.get("max_tokens") or kwargs.get("max_output_tokens") or 4096)
        schema = kwargs.get("output_schema") or kwargs.get("schema")

        request = Invocation(
            run_id=task_id,
            role="assistant",
            prompt=prompt,
            input_packet={},
            model_tier=self.model_tier,
            max_output_tokens=max_tokens,
            idempotency_key=f"{task_id}:{key_hash}",
            model=self.model,
            output_schema=schema,
        )

        res = self.provider.invoke(request)

        # Determine response text
        text = res.raw_text or ""
        if not text and isinstance(res.output, dict):
            if "raw_text" in res.output:
                text = str(res.output["raw_text"])
            else:
                text = json.dumps(res.output)
        elif not text and res.output is not None:
            text = str(res.output)

        prompt_tokens = res.input_tokens
        completion_tokens = res.output_tokens
        if res.usage:
            prompt_tokens = res.usage.input_tokens if prompt_tokens is None else prompt_tokens
            completion_tokens = res.usage.output_tokens if completion_tokens is None else completion_tokens

        return {
            "text": text,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost_usd": res.usage.cost_usd if res.usage else None,
                "evidence_status": res.usage.evidence_status if res.usage else "unknown",
                "cached_tokens": res.usage.cached_tokens if res.usage else None,
                "provider_request_id": res.provider_request_id,
            },
            "model_tier": res.model or self.model,
            "output": res.output,
        }

    def generate(self, prompt: str, task_id: str = "default", **kwargs: Any) -> str:
        """Return plain text response for prompt."""
        result = self.complete(prompt, task_id=task_id, **kwargs)
        return str(result.get("text") or "")

    def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any] | None = None,
        task_id: str = "default",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate structured response conforming to schema (JSON dictionary)."""
        result = self.complete(prompt, task_id=task_id, output_schema=schema, **kwargs)
        out = result.get("output")
        if isinstance(out, dict) and (not schema or set(out.keys()) != {"raw_text"}):
            return out
        text = str(result.get("text") or "")
        return extract_json(text)
