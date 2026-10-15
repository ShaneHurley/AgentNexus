"""Validation input vocabulary does not make a concrete task ambiguous."""
import hashlib
import importlib.util
from pathlib import Path
import uuid
import pytest
from daily_coder.router import size_request
from agent_core.contracts import ContractDenied

spec=importlib.util.spec_from_file_location("contained_size_helpers",Path(__file__).with_name("test_coder_v1.py"))
helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)

@pytest.mark.parametrize("phrase",["unknown fields","unknown/missing fields","unknown keys","unknown rulesets","unknown versions"])
def test_validation_terms_are_not_request_ambiguity(phrase):
    result=size_request("Reject malformed reports with "+phrase+" in the existing parser.")
    assert result["profile"]=="S" and not result["ambiguous"]

@pytest.mark.parametrize("task_text",["Investigate unknown behavior","Reject unknown fields and investigate unknown behavior","Compare options for this parser"])
def test_genuine_ambiguity_still_requires_larger_workflow(task_text):
    assert size_request(task_text)["profile"]!="S"

@pytest.mark.parametrize("task_text",["Change authentication and reject unknown fields","Change public API and reject unknown fields","Refactor architecture and reject unknown fields"])
def test_risk_and_broad_design_signals_are_preserved(task_text):
    assert size_request(task_text)["profile"]!="S"


def test_unsupported_scope_rejected_before_native_creation_or_model_call(tmp_path,monkeypatch):
    engine,run,packet,gateway,broker=helpers.make(tmp_path,live=True)
    task_text="Change authentication across the application"
    engine.task_contract["request_sha256"]=hashlib.sha256(task_text.encode()).hexdigest()
    key=str(uuid.uuid4())
    monkeypatch.setattr(engine.provider,"invoke",lambda *args:pytest.fail("No model dispatch permitted"))
    with pytest.raises(ContractDenied):engine.create(task_text,broker.repo,run_id=key)
    with pytest.raises(KeyError):engine.state.get(key)
    assert engine.state.active_budget_reservations(key)["calls"]==0
