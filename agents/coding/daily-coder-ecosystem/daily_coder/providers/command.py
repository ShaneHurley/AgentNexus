import json, os, shlex, subprocess
from .base import Provider
from ..models import InvocationResult, ToolCall
class CommandProvider(Provider):
    """Launches a configured executable once per role attempt."""
    name="command"
    def __init__(self,command,timeout=600): self.command=shlex.split(command); self.timeout=timeout
    def invoke(self,request):
        payload={"run_id":request.run_id,"role":request.role,"prompt":request.prompt,"input_packet":request.input_packet,
                 "model_tier":request.model_tier,"model":request.model,"max_output_tokens":request.max_output_tokens,
                 "idempotency_key":request.idempotency_key,"tools":list(request.tools),
                 "tool_results":list(request.tool_results),"turn":request.turn,"output_schema":request.output_schema}
        env={k:v for k,v in {"PATH":os.environ.get("PATH",""),"SYSTEMROOT":os.environ.get("SYSTEMROOT",""),
                     "HOME":os.environ.get("HOME",""),"PYTHONIOENCODING":"utf-8"}.items() if v}
        cp=subprocess.run(self.command,input=json.dumps(payload),capture_output=True,text=True,timeout=self.timeout,env=env)
        if cp.returncode: raise RuntimeError(f"provider failed: {cp.stderr[-2000:]}")
        obj=json.loads(cp.stdout)
        calls=[ToolCall(name=c["name"],arguments=c.get("arguments") or {},call_id=c.get("call_id","")) for c in (obj.get("tool_calls") or [])]
        return InvocationResult(output=obj.get("output") if not calls else None,tool_calls=calls,
                                input_tokens=int(obj.get("input_tokens",0)),output_tokens=int(obj.get("output_tokens",0)),
                                model=obj.get("model","command-adapter"))
