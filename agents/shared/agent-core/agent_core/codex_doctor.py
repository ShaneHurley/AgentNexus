"""Bounded local Codex readiness checks; never invokes a model."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from .contracts import ContractDenied
from .codex_settings import _path, _validate
from .providers.codex_cli import CodexCLIProvider, SUPPORTED_VERSIONS
from .providers.http import ProviderError

ACTIONS={
"configuration_missing":"Configure reviewed pins with agent-nexus codex configure --pins PATH --confirm.",
"invalid_security_configuration":"Review configuration fields and the security hash; activate reviewed pins.",
"executable_missing":"Install the supported Codex CLI and configure its absolute executable path.",
"unsupported_version":"Use a supported reviewed CLI version and update its pins explicitly.",
"pin_mismatch":"Review executable and catalog content, then activate matching pins explicitly.",
"signed_out":"Run codex login or codex login --device-auth, then rerun the doctor.",
"authentication_unavailable":"Check local Codex login availability and rerun the doctor.",
"status_unrecognized":"Review this CLI login-status format before adding an explicitly tested variant.",
"probe_unavailable":"Check CLI availability and bounded local probe execution.",
"ready":"Ready for a supervised Codex run.",
}

def report(status):
    return {"schema_version":1,"provider":"codex_cli","status":status,"ready":status=="ready","corrective_action":ACTIONS[status]}

def doctor(repository, *, provider_factory=CodexCLIProvider):
    try:
        path=_path(repository)
        if path.stat().st_size>16384: return report("invalid_security_configuration")
        raw=json.loads(path.read_text())
    except FileNotFoundError:
        return report("configuration_missing")
    except (OSError,ValueError,ContractDenied):
        return report("invalid_security_configuration")
    try:
        value=_validate(raw)
    except ValueError:
        if isinstance(raw,dict) and "version" in raw and raw["version"] not in SUPPORTED_VERSIONS:
            return report("unsupported_version")
        return report("invalid_security_configuration")
    try:
        observed=hashlib.sha256(Path(value["executable"]).read_bytes()).hexdigest()
    except FileNotFoundError:
        return report("executable_missing")
    except OSError:
        return report("probe_unavailable")
    if observed!=value["executable_sha256"]: return report("pin_mismatch")
    try:
        provider=provider_factory(executable=value["executable"],expected_version=value["version"],model=value["model"],reasoning_effort=value["reasoning_effort"],expected_executable_sha256=value["executable_sha256"],catalog_path=value["catalog_path"],expected_catalog_sha256=value["catalog_sha256"])
    except (OSError,ValueError,TypeError,ProviderError):
        return report("invalid_security_configuration")
    try:
        code,out,_=provider._probe(("--version",))
    except (OSError,ProviderError):
        return report("probe_unavailable")
    if code!=0: return report("probe_unavailable")
    if out.decode("utf-8",errors="replace").strip()!=value["version"]: return report("unsupported_version")
    try:
        provider._pins()
    except (OSError,ProviderError):
        return report("pin_mismatch")
    try:
        code,out,err=provider._probe(("login","status"))
    except (OSError,ProviderError):
        return report("authentication_unavailable")
    login=(out+err).decode("utf-8",errors="replace").strip()
    if login=="Not logged in" and code in (0,1): return report("signed_out")
    if code!=0: return report("authentication_unavailable")
    if login!="Logged in using ChatGPT": return report("status_unrecognized")
    if provider.security_config_sha256!=value["security_config_sha256"]: return report("invalid_security_configuration")
    result=report("ready")
    result.update(model=value["model"],version=value["version"],executable_sha256=observed,configuration_hash=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest())
    return result
