"""Anthropic Messages API provider."""
from __future__ import annotations
import json
from .base import Provider
from .http import post_json, extract_json, json_instruction, tool_result_text
from ..models import InvocationResult, ToolCall

class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, api_key=None, base_url="https://api.anthropic.com/v1",
                 default_model="claude-sonnet-4-5", timeout=180, version="2023-06-01"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self.version = version

    def invoke(self, request):
        model = request.model or self.default_model
        content = [{"type": "text", "text": json.dumps(request.input_packet, sort_keys=True, default=str)}]
        for result in request.tool_results:
            content.append({"type": "text", "text": "TOOL_RESULT " + tool_result_text(result)})
        payload = {"model": model, "max_tokens": request.max_output_tokens, "temperature": 0,
                   "system": request.prompt + json_instruction(request.output_schema),
                   "messages": [{"role": "user", "content": content}]}
        if request.tools:
            payload["tools"] = [{"name": t["name"], "description": t.get("description", ""),
                                 "input_schema": t.get("parameters", {"type": "object"})} for t in request.tools]
        data = post_json(f"{self.base_url}/messages", payload,
                 {"x-api-key": self.api_key or "", "anthropic-version": self.version,
                  "Idempotency-Key": request.idempotency_key}, self.timeout)
        usage = data.get("usage") or {}
        calls, text = [], []
        for block in data.get("content") or []:
            if block.get("type") == "tool_use":
                calls.append(ToolCall(name=block["name"], arguments=block.get("input") or {}, call_id=block.get("id", "")))
            elif block.get("type") == "text":
                text.append(block.get("text", ""))
        output = None if calls else extract_json("".join(text))
        return InvocationResult(output=output, tool_calls=calls,
                                input_tokens=int(usage.get("input_tokens", 0)),
                                output_tokens=int(usage.get("output_tokens", 0)),
                                model=data.get("model", model))
