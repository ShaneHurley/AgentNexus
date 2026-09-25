"""HTTP bridge provider.

Lets an external agent framework (LangGraph, Microsoft Agent Framework, CrewAI, ADK,
a coding CLI, or an MCP-backed service) act as a role runtime. The wire format is the
same JSON contract as the command provider, so one adapter satisfies both transports.
"""
from __future__ import annotations
import json
from .base import Provider
from .http import post_json
from ..models import InvocationResult, ToolCall

class HttpBridgeProvider(Provider):
    name = "http"

    def __init__(self, endpoint, token=None, timeout=600):
        self.endpoint = endpoint
        self.token = token
        self.timeout = timeout

    def invoke(self, request):
        payload = {"run_id": request.run_id, "role": request.role, "prompt": request.prompt,
                   "input_packet": request.input_packet, "model_tier": request.model_tier,
                   "model": request.model, "max_output_tokens": request.max_output_tokens,
                   "idempotency_key": request.idempotency_key, "tools": list(request.tools),
                   "tool_results": list(request.tool_results), "turn": request.turn,
                   "output_schema": request.output_schema}
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        data = post_json(self.endpoint, payload, headers, self.timeout, retries=2)
        calls = [ToolCall(name=c["name"], arguments=c.get("arguments") or {}, call_id=c.get("call_id", ""))
                 for c in (data.get("tool_calls") or [])]
        return InvocationResult(output=data.get("output") if not calls else None, tool_calls=calls,
                                input_tokens=int(data.get("input_tokens", 0)),
                                output_tokens=int(data.get("output_tokens", 0)),
                                model=data.get("model", "http-bridge"))
