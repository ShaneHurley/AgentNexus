"""Compile owned metadata into content-addressed, immutable capability snapshots."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import warnings
from functools import lru_cache
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .contracts import ACTIONS, ContractDenied, Grant
from jsonschema.validators import validator_for
from jsonschema import validate, ValidationError
from .contract_schema import ROLE_SCHEMA

ORCHESTRATORS = frozenset({"deep-research", "research-messenger", "plan-prep", "use-master", "daily-coder", "researcher"})
FORMAT_VERSION = 1
_ROLE_VALIDATOR = validator_for(ROLE_SCHEMA)(ROLE_SCHEMA)

@lru_cache(maxsize=256)
def _checked_schema(serialized):
    value=json.loads(serialized)
    validator_for(value).check_schema(value)

def _check_schema(value):
    _checked_schema(json.dumps(value,sort_keys=True))


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class RegistrySnapshot:
    _data: dict[str, Any]

    def __init__(self, data):
        validate_snapshot(data)
        object.__setattr__(self,"_data",json.loads(json.dumps(data)))

    @property
    def data(self):
        return json.loads(json.dumps(self._data))

    @property
    def snapshot_id(self) -> str:
        return digest(self._data)

    def role(self, role_id: str, workspace: str | Path | None = None) -> dict[str, Any]:
        row = self.data["roles"].get(role_id)
        if row is None:
            raise ContractDenied(f"unknown role: {role_id}")
        result = json.loads(json.dumps(row))
        root = str(Path(workspace).resolve()) if workspace is not None else None
        result["grant"]["workspace_roots"] = [root] if root and row["workspace_access"] else []
        result["grant"]["write_roots"] = [root] if root and row["write_authority"] == "gateway" else []
        return result

    def authorize_dispatch(self, role_id: str, *, caller: str | None, user_invoked: bool = False) -> None:
        role = self.role(role_id)
        if not role["active"]:
            raise ContractDenied("inactive role")
        if user_invoked:
            if role_id not in {f"ide:{name}" for name in ORCHESTRATORS}:
                raise ContractDenied("only the six orchestrators are user invocable")
        elif caller not in role["callers"]:
            raise ContractDenied("undeclared caller")

    def discover(self, effective, *, kind: str) -> list[dict[str, Any]]:
        if kind not in {"tools", "skills"}:
            raise ContractDenied("unsupported discovery kind")
        allowed = effective.capabilities(kind)
        return [{"id": key, "summary": row["summary"], "version": row["version"]}
                for key, row in self.data[kind].items() if key in allowed and row["active"]]


def validate_snapshot(data: dict[str, Any]) -> None:
    if data.get("version") != FORMAT_VERSION:
        raise ContractDenied("unsupported snapshot version")
    ids = set()
    for group in ("roles", "tools", "skills"):
        rows = data.get(group)
        if not isinstance(rows, dict):
            raise ContractDenied(f"snapshot missing {group}")
        for key, row in rows.items():
            if key in ids or key != row.get("id"):
                raise ContractDenied("duplicate or mismatched capability ID")
            ids.add(key)
            body = {k: v for k, v in row.items() if k != "content_hash"}
            if row.get("content_hash") != digest(body):
                raise ContractDenied(f"invalid content hash: {key}")
            if row.get("active") and not row.get("installed"):
                raise ContractDenied("uninstalled capability activated")
    for group in ("roles","tools","skills"):
        for row in data[group].values():
            for dep in row.get("dependencies",[]):
                dep_id = dep if isinstance(dep,str) else dep.get("id") if isinstance(dep,dict) else None
                if dep_id not in ids: raise ContractDenied("unresolved capability dependency")
                if isinstance(dep,dict):
                    actual = next(rows[dep_id] for rows in (data["roles"],data["tools"],data["skills"]) if dep_id in rows)
                    if dep.get("version") != actual["version"]: raise ContractDenied("incompatible capability dependency version")
    roles = data["roles"]
    actual = {r["id"].removeprefix("ide:") for r in roles.values() if r.get("user_invocable")}
    if actual != ORCHESTRATORS:
        raise ContractDenied("registry must preserve exactly six orchestrators")
    for row in roles.values():
        try: _ROLE_VALIDATOR.validate(row)
        except ValidationError as exc: raise ContractDenied("invalid role contract: "+row.get("id","unknown")) from exc
        grant = Grant.from_mapping(row["grant"])
        if row["leaf"] and grant.delegation:
            raise ContractDenied("leaf role declares delegation")
        for action, group in (("tools", "tools"), ("skills", "skills"), ("delegation", "roles")):
            if getattr(grant, action) - set(data[group]):
                raise ContractDenied(f"unresolved {action} for {row['id']}")
        if grant.secret_use - set(data.get("secret_refs", {})):
            raise ContractDenied("unresolved secret capability")
        if (grant.memory_read | grant.memory_write) - set(data.get("memory_refs", {})):
            raise ContractDenied("unresolved memory capability")
        for schema in (row.get("input_schema"), row.get("output_schema")):
            if schema is not None and schema not in data.get("schemas", {}):
                raise ContractDenied(f"unresolved schema: {schema}")
        for dep in row.get("dependencies", []):
            dep_id = dep if isinstance(dep,str) else dep.get("id")
            if dep_id not in ids: raise ContractDenied(f"unresolved dependency: {dep_id}")
            if isinstance(dep,dict):
                actual = next(rows[dep_id] for rows in (data["roles"],data["tools"],data["skills"]) if dep_id in rows)
                if dep.get("version") != actual["version"]: raise ContractDenied("incompatible dependency version")


def compile_repository(repo_root: str | Path) -> RegistrySnapshot:
    root = Path(repo_root).resolve()
    data: dict[str, Any] = {"version": FORMAT_VERSION, "roles": {}, "tools": {}, "skills": {}, "schemas": {}, "sources": {}, "warnings": []}

    def read(path):
        path = path.resolve()
        if root not in path.parents or not path.is_file():
            raise ContractDenied(f"missing or escaped metadata: {path.name}")
        raw = path.read_bytes()
        data["sources"][path.relative_to(root).as_posix()] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw) if path.suffix == ".json" else yaml.safe_load(raw)

    def add(group, row):
        if row["id"] in data[group]:
            raise ContractDenied(f"duplicate {group} ID: {row['id']}")
        row["content_hash"] = digest(row)
        data[group][row["id"]] = row

    def schema(package, name):
        if not name:
            return None
        path = root / package / "schemas" / f"{name}.schema.json"
        parsed = read(path)
        _check_schema(parsed)
        key = path.relative_to(root).as_posix()
        data["schemas"][key] = parsed
        def refs(node):
            if isinstance(node,dict):
                ref = node.get("$ref")
                if ref and not ref.startswith("#"):
                    relative = ref.split("#",1)[0]
                    if ":" in relative: raise ContractDenied("remote schema references are unavailable")
                    dependency = path.parent / relative
                    document = read(dependency); _check_schema(document)
                    data["schemas"][dependency.relative_to(root).as_posix()] = document
                for value in node.values(): refs(value)
            elif isinstance(node,list):
                for value in node: refs(value)
        refs(parsed)
        return key

    def role(key, version, summary, tools=(), *, skills=(), callers=(), leaf=True, invocable=False, write=False, input_schema=None, output_schema=None, source=None, resources=None):
        add("roles", {"id": key, "version": str(version), "summary": summary, "responsibilities": [summary],
             "prohibitions": ["no undeclared tools", "no authority escalation", "no autonomous skill promotion"],
             "installed": True, "active": True, "leaf": leaf, "user_invocable": invocable,
             "callers": list(callers), "workspace_access": True, "write_authority": "gateway" if write else "none",
             "artifact_destinations": ["runtime-owned"], "approval_conditions": ["approved plan required for engineering writes"] if write else [],
             "escalation_conditions": ["missing authority", "invalid output", "resource exhaustion"],
             "input_schema": input_schema, "output_schema": output_schema, "dependencies": [], "model_requirements": [],
             "grant": {"tools": sorted(set(tools)), "skills": sorted(set(skills)), "delegation": [], "memory_read": [], "memory_write": [],
                       "workspace_roots": [], "write_roots": [], "resources": resources or {"tokens": 0, "cost": 0, "wall_time": 900, "tool_turns": 100, "concurrency": 2, "delegation_depth": 2}},
             "source": source})

    dc = "agents/coding/daily-coder-ecosystem"
    dc_tools = read(root / dc / "config/tools.json")
    if dc_tools.get("deny_by_default") is not True:
        raise ContractDenied("DC legacy configuration must deny by default")
    for tool in dc_tools["ecosystem_catalog"]:
        add("tools", {"id": tool, "version": "1", "summary": tool, "installed": True,
                      "active": tool not in dc_tools.get("disabled_until_adapter_configured", []), "callers": [], "dependencies": []})
    for path in sorted((root / dc / "agents").glob("*/agent.json")):
        row = read(path)
        allowed = dc_tools["role_allowlists"].get(row["id"])
        if allowed is None or set(row["tools"]) != set(allowed):
            raise ContractDenied(f"contradictory DC tool metadata: {row['id']}")
        prompt = path.parent / "prompt.md"
        data["sources"][prompt.relative_to(root).as_posix()] = hashlib.sha256(prompt.read_bytes()).hexdigest()
        # Runtime dispatcher owns delegation; even master is a bounded leaf worker.
        role(f"dc:{row['id']}", "1", row["job"], allowed, callers=("ide:daily-coder", "ide:use-master"),
             write=row.get("write_scope") in {"implementer", "test_author", "documenter"}, output_schema=schema(dc, row.get("output_schema")), source=path.relative_to(root).as_posix())
    rf = "agents/research/research-forge"
    policy = read(root / rf / "config/policies.yaml")
    if policy.get("default_deny") is not True:
        raise ContractDenied("RF legacy configuration must deny by default")
    def rf_tool(tool):
        if tool not in data["tools"]:
            add("tools", {"id": tool, "version": "1", "summary": tool, "installed": True, "active": True, "callers": [], "dependencies": []})
    aliases = {"research_charter": "charter"}
    for path in sorted((root / rf / "agents").glob("*/manifest.yaml")):
        row = read(path)
        tools = row.get("tools", [])
        for tool in tools:
            rf_tool(tool)
        input_name = aliases.get(row.get("input_schema"), row.get("input_schema"))
        output_name = aliases.get(row.get("output_schema"), row.get("output_schema"))
        available = all(not n or (root / rf / "schemas" / f"{n}.schema.json").is_file() for n in (input_name, output_name))
        role(f"rf:{row['role_id']}", row["interface_version"], row["role_id"], tools if available else [],
             callers=("rf:orchestrator", "ide:deep-research"), input_schema=schema(rf, input_name) if available else None,
             output_schema=schema(rf, output_name) if available else None, source=path.relative_to(root).as_posix())
        if not available:
            data["roles"][f"rf:{row['role_id']}"]["active"] = False
            data["warnings"].append(f"Unavailable legacy RF role {row['role_id']}: unresolved schema; dispatch denied.")
    for name, tools in policy.get("role_tool_allowlist", {}).items():
        for tool in tools:
            rf_tool(tool)
        if f"rf:{name}" not in data["roles"]:
            role(f"rf:{name}", "1", "Runtime-owned research recording and dispatch" if name == "orchestrator" else name,
                 tools, callers=("ide:deep-research",), leaf=name != "orchestrator")
    catalog_path = root / "agents/shared/skills/personal-catalog.yaml"
    catalog = read(catalog_path)
    residents = sum(bool(row.get("resident")) for row in catalog["skills"])
    if residents > catalog["resident_max"]:
        raise ContractDenied("resident skill ceiling exceeded")
    for row in catalog["skills"]:
        skill_path = catalog_path.parent / row["path"]
        read_skill = skill_path.resolve()
        if catalog_path.parent.resolve() not in read_skill.parents or not read_skill.is_file():
            raise ContractDenied("unresolved or escaped skill path")
        data["sources"][read_skill.relative_to(root).as_posix()] = hashlib.sha256(read_skill.read_bytes()).hexdigest()
        add("skills", {"id": f"skill:{row['id']}", "version": str(catalog["version"]), "summary": row['id'], "installed": True,
                       "active": row.get("status") == "active", "permissions": row.get("permissions", []),
                       "side_effects": row.get("side_effects"), "path": read_skill.relative_to(root).as_posix(), "dependencies": ["skill:" + name for name in row.get("calls", [])]})
    # Explicit source adapters: shared contracts and DC just-in-time skills.
    shared_package = root / "agents/shared/agent-core"
    shared = read(shared_package / "registry.yaml")
    seen_shared = set()
    for row in shared["roles"]:
        if row["id"] in seen_shared:
            raise ContractDenied("duplicate shared role")
        seen_shared.add(row["id"])
        ref = row["contract"]
        if ref.startswith("services/"):
            source = shared_package / "agent_core" / (ref.split("/")[-1] + ".py")
            read_bytes = source.read_bytes()
            data["sources"][source.relative_to(root).as_posix()] = hashlib.sha256(read_bytes).hexdigest()
            ins = outs = None
        else:
            source = shared_package / ref
            contract = read(source)
            ins = outs = None
            for field in ("input_schema", "output_schema"):
                resolved = shared_package / contract[field]
                parsed = read(resolved); _check_schema(parsed)
                key = resolved.relative_to(root).as_posix(); data["schemas"][key] = parsed
                if field == "input_schema": ins = key
                else: outs = key
        role("shared:" + row["id"], row["version"], row["primary_outcome"],
             callers=tuple("skill:" + x for x in row.get("callers", [])), input_schema=ins, output_schema=outs,
             source=source.relative_to(root).as_posix())
        # Installing the shared library is not activation. Explicit opt-in remains required.
        data["roles"]["shared:" + row["id"]]["active"] = False
    secrets_path = shared_package / "config/secret-capabilities.yaml"
    if secrets_path.is_file():
        secret_config=read(secrets_path)
        if secret_config.get("version") != 1 or set(secret_config) != {"version","refs"}:
            raise ContractDenied("invalid secret capability source")
        data["secret_refs"]={}
        for ref, rule in secret_config["refs"].items():
            if not isinstance(ref,str) or not ref or ref == "*" or set(rule) != {"namespaces"} or not set(rule["namespaces"]) <= {"dc","rf"}:
                raise ContractDenied("invalid secret capability rule")
            data["secret_refs"][ref]={"id":ref,"namespaces":rule["namespaces"]}
        for key, role_row in data["roles"].items():
            role_row["grant"]["secret_use"]=[ref for ref, rule in data["secret_refs"].items() if key.split(":",1)[0] in rule["namespaces"]]
    dc_skills = []
    for path in sorted((root / dc / "skills").glob("*/SKILL.md")):
        resolved = path.resolve()
        if (root / dc / "skills").resolve() not in resolved.parents:
            raise ContractDenied("escaped skill path")
        text = resolved.read_text(); front = yaml.safe_load(text.split("---", 2)[1])
        key = "skill:dc:" + front["name"]; dc_skills.append(key)
        data["sources"][resolved.relative_to(root).as_posix()] = hashlib.sha256(resolved.read_bytes()).hexdigest()
        add("skills", {"id":key, "version":str(front.get("version", "0")), "summary":front.get("description",key),
                       "installed":True, "active":front.get("status") == "active", "path":resolved.relative_to(root).as_posix(), "dependencies":[]})
    for name in ("planner", "implementer"):
        data["roles"]["dc:" + name]["grant"]["skills"] = dc_skills
    for rel in ("config/default.json", "config/budgets.json", "config/policies.json"):
        read(root / dc / rel)
    manifest = read(root / "agents/ide/MANIFEST.yml")
    invocable = {row["name"] for row in manifest["agents"] if row.get("user_invocable")}
    if invocable != ORCHESTRATORS:
        raise ContractDenied("IDE source roster does not contain exactly six orchestrators")
    for row in manifest["agents"]:
        name = row["name"]
        source = root / "agents/ide/canonical" / f"{name}.md"
        if not source.is_file():
            raise ContractDenied(f"missing canonical role {name}")
        data["sources"][source.relative_to(root).as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
        role(f"ide:{name}", manifest["contract_version"], name, leaf=name not in ORCHESTRATORS,
             invocable=name in ORCHESTRATORS, callers=(f"ide:{row['parent']}",) if row.get("parent") else (), source=source.relative_to(root).as_posix())
    for name in ("daily-coder", "use-master"):
        data["roles"][f"ide:{name}"]["grant"]["delegation"] = sorted(k for k in data["roles"] if k.startswith("dc:"))
    data["roles"]["ide:deep-research"]["grant"]["delegation"] = sorted(k for k in data["roles"] if k.startswith("rf:") and data["roles"][k]["active"])
    data["roles"]["rf:orchestrator"]["grant"]["delegation"] = sorted(k for k in data["roles"] if k.startswith("rf:") and k != "rf:orchestrator" and data["roles"][k]["active"])
    memory_config=read(shared_package / "config/memory-capabilities.yaml")
    if memory_config.get("version") != 1 or set(memory_config) != {"version", "refs", "roles"}:
        raise ContractDenied("invalid memory capability source")
    refs=memory_config["refs"]
    if not isinstance(refs,list) or len(refs)!=len(set(refs)) or any(ref not in {kind+":"+ns for kind in ("project","research","daily","shared") for ns in ("default","meta")} for ref in refs):
        raise ContractDenied("invalid memory capability references")
    data["memory_refs"]={ref:{"id":ref} for ref in refs}
    for tool in ("memory.export", "memory.import", "memory.backup"):
        rf_tool(tool)
    for key, rule in memory_config["roles"].items():
        if key not in data["roles"] or set(rule)!={"memory_read","memory_write","data_classes"}:
            raise ContractDenied("unknown memory role or rule")
        for action in ("memory_read","memory_write"):
            if not isinstance(rule[action],list) or set(rule[action])-set(refs):
                raise ContractDenied("undeclared memory scope")
        Grant.from_mapping(rule)
        data["roles"][key]["grant"].update(rule)
        if rule["memory_write"]:
            data["roles"][key]["grant"]["tools"]=sorted(set(data["roles"][key]["grant"]["tools"]) | {"memory.export","memory.import","memory.backup"})
    # IDE-only roles without runtime schema/tool contracts remain discoverable, not generic executable capabilities.
    data["warnings"].append("Legacy IDE prompt-only roles have no inferred tool grants; Daily personal skills require explicit task grants.")
    for row in data["roles"].values():
        row["content_hash"] = digest({k: v for k, v in row.items() if k != "content_hash"})
    validate_snapshot(data)
    return RegistrySnapshot(data)


class SnapshotStore:
    """Atomic publication. Activation requires an explicit grant ceiling and revocations."""
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def _atomic(self, path: Path, value: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".registry-", dir=self.directory)
        try:
            with os.fdopen(fd, "w") as out:
                json.dump(value, out, sort_keys=True)
                out.flush()
                os.fsync(out.fileno())
            os.replace(name, path)
            parent = os.open(self.directory, os.O_RDONLY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def publish(self, snapshot: RegistrySnapshot) -> str:
        validate_snapshot(snapshot.data)
        key = snapshot.snapshot_id
        path = self.directory / f"{key}.json"
        if path.exists():
            if self.load(key).snapshot_id != key:
                raise ContractDenied("snapshot collision")
        else:
            self._atomic(path, snapshot.data)
        return key

    def load(self, snapshot_id: str | None = None) -> RegistrySnapshot:
        if snapshot_id is None:
            snapshot_id = json.loads((self.directory / "active.json").read_text())["snapshot_id"]
        if not isinstance(snapshot_id, str) or len(snapshot_id) != 64 or any(c not in "0123456789abcdef" for c in snapshot_id):
            raise ContractDenied("invalid snapshot ID")
        data = json.loads((self.directory / f"{snapshot_id}.json").read_text())
        validate_snapshot(data)
        result = RegistrySnapshot(data)
        if result.snapshot_id != snapshot_id:
            raise ContractDenied("snapshot content changed")
        return result

    @contextmanager
    def _activation_lock(self):
        try: import fcntl
        except ImportError as exc: raise ContractDenied("registry activation locking is unavailable") from exc
        self.directory.mkdir(parents=True,exist_ok=True)
        with (self.directory / ".activation.lock").open("a") as handle:
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
            try: yield
            finally: fcntl.flock(handle.fileno(),fcntl.LOCK_UN)

    def activate(self, snapshot_id: str, *, ceiling: dict[str, Grant], revoked=()) -> None:
        with self._activation_lock():
            self._activate(snapshot_id,ceiling=ceiling,revoked=revoked)

    def _activate(self, snapshot_id: str, *, ceiling: dict[str, Grant], revoked=()) -> None:
        snapshot = self.load(snapshot_id)
        ceiling = dict(ceiling)
        revoked = set(revoked)
        current_path = self.directory / "active.json"
        if current_path.exists():
            current = json.loads(current_path.read_text())
            revoked |= set(current.get("revoked", []))
            previous = {key:Grant.from_mapping(value) for key,value in current.get("ceiling", {}).items()}
            for key, supplied in list(ceiling.items()):
                old = previous.get(key,Grant())
                merged = {action:sorted(getattr(old,action)&getattr(supplied,action)) for action in ACTIONS}
                merged["resources"] = {name:min(value,supplied.resources.get(name,0)) for name,value in old.resources.items()}
                ceiling[key]=Grant.from_mapping(merged)
        for key, row in snapshot.data["roles"].items():
            requested = Grant.from_mapping(row["grant"])
            allowed = ceiling.get(key, Grant())
            if any(value > allowed.resources.get(name, 0) for name, value in requested.resources.items()):
                raise ContractDenied("snapshot activation would increase resource ceilings")
            for action in ACTIONS:
                if getattr(requested, action) - (getattr(allowed, action) - revoked):
                    raise ContractDenied("snapshot activation would widen current grants or restore a revocation")
        self._atomic(self.directory / "active.json", {"snapshot_id": snapshot_id,"ceiling":{key:value.as_mapping() for key,value in ceiling.items()},"revoked":sorted(revoked)})

    rollback = activate
