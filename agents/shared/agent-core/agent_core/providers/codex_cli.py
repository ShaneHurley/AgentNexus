"""Codex CLI v2 transport, compatibility diagnostics, and offline contracts.

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
import fcntl
import stat
import hashlib
import json
import math
import re
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import threading
from dataclasses import dataclass
from agent_core.providers.base import Invocation,InvocationResult,Provider,ProviderCapabilities,TokenUsage,ToolCall
from agent_core.providers.http import ProviderError

CLI_VERSION="codex-cli 0.162.0-alpha.2"
SUPPORTED_VERSIONS=(CLI_VERSION,"codex-cli 0.162.0-alpha.17.2")
LEGACY_ENVELOPE_VERSION="anx_codex_role_v1"
ENVELOPE_VERSION="anx_codex_role_v2"
ADAPTER_VERSION=2
BLOCKER="Codex native tool denial and inherited configuration isolation are unverified; supervised invocation disabled"
MAX_OUTPUT_BYTES=1_000_000
MAX_EVENTS=10_000
DISABLED_FEATURES=('agent_message_board', 'analytics_plan_history', 'api_key_cyber_access_programs', 'api_key_model_discovery', 'apply_patch_preserve_line_endings', 'apply_patch_streaming_events', 'apps', 'artifact', 'auth_elicitation', 'background_paginated_rollout_migration', 'bedrock_setup_wizard', 'browser_annotation_api', 'browser_use', 'browser_use_external', 'browser_use_full_cdp_access', 'chronicle', 'code_mode', 'code_mode_host', 'code_mode_interrupt', 'code_mode_only', 'code_mode_prewarm', 'codex_apps_mcp_2026_07_28', 'compaction_image_budget', 'computer_use', 'concurrent_reasoning_summaries', 'content_item_kinds', 'context_management', 'current_time_reminder', 'cwd_relative_turn_diffs', 'daemon_auto_start', 'default_mode_request_user_input', 'defer_mailbox_preemption', 'deferred_executor', 'deferred_tool_world_state', 'enable_mcp_apps', 'enable_request_compression', 'exec_permission_approvals', 'executed_tool_call_metadata', 'executor_capability_discovery', 'external_agent_memory_import', 'fast_mode', 'goals', 'guardian_approval', 'guardian_conversation_history_tools', 'guardian_enhanced_node_repl_transcripts', 'guardian_node_repl_transcript_images', 'guardian_reuse_parent_compaction', 'guardian_root_handoff_context', 'guardianv2', 'guardianv2_decisions_comparison', 'hooks', 'image_generation', 'image_resize_notice', 'in_app_browser', 'in_app_chat', 'in_app_dictation', 'in_app_local_automation', 'in_app_updates', 'in_app_voice', 'instant_interrupt', 'local_thread_store_compression', 'login_shell_package_path', 'mcp_2026_07_28', 'mcp_oauth_refresh_coordination', 'memories', 'mentions_v2', 'model_catalog_in_context', 'multi_agent', 'multi_agent_v2', 'multi_agent_v2_dynamic_tools', 'network_proxy', 'non_prefixed_mcp_tool_names', 'nonfatal_clock_read_errors', 'omit_app_server_notification_media', 'plugin_sharing', 'plugins', 'powershell_shell_version', 'prefer_mxc', 'prevent_idle_sleep', 'psp', 'realtime_conversation', 'reasoning_effort_override', 'recommended_plugins', 'remote_plugin', 'request_permissions_tool', 'respect_system_proxy', 'retain_client_developer_messages', 'rollout_budget', 'runtime_metrics', 'secret_auth_storage', 'send_message_to_user_async', 'shell_snapshot', 'shell_snapshot_v2', 'shell_tool', 'shell_zsh_fork', 'skill_mcp_dependency_install', 'skill_search', 'sleep_tool', 'standalone_web_search', 'step_model_switching', 'system_proxy_fallback', 'terminal_visualization_instructions', 'token_budget', 'tool_call_mcp_elicitation', 'tool_suggest', 'unbounded_connection_retries', 'unified_exec', 'unified_exec_tty', 'unified_image_budget', 'use_agent_identity', 'use_xaa', 'view_image', 'windows_sandbox_service', 'workspace_dependencies', 'worktrees', 'write_stdin_approval')
DISABLED_FEATURES+=('cli_daybreak','code_mode_only_strict_3p_tools','code_mode_tool_search','incremental_tools','stable_environment_tools','ultrafast_mode')
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
    error=ProviderError(message,category=category,remote_acceptance=acceptance,retryable=False)
    error.reason_code={"Codex structured role output invalid":"role_schema","Codex role envelope version unsupported":"envelope_version",
                       "Codex tool request outside invocation contract":"tool_contract","Codex tool argument schema invalid":"tool_schema",
                       "Codex native tool event denied":"native_tool","Codex completion evidence missing":"missing_completion",
                       "Codex preceding structured message denied":"preceding_structured", "Codex usage invalid":"usage_contract",
                       "Codex tool arguments invalid":"tool_schema", "Codex turn failed":"turn_failed",
                       "Codex event version unsupported":"event_version", "Codex envelope has contradictory outcomes":"contradictory_outcomes"}.get(message,"contract_failure")
    return error

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


def _turn_failure(event, thread_id=None):
    """Classify failed JSONL turns without persisting provider text or secrets."""
    values=[]
    def collect(value, depth=0):
        if isinstance(value,str):
            values.append(value[:4096])
        elif isinstance(value,dict) and depth<3:
            for key in ("code","message","error","reason","type"):
                if key in value: collect(value[key],depth+1)
    collect(event)
    text="\n".join(values).lower()
    hints=(
        ("account_limit","usage_limit",("usage limit","usage_limit","quota exceeded","rate limit","insufficient_quota")),
        ("authorization","authentication_failed",("invalid api key","authentication failed","not logged in","unauthorized","authentication_error")),
        ("configuration","invalid_schema",("invalid schema","invalid_json_schema","schema validation")),
        ("configuration","context_capacity",("context_length_exceeded","context window","maximum context","too many tokens")),
        ("configuration","invalid_configuration",("invalid config","unknown config","unrecognized argument","invalid_request")),
        ("transport","connection_failure",("stream disconnected","connection reset","connection failed","connection_failed","connection closed","stream_disconnected")),
        ("deadline","response_timeout",("timed out","request_timeout","deadline exceeded")),
        ("transport","service_failure",("server overloaded","server_overloaded","internal server error","server_error","internal_error")),
    )
    category,hint="response","unclassified_turn_failure"
    for candidate,reason,markers in hints:
        if any(marker in text for marker in markers):
            category,hint=candidate,reason
            break
    error=_failure("Codex turn failed",category=category)
    encoded=json.dumps(event,sort_keys=True,ensure_ascii=False).encode()
    error.diagnostics={"event_type":event.get("type"),"failure_hint":hint,
                       "event_sha256":hashlib.sha256(encoded).hexdigest(),
                       "event_bytes":len(encoded)}
    # Only the documented UUID form is safe to preserve as a correlation ID.
    if isinstance(thread_id,str) and re.fullmatch(r"[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}",thread_id):
        error.diagnostics["provider_thread_id"]=thread_id
    return error

def _dispatch_state_directory():
    # HOME and CODEX_HOME are caller-controlled. Use the OS account record
    # so every adapter process for this UID shares the same admission lock.
    try:
        if sys.platform not in {"darwin","linux"}:raise ValueError()
        import pwd
        account_home=pwd.getpwuid(os.getuid()).pw_dir
        if not isinstance(account_home,str) or not account_home:raise ValueError()
        home=Path(account_home)
        if not home.is_absolute() or ".." in home.parts:raise ValueError()
        return home/".agentnexus-codex"
    except (ImportError,KeyError,OSError,AttributeError,TypeError,ValueError):
        raise _failure("Codex OS account state unavailable",category="security",acceptance="rejected") from None

def _acquire_process_lock():
    """Return a close-on-exec fd holding the OS lock; caller must close it.

    Walk directories using no-follow descriptors, including ancestors, rather
    than resolving symlinks and then opening a mutable pathname. Never repair
    insecure permissions silently, and never include paths in error messages.
    """
    directory=_dispatch_state_directory()
    directory_fd=None; lock_fd=None
    try:
        if not directory.is_absolute() or ".." in directory.parts:
            raise ValueError()
        flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC
        directory_fd=os.open(directory.anchor,flags)
        for index,part in enumerate(directory.parts[1:]):
            final=index==len(directory.parts)-2
            if final:
                try:os.mkdir(part,mode=0o700,dir_fd=directory_fd)
                except FileExistsError:pass
            next_fd=os.open(part,flags,dir_fd=directory_fd)
            os.close(directory_fd);directory_fd=next_fd
        info=os.fstat(directory_fd)
        if info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:
            raise ValueError()
        lock_fd=os.open("dispatch.lock",os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=directory_fd)
        info=os.fstat(lock_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1:
            raise ValueError()
        try:fcntl.flock(lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise _failure("Codex invocation concurrency ceiling exceeded",category="budget",acceptance="rejected") from None
        result=lock_fd;lock_fd=None
        return result
    except (OSError,ValueError):
        raise _failure("Codex private dispatch state unavailable",category="security",acceptance="rejected") from None
    finally:
        if lock_fd is not None:os.close(lock_fd)
        if directory_fd is not None:os.close(directory_fd)

def parse_codex_jsonl(lines,request: Invocation,*,model: str,max_output_bytes=MAX_OUTPUT_BYTES,envelope_version=None):
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
        if kind in {"error","turn.failed"}: raise _turn_failure(event,thread_id)
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
                if not isinstance(item.get("text"),str):raise _failure()
                if message is not None:
                    # Completed ordinary commentary may precede the final
                    # envelope. It never supplies output/tool authority. Keep
                    # this narrow: reject JSON, malformed structural text, and
                    # fenced content rather than searching for an envelope.
                    preceding=message.strip()
                    if preceding.startswith('"') or ("```" in preceding or any(marker in preceding for marker in "{}[]")):
                        raise _failure("Codex preceding structured message denied")
                    try:json.loads(preceding)
                    except ValueError:pass
                    else:raise _failure("Codex preceding structured message denied")
                message=item["text"]
        elif kind=="turn.completed":
            complete=True;usage=event.get("usage")
            if usage is not None and not isinstance(usage,dict): raise _failure()
        else: raise _failure("Codex event version unsupported")
    if not complete or message is None: raise _failure("Codex completion evidence missing")
    try: envelope=json.loads(message)
    except ValueError: raise _failure() from None
    if not isinstance(envelope,dict):raise _failure("Codex role envelope version unsupported")
    version=envelope.get("version")
    if version not in (LEGACY_ENVELOPE_VERSION,ENVELOPE_VERSION) or (envelope_version is not None and version!=envelope_version):
        raise _failure("Codex role envelope version unsupported")
    output_key="output_json" if version==ENVELOPE_VERSION else "output"
    arguments_key="arguments_json" if version==ENVELOPE_VERSION else "arguments"
    if set(envelope)!={"version",output_key,"tool_calls"}:raise _failure()
    output=envelope[output_key];calls=envelope["tool_calls"]
    if version==ENVELOPE_VERSION and output is not None:
        if not isinstance(output,str):raise _failure()
        try:output=json.loads(output)
        except (ValueError,TypeError):raise _failure("Codex structured role output invalid") from None
        if output is None:raise _failure("Codex structured role output invalid")
    if output is not None and not request.output_schema and not isinstance(output,dict):raise _failure()
    if not isinstance(calls,list) or len(calls)>128 or (output is None and not calls):raise _failure()
    u=usage or {}
    try:
        tokens=TokenUsage(input_tokens=u.get("input_tokens"),output_tokens=u.get("output_tokens"),cached_tokens=u.get("cached_input_tokens"),cache_creation_tokens=u.get("cache_write_input_tokens"),reasoning_tokens=u.get("reasoning_output_tokens"),cost_usd=None,evidence_status="reported" if usage else "unknown")
    except (ValueError,TypeError): raise _failure("Codex usage invalid") from None
    allowed={item["name"]:item for item in request.tools};seen=set();parsed=[]
    for call in calls:
        if not isinstance(call,dict) or set(call)!={"name",arguments_key,"call_id"}:raise _failure()
        if not isinstance(call["name"],str) or call["name"] not in allowed or not isinstance(call["call_id"],str) or not 0<len(call["call_id"])<=128 or call["call_id"] in seen:
            raise _failure("Codex tool request outside invocation contract")
        arguments=call[arguments_key]
        if version==ENVELOPE_VERSION:
            if not isinstance(arguments,str):raise _failure()
            try:arguments=json.loads(arguments)
            except (ValueError,TypeError):raise _failure("Codex tool arguments invalid") from None
        if not isinstance(arguments,dict):raise _failure("Codex tool arguments invalid")
        try:
            import jsonschema
            jsonschema.validate(arguments,allowed[call["name"]].get("parameters",{"type":"object"}))
        except Exception:raise _failure("Codex tool arguments invalid") from None
        seen.add(call["call_id"]);parsed.append(ToolCall(call["name"],arguments,call["call_id"]))
    if parsed and output is not None:raise _failure("Codex envelope has contradictory outcomes")
    if output is not None and request.output_schema:
        try:import jsonschema
        except ImportError:raise _failure("Codex structured role output invalid") from None
        try:
            jsonschema.validate(output,request.output_schema)
        except jsonschema.ValidationError:
            error=_failure("Codex structured role output invalid")
            error.reason="role_schema"
            # A completed turn with fully validated reported counts is an
            # accounting receipt even when its role output must be denied.
            # Never attach model content, tool requests, or uncertain usage.
            if tokens.input_tokens is not None and tokens.output_tokens is not None:
                error.remote_acceptance="accepted"
                error.response=InvocationResult(output=None,tool_calls=[],model=model,usage=tokens,finish_reason="invalid_output_schema",raw_ref="codex-thread:"+thread_id if thread_id else None)
            raise error from None
        except Exception:raise _failure("Codex structured role output invalid") from None
    return InvocationResult(output=output,tool_calls=parsed,model=model,usage=tokens,raw_ref="codex-thread:"+thread_id if thread_id else None,finish_reason="tool_calls" if parsed else "stop")

class CodexCLIProvider(Provider):
    """Version-pinned inference-only Codex transport; returned tools are requests."""
    name="codex_cli"
    max_transport_retries=0
    max_parallelism=1
    billing_kind="chatgpt_subscription"
    capabilities=ProviderCapabilities()
    def __init__(self,*,executable,expected_version=CLI_VERSION,model,expected_executable_sha256=None,catalog_path=None,expected_catalog_sha256=None,reasoning_effort="medium",timeout=180.0,probe_timeout=5.0,max_probe_bytes=16_384):
        path=Path(executable)
        if not path.is_absolute() or not path.is_file() or not os.access(path,os.X_OK): raise ValueError("Codex executable must be an absolute executable file")
        if expected_version not in SUPPORTED_VERSIONS or not isinstance(model,str) or not model.strip(): raise ValueError("unsupported Codex version or missing model pin")
        if not math.isfinite(probe_timeout) or not 0<probe_timeout<=30 or not isinstance(max_probe_bytes,int) or not 0<max_probe_bytes<=16_384:
            raise ValueError("invalid Codex diagnostic budget")
        self.executable=str(path.resolve());self.expected_version=expected_version;self.model=model
        if reasoning_effort not in {"low","medium","high","xhigh","max","ultra"} or not math.isfinite(timeout) or not 0<timeout<=180:
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
        # Strict remote schemas cannot express every native role/tool schema.
        # Encode payloads as JSON strings and validate their original schemas
        # locally after decoding, before returning anything to the supervisor.
        options=[]
        for tool in request.tools:
            options.append({"type":"object","properties":{"name":{"type":"string","enum":[tool["name"]]},"arguments_json":{"type":"string"},"call_id":{"type":"string"}},"required":["name","arguments_json","call_id"],"additionalProperties":False})
        return {"type":"object","properties":{"version":{"type":"string","enum":[ENVELOPE_VERSION]},"output_json":{"anyOf":[{"type":"string"},{"type":"null"}]},"tool_calls":{"type":"array","items":{"anyOf":options} if options else {"type":"object","properties":{},"required":[],"additionalProperties":False},"maxItems":128 if options else 0}},"required":["version","output_json","tool_calls"],"additionalProperties":False}

    def invoke(self,request):
        catalog=self._pins()
        if request.model not in ("unknown",self.model) or request.provider_options or request.max_transport_retries:
            raise _failure("Codex invocation overrides or retries denied",category="configuration",acceptance="rejected")
        end=min(time.time()+self.timeout,request.deadline if request.deadline is not None else float("inf"))
        if end<=time.time(): raise _failure("Codex deadline exhausted",category="deadline",acceptance="rejected")
        if not _DISPATCH_LOCK.acquire(blocking=False):
            raise _failure("Codex invocation concurrency ceiling exceeded",category="budget",acceptance="rejected")
        process_lock=None
        try:
            process_lock=_acquire_process_lock()
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
                prompt=json.dumps({"envelope_version":ENVELOPE_VERSION,"role":request.role,"instructions":request.prompt,"input_packet":request.input_packet,"tool_results":request.tool_results,"allowed_tool_requests":request.tools,"max_output_tokens_advisory":request.max_output_tokens,"output_schema":request.output_schema,"instructions_for_tools":"Return anx_codex_role_v2: output_json is a JSON-encoded role output string or null; tool_calls contain name, arguments_json (JSON-encoded arguments), call_id. Return either output or tool requests. Native tools are unavailable."},sort_keys=True)
                if len(prompt.encode())>1_000_000: raise _failure("Codex prompt ceiling exceeded",category="budget",acceptance="rejected")
                code,out,err=self._run(tuple(args),input_text=prompt,cwd=str(cwd),deadline=end,max_bytes=MAX_OUTPUT_BYTES,key=request.idempotency_key)
                if code!=0: raise _process_failure(code,out,err)
                try: lines=out.decode("utf-8").splitlines()
                except UnicodeError: raise _failure() from None
                result=parse_codex_jsonl(lines,request,model=self.model,envelope_version=ENVELOPE_VERSION)
                result.cancellation_status="not_requested"
                return result
        finally:
            if process_lock is not None:os.close(process_lock)
            _DISPATCH_LOCK.release()

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
