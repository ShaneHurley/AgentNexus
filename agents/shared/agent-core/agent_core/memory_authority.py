"""Bind reviewed role maxima to one store; explicit six-layer task grants remain required."""
from __future__ import annotations
import json
import uuid
from pathlib import Path
from .contracts import ContractDenied, EffectiveGrant, Grant
from .runtime_authority import RuntimeAuthority, runtime_snapshot


def read_json(path, *, maximum=2_000_000):
    path=Path(path).absolute()
    if any(part.is_symlink() for part in (path,*path.parents)):
        raise ContractDenied("symlink configuration/input denied")
    if not path.is_file() or path.stat().st_size>maximum:
        raise ValueError("missing or oversized JSON input")
    return json.loads(path.read_text())


def _bind(mapping,store_id,kind):
    result=dict(mapping)
    for action in ("memory_read","memory_write"):
        result[action]=["store:"+store_id+":"+ref.split(":",1)[1] for ref in mapping.get(action,[]) if ref.startswith(kind+":")]
    return result


def evaluate_memory_access(spec, *, workspace, store_id, kind, snapshot=None):
    from .memory import MemoryAccess
    if not isinstance(spec,dict) or set(spec)!={"version","identity","run_id","role","layers"} or spec["version"]!=1:
        raise ContractDenied("versioned explicit memory grant required")
    if any(not isinstance(spec[k],str) or not spec[k].strip() for k in ("identity","run_id","role")):
        raise ContractDenied("identity, run and role required")
    try:
        if str(uuid.UUID(store_id))!=store_id: raise ValueError()
    except (ValueError,TypeError,AttributeError) as exc: raise ContractDenied("canonical store UUID required") from exc
    if kind not in {"project","research","daily","shared"}: raise ContractDenied("unknown store kind")
    workspace=Path(workspace).absolute()
    if not workspace.is_dir() or any(p.is_symlink() for p in (workspace,*workspace.parents)):
        raise ContractDenied("existing non-symlink workspace required")
    reviewed=snapshot or runtime_snapshot()
    ns,sep,role=spec["role"].partition(":")
    if not sep: raise ContractDenied("qualified role required")
    authority=RuntimeAuthority(ns,workspace,snapshot=reviewed)
    contract=reviewed.role(spec["role"],workspace)
    contract["grant"]=_bind(contract["grant"],store_id,kind)
    revoked=set(authority.revoked)
    for ref in authority.revoked:
        if ref.startswith(kind+":"): revoked.add("store:"+store_id+":"+ref.split(":",1)[1])
    effective=EffectiveGrant.evaluate(contract,spec["layers"],revoked=revoked)
    if authority.current_ceiling is not None:
        ceiling=_bind(authority.current_ceiling.get(spec["role"],{}),store_id,kind)
        ceiling["workspace_roots"]=contract["grant"]["workspace_roots"]
        ceiling["write_roots"]=contract["grant"]["write_roots"]
        effective=effective.narrow(Grant.from_mapping(ceiling))
    return MemoryAccess(spec["identity"],spec["run_id"],effective)
