"""OpenAI-compatible provider.

Covers OpenAI, OpenRouter, and any OpenAI-compatible local server (Ollama, vLLM,
LM Studio) through a base URL change.
"""
from __future__ import annotations
import json
from collections import defaultdict
from .base import Provider
from .http import (post_json, extract_json, json_instruction_compact, tool_result_text,
                   ProviderError)
from ..models import InvocationResult, ToolCall

class OpenAICompatibleProvider(Provider):
    name = "openai"

    def __init__(self, api_key=None, base_url="https://api.openai.com/v1", default_model="gpt-4o-mini",
                 timeout=180, extra_headers=None, supports_json_response_format=True):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        self.supports_json_response_format = supports_json_response_format

    def _headers(self):
        headers = dict(self.extra_headers)
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_messages(self, request):
        messages = [
            {"role": "system", "content": request.prompt + json_instruction_compact(request.output_schema)},
            {"role": "user", "content": json.dumps(request.input_packet, sort_keys=True, default=str)},
        ]
        by_turn = defaultdict(list)
        for result in request.tool_results:
            by_turn[result.get("turn", 0)].append(result)
        for turn in sorted(by_turn):
            group = by_turn[turn]
            if group and all((item.get("call_id") or "") for item in group):
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": item["call_id"],
                            "type": "function",
                            "function": {
                                "name": item.get("tool") or "",
                                "arguments": json.dumps(item.get("arguments") or {}, default=str),
                            },
                        }
                        for item in group
                    ],
                })
                for item in group:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": item["call_id"],
                        "content": tool_result_text(item),
                    })
            else:
                for item in group:
                    messages.append({"role": "user", "content": "TOOL_RESULT " + tool_result_text(item)})
        return messages

    def invoke(self, request):
        model = request.model or self.default_model
        messages = self._build_messages(request)
        payload = {"model": model, "messages": messages, "max_tokens": request.max_output_tokens, "temperature": 0}
        if request.tools:
            payload["tools"] = [{"type": "function", "function": t} for t in request.tools]
            payload["tool_choice"] = "auto"
        elif self.supports_json_response_format:
            payload["response_format"] = {"type": "json_object"}
        headers = self._headers()
        headers["Idempotency-Key"] = request.idempotency_key
        try:
            data = post_json(f"{self.base_url}/chat/completions", payload, headers, self.timeout)
        except ProviderError as exc:
            if "response_format" in payload and self._response_format_unsupported(exc):
                payload.pop("response_format", None)
                data = post_json(f"{self.base_url}/chat/completions", payload, headers, self.timeout)
            else:
                raise
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = data.get("usage") or {}
        calls = [ToolCall(name=c["function"]["name"], arguments=json.loads(c["function"].get("arguments") or "{}"),
                          call_id=c.get("id", ""))
                 for c in (message.get("tool_calls") or [])]
        output = None if calls else extract_json(message.get("content"))
        return InvocationResult(output=output, tool_calls=calls,
                                input_tokens=int(usage.get("prompt_tokens", 0)),
                                output_tokens=int(usage.get("completion_tokens", 0)),
                                model=data.get("model", model))

    @staticmethod
    def _response_format_unsupported(exc: ProviderError) -> bool:
        text = str(exc).lower()
        return "response_format" in text or "json_object" in text
