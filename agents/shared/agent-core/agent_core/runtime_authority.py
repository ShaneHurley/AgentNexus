"""Owned runtime translation of legacy task scopes into six explicit grant layers."""
from __future__ import annotations
from pathlib import Path
import os,json
from .contracts import ContractDenied, Grant, EffectiveGrant, LAYERS
from .registry_snapshot import compile_repository, RegistrySnapshot, SnapshotStore


def repository_root(start=None):
    for path in (Path(start or __file__).resolve(), *Path(start or __file__).resolve().parents):
        if (path/'agents/ide/MANIFEST.yml').is_file(): return path
    raise ContractDenied("shared registry requires an AgentNexus source root")

def registry_store():
    return Path(os.environ.get("AGENTNEXUS_REGISTRY_STORE",str(repository_root()/".agentnexus/registry"))).expanduser().resolve()

def runtime_snapshot():
    compiled=compile_repository(repository_root())
    directory=registry_store()
    if not (directory/"active.json").is_file(): return compiled
    reviewed=SnapshotStore(directory).load()
    if reviewed.data["sources"] != compiled.data["sources"]:
        raise ContractDenied("active registry source pins do not match installed metadata")
    for key,row in reviewed.data["roles"].items():
        baseline=compiled.data["roles"].get(key)
        if baseline is None or (row["active"] and not baseline["active"]): raise ContractDenied("active registry broadens installed authority")
        if set(row["callers"]) - set(baseline["callers"]): raise ContractDenied("active registry broadens callers")
        for action in ("tools","skills","delegation","memory_read","memory_write","secret_use"):
            if set(row["grant"].get(action,[])) - set(baseline["grant"].get(action,[])): raise ContractDenied("active registry broadens capability grants")
    return reviewed

class RuntimeAuthority:
    def __init__(self, namespace, workspace, *, snapshot=None, task_layers=None, revoked=()):
        self.snapshot=snapshot or runtime_snapshot()
        self.namespace=namespace; self.workspace=Path(workspace).resolve()
        self.task_layers=task_layers
        self.current_ceiling=None
        pointer=registry_store()/"active.json"
        if pointer.is_file():
            policy=json.loads(pointer.read_text())
            if policy["snapshot_id"] != self.snapshot.snapshot_id: raise ContractDenied("run registry pin differs from active registry")
            self.current_ceiling=policy.get("ceiling",{})
            revoked=set(revoked)|set(policy.get("revoked",[]))
        self.revoked=frozenset(revoked)

    def effective(self, role):
        contract=self.snapshot.role(self.namespace+':'+role,self.workspace)
        baseline=Grant.from_mapping(contract['grant'])
        # Legacy task invocation authorizes existing capabilities only, within this
        # workspace. Explicit configured layers can narrow any of these bounds.
        layers={name:baseline for name in LAYERS}
        # Installed secret capabilities never imply task authorization.
        user=baseline.as_mapping(); user["secret_use"]=[]
        layers["user"]=Grant.from_mapping(user)
        if self.task_layers is not None:
            if set(self.task_layers) != set(LAYERS): raise ContractDenied("incomplete task authority")
            layers={name:Grant.from_mapping(self.task_layers[name]) for name in LAYERS}
        result=EffectiveGrant.evaluate(contract,layers,revoked=self.revoked)
        if self.current_ceiling is not None:
            mapping=dict(self.current_ceiling.get(contract["id"],{}))
            mapping["workspace_roots"]=contract["grant"]["workspace_roots"]
            mapping["write_roots"]=contract["grant"]["write_roots"]
            result=result.narrow(Grant.from_mapping(mapping))
        return result

    def dispatch(self, role, caller, *, depth=None, active_children=0, task_key=None, ancestor_keys=()):
        self.snapshot.authorize_dispatch(self.namespace+':'+role,caller=caller)
        parent=self.snapshot.role(caller,self.workspace)
        g=Grant.from_mapping(parent['grant'])
        layers={name:g for name in LAYERS}
        if self.task_layers is not None:
            if set(self.task_layers) != set(LAYERS): raise ContractDenied("incomplete task authority")
            layers={name:Grant.from_mapping(self.task_layers[name]) for name in LAYERS}
        authority=EffectiveGrant.evaluate(parent,layers,revoked=self.revoked)
        if self.current_ceiling is not None:
            authority=authority.narrow(Grant.from_mapping(self.current_ceiling.get(caller,{})))
        authority.authorize_delegation(self.namespace+':'+role,
            depth=(1 if caller.startswith("rf:") else 0) if depth is None else depth,
            active_children=active_children,task_key=task_key or caller+"->"+self.namespace+":"+role,
            ancestor_keys=ancestor_keys)
        self.effective(role) # validate activation and grant before prompt/model work

    def tool(self, role, tool, *, target=None, write=False):
        row=self.snapshot.data['tools'].get(tool)
        if not row or not row['active']: raise ContractDenied("unknown or inactive tool")
        self.effective(role).authorize('tools',tool,target,write=write)

    def skill(self, role, skill):
        row=self.snapshot.data['skills'].get(skill)
        if not row or not row['active']: raise ContractDenied("unknown or inactive skill")
        self.effective(role).authorize('skills',skill)

    def memory(self, role, namespace, *, write=False):
        self.effective(role).authorize('memory_write' if write else 'memory_read',namespace)

    def pin(self, directory):
        store=SnapshotStore(directory); key=store.publish(self.snapshot)
        return key
