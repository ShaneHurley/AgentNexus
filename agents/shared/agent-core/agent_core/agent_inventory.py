"""Read-only inventory of existing manifests, prompts, and runtime contracts.

This report is an audit view, never a dispatch registry or an authority source.
Source sha256 hashes raw bytes; normalized_text_sha256 matches Daily Coder's
universal-newline UTF-8 text hashes for declared prompt, JSON, and canonical
provenance. Research Forge source_sha256 declarations remain raw-byte hashes.
It executes no agents, tools, hooks, or model calls. Token sizes are estimates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
from urllib.parse import unquote
from typing import Any, Iterable

import yaml
from jsonschema.exceptions import SchemaError, ValidationError
from .contracts import ContractDenied

PUBLIC_AGENTS = frozenset({"deep-research", "research-messenger", "plan-prep", "use-master", "daily-coder", "researcher"})
ALIASES = {"ide-agents/": "agents/ide/", "daily-coder-ecosystem/": "agents/coding/daily-coder-ecosystem/", "research-forge/": "agents/research/research-forge/"}
PROJECTIONS = {"cursor": (".cursor/agents", "{name}.md"), "claude": (".claude/agents", "{name}.md"), "vscode": (".github/agents", "{name}.agent.md")}


def _frontmatter(text: str) -> tuple[dict, str]:
    match = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", text, re.S)
    if not match:
        return {}, text
    value = yaml.safe_load(match[1])
    return (value if isinstance(value, dict) else {}), match[2]


def _projection_front(front: dict, platform: str) -> dict:
    """Semantic projection rules from the existing IDE sync format.

    Compare complete metadata, including tool restrictions; ignore YAML layout.
    """
    readonly = bool(front["readonly"]) if "readonly" in front else str(front.get("authority", "")).lower() != "implementation"
    name = front.get("name")
    description = front.get("description", f"IDE agent {name} (canonical projection)" if platform == "cursor" else f"IDE agent {name}")
    if platform == "cursor":
        expected = dict(front, name=name, description=description, readonly=readonly)
        if readonly and "tools" not in expected:
            expected["tools"] = {"deny": ["Write", "StrReplace", "Delete", "EditNotebook", "Shell"]}
        return expected
    expected = {"name": name, "description": str(description)}
    if platform == "claude":
        expected["readonly"] = readonly
        disallowed = front.get("disallowedTools")
        if disallowed is None and readonly:
            disallowed = ["Write", "Edit", "MultiEdit", "NotebookEdit", "Bash"]
        if disallowed is not None:
            expected["disallowedTools"] = disallowed
        if front.get("allowedTools") is not None:
            expected["allowedTools"] = front["allowedTools"]
        fields = ("authority", "contract_version", "skill_refs", "user_invocable")
    else:
        expected["tools"] = front.get("tools") if front.get("tools") is not None else ["search/codebase", "web/fetch", "read/readFile"]
        expected["user-invocable"] = front.get("user_invocable", front.get("user-invocable", False))
        if readonly:
            expected["readonly"] = True
        fields = ("authority", "contract_version", "skill_refs", "hooks", "handoffs", "agents")
    for field in fields:
        if field in front:
            expected[field] = front[field]
    return expected


def build_inventory(repo_root: str | Path, *, selected: Iterable[str] = (), max_prompt_bytes: int = 32000) -> dict[str, Any]:
    """Return a deterministic audit; selected IDs estimate only their prompt loads.

    IDs use ide:<name> and browser:<family>[/<variant>]. Unknown metadata is
    explicit. Findings retain repository-relative paths and one-based lines.
    Missing or escaped paths are never read, including through symlinks.
    """
    if type(max_prompt_bytes) is not int or max_prompt_bytes < 256:
        raise ValueError("invalid prompt byte ceiling")
    root = Path(repo_root).resolve()
    sources: dict[str, dict] = {}
    findings: list[dict] = []
    logical_aliases: list[dict] = []
    ide_agents: list[dict] = []
    browser_agents: list[dict] = []
    assets: list[dict] = []

    def finding(code, path, message, line=1, severity="error"):
        row = {"code": code, "path": str(path), "line": line, "severity": severity, "message": message}
        if row not in findings:
            findings.append(row)

    def safe_path(rel):
        path = root / rel
        if not path.resolve().is_relative_to(root):
            finding("escaped-path", rel, "Path escapes the repository; not read")
            return None
        return path

    def read(rel, *, required=True):
        path = safe_path(rel)
        if path is None:
            return None
        if not path.is_file():
            if required:
                finding("missing-path", rel, "Missing file: " + str(rel))
            return None
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        sources[str(rel)] = {"sha256": hashlib.sha256(raw).hexdigest(), "normalized_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "bytes": len(raw), "characters": len(text), "estimated_tokens": math.ceil(len(text) / 4)}
        return text

    def document(rel, required=True):
        text = read(rel, required=required)
        if text is None:
            return {}
        try:
            value = json.loads(text) if str(rel).endswith(".json") else yaml.safe_load(text)
            if not isinstance(value, dict):
                raise ValueError("Expected mapping")
            return value
        except (ValueError, yaml.YAMLError) as exc:
            finding("invalid-manifest", rel, "Cannot parse manifest: " + str(exc))
            return {}

    def resolve_alias(ref, owner):
        for old, new in ALIASES.items():
            if ref.startswith(old):
                resolved = new + ref[len(old):]
                logical_aliases.append({"owner": owner, "alias": ref, "resolved": resolved})
                return resolved
        return ref

    def check_ref(ref, owner):
        resolved = resolve_alias(str(ref), owner)
        path = safe_path(resolved)
        if path is not None and not path.exists():
            finding("missing-path", owner, "Missing metadata reference: " + resolved)
        elif path is not None and path.is_file():
            read(resolved)
        return resolved

    def rows(document_value, key, owner):
        value = document_value.get(key, [])
        if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
            finding("invalid-manifest", owner, key + " must be a list of mappings")
            return []
        return value

    manifest_path = "agents/ide/MANIFEST.yml"
    manifest = document(manifest_path)
    roster = rows(manifest, "agents", manifest_path)
    names = {row.get("name") for row in roster}
    actual_public = {row.get("name") for row in roster if row.get("user_invocable") is True}
    if actual_public != PUBLIC_AGENTS:
        finding("public-six-invariant", manifest_path, "Expected exactly six public agents; actual: " + ", ".join(sorted(str(n) for n in actual_public)))
    seen = set()
    bodies = {}
    for row in roster:
        name = row.get("name")
        if not isinstance(name, str) or not name:
            finding("invalid-manifest", manifest_path, "Agent name is missing")
            continue
        identifier = "ide:" + name
        if identifier in seen:
            finding("duplicate-id", manifest_path, "Duplicate ID: " + identifier)
        seen.add(identifier)
        rel = "agents/ide/canonical/" + name + ".md"
        text = read(rel)
        front, body = {}, ""
        if text is not None:
            try:
                front, body = _frontmatter(text)
            except yaml.YAMLError as exc:
                finding("invalid-frontmatter", rel, str(exc))
            if not front.get("contract_version"):
                finding("missing-contract", rel, "Canonical prompt has no contract_version")
            if front.get("name") != name:
                finding("canonical-name-mismatch", rel, "Canonical name disagrees with manifest")
            if front.get("user_invocable") != row.get("user_invocable"):
                finding("public-metadata-mismatch", rel, "Canonical public flag disagrees with manifest")
            bodies[name] = (front, body)
        parent = row.get("parent") or "unknown"
        if parent != "unknown" and parent not in names:
            finding("unknown-parent", manifest_path, name + " names missing parent " + str(parent))
        if row.get("user_invocable") is None:
            finding("unknown-public-status", manifest_path, name + " has no explicit user_invocable flag")
        for field in ("canonical", "source", "import_script"):
            if row.get(field):
                check_ref(row[field], manifest_path)
        if row.get("canonical_sha256") and sources.get(rel) and row["canonical_sha256"] != sources[rel]["normalized_text_sha256"]:
            finding("source-hash-mismatch", manifest_path, "Declared canonical_sha256 (universal-newline UTF-8 text) differs from file: " + rel)
        if row.get("source") and row.get("source_sha256"):
            source_rel = resolve_alias(str(row["source"]), manifest_path)
            if sources.get(source_rel) and row["source_sha256"] != sources[source_rel]["sha256"]:
                finding("source-hash-mismatch", manifest_path, "Declared source_sha256 differs from file: " + source_rel)
        projection = row.get("projection")
        if isinstance(projection, dict) and projection.get("source_agent"):
            source_dir = check_ref(projection["source_agent"], manifest_path)
            for hash_field, filename in (("prompt_sha256", "prompt.md"), ("agent_json_sha256", "agent.json")):
                if projection.get(hash_field):
                    source_rel = str(Path(source_dir) / filename)
                    read(source_rel)
                    if sources.get(source_rel) and projection[hash_field] != sources[source_rel]["normalized_text_sha256"]:
                        finding("source-hash-mismatch", manifest_path, "Declared " + hash_field + " (universal-newline UTF-8 text) differs from file: " + source_rel)
        ide_agents.append({"id": identifier, "name": name, "path": rel, "public": row.get("user_invocable", "unknown"), "parent": parent,
                           "authority": row.get("authority", "unknown"), "execution_surface": "IDE prompt; runtime status recorded separately", "runtime_ids": [], "size": sources.get(rel)})
        for platform, (default_dir, pattern) in PROJECTIONS.items():
            config = manifest.get("projections", {}).get(platform, {})
            rel_projection = str(Path(config.get("rel_dir", default_dir)) / config.get("filename_pattern", pattern).format(name=name))
            projected = read(rel_projection)
            if projected is None or text is None:
                continue
            try:
                projected_front, projected_body = _frontmatter(projected)
                # Generated banners precede the canonical body; compare the full
                # remaining body and authority/public metadata across IDE formats.
                projected_body = re.sub(r"\A\s*(?:<!--.*?-->\s*)+", "", projected_body, flags=re.S)
                drift = projected_body.strip() != body.strip() or projected_front != _projection_front(front, platform)
                if drift:
                    finding("projection-drift", rel_projection, "Projection body or contract metadata differs from canonical " + rel)
            except yaml.YAMLError as exc:
                finding("invalid-frontmatter", rel_projection, str(exc))
    canonical_dir = safe_path("agents/ide/canonical")
    if canonical_dir and canonical_dir.is_dir():
        for path in sorted(canonical_dir.glob("*.md")):
            if path.stem not in names and path.name != "README.md":
                rel = path.relative_to(root).as_posix()
                read(rel)
                finding("unlisted-canonical", rel, "Canonical prompt is absent from IDE manifest")

    index_path = "agents/shared/browser/MANIFEST.index.json"
    index = document(index_path)
    index_families = set(index.get("families", []))
    all_families = set()
    browser_seen = set()
    shards = []
    for shard in rows(index, "shards", index_path):
        shard_path = shard.get("manifest")
        shard_root = shard.get("root")
        if not isinstance(shard_path, str) or not isinstance(shard_root, str):
            finding("invalid-manifest", index_path, "Shard requires manifest and root paths")
            continue
        value = document(shard_path)
        entries = rows(value, "agents", shard_path)
        actual_families = {entry.get("family") for entry in entries if isinstance(entry.get("family"), str)}
        all_families |= actual_families
        declared_families = set(value.get("families", []))
        if declared_families != actual_families:
            finding("shard-family-list-mismatch", shard_path, "Declared families differ from actual entries: declared=" + str(sorted(declared_families)) + "; actual=" + str(sorted(actual_families)))
        if set(shard.get("family_ids", [])) != actual_families:
            finding("index-shard-family-mismatch", index_path, "Indexed families differ from actual entries in " + shard_path)
        if value.get("agent_count") != len(entries):
            finding("declared-count-mismatch", shard_path, "agent_count differs from actual entry count " + str(len(entries)))
        shards.append({"id": shard.get("id", "unknown"), "manifest": shard_path, "actual_families": sorted(actual_families), "declared_families": sorted(declared_families), "count": len(entries)})
        for entry in entries:
            family, variant = entry.get("family"), entry.get("variant")
            if not isinstance(family, str) or (variant is not None and not isinstance(variant, str)) or not isinstance(entry.get("path"), str):
                finding("invalid-manifest", shard_path, "Paste entry requires family, path, and optional string variant")
                continue
            identifier = "browser:" + family + ("/" + variant if variant else "")
            if identifier in browser_seen:
                finding("duplicate-id", shard_path, "Duplicate ID: " + identifier)
            browser_seen.add(identifier)
            paste_rel = str(Path(shard_root) / entry["path"] / "AGENT_MESSAGE.md")
            paste = read(paste_rel)
            if variant is None:
                guide_rel = str(Path(shard_root) / entry["path"] / "HOW_TO.md")
                if read(guide_rel, required=False) is not None:
                    assets.append({"kind": "browser-guide", "path": guide_rel, "size": sources[guide_rel]})
            counterpart = entry.get("ide_counterpart")
            if isinstance(counterpart, str) and re.search(r"/code-reviewer\b", counterpart) and not re.search(r"delegate.only|via|through", counterpart, re.I):
                manifest_text = read(shard_path)
                line_number = next((i for i, line in enumerate((manifest_text or "").splitlines(), 1) if '"ide_counterpart"' in line and counterpart in line), 1)
                finding("delegate-public-claim", shard_path, "Browser counterpart advertises direct /code-reviewer, which is delegate-only", line_number)
            if paste is not None and "contract" not in paste.lower():
                finding("missing-contract", paste_rel, "Browser paste has no behavioral contract marker")
            browser_agents.append({"id": identifier, "family": family, "variant": variant, "path": paste_rel, "manifest": shard_path,
                                   "execution_surface": "paste-only", "public": "browser paste; not an IDE public role", "parent": "unknown", "ide_counterpart": entry.get("ide_counterpart"), "size": sources.get(paste_rel)})
    if all_families != index_families:
        finding("index-family-mismatch", index_path, "Index family list differs from actual shard entries")
    aggregate_path = "agents/shared/browser/MANIFEST.json"
    aggregate = document(aggregate_path, required=False)
    if aggregate:
        aggregate_entries = rows(aggregate, "agents", aggregate_path)
        aggregate_ids = ["browser:" + str(entry.get("family")) + ("/" + str(entry["variant"]) if entry.get("variant") else "") for entry in aggregate_entries]
        if len(aggregate_ids) != len(set(aggregate_ids)):
            finding("duplicate-id", aggregate_path, "Duplicate ID in aggregate browser manifest")
        if sorted(aggregate_ids) != sorted(row["id"] for row in browser_agents) or aggregate.get("agent_count") != len(browser_agents):
            finding("aggregate-browser-mismatch", aggregate_path, "Aggregate browser manifest differs from federated shard entries")

    # Enumerate shared supporting assets without treating them as loaded prompts.
    asset_patterns = {"shared-skill": ("agents/shared/skills/**/SKILL.md",), "hook": (".cursor/hooks.json", ".cursor/hooks/*.py", ".claude/hooks*",),
                      "task-packet": ("agents/shared/browser/_shared/TASK_PACKET*", "agents/**/examples/task-packet*"), "shared-contract": ("agents/shared/browser/_shared/*.md", "agents/ide/contracts/*")}
    for kind, patterns in asset_patterns.items():
        asset_paths = set()
        for pattern in patterns:
            asset_paths.update(root.glob(pattern))
        for path in sorted(asset_paths):
            if path.is_file():
                rel = path.relative_to(root).as_posix()
                if read(rel) is not None:
                    assets.append({"kind": kind, "path": rel, "size": sources[rel]})
    hooks_path = ".cursor/hooks.json"
    hook_config = document(hooks_path, required=False)
    hook_events = hook_config.get("hooks", {})
    if isinstance(hook_events, dict):
        for event, commands in sorted(hook_events.items()):
            if not isinstance(commands, list):
                finding("invalid-manifest", hooks_path, "Hook event must contain command mappings: " + str(event))
                continue
            for command in commands:
                if not isinstance(command, dict) or not isinstance(command.get("command"), str):
                    finding("invalid-manifest", hooks_path, "Hook command is missing: " + str(event))
                    continue
                try:
                    parts = shlex.split(command["command"])
                except ValueError:
                    finding("invalid-manifest", hooks_path, "Malformed hook command: " + str(event))
                    continue
                if len(parts) >= 2 and Path(parts[0]).name in ("python", "python3"):
                    command_path = safe_path(parts[1])
                    if command_path is not None and not command_path.is_file():
                        finding("missing-hook-command", hooks_path, "Hook script does not exist: " + parts[1])
                    elif command_path is not None:
                        read(parts[1])
    catalog_path = "agents/shared/skills/personal-catalog.yaml"
    catalog = document(catalog_path, required=False)
    skill_seen = set()
    for skill in rows(catalog, "skills", catalog_path):
        identifier = skill.get("id")
        if identifier in skill_seen:
            finding("duplicate-id", catalog_path, "Duplicate skill ID: " + str(identifier))
        skill_seen.add(identifier)
        if skill.get("path"):
            check_ref("agents/shared/skills/" + skill["path"], catalog_path)
        else:
            finding("missing-contract", catalog_path, "Skill has no contract path: " + str(identifier))

    # Audit literal runnable paths separately from logical manifest aliases.
    for script in sorted(root.glob("agents/ide/scripts/*.py")):
        read(script.relative_to(root).as_posix())
    guide_paths = {asset["path"] for asset in assets if asset["kind"] == "browser-guide"}
    audited_paths = sorted(path for path in sources if path in guide_paths or path.startswith(("agents/ide/canonical/", "agents/ide/scripts/", "agents/shared/browser/_shared/")))
    for rel in audited_paths:
        text = read(rel)
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for match in re.finditer(r"\bpython(?:3)?\s+(ide-agents/scripts/[\w.-]+\.py)", line):
                literal = match[1]
                literal_path = safe_path(literal)
                if literal_path is not None and not literal_path.is_file():
                    replacement = "agents/ide/" + literal.removeprefix("ide-agents/")
                    finding("broken-generator-path", rel, "Literal command path does not exist: " + literal + "; logical alias resolves to " + replacement, line_number)
            if (rel in guide_paths or rel.startswith("agents/shared/browser/_shared/")) and re.search(r"/code-reviewer\b", line) and not re.search(r"delegate.only|do not (?:invoke|call)|not user.invocable", line, re.I):
                finding("delegate-public-claim", rel, "Direct /code-reviewer invocation advertised, but IDE manifest marks it delegate-only", line_number)
            if rel in guide_paths or rel.startswith("agents/shared/browser/_shared/"):
                for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", line):
                    target = match[1].strip().split(' "', 1)[0].strip("<>")
                    if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith(("#", "/")):
                        continue
                    # Browser contract aliases _shared#FILE and profiles#FILE
                    # are logical references, not relative filesystem links.
                    if re.match(r"(?:_shared|profiles|scripts|shared)#[^/]+$", target):
                        logical_aliases.append({"owner": rel, "alias": target, "resolved": "logical browser reference"})
                        continue
                    local = unquote(target.split("#", 1)[0].split("?", 1)[0])
                    if not local:
                        continue
                    candidate = Path(rel).parent / local
                    resolved = safe_path(candidate.as_posix())
                    if resolved is not None and not resolved.exists():
                        finding("broken-markdown-link", rel, "Relative link target does not exist: " + target + "; resolved=" + candidate.as_posix(), line_number)
        if rel == "agents/ide/canonical/master-orchestrator.md" and re.search(r"only.*valid JSON", text) and "fenced JSON block" in text:
            line_number = next(i for i, line in enumerate(text.splitlines(), 1) if "fenced JSON block" in line)
            finding("conflicting-output-contract", rel, "Requires only valid JSON and also a fenced JSON block with optional preamble", line_number)

    # Read the existing capability compiler's output; never publish or activate it.
    runtime = {"status": "unavailable", "roles": [], "snapshot_id": None}
    if (root / "agents/shared/agent-core/registry.yaml").is_file():
        try:
            from .registry_snapshot import compile_repository
            snapshot = compile_repository(root)
            data = snapshot.data
            runtime = {"status": "compiled-existing-contracts", "snapshot_id": snapshot.snapshot_id,
                       "roles": [{"id": key, "active": row["active"], "input_schema": row.get("input_schema"), "output_schema": row.get("output_schema"), "source": row.get("source"),
                                  "execution_surface": "runtime contract" if row.get("input_schema") and row.get("output_schema") else "discoverable metadata; no generic executable contract"} for key, row in sorted(data["roles"].items())]}
            for rel in sorted(data["sources"]):
                read(rel)
            for agent in ide_agents:
                metadata = next(row for row in roster if "ide:" + str(row.get("name")) == agent["id"])
                projection = metadata.get("projection")
                candidates = []
                if isinstance(projection, dict) and projection.get("source_agent"):
                    candidates.append("dc:" + Path(projection["source_agent"]).name)
                if metadata.get("rf_role_id"):
                    candidates.append("rf:" + metadata["rf_role_id"])
                agent["runtime_ids"] = sorted(key for key in candidates if key in data["roles"])
        except (ContractDenied, ValueError, KeyError, OSError, yaml.YAMLError, SchemaError, ValidationError) as exc:
            finding("runtime-contract-unavailable", "agents/shared/agent-core/registry.yaml", str(exc))
    else:
        finding("runtime-contract-unavailable", "agents/shared/agent-core/registry.yaml", "Existing runtime contracts are absent", severity="warning")

    for row in ide_agents + browser_agents:
        if row["size"] is not None and row["size"]["bytes"] > max_prompt_bytes:
            finding("oversized-prompt",row["path"],"Prompt exceeds reviewed byte ceiling: "+str(max_prompt_bytes))
    by_id = {row["id"]: row for row in ide_agents + browser_agents}
    loaded = []
    for identifier in sorted(set(selected)):
        row = by_id.get(identifier)
        if row is None:
            finding("unknown-selection", manifest_path, "Unknown selected inventory ID: " + identifier)
        elif row["size"] is not None:
            loaded.append({"id": identifier, "path": row["path"], **row["size"]})
    selected_load = {"items": loaded, "bytes": sum(row["bytes"] for row in loaded), "characters": sum(row["characters"] for row in loaded),
                     "estimated_tokens": sum(row["estimated_tokens"] for row in loaded),
                     "token_estimate_note": "Rough estimate: ceil(normalized Unicode characters / 4) per file; not a tokenizer count or guarantee. Only explicitly selected prompt files; excludes implicit contracts, history, tools, and provider overhead."}
    return {"schema_version": 1, "kind": "agent-inventory-audit", "counts": {"ide_agents": len(ide_agents), "public_agents": len(actual_public), "browser_pastes": len(browser_agents), "browser_families": len(all_families), "browser_variants": sum(row["variant"] is not None for row in browser_agents)},
            "public_agents": sorted(actual_public), "ide_agents": sorted(ide_agents, key=lambda row: row["id"]), "browser_agents": sorted(browser_agents, key=lambda row: row["id"]),
            "browser_shards": sorted(shards, key=lambda row: row["id"]), "assets": sorted(assets, key=lambda row: (row["kind"], row["path"])),
            "logical_aliases": sorted(logical_aliases, key=lambda row: (row["owner"], row["alias"])), "runtime": runtime,
            "sources": dict(sorted(sources.items())), "selected_load": selected_load, "findings": sorted(findings, key=lambda row: (row["path"], row["line"], row["code"], row["message"]))}


def audit_inventory(repo_root: str | Path, *, selected: Iterable[str] = ()) -> dict[str, Any]:
    """Convenience spelling for the same read-only inventory audit."""
    return build_inventory(repo_root, selected=selected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--select", action="append", default=[], metavar="ID")
    args = parser.parse_args(argv)
    report = build_inventory(args.root, selected=args.select)
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
