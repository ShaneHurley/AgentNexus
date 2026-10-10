"""OpenAI-compatible provider supporting OpenAI, OpenRouter, and local OpenAI-compatible endpoints."""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Iterator

from agent_core.providers.base import Invocation, InvocationResult, Provider, TokenUsage, ToolCall, ProviderCapabilities, StreamEvent
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
        secret_broker=None,
        secret_grant_factory=None,
        credential_ref: str | None = None,
    ) -> None:
        self.secret_broker = secret_broker
        self.secret_grant_factory = secret_grant_factory
        self.credential_ref = credential_ref
        self.capabilities = ProviderCapabilities(tools=True, json_schema=False, streaming=True)
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

    def _authorized(self, request, operation, *, streaming=False):
        if request.tools and not self.capabilities.tools:
            raise ProviderError("tool calls unsupported",category="capability",remote_acceptance="rejected")
        if request.output_schema and request.provider_options.get("require_json_schema") and not self.capabilities.json_schema:
            raise ProviderError("JSON schema unsupported",category="capability",remote_acceptance="rejected")
        if self.secret_broker is not None:
            if self.secret_grant_factory is None:
                raise ProviderError("secret use grant required",category="authorization",remote_acceptance="rejected")
            ref=request.credential_ref or self.credential_ref
            grant=self.secret_grant_factory(request)
            if self.api_key is not None:
                raise ProviderError("supervised raw credential denied",category="authorization",remote_acceptance="rejected")
            if grant.ref != ref or grant.task_id != request.run_id or grant.caller != "dc:"+request.role:
                raise ProviderError("secret use identity denied",category="authorization",remote_acceptance="rejected")
            return self.secret_broker.stream_use(grant,operation) if streaming else self.secret_broker.use(grant,operation)
        if self.name != "local" and not self.api_key:
            raise ProviderError("provider credential unavailable",category="authorization",remote_acceptance="rejected")
        return operation(self.api_key)

    def invoke(self, request: Invocation) -> InvocationResult:
        return self._authorized(request,lambda value:self._invoke(request,value))

    def _invoke(self, request: Invocation, value) -> InvocationResult:
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

        if self.name == "openrouter":
            options=dict(request.provider_options.get("provider") or {})
            options.update(require_parameters=True,data_collection="deny",zdr=True)
            payload["provider"]=options
        headers = dict(self.extra_headers)
        if value:
            headers["Authorization"] = "Bearer "+value
        headers["Idempotency-Key"]=request.idempotency_key
        endpoint = f"{self.base_url}/chat/completions"
        data = post_json(endpoint,payload,headers,timeout=self.timeout,retries=request.max_transport_retries,deadline=request.deadline)

        reverse_map: dict[str, str] = {}
        if request.tools:
            for t in request.tools:
                name = t.get("name", "")
                reverse_map[name.replace(".", "_")] = name

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = data.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        token_usage = TokenUsage(input_tokens=prompt_tokens,output_tokens=completion_tokens,
            total_tokens=usage.get("total_tokens"),cost_usd=usage.get("cost"),
            cached_tokens=(usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
            reasoning_tokens=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
            evidence_status="reported" if usage else "unknown")
        if self.name=="local":
            token_usage.cost_usd=0.0
            token_usage.evidence_status="reported"

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
            provider_request_id=data.get("id"),
            finish_reason=choice.get("finish_reason"),
        )

    def stream_events(self,request):
        return self._authorized(request,lambda value:self._stream_events(request,value),streaming=True)

    def _stream_events(self,request,value):
        payload={"model":self.resolve_model(request.model,request.model_tier),"messages":self._build_messages(request),
            "max_tokens":request.max_output_tokens,"stream":True,"stream_options":{"include_usage":True}}
        if request.tools:
            payload["tools"]=[{"type":"function","function":dict(t,name=t["name"].replace(".","_"))} for t in request.tools]
        if self.name=="openrouter":
            payload["provider"]={**(request.provider_options.get("provider") or {}),"require_parameters":True,"data_collection":"deny","zdr":True}
        headers=dict(self.extra_headers)
        if value: headers["Authorization"]="Bearer "+value
        headers["Idempotency-Key"]=request.idempotency_key
        calls={}
        for line in post_stream(f"{self.base_url}/chat/completions",payload,headers,timeout=self.timeout,deadline=request.deadline):
            try: data=json.loads(line)
            except ValueError: continue
            if "error" in data: raise ProviderError("provider stream error")
            request_id=data.get("id")
            if data.get("usage"):
                u=data["usage"]
                yield StreamEvent("usage",usage=TokenUsage(input_tokens=u.get("prompt_tokens"),output_tokens=u.get("completion_tokens"),total_tokens=u.get("total_tokens"),cost_usd=u.get("cost"),cached_tokens=(u.get("prompt_tokens_details") or {}).get("cached_tokens"),reasoning_tokens=(u.get("completion_tokens_details") or {}).get("reasoning_tokens"),evidence_status="reported"),provider_request_id=request_id)
            for choice in data.get("choices") or []:
                delta=choice.get("delta") or {}
                if delta.get("content"): yield StreamEvent("text",text=delta["content"],provider_request_id=request_id)
                for item in delta.get("tool_calls") or []:
                    current=calls.setdefault(item["index"],{"id":"","name":"","arguments":""})
                    current["id"]+=item.get("id") or ""
                    function=item.get("function") or {}
                    current["name"]+=function.get("name") or ""
                    current["arguments"]+=function.get("arguments") or ""
                    if len(calls)>128 or len(current["arguments"])>1_000_000 or len(current["name"])>512 or len(current["id"])>512:
                        raise ProviderError("streamed tool accumulator exceeds ceiling")
                if choice.get("finish_reason"):
                    reverse={t["name"].replace(".","_"):t["name"] for t in request.tools}
                    for current in calls.values():
                        try: arguments=json.loads(current["arguments"] or "{}")
                        except ValueError: raise ProviderError("malformed streamed tool arguments") from None
                        yield StreamEvent("tool_call",tool_call=ToolCall(reverse.get(current["name"],current["name"]),arguments,current["id"]),provider_request_id=request_id)
                    calls.clear()
                    yield StreamEvent("finish",finish_reason=choice["finish_reason"],provider_request_id=request_id)

    def stream(self,request):
        for event in self.stream_events(request):
            if event.type=="text": yield event.text

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
        if self.secret_broker is not None:
            raise ProviderError("supervised completion requires Invocation",category="authorization",remote_acceptance="rejected")
        if self.name != "local" and not self.api_key:
            raise ProviderError("provider credential unavailable",category="authorization",remote_acceptance="rejected")
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
        if self.name=="openrouter":
            payload["provider"]={"require_parameters":True,"data_collection":"deny","zdr":True}
        data = post_json(endpoint, payload, headers, timeout=self.timeout)
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        return msg.get("content") or ""

    @staticmethod
    def _response_format_unsupported(exc: ProviderError) -> bool:
        text = str(exc).lower()
        return "response_format" in text or "json_object" in text
