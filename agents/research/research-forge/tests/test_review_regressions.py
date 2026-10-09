import pytest
from research_forge.wave1.orchestrator import Wave1Orchestrator
from research_forge.wave1.lifecycle import LifecycleJournal
from research_forge.adapters.search.gateway import gated_search
from research_forge.budget.wrapper import budget_wrapped_call
from agent_core.contracts import ContractDenied
from research_forge.errors import ForgeException

def journal_engine(root,tmp):
    engine=Wave1Orchestrator(root,workspace=tmp)
    engine.budget.start("S")
    journal=LifecycleJournal(tmp,"run-review")
    engine.budget.journal=journal
    return engine,journal

def test_distinct_search_requests_and_monotonic_cache(repo_root,tmp_path):
    engine,journal=journal_engine(repo_root,tmp_path)
    def search(query,**kw): return gated_search(engine.gateway,engine.budget,engine.search,role="orchestrator",phase="search",query=query,live=False,**kw)
    a=search("alpha");b=search("beta")
    assert b["exact_query"]=="beta"
    search("beta",cursor=1)
    spent=engine.budget.state.spent_usd
    assert search("alpha")["exact_query"]=="alpha"
    assert engine.budget.state.spent_usd==spent
    assert len(journal.view()["calls"])==3

def test_cache_rechecks_authority(repo_root,tmp_path):
    engine,journal=journal_engine(repo_root,tmp_path)
    auth={"role":"orchestrator","phase":"search","tool_id":engine.search.adapter_id,"operation":"search","target":"mock://"+engine.search.adapter_id,"live":False}
    budget_wrapped_call(engine.gateway,engine.budget,cost_usd=.01,auth_kwargs=auth,fn=lambda:{"a":1})
    engine.gateway.policy["role_tool_allowlist"]["orchestrator"]=[]
    with pytest.raises((ForgeException,ContractDenied)):
        budget_wrapped_call(engine.gateway,engine.budget,cost_usd=.01,auth_kwargs=auth,fn=lambda:{"a":2})

@pytest.mark.parametrize("part",["run","journal","lock","runs"])
def test_journal_symlink_escape_denied(tmp_path,part):
    root=tmp_path/"workspace";root.mkdir();outside=tmp_path/"outside";outside.mkdir()
    run=root/"runs/wave1/run-escape";run.mkdir(parents=True)
    if part=="run": run.rmdir();run.symlink_to(outside,target_is_directory=True)
    elif part=="runs":
        import shutil
        shutil.rmtree(root/"runs");(root/"runs").symlink_to(outside,target_is_directory=True)
    else: (run/("lifecycle.sqlite" if part=="journal" else "execution.lock")).symlink_to(outside/"target")
    with pytest.raises((ContractDenied,ValueError,OSError)):
        journal=LifecycleJournal(root,"run-escape")
        with journal.lock(): pass
    assert not (outside/"lifecycle.sqlite").exists()

def test_composition_cannot_finish_after_deadline(repo_root,tmp_path,monkeypatch):
    import time
    engine=Wave1Orchestrator(repo_root,workspace=tmp_path,resource_limits={"tokens":1000,"usd":1,"deadline":time.time()+5})
    compose=engine.composer.compose_report
    def expire(*a,**kw):
        result=compose(*a,**kw)
        monkeypatch.setattr("research_forge.wave1.orchestrator.time.time",lambda:engine.resource_limits["deadline"]+1)
        return result
    monkeypatch.setattr(engine.composer,"compose_report",expire)
    request={"topic":"alpha beta", "objective":"compare", "intended_decision_or_use":"planning","required_output":"brief","desired_depth":"standard"}
    with pytest.raises(ForgeException): engine.run(request)


def test_reader_locators_have_distinct_receipts(repo_root,tmp_path):
    from research_forge.adapters.reader.gateway import gated_read
    engine,journal=journal_engine(repo_root,tmp_path)
    class Reader:
        adapter_id="web_reader_v1"
        def read(self,source,locator=None): return {"locator":locator}
    for locator in ("section:1","section:2"):
        out=gated_read(engine.gateway,engine.budget,Reader(),role="orchestrator",phase="read",source_ref={"url":"https://example.org/a"},live=False,locator=locator)
        assert out["locator"]==locator
    assert len(journal.view()["calls"])==2
