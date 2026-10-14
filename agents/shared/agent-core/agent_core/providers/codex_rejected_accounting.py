"""Accounting evidence for rejected role output; never execution authority."""
import hashlib,json,re
from .base import InvocationResult

def _unique(pairs):
    value={}
    for key,item in pairs:
        if key in value: raise ValueError("Duplicate JSON field")
        value[key]=item
    return value

def _constant(value): raise ValueError("Nonstandard JSON value")
def strict(value): return json.loads(value,object_pairs_hook=_unique,parse_constant=_constant)

def rejected_receipt(lines,request,parse_final,model,max_bytes,envelope_version):
    """Return usage only after validating all events and the final envelope."""
    try:
        starts={"thread.started":0,"turn.started":0}; messages=[]; events=[]
        for index,line in enumerate(lines):
            event=strict(line)
            if not isinstance(event,dict): return None
            kind=event.get("type")
            if kind in starts:
                starts[kind]+=1
                if starts[kind]!=1: return None
            elif kind in {"item.started","item.updated","item.completed"}:
                item=event.get("item")
                if not isinstance(item,dict) or item.get("type") not in {"agent_message","reasoning"}: return None
                if kind=="item.completed" and item["type"]=="agent_message":
                    if not isinstance(item.get("text"),str): return None
                    messages.append(index)
            elif kind!="turn.completed": return None
            events.append(event)
        if not messages: return None
        envelope=strict(events[messages[-1]]["item"]["text"])
        if not isinstance(envelope,dict): return None
        if isinstance(envelope.get("output_json"),str): strict(envelope["output_json"])
        for call in envelope.get("tool_calls",[]):
            if isinstance(call,dict) and isinstance(call.get("arguments_json"),str): strict(call["arguments_json"])
        removed=set(messages[:-1])
        result=parse_final([line for i,line in enumerate(lines) if i not in removed],request,model=model,max_output_bytes=max_bytes,envelope_version=envelope_version)
        if result.usage.evidence_status!="reported" or result.input_tokens is None or result.output_tokens is None: return None
        thread=next((event.get("thread_id") for event in events if event.get("type")=="thread.started"),None)
        if not isinstance(thread,str) or not re.fullmatch(r"[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}",thread): thread=None
        receipt=InvocationResult(output=None,tool_calls=[],raw_text=None,model=model,usage=result.usage,finish_reason="rejected_role_output",provider_request_id=request.idempotency_key,raw_ref="codex-thread:"+thread if thread else None)
        metadata={"schema_version":1,"run_id":request.run_id,"invocation_id":request.idempotency_key,"model":model,"reason_code":"preceding_structured","stream_sha256":hashlib.sha256("\n".join(lines).encode()).hexdigest(),"event_count":len(events),"output_bytes":sum(len(line.encode()) for line in lines),"thread_id":thread}
        return receipt,metadata
    except (ValueError,TypeError,KeyError,RecursionError): return None
    except Exception:
        # Any rejected reconstruction remains uncertain; never salvage tools.
        return None
