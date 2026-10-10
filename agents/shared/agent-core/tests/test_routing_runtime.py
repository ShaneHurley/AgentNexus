import json
from pathlib import Path
import pytest
from agent_core.routing_runtime import load_model_settings, SupervisedProvider
from agent_core.model_catalog import digest
from agent_core.providers.base import Invocation,InvocationResult,TokenUsage
from agent_core.contracts import ContractDenied

ROOT=Path(__file__).resolve().parents[4]
class Mock:
    name="mock"
    def invoke(self,request):
        return InvocationResult(output={"ok":True},model=request.model,usage=TokenUsage(0,0,0,0,evidence_status="reported"))

def test_pinned_settings_ignore_later_activation(tmp_path):
    pin=load_model_settings(ROOT,directory=tmp_path)
    broken=dict(pin);broken["model_policy_hash"]="0"*64
    with pytest.raises(ValueError):load_model_settings(ROOT,directory=tmp_path,pinned=broken)
    (tmp_path/"routing-active.json").write_text(json.dumps({"catalog_hash":"0"*64,"policy_hash":"0"*64}))
    assert load_model_settings(ROOT,directory=tmp_path,pinned=pin)==pin

def test_supervised_provider_records_selection_and_pin():
    pin=load_model_settings(ROOT)
    provider=SupervisedProvider(Mock(),pin,provider_name="mock",run_id="run",workspace=ROOT)
    request=Invocation("run","researcher","inspect",{},"lowest",100,"one",model="mock")
    result=provider.invoke(request)
    assert result.model=="mock" and provider.decisions[-1]["catalog_hash"]==pin["model_catalog_hash"]
    with pytest.raises(ContractDenied):provider.invoke(Invocation("other","researcher","",{},"lowest",10,"x"))

def test_unreviewed_live_provider_denied_before_network():
    pin=load_model_settings(ROOT)
    provider=SupervisedProvider(Mock(),pin,provider_name="openrouter",run_id="run",workspace=ROOT)
    with pytest.raises(ContractDenied):provider.resolve_for_role("researcher","lowest",100,10)


def test_context_capacity_reserves_output_space():
    pin=load_model_settings(ROOT)
    pin['model_catalog']['models']['offline-mock']['context_tokens']=150
    pin['model_catalog_hash']=digest(pin['model_catalog'])
    provider=SupervisedProvider(Mock(),pin,provider_name='mock',run_id='run',workspace=ROOT)
    with pytest.raises(ContractDenied):provider.resolve_for_role('researcher','lowest',100,60)
