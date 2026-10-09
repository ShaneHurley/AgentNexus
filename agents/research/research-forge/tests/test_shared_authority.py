from pathlib import Path
import pytest
from research_forge.policy.gateway import PolicyGateway
from research_forge.policy.manifest import ToolManifest
from research_forge.adapters.reader.gateway import gated_read
from research_forge.adapters.reader.local import LocalTextReader
from research_forge.budget.manager import BudgetManager
from research_forge.errors import ForgeError
from agent_core.contracts import ContractDenied

def test_reader_ambiguous_resource_denied(repo_root,tmp_path):
    gw=PolicyGateway(repo_root/'config/policies.yaml',workspace_root=tmp_path)
    gw.register_tool(ToolManifest('local_reader_v1',{'read':True,'write':False,'network':False,'execute':False,'credential':False,'data_class':'public'}))
    with pytest.raises((ValueError,PermissionError)):
        gated_read(gw,BudgetManager(repo_root/'config/budgets.yaml'),LocalTextReader(),role='orchestrator',phase='read',source_ref={'url':'https://allowed.example','path':str(repo_root/'README.md')},live=False)

def test_shared_gateway_denies_unknown_role_and_manifest_expansion(repo_root,tmp_path):
    gw=PolicyGateway(repo_root/'config/policies.yaml',workspace_root=tmp_path)
    assert gw.register_tool(ToolManifest('mock_search_v1',{'read':True,'write':True,'network':False,'execute':False,'credential':False,'data_class':'public'})) is not None
    with pytest.raises(ContractDenied): gw.authority.dispatch('charter_planner','dc:master')
    with pytest.raises(ContractDenied): gw.authority.memory('orchestrator','project')


def test_negation_and_missing_provenance_never_verify(repo_root):
    import hashlib
    from research_forge.schemas_pkg.registry import get_registry
    from research_forge.wave1.verifier import CitationVerifier
    card={"evidence_id":"EVD-00000099","source_id":"SRC-0099","question_addressed":"RQ-001","claim":"Treatment improves survival.","claim_status":"UNKNOWN","locator":"paragraph:1","access_level":"full","confidence":"MEDIUM","confidence_reason":"test","verifier_status":"pending"}
    source={"canonical_title":"Study","canonical_url":"https://public.example/study"}
    text="There is no evidence that treatment improves survival."
    read={"canonical_url":source['canonical_url'],"access_level":"full","chunks":[{"locator":"paragraph:1","text":text}]}
    verifier=CitationVerifier(get_registry(repo_root))
    result=verifier.verify(card,source=source,read_response=read)
    assert result['verifier_status']=='failed' and result['claim_status']=='REJECTED'
    # Even an injected semantic checker cannot bypass retrieval provenance.
    verifier=CitationVerifier(get_registry(repo_root),entailment_checker=lambda *a:'supports')
    result=verifier.verify(card,source=source,read_response=read,live=True)
    assert result['verifier_status']=='failed'
    read['metadata']={"retrieval_status":"retrieved","synthetic":False,"content_hash":"sha256:"+hashlib.sha256(text.encode()).hexdigest()}
    read.pop('canonical_url')
    assert verifier.verify(card,source=source,read_response=read,live=True)['verifier_status']=='failed'

def test_rf_pin_roundtrip_and_legacy_resume_denied(repo_root):
    from research_forge.wave1.orchestrator import Wave1Orchestrator, RunState
    orch=Wave1Orchestrator(repo_root)
    out=orch.run({'topic':'Alpha vs Beta'})
    state=RunState.from_dict(out['state'])
    assert state.registry_hash==orch.gateway.authority.snapshot.snapshot_id
    state.registry_hash=None
    with pytest.raises(ContractDenied): orch.resume(state,{})

def test_experiment_store_jail_and_code_backend_requirement(repo_root,tmp_path):
    from research_forge.experiments.store import ExperimentStore
    from research_forge.experiments.kinds import run_python_unittest_benchmark
    from agent_core.isolation import IsolationUnavailable
    store=ExperimentStore(tmp_path,package_root=repo_root)
    with pytest.raises(PermissionError): store.exp_dir('../../escape')
    with pytest.raises(PermissionError): store.path('EXP-safe','../outside')
    outside=tmp_path/'outside'; outside.mkdir()
    store.root.mkdir(parents=True,exist_ok=True)
    (store.root/'EXP-escape').symlink_to(outside,target_is_directory=True)
    with pytest.raises(PermissionError): store.exp_dir('EXP-escape')
    with pytest.raises(IsolationUnavailable): run_python_unittest_benchmark(tmp_path)
