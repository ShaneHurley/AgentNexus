"""Explicit reviewed Codex CLI settings; no authentication material is stored."""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
from .contracts import ContractDenied
from .model_catalog import canonical,digest
from .providers.codex_cli import CodexCLIProvider,SUPPORTED_VERSIONS
FIELDS={"version","model","reasoning_effort","executable","executable_sha256","catalog_path","catalog_sha256","security_config_sha256"}

def _validate(value):
    if not isinstance(value,dict) or set(value)!=FIELDS:raise ValueError("unsupported Codex configuration fields")
    if value["version"] not in SUPPORTED_VERSIONS:raise ValueError("unsupported Codex executable version")
    for field in ("executable","catalog_path"):
        if not isinstance(value[field],str) or not Path(value[field]).is_absolute():raise ValueError("Codex paths must be absolute")
    for field in ("executable_sha256","catalog_sha256","security_config_sha256"):
        text=value[field]
        if not isinstance(text,str) or len(text)!=64 or any(c not in "0123456789abcdef" for c in text):raise ValueError("invalid Codex content pin")
    if not isinstance(value["model"],str) or not value["model"].strip():raise ValueError("missing Codex model pin")
    if value["reasoning_effort"] not in {"low","medium","high","xhigh","max","ultra"}:raise ValueError("invalid Codex effort")
    return json.loads(canonical(value))

def build_provider(value,*,provider_factory=CodexCLIProvider):
    value=_validate(value)
    provider=provider_factory(executable=value["executable"],expected_version=value["version"],model=value["model"],
        reasoning_effort=value["reasoning_effort"],expected_executable_sha256=value["executable_sha256"],
        catalog_path=value["catalog_path"],expected_catalog_sha256=value["catalog_sha256"])
    if provider.security_config_sha256!=value["security_config_sha256"]:raise ContractDenied("Codex security settings differ from reviewed pin")
    return provider

def _path(repository):
    directory=Path(repository).resolve()/".agentnexus"
    path=directory/"codex.json"
    if directory.is_symlink() or path.is_symlink():raise ContractDenied("Codex configuration symlink denied")
    return path

def configure(repository,value,*,confirmed=False,provider_factory=CodexCLIProvider):
    if confirmed is not True:raise ContractDenied("Codex activation requires explicit reviewed configuration confirmation")
    value=_validate(value);provider=build_provider(value,provider_factory=provider_factory)
    if not provider.diagnostics().supervised_ready:raise ContractDenied("pinned Codex ChatGPT login unavailable")
    path=_path(repository);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=".codex-",dir=path.parent)
    try:
        with os.fdopen(fd,"w") as handle:
            handle.write(canonical(value));handle.flush();os.fsync(handle.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)
    return {"configuration_hash":digest(value),"provider":"codex_cli","billing_kind":"chatgpt_subscription","total_cost_usd":None}

def load_settings(repository,*,pinned=None,provider_factory=CodexCLIProvider):
    path=_path(repository)
    try:
        if path.stat().st_size>16384:raise ValueError("Codex configuration too large")
        value=_validate(json.loads(path.read_text()))
    except (OSError,ValueError) as exc:raise ContractDenied("reviewed Codex configuration unavailable") from exc
    result={"codex_configuration":value,"codex_configuration_hash":digest(value)}
    if pinned is not None and any(result[key]!=pinned.get(key) for key in result):raise ContractDenied("Codex configuration changed; start a new run")
    provider=build_provider(value,provider_factory=provider_factory)
    if not provider.diagnostics().supervised_ready:raise ContractDenied("pinned Codex ChatGPT login unavailable")
    return result

def routing_pins(repository,settings):
    from .routing_runtime import load_model_settings
    from .model_resolver import ModelResolver
    original=load_model_settings(repository)
    model={"provider":"codex_cli","model":settings["codex_configuration"]["model"],"context_tokens":128000,"output_tokens":16000,
        "risks":["low","high"],"privacy":["private"],"features":["tools","json_schema"],"credential_ref":None,
        "pricing":{"input_per_million":None,"output_per_million":None},"latency_ms":60000}
    catalog={"schema_version":1,"models":{"reviewed-codex":model}}
    roles={key:{"allowed_models":["reviewed-codex"],"default":"reviewed-codex","fallback":None,"reviewed_baseline":True,
        "evaluation_class":"codex-functional-baseline","qualifications":{}} for key in original["model_policy"]["roles"] if key.startswith("dc:")}
    policy={"schema_version":1,"roles":roles};ModelResolver(catalog,policy)
    return {"model_catalog":catalog,"model_policy":policy,"model_catalog_hash":digest(catalog),"model_policy_hash":digest(policy)}

def translate_budgets(budgets,parent_tokens,input_overhead_tokens):
    """Translate API-era profile ceilings for the measured CLI substrate.

    Retain call/turn limits; the user/parent token ceiling always wins. This is
    baseline compatibility accounting, not evidence of token savings.
    """
    for value in (parent_tokens,input_overhead_tokens):
        if not isinstance(value,int) or isinstance(value,bool) or value<0:raise ValueError("invalid Codex token translation")
    result=json.loads(canonical(budgets))
    for profile in result["profiles"].values():
        base=profile["total_tokens"];calls=profile["max_calls"]
        if any(not isinstance(v,int) or isinstance(v,bool) or v<0 for v in (base,calls)):raise ValueError("invalid profile budget")
        profile["total_tokens"]=min(parent_tokens,base+input_overhead_tokens*calls)
    return result
