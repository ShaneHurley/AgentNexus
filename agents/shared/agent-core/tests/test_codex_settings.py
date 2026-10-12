import json
from pathlib import Path
import pytest
from agent_core.contracts import ContractDenied
from agent_core.codex_settings import configure, load_settings, routing_pins
ROOT=Path(__file__).resolve().parents[4]
PINS={"version":"codex-cli 0.162.0-alpha.2","model":"reviewed-test-model","reasoning_effort":"medium","executable":"/tmp/fake-codex","executable_sha256":"a"*64,"catalog_path":"/tmp/catalog.json","catalog_sha256":"b"*64,"security_config_sha256":"c"*64}
class Ready:
    security_config_sha256="c"*64
    def __init__(self,**kwargs):self.kwargs=kwargs
    def diagnostics(self):return type("Diagnostic",(),{"supervised_ready":True})()

def test_configuration_requires_explicit_confirmation(tmp_path):
    with pytest.raises(ContractDenied):configure(tmp_path,PINS,provider_factory=Ready)
    assert not (tmp_path/".agentnexus").exists()

def test_config_pinned_and_subscription_price_unknown(tmp_path):
    configure(tmp_path,PINS,confirmed=True,provider_factory=Ready)
    value=load_settings(tmp_path,provider_factory=Ready)
    assert value["codex_configuration"]["model"]==PINS["model"]
    assert value==load_settings(tmp_path,pinned=value,provider_factory=Ready)
    routing=routing_pins(ROOT,value)
    model=routing["model_catalog"]["models"]["reviewed-codex"]
    assert model["provider"]=="codex_cli" and model["credential_ref"] is None
    assert model["pricing"]["input_per_million"] is None
    assert routing["model_policy"]["roles"]["dc:researcher"]["default"]=="reviewed-codex"

def test_settings_change_cannot_silently_resume(tmp_path):
    configure(tmp_path,PINS,confirmed=True,provider_factory=Ready)
    pinned=load_settings(tmp_path,provider_factory=Ready)
    path=tmp_path/".agentnexus/codex.json"
    path.write_text(json.dumps({**PINS,"model":"different"}))
    with pytest.raises(ContractDenied):load_settings(tmp_path,pinned=pinned,provider_factory=Ready)

def test_missing_configuration_and_bad_security_pin_deny(tmp_path):
    with pytest.raises(ContractDenied):load_settings(tmp_path,provider_factory=Ready)
    with pytest.raises(ContractDenied):configure(tmp_path,{**PINS,"security_config_sha256":"d"*64},confirmed=True,provider_factory=Ready)
    assert not (tmp_path/".agentnexus/codex.json").exists()

def test_unknown_fields_and_symlink_configuration_deny(tmp_path):
    with pytest.raises(ValueError):configure(tmp_path,{**PINS,"api_key":"do-not-store"},confirmed=True,provider_factory=Ready)
    outside=tmp_path/"outside.json";outside.write_text(json.dumps(PINS))
    (tmp_path/".agentnexus").mkdir();(tmp_path/".agentnexus/codex.json").symlink_to(outside)
    with pytest.raises(ContractDenied):load_settings(tmp_path,provider_factory=Ready)

def test_reviewed_updated_version_requires_its_own_pins(tmp_path):
    configure(tmp_path,{**PINS,"version":"codex-cli 0.162.0-alpha.17.2"},confirmed=True,provider_factory=Ready)
    assert load_settings(tmp_path,provider_factory=Ready)["codex_configuration"]["version"]=="codex-cli 0.162.0-alpha.17.2"
    with pytest.raises(ValueError):configure(tmp_path,{**PINS,"version":"codex-cli future"},confirmed=True,provider_factory=Ready)

def test_cli_provider_failure_is_structured_not_traceback(tmp_path,capsys,monkeypatch):
    import agent_core.codex_settings as settings
    from agent_core.providers.http import ProviderError
    from agent_core.nexus_cli import main
    def failure(*args,**kwargs):raise ProviderError("private diagnostic",category="configuration",remote_acceptance="rejected")
    monkeypatch.setattr(settings,"load_settings",failure)
    assert main(["--repository",str(tmp_path),"codex","inspect"])==3
    value=json.loads(capsys.readouterr().out)
    assert value["error"]=="ProviderError" and value["category"]=="configuration"
    assert "private diagnostic" not in json.dumps(value)

def test_cli_overhead_translation_preserves_parent_budget_and_call_caps():
    from agent_core.codex_settings import translate_budgets
    source={"profiles":{"S":{"total_tokens":40000,"max_calls":12},"M":{"total_tokens":80000,"max_calls":24}}}
    translated=translate_budgets(source,80000,8192)
    assert translated["profiles"]["S"]["total_tokens"]==80000
    assert translated["profiles"]["S"]["max_calls"]==12
    assert source["profiles"]["S"]["total_tokens"]==40000
    assert translate_budgets(source,1000,8192)["profiles"]["S"]["total_tokens"]==1000
    with pytest.raises(ValueError):translate_budgets(source,-1,8192)
