"""Pinned reviewed model policy and task-authorized adapter dispatch."""
from __future__ import annotations
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import time
import yaml
from .contracts import ContractDenied, EffectiveGrant, LAYERS
from .model_catalog import CatalogSnapshot, CatalogStore, digest, canonical
from .model_resolver import ModelResolver
from .runtime_authority import RuntimeAuthority, runtime_snapshot

PIN_FIELDS={'model_catalog','model_policy','model_catalog_hash','model_policy_hash'}

def load_model_settings(repository,*,directory=None,pinned=None):
    root=Path(repository)
    if pinned is not None:
        result={k:pinned[k] for k in PIN_FIELDS}
    else:
        directory=Path(directory or root/'.agentnexus/models')
        pointer=directory/'routing-active.json'
        if pointer.is_file():
            active=json.loads(pointer.read_text())
            if set(active)!={'catalog_hash','policy_hash'}:raise ValueError('invalid routing activation')
            catalog=CatalogStore(directory).load(active['catalog_hash']).data
            policy_hash=active['policy_hash']
            if not isinstance(policy_hash,str) or len(policy_hash)!=64 or any(c not in '0123456789abcdef' for c in policy_hash):raise ValueError('invalid policy pin')
            policy=json.loads((directory/('policy-'+policy_hash+'.json')).read_text())
            result={'model_catalog':catalog,'model_policy':policy,'model_catalog_hash':active['catalog_hash'],'model_policy_hash':policy_hash}
        else:
            config=root/'agents/shared/agent-core/config'
            catalog=yaml.safe_load((config/'catalog.yaml').read_text())
            policy=yaml.safe_load((config/'agents.yaml').read_text())
            result={'model_catalog':catalog,'model_policy':policy,'model_catalog_hash':digest(catalog),'model_policy_hash':digest(policy)}
    resolver=ModelResolver(result['model_catalog'],result['model_policy'])
    if resolver.catalog.hash!=result['model_catalog_hash'] or resolver.policy_hash!=result['model_policy_hash']:raise ValueError('routing pin integrity mismatch')
    return json.loads(canonical(result))

def activate_model_settings(directory,catalog_hash,policy,*,confirmed=False):
    if confirmed is not True:raise ContractDenied('model policy activation requires confirmation')
    directory=Path(directory);store=CatalogStore(directory);catalog=store.load(catalog_hash)
    resolver=ModelResolver(catalog,policy)
    policy_path=directory/('policy-'+resolver.policy_hash+'.json')
    if policy_path.exists() and policy_path.read_text()!=canonical(policy):raise ValueError('policy integrity mismatch')
    store._atomic(policy_path,canonical(policy))
    # This one pointer is the supervisor authority for the matching pair.
    store._atomic(directory/'routing-active.json',canonical({'catalog_hash':catalog.hash,'policy_hash':resolver.policy_hash}))
    return {'catalog_hash':catalog.hash,'policy_hash':resolver.policy_hash}

class SupervisedProvider:
    def __init__(self,provider,pins,*,provider_name,run_id,workspace,namespace='dc',broker=None,registry=None,task_layers=None):
        self.provider=provider;self.name=provider_name;self.run_id=run_id;self.workspace=Path(workspace).resolve();self.namespace=namespace
        self.pins=pins;self.resolver=ModelResolver(pins['model_catalog'],pins['model_policy']);self.broker=broker
        self.registry=registry or runtime_snapshot();self.task_layers=task_layers;self.decisions=[];self.call_decisions={}
        self.capabilities=getattr(provider,'capabilities',None)

    def _grant(self,role,ref):
        contract=self.registry.role(self.namespace+':'+role,self.workspace)
        baseline=contract['grant']
        if self.task_layers is None:
            layers={name:dict(baseline) for name in LAYERS}
            layers['user']=dict(baseline,secret_use=[ref])
        else:layers=self.task_layers
        effective=RuntimeAuthority(self.namespace,self.workspace,snapshot=self.registry,task_layers=layers).effective(role)
        effective.authorize('secret_use',ref)
        return effective

    def secret_grant(self,request):
        ref=request.credential_ref
        if request.run_id!=self.run_id or not ref or self.broker is None:raise ContractDenied('credential task binding denied')
        grant=self._grant(request.role,ref)
        expiry=min(time.time()+120,request.deadline) if request.deadline is not None else time.time()+120
        return self.broker.authorize(self.namespace+':'+request.role,self.run_id,ref,'invoke',expiry,grant)

    def _explain(self,role,max_output,input_tokens=0,deadline=None,features=()):
        role_id=self.namespace+':'+role
        credentials=[]
        if self.broker is not None:
            for model in self.resolver.catalog.data['models'].values():
                ref=model['credential_ref']
                if model['provider']!=self.name or not ref:continue
                request=type('Probe',(),dict(role=role,run_id=self.run_id,credential_ref=ref,deadline=deadline))()
                try:
                    if self.broker.probe(self.secret_grant(request)):credentials.append(ref)
                except (ContractDenied,RuntimeError):pass
        req={'risk':'high' if role in {'implementer','test_author','documenter','master','frontier_advisor'} else 'low',
             'privacy':'local' if self.name in {'mock','local'} else 'private','features':list(features),
             'context_tokens':input_tokens+max_output,'output_tokens':max_output,'expected_input_tokens':input_tokens,'expected_output_tokens':max_output}
        if deadline is not None:req['deadline_ms']=max(0,(deadline-time.time())*1000)
        explanation=self.resolver.explain(role_id,req,{'available_providers':[self.name],'available_credentials':sorted(set(credentials))})
        if explanation['selected_alias'] is None:raise ContractDenied('no eligible reviewed model for role/provider; inspect model exclusions')
        self.decisions.append(explanation)
        return explanation

    def resolve_for_role(self,role,tier,max_output_tokens,estimated_input_tokens=0,deadline=None,features=()):
        selection=self._explain(role,max_output_tokens,estimated_input_tokens,deadline,features)
        return self.resolver.catalog.data['models'][selection['selected_alias']]['model']

    def invoke(self,request):
        if request.run_id!=self.run_id:raise ContractDenied('provider task binding denied')
        from .efficiency_tools import token_estimate
        estimate=token_estimate(request.prompt+json.dumps(request.input_packet,sort_keys=True)+json.dumps(request.tool_results,default=str))
        features=['tools'] if request.tools else []
        selection=self._explain(request.role,request.max_output_tokens,estimate,request.deadline,features)
        model=self.resolver.catalog.data['models'][selection['selected_alias']]
        if request.model not in {'unknown',model['model']}:raise ContractDenied('native model differs from reviewed selection')
        options=dict(request.provider_options)
        if self.name=='openrouter':
            requested=options.get('provider',{})
            if not isinstance(requested,dict):raise ContractDenied('invalid downstream provider policy')
            options['provider']={**requested,'require_parameters':True,'data_collection':'deny'}
        pinned=replace(request,model=model['model'],credential_ref=model['credential_ref'],catalog_id=self.pins['model_catalog_hash'],policy_id=self.pins['model_policy_hash'],provider_options=options)
        self.call_decisions[request.idempotency_key]=selection
        result=self.provider.invoke(pinned)
        if result.model not in {model['model'],'unknown'}:raise ContractDenied('provider model differs from reviewed selection')
        return result

    def cancel(self,request_id):
        return self.provider.cancel(request_id) if hasattr(self.provider,'cancel') else 'unsupported'
