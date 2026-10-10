import json
from pathlib import Path
from agent_core.engine_adapters import DailyCoderAdapter
from agent_core.routing_runtime import SupervisedProvider, load_model_settings
from agent_core.supervisor import Supervisor
class Engine:
    def snapshot(self,workspace,live,provider):return {"provider":provider}
    def create(self,row):return "native-"+row["run_id"]
    def inspect(self,row):return {"status":"QUEUED"}


ROOT=Path(__file__).resolve().parents[4]

def test_adapter_uses_reviewed_provider_without_ambient_secrets(tmp_path,monkeypatch):
    adapter=DailyCoderAdapter(ROOT/"agents/coding/daily-coder-ecosystem")
    pin=adapter.snapshot(tmp_path,False,"mock")
    assert pin["model_catalog_hash"]==load_model_settings(ROOT)["model_catalog_hash"]
    monkeypatch.setenv("OPENROUTER_API_KEY","must-not-read")
    engine=adapter._engine({"snapshot":pin,"run_id":"integration-test","live":False,"workspace":str(tmp_path),"limit_tokens":80000,"limit_usd":1,"deadline":None})
    assert engine.pricing=={"mock":{"input_per_1k":0,"output_per_1k":0}}
    assert isinstance(engine.provider,SupervisedProvider)
    assert engine.provider.resolve_for_role("researcher","lowest",100)=="mock"


def test_missing_usage_is_unknown_not_zero(tmp_path):
    engine=Engine()
    def execute(row,answers=None):
        return {"status":"COMPLETE","usage":{"tokens":10},"artifacts":[]}
    engine.execute=execute
    supervisor=Supervisor(tmp_path,adapters={"daily-coder":engine})
    run=supervisor.create_run(supervisor.new_session()["session_id"],"daily-coder","inspect",tmp_path)
    out=supervisor.execute(run["run_id"])
    assert out["status"]=="RECONCILIATION_REQUIRED"
    assert out["accounting"]["reserved_usd"]>0


def test_unknown_catalog_price_does_not_inherit_native_price(tmp_path):
    import pytest
    from agent_core.model_catalog import digest
    from daily_coder.budget import BudgetExceeded
    adapter=DailyCoderAdapter(ROOT/"agents/coding/daily-coder-ecosystem")
    pin=adapter.snapshot(tmp_path,False,"mock")
    pin["model_catalog"]["models"]["offline-mock"]["pricing"]["input_per_million"]=None
    pin["model_catalog_hash"]=digest(pin["model_catalog"])
    engine=adapter._engine({"snapshot":pin,"run_id":"unknown-price","live":False,"workspace":str(tmp_path),"limit_tokens":80000,"limit_usd":1,"deadline":None})
    with pytest.raises(BudgetExceeded):engine.budget.validate_model_pricing("mock")
