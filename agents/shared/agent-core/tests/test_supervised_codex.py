import json
from pathlib import Path
import pytest
from agent_core.supervisor import Supervisor
from agent_core.engine_adapters import DailyCoderAdapter
from agent_core.contracts import ContractDenied
ROOT=Path(__file__).resolve().parents[4]
class SubscriptionEngine:
    def __init__(self,unknown=False):self.unknown=unknown;self.calls=0
    def snapshot(self,workspace,live,provider,**kwargs):return {"provider":provider,"codex_configuration_hash":"a"*64,"codex_configuration":{"model":"test"}}
    def create(self,row):return row["run_id"]
    def execute(self,row,answers=None):
        self.calls+=1
        return {"status":"COMPLETE","phase":"done","usage":{"tokens":12,"usd":None,"known_api_cash_usd":0.0,"billing_kind":"chatgpt_subscription","usage_status":"reported","unknown":self.unknown}}
    def inspect(self,row):return self.execute(row)

def test_subscription_settles_reported_tokens_without_inventing_price(tmp_path):
    engine=SubscriptionEngine();s=Supervisor(tmp_path,adapters={"daily-coder":engine})
    run=s.create_run(s.new_session()["session_id"],"daily-coder","inspect",tmp_path,True,provider="codex_cli",limit_usd=0)
    result=s.execute(run["run_id"])
    assert result["status"]=="COMPLETE"
    assert result["accounting"]["tokens"]==12
    assert result["accounting"]["total_cost_usd"] is None
    assert result["accounting"]["known_api_cash_usd"]==0
    assert not s.store.pending_calls(run["run_id"])
    assert s.execute(run["run_id"])["status"]=="COMPLETE" and engine.calls==1

def test_unknown_subscription_outcome_keeps_reservation(tmp_path):
    s=Supervisor(tmp_path,adapters={"daily-coder":SubscriptionEngine(True)})
    run=s.create_run(s.new_session()["session_id"],"daily-coder","inspect",tmp_path,True,provider="codex_cli",limit_usd=0)
    result=s.execute(run["run_id"])
    assert result["status"]=="RECONCILIATION_REQUIRED" and s.store.pending_calls(run["run_id"])

def test_api_cannot_self_declare_subscription_exemption(tmp_path):
    s=Supervisor(tmp_path,adapters={"daily-coder":SubscriptionEngine()})
    run=s.create_run(s.new_session()["session_id"],"daily-coder","inspect",tmp_path,True,provider="openai")
    result=s.execute(run["run_id"])
    assert result["status"]=="RECONCILIATION_REQUIRED" and s.store.pending_calls(run["run_id"])

def test_codex_requires_explicit_live_authorization():
    adapter=DailyCoderAdapter(ROOT/"agents/coding/daily-coder-ecosystem")
    with pytest.raises(ContractDenied):adapter.snapshot(ROOT,False,"codex_cli")
