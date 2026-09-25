"""Google Gemini provider (generateContent)."""
from __future__ import annotations
import json
from .base import Provider
from .http import post_json, extract_json, json_instruction, tool_result_text
from ..models import InvocationResult, ToolCall

class GeminiProvider(Provider):
    name = "gemini"

    def __init__(self, api_key=None, base_url="https://generativelanguage.googleapis.com/v1beta",
                 default_model="gemini-2.5-flash", timeout=180):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout

    def invoke(self, request):
        model = request.model or self.default_model
        parts = [{"text": json.dumps(request.input_packet, sort_keys=True, default=str)}]
        for result in request.tool_results:
            parts.append({"text": "TOOL_RESULT " + tool_result_text(result)})
        payload = {"systemInstruction": {"parts": [{"text": request.prompt + json_instruction(request.output_schema)}]},
                   "contents": [{"role": "user", "parts": parts}],
                   "generationConfig": {"maxOutputTokens": request.max_output_tokens, "temperature": 0}}
        if request.tools:
            payload["tools"] = [{"functionDeclarations": [
                {"name": t["name"], "description": t.get("description", ""),
                 "parameters": t.get("parameters", {"type": "object"})} for t in request.tools]}]
        url = f"{self.base_url}/models/{model}:generateContent"
        data = post_json(url, payload, {"x-goog-api-key": self.api_key or ""}, self.timeout)
        candidate = (data.get("candidates") or [{}])[0]
        usage = data.get("usageMetadata") or {}
        calls, text = [], []
        for part in (candidate.get("content") or {}).get("parts") or []:
            if "functionCall" in part:
                fc = part["functionCall"]
                calls.append(ToolCall(name=fc.get("name", ""), arguments=fc.get("args") or {}))
            elif "text" in part:
                text.append(part["text"])
        output = None if calls else extract_json("".join(text))
        return InvocationResult(output=output, tool_calls=calls,
                                input_tokens=int(usage.get("promptTokenCount", 0)),
                                output_tokens=int(usage.get("candidatesTokenCount", 0)),
                                model=model)
