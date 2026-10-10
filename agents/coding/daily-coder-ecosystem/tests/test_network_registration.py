"""Adapter registration must not acquire credentials before a tool is invoked."""
from pathlib import Path
import pytest
from agent_core.contracts import ContractDenied
from daily_coder.orchestrator import Orchestrator
from daily_coder.providers.mock import MockProvider
from daily_coder.state_store import StateStore

class RejectCredentials:
    def get(self, *args, **kwargs):
        raise ContractDenied("credential use requires explicit task authorization")

class RegisteredAdapters:
    def __init__(self): self.operations={}
    def register(self,name,operation): self.operations[name]=operation

def test_registering_optional_github_adapters_does_not_use_credentials(tmp_path):
    root=Path(__file__).resolve().parents[1]
    engine=Orchestrator(root,StateStore(tmp_path/"state.sqlite"),MockProvider(),secrets=RejectCredentials())
    broker=RegisteredAdapters()
    engine._register_github(broker)
    assert set(broker.operations) == {"github.repo.metadata","github.pull.list"}
    with pytest.raises(ContractDenied):
        broker.operations["github.repo.metadata"]({"owner":"public","repo":"fixture"})
