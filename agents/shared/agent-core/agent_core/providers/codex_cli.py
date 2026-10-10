"""Codex CLI v1 compatibility diagnostics and offline response contract.

Only the pinned executable/catalog and reviewed tool-free settings may dispatch.
Offline loopback tests proved tools absent and hallucinated native exec denied.
Unpinned adapters fail before spawn. max_output_tokens is advisory: this CLI
cannot enforce a remote generation token cap. Deadline/outputbytes are local
ceilings; local cancellation does not prove remote cancellation.

Evidence: codex-cli 0.162.0-alpha.2 exec --help, generated ThreadStartParams and
TurnStartParams; official config reference and first-party core tool registry:
https://developers.openai.com/codex/config-reference
https://developers.openai.com/codex/app-server
https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/spec_plan.rs
Disabling ShellTool only gates add_shell_tools; add_core_utility_tools registers
ApplyPatchHandler independently. Dynamic tools extend the core registry.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import tempfile
import time
import threading
from dataclasses import dataclass
from agent_core.providers.base import Invocation,InvocationResult,Provider,ProviderCapabilities,TokenUsage,ToolCall
from agent_core.providers.http import ProviderError

CLI_VERSION="codex-cli 0.162.0-alpha.2"
ENVELOPE_VERSION="anx_codex_role_v1"
ADAPTER_VERSION=1
BLOCKER="Codex native tool denial and inherited configuration isolation are unverified; supervised invocation disabled"
MAX_OUTPUT_BYTES=1_000_000
MAX_EVENTS=10_000
DISABLED_FEATURES=('agent_message_board', 'analytics_plan_history', 'api_key_cyber_access_programs', 'api_key_model_discovery', 'apply_patch_preserve_line_endings', 'apply_patch_streaming_events', 'apps', 'artifact', 'auth_elicitation', 'background_paginated_rollout_migration', 'bedrock_setup_wizard', 'browser_annotation_api', 'browser_use', 'browser_use_external', 'browser_use_full_cdp_access', 'chronicle', 'code_mode', 'code_mode_host', 'code_mode_interrupt', 'code_mode_only', 'code_mode_prewarm', 'codex_apps_mcp_2026_07_28', 'compaction_image_budget', 'computer_use', 'concurrent_reasoning_summaries', 'content_item_kinds', 'context_management', 'current_time_reminder', 'cwd_relative_turn_diffs', 'daemon_auto_start', 'default_mode_request_user_input', 'defer_mailbox_preemption', 'deferred_executor', 'deferred_tool_world_state', 'enable_mcp_apps', 'enable_request_compression', 'exec_permission_approvals', 'executed_tool_call_metadata', 'executor_capability_discovery', 'external_agent_memory_import', 'fast_mode', 'goals', 'guardian_approval', 'guardian_conversation_history_tools', 'guardian_enhanced_node_repl_transcripts', 'guardian_node_repl_transcript_images', 'guardian_reuse_parent_compaction', 'guardian_root_handoff_context', 'guardianv2', 'guardianv2_decisions_comparison', 'hooks', 'image_generation', 'image_resize_notice', 'in_app_browser', 'in_app_chat', 'in_app_dictation', 'in_app_local_automation', 'in_app_updates', 'in_app_voice', 'instant_interrupt', 'local_thread_store_compression', 'login_shell_package_path', 'mcp_2026_07_28', 'mcp_oauth_refresh_coordination', 'memories', 'mentions_v2', 'model_catalog_in_context', 'multi_agent', 'multi_agent_v2', 'multi_agent_v2_dynamic_tools', 'network_proxy', 'non_prefixed_mcp_tool_names', 'nonfatal_clock_read_errors', 'omit_app_server_notification_media', 'plugin_sharing', 'plugins', 'powershell_shell_version', 'prefer_mxc', 'prevent_idle_sleep', 'psp', 'realtime_conversation', 'reasoning_effort_override', 'recommended_plugins', 'remote_plugin', 'request_permissions_tool', 'respect_system_proxy', 'retain_client_developer_messages', 'rollout_budget', 'runtime_metrics', 'secret_auth_storage', 'send_message_to_user_async', 'shell_snapshot', 'shell_snapshot_v2', 'shell_tool', 'shell_zsh_fork', 'skill_mcp_dependency_install', 'skill_search', 'sleep_tool', 'standalone_web_search', 'step_model_switching', 'system_proxy_fallback', 'terminal_visualization_instructions', 'token_budget', 'tool_call_mcp_elicitation', 'tool_suggest', 'unbounded_connection_retries', 'unified_exec', 'unified_exec_tty', 'unified_image_budget', 'use_agent_identity', 'use_xaa', 'view_image', 'windows_sandbox_service', 'workspace_dependencies', 'worktrees', 'write_stdin_approval')
_DISPATCH_LOCK=threading.Lock()

@dataclass(frozen=True)
class CodexDiagnostics:
    adapter_version: int
    expected_version: str
    version_matches: bool
    chatgpt_login: bool
    executable_sha256: str
    model: str
    supervised_ready: bool = False
    blocker: str = BLOCKER

def _failure(message="Codex response contract failed",category="response",acceptance="unknown"):
    return ProviderError(message,category=category,remote_acceptance=acceptance,retryable=False)

def _process_failure(code, stdout, stderr):
    # Classification is diagnostic only. A textual error does not establish
    # whether a remote request was accepted; retain uncertainty and no retries.
    text=(stdout+b"\n"+stderr).decode("utf-8",errors="replace").lower()
    category="transport"
    for candidate,markers in (
        ("account_limit",("usage limit","usage_limit","quota exceeded","rate limit")),
        ("authorization",("invalid api key","authentication failed","not logged in","unauthorized")),
        ("configuration",("invalid schema","invalid config","unknown config","unrecognized argument")),
    ):
        if any(marker in text for marker in markers):
            category=candidate
            break
    error=_failure("Codex process failed: "+category,category=category)
    error.diagnostics={"exit_code":code,"category":category,"output_sha256":hashlib.sha256(stdout+b"\0"+stderr).hexdigest(),"output_bytes":len(stdout)+len(stderr)}
    return error

def parse_codex_jsonl(lines,request: Invocation,*,model: str,max_output_bytes=MAX_OUTPUT_BYTES):
    """Offline only: decode a completed tool-request envelope, never execute it."""
    if not isinstance(max_output_bytes,int) or not 0<max_output_bytes<=MAX_OUTPUT_BYTES:
        raise ValueError("invalid Codex output ceiling")
    if not model or request.model not in ("unknown",model):
        raise _failure("Codex model pin mismatch",category="configuration",acceptance="rejected")
    total=0;complete=False;message=None;usage=None;thread_id=None
    for number,line in enumerate(lines):
        if not isinstance(line,str): raise _failure()
        total+=len(line.encode("utf-8"))
        if total>max_output_bytes or number>=MAX_EVENTS: raise _failure("Codex output ceiling exceeded")
        try: event=json.loads(line)
        except (ValueError,TypeError): raise _failure() from None
        if not isinstance(event,dict): raise _failure()
        kind=event.get("type")
        if kind in {"error","turn.failed"}: raise _failure("Codex turn failed")
        if complete: raise _failure("Codex events followed terminal completion")
        if kind=="thread.started":
            candidate=event.get("thread_id")
            if not isinstance(candidate,str) or len(candidate)>128: raise _failure()
            thread_id=candidate
        elif kind=="turn.started": pass
        elif kind in {"item.started","item.updated","item.completed"}:
            item=event.get("item")
            if not isinstance(item,dict): raise _failure()
            if item.get("type") not in {"agent_message","reasoning"}:
                raise _failure("Codex native tool event denied",category="security")
            if kind=="item.completed" and item.get("type")=="agent_message":
                if message is not None or not isinstance(item.get("text"),str): raise _failure()
                message=item["text"]
        elif kind=="turn.completed":
            complete=True;usage=event.get("usage")
            if usage is not None and not isinstance(usage,dict): raise _failure()
        else: raise _failure("Codex event version unsupported")
    if not complete or message is None: raise _failure("Codex completion evidence missing")
    try: envelope=json.loads(message)
    except ValueError: raise _failure() from None
    if not isinstance(envelope,dict) or set(envelope)!={"version","output","tool_calls"} or envelope["version"]!=ENVELOPE_VERSION:
        raise _failure("Codex role envelope version unsupported")
    output=envelope["output"];calls=envelope["tool_calls"]
    if output is not None and not isinstance(output,dict): raise _failure()
    if not isinstance(calls,list) or len(calls)>128 or (output is None and not calls): raise _failure()
    allowed={item["name"] for item in request.tools};seen=set();parsed=[]
    for call in calls:
        if not isinstance(call,dict) or set(call)!={"name","arguments","call_id"}: raise _failure()
        if call["name"] not in allowed or not isinstance(call["arguments"],dict) or not isinstance(call["call_id"],str) or not 0<len(call["call_id"])<=128 or call["call_id"] in seen:
            raise _failure("Codex tool request outside invocation contract")
        seen.add(call["call_id"]);parsed.append(ToolCall(call["name"],call["arguments"],call["call_id"]))
    if parsed and output is not None: raise _failure("Codex envelope has contradictory outcomes")
    if output is not None and request.output_schema:
        try:
            import jsonschema
            jsonschema.validate(output,request.output_schema)
        except Exception: raise _failure("Codex structured role output invalid") from None
    u=usage or {}
    try:
        tokens=TokenUsage(input_tokens=u.get("input_tokens"),output_tokens=u.get("output_tokens"),cached_tokens=u.get("cached_input_tokens"),cache_creation_tokens=u.get("cache_write_input_tokens"),reasoning_tokens=u.get("reasoning_output_tokens"),cost_usd=None,evidence_status="reported" if usage else "unknown")
    except (ValueError,TypeError): raise _failure("Codex usage invalid") from None
    return InvocationResult(output=output,tool_calls=parsed,model=model,usage=tokens,raw_ref="codex-thread:"+thread_id if thread_id else None,finish_reason="tool_calls" if parsed else "stop")

class CodexCLIProvider(Provider):
    """Version-pinned inference-only Codex transport; returned tools are requests."""
    name="codex_cli"
    capabilities=ProviderCapabilities()
    def __init__(self,*,executable,expected_version=CLI_VERSION,model,expected_executable_sha256=None,catalog_path=None,expected_catalog_sha256=None,reasoning_effort="medium",timeout=60.0,probe_timeout=5.0,max_probe_bytes=16_384):
        path=Path(executable)
        if not path.is_absolute() or not path.is_file() or not os.access(path,os.X_OK): raise ValueError("Codex executable must be an absolute executable file")
        if expected_version!=CLI_VERSION or not isinstance(model,str) or not model.strip(): raise ValueError("unsupported Codex version or missing model pin")
        if not math.isfinite(probe_timeout) or not 0<probe_timeout<=30 or not isinstance(max_probe_bytes,int) or not 0<max_probe_bytes<=16_384:
            raise ValueError("invalid Codex diagnostic budget")
        self.executable=str(path.resolve());self.expected_version=expected_version;self.model=model
        if reasoning_effort not in {"low","medium","high","xhigh","max","ultra"} or not math.isfinite(timeout) or not 0<timeout<=60:
            raise ValueError("invalid pinned reasoning or deadline")
        self.expected_executable_sha256=expected_executable_sha256;self.probe_timeout=probe_timeout;self.max_probe_bytes=max_probe_bytes
        self.catalog_path=Path(catalog_path) if catalog_path is not None else None
        self.expected_catalog_sha256=expected_catalog_sha256;self.reasoning_effort=reasoning_effort;self.timeout=timeout
        self._active={};self._active_lock=threading.Lock()
        if catalog_path is not None and expected_catalog_sha256 and expected_executable_sha256:
            self.capabilities=ProviderCapabilities(tools=True,json_schema=True,cancellation=True)

    def _pins(self):
        if self.catalog_path is None or not self.catalog_path.is_absolute() or not self.expected_catalog_sha256 or not self.expected_executable_sha256:
            raise _failure(BLOCKER,category="security",acceptance="rejected")
        try:
            data=self.catalog_path.read_bytes()
            if len(data)>1_000_000 or hashlib.sha256(data).hexdigest()!=self.expected_catalog_sha256:
                raise ValueError()
            catalog=json.loads(data)
            rows=catalog["models"]
            if len(rows)!=1 or rows[0]["slug"]!=self.model: raise ValueError()
            required={"shell_type":"disabled","apply_patch_tool_type":None,"node_repl_disabled":True,"tool_mode":"direct","experimental_supported_tools":[],"supports_search_tool":False,"include_skills_usage_instructions":False,"include_plugin_usage_instructions":False,"include_apps_usage_instructions":False}
            if any(key not in rows[0] or rows[0][key]!=value for key,value in required.items()): raise ValueError()
            if hashlib.sha256(Path(self.executable).read_bytes()).hexdigest()!=self.expected_executable_sha256: raise ValueError()
        except (OSError,ValueError,TypeError,KeyError):
            raise _failure("Codex executable or model catalog pin invalid",category="configuration",acceptance="rejected") from None
        return data

    def security_settings(self):
        return {"features":{**{name:False for name in DISABLED_FEATURES},"skip_host_skill_discovery":True},
            "suppress_unstable_features_warning":True,"model":self.model,"model_reasoning_effort":self.reasoning_effort,
            "model_provider":"openai","mcp_servers":{},"plugins":{},"apps":{"_default":{"enabled":False}},
            "web_search":"disabled","tools":{"update_plan":{"enabled":False},"experimental_request_user_input":{"enabled":False}},
            "project_doc_max_bytes":0,"forced_login_method":"chatgpt","cli_auth_credentials_store":"auto","history":{"persistence":"none"}}

    @property
    def security_config_sha256(self):
        return hashlib.sha256(json.dumps({"settings":self.security_settings(),"catalog_sha256":self.expected_catalog_sha256,"executable_sha256":self.expected_executable_sha256,"version":self.expected_version},sort_keys=True,separators=(",",":")).encode()).hexdigest()

    @staticmethod
    def _toml(value):
        if isinstance(value,dict): return "{"+",".join(json.dumps(k)+"="+CodexCLIProvider._toml(v) for k,v in value.items())+"}"
        return json.dumps(value)

    def _schema(self,request):
        options=[]
        for tool in request.tools:
            options.append({"type":"object","properties":{"name":{"type":"string","enum":[tool["name"]]},"arguments":tool.get("parameters",{"type":"object","properties":{},"additionalProperties":False}),"call_id":{"type":"string"}},"required":["name","arguments","call_id"],"additionalProperties":False})
        output=request.output_schema or {"type":"object","properties":{"raw_text":{"type":"string"}},"required":["raw_text"],"additionalProperties":False}
        return {"type":"object","properties":{"version":{"type":"string","enum":[ENVELOPE_VERSION]},"output":{"anyOf":[output,{"type":"null"}]},"tool_calls":{"type":"array","items":{"anyOf":options} if options else {"type":"object","properties":{},"additionalProperties":False},"maxItems":128 if options else 0}},"required":["version","output","tool_calls"],"additionalProperties":False}

    def invoke(self,request):
        catalog=self._pins()
        if request.model not in ("unknown",self.model) or request.provider_options or request.max_transport_retries:
            raise _failure("Codex invocation overrides or retries denied",category="configuration",acceptance="rejected")
        end=min(time.time()+self.timeout,request.deadline if request.deadline is not None else float("inf"))
        if end<=time.time(): raise _failure("Codex deadline exhausted",category="deadline",acceptance="rejected")
        if not _DISPATCH_LOCK.acquire(blocking=False):
            raise _failure("Codex invocation concurrency ceiling exceeded",category="budget",acceptance="rejected")
        try:
            diagnostics=self.diagnostics(deadline=end)
            if not diagnostics.supervised_ready:
                raise _failure("Codex pinned ChatGPT login unavailable",category="authorization",acceptance="rejected")
            with tempfile.TemporaryDirectory(prefix="anx-codex-call-") as directory:
                cwd=Path(directory)
                (cwd/"catalog.json").write_bytes(catalog)
                (cwd/"output.schema.json").write_text(json.dumps(self._schema(request)))
                settings=self.security_settings()
                settings.update(model_catalog_json=str(cwd/"catalog.json"),sqlite_home=str(cwd/"sqlite"),log_dir=str(cwd/"logs"))
                args=["exec","--ignore-user-config","--ignore-rules","--strict-config","--ephemeral","--skip-git-repo-check","--sandbox","read-only","--json","--color","never","--model",self.model,"--output-schema",str(cwd/"output.schema.json")]
                for key,value in settings.items(): args.extend(["-c",key+"="+self._toml(value)])
                args.append("-")
                prompt=json.dumps({"envelope_version":ENVELOPE_VERSION,"role":request.role,"instructions":request.prompt,"input_packet":request.input_packet,"tool_results":request.tool_results,"allowed_tool_requests":request.tools,"max_output_tokens_advisory":request.max_output_tokens,"instructions_for_tools":"Return tool requests in the JSON envelope; native tools are unavailable."},sort_keys=True)
                if len(prompt.encode())>1_000_000: raise _failure("Codex prompt ceiling exceeded",category="budget",acceptance="rejected")
                code,out,err=self._run(tuple(args),input_text=prompt,cwd=str(cwd),deadline=end,max_bytes=MAX_OUTPUT_BYTES,key=request.idempotency_key)
                if code!=0: raise _process_failure(code,out,err)
                try: lines=out.decode("utf-8").splitlines()
                except UnicodeError: raise _failure() from None
                result=parse_codex_jsonl(lines,request,model=self.model)
                result.cancellation_status="not_requested"
                return result
        finally: _DISPATCH_LOCK.release()

    def cancel(self,request_id):
        with self._active_lock:
            entry=self._active.get(request_id)
            if entry is None:return "unknown"
            process,cancelled=entry;cancelled.set();self._terminate(process)
        return "local_terminated_remote_unknown"

    @staticmethod
    def _terminate(process):
        # Signal the entire group even if its original leader has already exited.
        try: os.killpg(process.pid,signal.SIGKILL)
        except (ProcessLookupError,PermissionError):
            # A concurrent canceller may have already reaped the group leader.
            # Never let cleanup replace the sanitized cancellation outcome.
            if process.poll() is None:
                try:process.kill()
                except (ProcessLookupError,PermissionError):pass
        try: process.wait(timeout=1)
        except subprocess.TimeoutExpired: pass

    def _run(self,args,*,input_text=None,cwd=None,deadline,max_bytes,key=None):
        allowed_env={key:value for key,value in os.environ.items() if key in {"HOME","CODEX_HOME","USER","LOGNAME","PATH","TMPDIR","LANG"}}
        process=None;chunks={"stdout":bytearray(),"stderr":bytearray()};cancelled=threading.Event()
        source=tempfile.TemporaryFile()
        if input_text is not None: source.write(input_text.encode());source.seek(0)
        try:
            remaining=deadline-time.time()
            if remaining<=0: raise _failure("Codex deadline exhausted",category="deadline",acceptance="rejected")
            process=subprocess.Popen([self.executable,*args],stdin=source,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=cwd,env=allowed_env,start_new_session=True)
            if key is not None:
                with self._active_lock:self._active[key]=(process,cancelled)
            with selectors.DefaultSelector() as selector:
                for name in chunks: selector.register(getattr(process,name),selectors.EVENT_READ,name)
                while selector.get_map():
                    remaining=deadline-time.time()
                    if cancelled.is_set():raise _failure("Codex locally cancelled; remote status unknown",category="cancelled")
                    if remaining<=0:raise _failure("Codex process deadline exceeded",category="deadline",acceptance="unknown" if key is not None else "rejected")
                    for entry,_ in selector.select(min(remaining,.05)):
                        data=os.read(entry.fileobj.fileno(),4096)
                        if not data:selector.unregister(entry.fileobj);continue
                        chunks[entry.data].extend(data)
                        if sum(map(len,chunks.values()))>max_bytes:raise _failure("Codex output ceiling exceeded",category="budget",acceptance="unknown" if key is not None else "rejected")
                if cancelled.is_set():raise _failure("Codex locally cancelled; remote status unknown",category="cancelled")
                remaining=deadline-time.time()
                if remaining<=0:raise _failure("Codex process deadline exceeded",category="deadline",acceptance="unknown" if key is not None else "rejected")
                try:code=process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:raise _failure("Codex process deadline exceeded",category="deadline",acceptance="unknown" if key is not None else "rejected") from None
                return code,bytes(chunks["stdout"]),bytes(chunks["stderr"])
        except OSError:raise _failure("Codex process unavailable",category="transport",acceptance="unknown" if key is not None else "rejected") from None
        finally:
            source.close()
            if process is not None:
                self._terminate(process)
                for stream in (process.stdout,process.stderr):
                    if stream is not None:stream.close()
            if key is not None:
                with self._active_lock:self._active.pop(key,None)

    def _probe(self,args,deadline=None):
        if args not in (("--version",),("login","status")):raise ValueError("unsupported Codex diagnostic operation")
        end=min(time.time()+self.probe_timeout,deadline if deadline is not None else float("inf"))
        with tempfile.TemporaryDirectory(prefix="anx-codex-probe-") as cwd:
            return self._run(args,cwd=cwd,deadline=end,max_bytes=self.max_probe_bytes)

    def diagnostics(self,deadline=None):
        digest=hashlib.sha256(Path(self.executable).read_bytes()).hexdigest()
        if self.expected_executable_sha256 is not None and digest!=self.expected_executable_sha256:
            raise _failure("Codex executable pin mismatch",category="configuration",acceptance="rejected")
        code,out,err=self._probe(("--version",),deadline)
        matches=code==0 and out.decode("utf-8",errors="replace").strip()==self.expected_version
        if not matches:
            return CodexDiagnostics(ADAPTER_VERSION,self.expected_version,False,False,digest,self.model)
        code,out,err=self._probe(("login","status"),deadline)
        login=code==0 and (out+err).decode("utf-8",errors="replace").strip()=="Logged in using ChatGPT"
        ready=False
        if login:
            try:self._pins();ready=True
            except ProviderError:pass
        return CodexDiagnostics(ADAPTER_VERSION,self.expected_version,True,login,digest,self.model,supervised_ready=ready,blocker="" if ready else BLOCKER)
