import pytest
from dataclasses import asdict
from research_forge.budget.manager import BudgetManager,BudgetState
from research_forge.budget.wrapper import budget_wrapped_call
from research_forge.errors import ForgeException
class Gateway:
    def authorize(self,**kwargs): return True,None
class Journal:
    def __init__(self): self.saved=None
    def check_dispatch(self): pass
    def call(self,key): return None
    def prepare(self,key,cost,budget,auth): self.saved=asdict(budget.state);return {}
    def complete(self,row,result,budget): self.saved=asdict(budget.state)
def budget(repo_root):
    b=BudgetManager(repo_root/"config/budgets.yaml");b.start("S");return b
def call(b,fn,**kwargs):
    return budget_wrapped_call(Gateway(),b,cost_usd=.1,auth_kwargs={"operation":"model_call","role":"role"},fn=fn,**kwargs)
def test_known_zero(repo_root):
    b=budget(repo_root)
    call(b,lambda:{"usage":{"prompt_tokens":0,"completion_tokens":0,"cost_usd":0}},reservation_tokens=10)
    assert b.state.actual_tokens==0 and b.state.reserved_tokens==0
    assert b.state.spent_usd==0 and b.state.unknown_token_calls==0
def test_missing_retains_reserve(repo_root):
    b=budget(repo_root)
    call(b,lambda:{},reservation_tokens=10)
    assert b.state.reserved_tokens==10 and b.state.unknown_token_calls==1
    assert b.state.spent_usd==.1
def test_denied_before_function(repo_root):
    b=budget(repo_root)
    b.state.limit_tokens=2
    with pytest.raises(ForgeException): call(b,lambda:pytest.fail("dispatched"),reservation_tokens=3)
    assert b.state.reserved_usd==0 and b.state.reserved_tokens==0
    with pytest.raises(ForgeException): call(b,lambda:pytest.fail("dispatched"))
def test_crash_reservation_persisted(repo_root):
    b=budget(repo_root);b.journal=Journal()
    def crash(): raise RuntimeError("crash")
    with pytest.raises(RuntimeError): call(b,crash,reservation_tokens=10)
    state=BudgetState(**b.journal.saved)
    assert state.reserved_tokens==10 and state.reserved_usd==.1

def test_resource_token_limit_and_deadline(repo_root):
    import time
    b=budget(repo_root)
    b.resource_limits={"tokens":2,"usd":5,"deadline":time.time()+10}
    with pytest.raises(ForgeException): call(b,lambda:pytest.fail("dispatched"),reservation_tokens=3)
    b.resource_limits["deadline"]=time.time()-1
    with pytest.raises(ForgeException): call(b,lambda:pytest.fail("dispatched"),reservation_tokens=1)

def test_reported_usage_and_estimated_missing_cost(repo_root):
    b=budget(repo_root)
    call(b,lambda:{"usage":{"input_tokens":2,"output_tokens":3,"cost_usd":.02}},reservation_tokens=10)
    assert b.state.actual_tokens==5 and b.state.reserved_tokens==0
    assert b.state.spent_usd==.02
    call(b,lambda:{"usage":{"input_tokens":0,"output_tokens":0}},reservation_tokens=10)
    assert b.state.spent_usd==pytest.approx(.12)
    assert b.state.actual_tokens==5 and b.state.reserved_tokens==0

def test_actual_journal_crash_and_reopen(repo_root,tmp_path):
    from research_forge.wave1.lifecycle import LifecycleJournal
    from agent_core.contracts import ContractDenied
    b=budget(repo_root);b.journal=LifecycleJournal(tmp_path,"token-crash")
    def crash(): raise RuntimeError("crash")
    with pytest.raises(RuntimeError): call(b,crash,reservation_tokens=10)
    reopened=LifecycleJournal(tmp_path,"token-crash")
    saved=reopened.view()["budget"]
    assert saved["reserved_tokens"]==10 and saved["unknown_token_calls"]==1
    assert saved["reserved_usd"]==.1
    b2=budget(repo_root);b2.journal=reopened
    with pytest.raises(ContractDenied): call(b2,lambda:pytest.fail("replayed"),reservation_tokens=10)
    assert b2.state.reserved_tokens==10

def test_backward_state_and_zero_retrieval(repo_root):
    state=BudgetState(profile="S",limit_usd=5)
    assert state.reserved_tokens==0 and state.actual_tokens==0
    b=budget(repo_root)
    result=budget_wrapped_call(Gateway(),b,cost_usd=0,auth_kwargs={"operation":"retrieve"},fn=lambda:{"usage":{"total_tokens":0,"cost_usd":0}})
    assert result["usage"]["total_tokens"]==0 and b.state.actual_tokens==0 and b.state.spent_usd==0

def test_unknown_reservation_blocks_changed_request(repo_root,tmp_path):
    from research_forge.wave1.lifecycle import LifecycleJournal
    from agent_core.contracts import ContractDenied
    b=budget(repo_root);b.journal=LifecycleJournal(tmp_path,"changed-request")
    with pytest.raises(RuntimeError): call(b,lambda:(_ for _ in ()).throw(RuntimeError("crash")),reservation_tokens=10)
    fresh=budget(repo_root);fresh.journal=LifecycleJournal(tmp_path,"changed-request")
    with pytest.raises(ContractDenied): call(fresh,lambda:pytest.fail("new dispatch"),reservation_tokens=10,request={"changed":True})
    assert fresh.state.reserved_tokens==10
