"""Native Anthropic Messages API with tool IDs and cache usage preserved."""
from __future__ import annotations
import json
from collections import defaultdict
from agent_core.providers.base import InvocationResult, ToolCall, TokenUsage, ProviderCapabilities, StreamEvent
from agent_core.providers.openai_compat import OpenAICompatibleProvider
from agent_core.providers.http import post_json, post_stream, extract_json, json_instruction, ProviderError

class AnthropicProvider(OpenAICompatibleProvider):
    name="anthropic"
    def __init__(self,api_key=None,base_url="https://api.anthropic.com/v1",default_model="claude-sonnet-4-5",timeout=180,version="2023-06-01",**kwargs):
        super().__init__(api_key,base_url,default_model,timeout,name="anthropic",**kwargs)
        self.version=version
        self.capabilities=ProviderCapabilities(tools=True,streaming=True)

    def _payload(self,request):
        messages=[{"role":"user","content":[{"type":"text","text":json.dumps(request.input_packet,sort_keys=True,default=str)}]}]
        turns=defaultdict(list)
        for item in request.tool_results: turns[item.get("turn",0)].append(item)
        for turn in sorted(turns):
            group=turns[turn]
            if not all(item.get("call_id") for item in group):
                raise ProviderError("native tool result requires call ID",category="request",remote_acceptance="rejected")
            messages.append({"role":"assistant","content":[{"type":"tool_use","id":item["call_id"],"name":item.get("tool", ""),"input":item.get("arguments") or {}} for item in group]})
            messages.append({"role":"user","content":[{"type":"tool_result","tool_use_id":item["call_id"],"content":json.dumps(item.get("result",item),default=str)} for item in group]})
        payload={"model":self.resolve_model(request.model,request.model_tier),"max_tokens":request.max_output_tokens,"system":request.prompt+(json_instruction(request.output_schema) if request.output_schema else ""),"messages":messages}
        if request.tools:
            payload["tools"]=[{"name":t["name"],"description":t.get("description",""),"input_schema":t.get("parameters",{"type":"object"})} for t in request.tools]
        return payload

    def _native_headers(self,request,value):
        return {"x-api-key":value or "","anthropic-version":self.version,"Idempotency-Key":request.idempotency_key}

    def _usage(self,u):
        uncached=u.get("input_tokens")
        cached=u.get("cache_read_input_tokens")
        created=u.get("cache_creation_input_tokens")
        # Native input_tokens excludes both cache categories. Absent cache
        # counters mean no cache accounting was reported for this response.
        input_count=uncached+(cached or 0)+(created or 0) if uncached is not None else None
        output_count=u.get("output_tokens")
        return TokenUsage(input_count,output_count,(input_count+output_count) if input_count is not None and output_count is not None else None,None,
            cached_tokens=cached,cache_creation_tokens=created,evidence_status="reported" if u else "unknown")

    def _invoke(self,request,value):
        payload=self._payload(request)
        data=post_json(self.base_url+"/messages",payload,self._native_headers(request,value),timeout=self.timeout,retries=request.max_transport_retries,deadline=request.deadline)
        calls=[];texts=[]
        for block in data.get("content") or []:
            if block.get("type")=="tool_use": calls.append(ToolCall(block["name"],block.get("input") or {},block.get("id","")))
            elif block.get("type")=="text": texts.append(block.get("text", ""))
        text="".join(texts)
        if calls: output=None
        elif request.output_schema: output=extract_json(text)
        else:
            try: output=extract_json(text)
            except ProviderError: output={"raw_text":text}
        return InvocationResult(output=output,tool_calls=calls,model=data.get("model",payload["model"]),raw_text=text,usage=self._usage(data.get("usage") or {}),provider_request_id=data.get("id"),finish_reason=data.get("stop_reason"))

    def _stream_events(self,request,value):
        payload=self._payload(request);payload["stream"]=True
        calls={};request_id=None;usage={}
        for line in post_stream(self.base_url+"/messages",payload,self._native_headers(request,value),timeout=self.timeout,deadline=request.deadline):
            try: data=json.loads(line)
            except ValueError: continue
            kind=data.get("type")
            if kind=="error": raise ProviderError("native provider stream error")
            if kind=="message_start":
                message=data.get("message") or {}; request_id=message.get("id");usage.update(message.get("usage") or {})
            elif kind=="content_block_start":
                block=data.get("content_block") or {}
                if block.get("type")=="tool_use": calls[data["index"]]={"id":block["id"],"name":block["name"],"arguments":"","input":block.get("input") or {}}
            elif kind=="content_block_delta":
                delta=data.get("delta") or {}
                if delta.get("type")=="text_delta": yield StreamEvent("text",text=delta.get("text"),provider_request_id=request_id)
                elif delta.get("type")=="input_json_delta":
                    calls[data["index"]]["arguments"]+=delta.get("partial_json","")
                    if len(calls)>128 or len(calls[data["index"]]["arguments"])>1_000_000:
                        raise ProviderError("native streamed tool accumulator exceeds ceiling")
            elif kind=="content_block_stop" and data["index"] in calls:
                call=calls.pop(data["index"])
                try: arguments=json.loads(call["arguments"]) if call["arguments"] else call["input"]
                except ValueError: raise ProviderError("malformed native streamed tool arguments") from None
                yield StreamEvent("tool_call",tool_call=ToolCall(call["name"],arguments,call["id"]),provider_request_id=request_id)
            elif kind=="message_delta":
                usage.update(data.get("usage") or {})
                yield StreamEvent("usage",usage=self._usage(usage),provider_request_id=request_id)
                yield StreamEvent("finish",finish_reason=(data.get("delta") or {}).get("stop_reason"),provider_request_id=request_id)
