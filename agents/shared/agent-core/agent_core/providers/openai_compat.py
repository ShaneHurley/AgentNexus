"""OpenAI-compatible provider supporting OpenAI, OpenRouter, and local OpenAI-compatible endpoints."""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Iterator

from agent_core.providers.base import Invocation, InvocationResult, Provider, TokenUsage, ToolCall
from agent_core.providers.http import (
    ProviderError,
    extract_json,
    json_instruction,
    post_json,
    post_stream,
    tool_result_text,
)


class OpenAICompatibleProvider(Provider):
    """Provider implementation conforming to OpenAI / OpenRouter Chat Completions REST API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-4o-mini",
        timeout: float = 180.0,
        extra_headers: dict[str, str] | None = None,
        supports_json_response_format: bool = True,
        name: str = "openai",
        model_mapping: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self.extra_headers = dict(extra_headers or {})
        self.supports_json_response_format = supports_json_response_format
        self.model_mapping = dict(model_mapping or {})

    def resolve_model(self, model: str | None = None, tier: str | None = None) -> str:
        """Resolve model name through model_mapping or defaults."""
        if model and model in self.model_mapping:
            return self.model_mapping[model]
        if model and model != "unknown":
            return model
        if tier and tier in self.model_mapping:
            return self.model_mapping[tier]
        return self.default_model

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = dict(self.extra_headers)
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _build_messages(self, request: Invocation) -> list[dict[str, Any]]:
        instruction = json_instruction(request.output_schema) if request.output_schema else ""
        system_content = request.prompt + instruction
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": json.dumps(request.input_packet, sort_keys=True, default=str)
                if isinstance(request.input_packet, dict)
                else str(request.input_packet),
            },
        ]
        by_turn = defaultdict(list)
        for result in request.tool_results:
            by_turn[result.get("turn", 0)].append(result)
        for turn in sorted(by_turn):
            group = by_turn[turn]
            if group and all((item.get("call_id") or "") for item in group):
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": item["call_id"],
                                "type": "function",
                                "function": {
                                    "name": (item.get("tool") or "").replace(".", "_"),
                                    "arguments": json.dumps(item.get("arguments") or {}, default=str),
                                },
                            }
                            for item in group
                        ],
                    }
                )
                for item in group:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": item["call_id"],
                            "content": tool_result_text(item),
                        }
                    )
            else:
                for item in group:
                    messages.append({"role": "user", "content": "TOOL_RESULT " + tool_result_text(item)})
        return messages

    def invoke(self, request: Invocation) -> InvocationResult:
        """Invoke chat completion endpoint synchronously."""
        model = self.resolve_model(request.model, request.model_tier)
        messages = self._build_messages(request)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_output_tokens,
            "temperature": 0,
        }
        if request.tools:
            payload["tools"] = [
                {"type": "function", "function": dict(t, name=t.get("name", "").replace(".", "_"))}
                for t in request.tools
            ]
            payload["tool_choice"] = "auto"
        elif self.supports_json_response_format and request.output_schema:
            payload["response_format"] = {"type": "json_object"}

        headers = self._headers(request.idempotency_key)
        endpoint = f"{self.base_url}/chat/completions"

        try:
            data = post_json(endpoint, payload, headers, timeout=self.timeout)
        except ProviderError as exc:
            if "response_format" in payload and self._response_format_unsupported(exc):
                payload.pop("response_format", None)
                data = post_json(endpoint, payload, headers, timeout=self.timeout)
            else:
                raise

        reverse_map: dict[str, str] = {}
        if request.tools:
            for t in request.tools:
                name = t.get("name", "")
                reverse_map[name.replace(".", "_")] = name

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = data.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        token_usage = TokenUsage.from_counts(prompt_tokens, completion_tokens)

        calls = [
            ToolCall(
                name=reverse_map.get(c["function"]["name"], c["function"]["name"].replace("_", ".")),
                arguments=json.loads(c["function"].get("arguments") or "{}"),
                call_id=c.get("id", ""),
            )
            for c in (message.get("tool_calls") or [])
        ]

        raw_content = message.get("content") or ""
        output: dict[str, Any] | None = None
        if not calls:
            if request.output_schema:
                output = extract_json(raw_content)
            else:
                try:
                    output = extract_json(raw_content)
                except Exception:
                    output = {"raw_text": raw_content}

        return InvocationResult(
            output=output,
            tool_calls=calls,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            model=data.get("model", model),
            raw_text=raw_content,
            usage=token_usage,
        )

    def stream(self, request: Invocation) -> Iterator[str]:
        """Stream completion text tokens via SSE."""
        model = self.resolve_model(request.model, request.model_tier)
        messages = self._build_messages(request)
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_output_tokens,
            "temperature": 0,
            "stream": True,
        }
        headers = self._headers(request.idempotency_key)
        endpoint = f"{self.base_url}/chat/completions"

        for line in post_stream(endpoint, payload, headers, timeout=self.timeout):
            try:
                data = json.loads(line)
                choices = data.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield content
            except Exception:
                continue

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> str:
        """Simple direct text completion helper."""
        resolved = self.resolve_model(model)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": resolved,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = self._headers()
        endpoint = f"{self.base_url}/chat/completions"
        data = post_json(endpoint, payload, headers, timeout=self.timeout)
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        return msg.get("content") or ""

    @staticmethod
    def _response_format_unsupported(exc: ProviderError) -> bool:
        text = str(exc).lower()
        return "response_format" in text or "json_object" in text
