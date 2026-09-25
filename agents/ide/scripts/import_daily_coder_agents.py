#!/usr/bin/env python3
"""Generate delegate-only IDE canonical agents from Daily Coder role SSOT.

Reads daily-coder-ecosystem/agents/*/prompt.md + agent.json (16 roles).
Writes ide-agents/canonical/<kebab-id>.md and updates MANIFEST DC agent entries.

Usage (repository root):
  python ide-agents/scripts/import_daily_coder_agents.py
  python ide-agents/scripts/import_daily_coder_agents.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

from _repo_layout import REPO_ROOT, dc_root, ide_pack_root  # type: ignore[import-not-found]

IDE_PACK_ROOT = ide_pack_root()
DC_AGENTS_ROOT = dc_root() / "agents"
CANONICAL_DIR = IDE_PACK_ROOT / "canonical"
MANIFEST_PATH = IDE_PACK_ROOT / "MANIFEST.yml"

HAND_AUTHORED_STEMS = frozenset({"daily-coder"})
USER_INVOCABLE_ROLES = frozenset({"researcher"})

GENERATED_MARKER = "import_daily_coder_agents.py"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_text(path.read_text(encoding="utf-8"))


def _dc_id_to_stem(dc_id: str) -> str:
    return dc_id.replace("_", "-")


def _discover_roles() -> list[Path]:
    if not DC_AGENTS_ROOT.is_dir():
        return []
    dirs = [p for p in DC_AGENTS_ROOT.iterdir() if p.is_dir()]
    return sorted(dirs, key=lambda p: p.name)


def _load_role(dir_path: Path) -> tuple[dict[str, Any], str, str, str]:
    agent_json_path = dir_path / "agent.json"
    prompt_path = dir_path / "prompt.md"
    if not agent_json_path.is_file() or not prompt_path.is_file():
        raise FileNotFoundError(f"missing prompt.md or agent.json under {dir_path}")
    meta = json.loads(agent_json_path.read_text(encoding="utf-8"))
    prompt = prompt_path.read_text(encoding="utf-8")
    dc_id = str(meta.get("id") or dir_path.name)
    rel_agent = f"daily-coder-ecosystem/agents/{dir_path.name}"
    return meta, prompt, dc_id, rel_agent


def _authority_for(write_scope: str) -> str:
    if write_scope == "none":
        return "read-only"
    return "implementation"


def _prompt_summary(prompt: str, job: str) -> str:
    """One-line summary for IDE projection without inlining full prompt.md."""
    for line in prompt.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lower = stripped.lower()
        if lower.startswith("one job:"):
            return stripped.split(":", 1)[1].strip() or job
        return stripped
    return job


def _render_canonical(
    *,
    stem: str,
    dc_id: str,
    meta: dict[str, Any],
    rel_agent: str,
    prompt_sha: str,
    json_sha: str,
    prompt_summary: str,
) -> str:
    job = str(meta.get("job", "")).strip()
    write_scope = str(meta.get("write_scope", "none"))
    readonly = write_scope == "none" or True  # IDE: all DC roles are readonly projections
    readonly = True
    user_invocable = dc_id in USER_INVOCABLE_ROLES
    authority = _authority_for(write_scope)
    tools = meta.get("tools") or []
    output_schema = meta.get("output_schema", "")

    description = (
        f"Delegate-only — Daily Coder `{dc_id}`. {job} "
        "Invoked from `daily-coder` / `use-master` / runtime only; not a picker entry."
        if not user_invocable
        else f"Daily Coder `{dc_id}` (codebase recon, read-only). User-facing (/researcher). {job}"
    )

    fm: dict[str, Any] = {
        "name": stem,
        "description": description,
        "readonly": readonly,
        "authority": authority,
        "contract_version": "1.0",
        "user_invocable": user_invocable,
        "dc_role_id": dc_id,
        "dc_write_scope": write_scope,
        "projection": {
            "engine": "daily-coder",
            "source_agent": rel_agent,
            "prompt_sha256": prompt_sha,
            "agent_json_sha256": json_sha,
            "generated_by": GENERATED_MARKER,
        },
    }
    if tools:
        fm["dc_tools"] = tools
    if output_schema:
        fm["dc_output_schema"] = output_schema
    fm["dc_runtime_prompt"] = {
        "load_on_invoke": f"{rel_agent}/prompt.md",
        "sha256": prompt_sha,
    }

    delegate_line = (
        "**Delegate only** from `daily-coder`, `use-master`, or Daily Coder runtime."
        if not user_invocable
        else "**User-facing** as `/researcher`; also delegated from Daily Coder runtime."
    )

    body = f"""# Daily Coder role: {dc_id}

## ROLE

{delegate_line}

Runtime job: {job}

## AUTHORITY

IDE projection is **read-only**. Side effects and audited writes happen only in Daily Coder via `PolicyGateway` / `ToolBroker`, typically through **`ide-bridge daily-coder`**.

- Runtime `write_scope`: `{write_scope}`
- Claim tags follow Daily Coder vocabulary; when mapping enums, load `load-on-invoke:ide-agents/contracts/claim-enum-map.md` at runtime only.

## MUST NOT

- Emulate the Daily Coder phase DAG or SQLite state machine in chat.
- Use native IDE write tools for audited implementation (use `ide-bridge`).
- Nest or spawn other IDE agents unless the parent orchestrator explicitly delegates.
- Preload or `#file:`-inline the full SSOT `prompt.md` in parent orchestrator context (pointer-only projection).

## Runtime prompt (SSOT — load on invoke)

Summary: {prompt_summary}

When **this agent** is invoked, read the full runtime instructions from SSOT (not at picker/resident load):

`load-on-invoke:{rel_agent}/prompt.md` (sha256 `{prompt_sha}`)

## Projection SSOT

| Field | Value |
|-------|-------|
| Agent directory | `{rel_agent}` |
| `prompt.md` sha256 | `{prompt_sha}` |
| `agent.json` sha256 | `{json_sha}` |
| Regenerate | `python ide-agents/scripts/import_daily_coder_agents.py` |

## Tool intent (runtime allowlist reference)

Configured DC tools (prompt cannot grant tools): {", ".join(str(t) for t in tools) if tools else "(none listed)"}.

Output schema: `{output_schema or "n/a"}`.

## Examples

- **Good:** Parent passes bounded context; role emits schema-shaped JSON with tagged claims only.
- **Anti-pattern:** Chat claims COMPLETE or SIMULATED without `ide-bridge` / runtime acceptance.
"""
    if yaml is None:
        raise RuntimeError("PyYAML required (pip install pyyaml)")
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).rstrip() + "\n---\n\n" + body


def _build_dc_manifest_entries(role_dirs: list[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for dir_path in role_dirs:
        meta, _prompt, dc_id, rel_agent = _load_role(dir_path)
        stem = _dc_id_to_stem(dc_id)
        prompt_sha = _sha256_file(dir_path / "prompt.md")
        json_sha = _sha256_file(dir_path / "agent.json")
        entries.append(
            {
                "name": stem,
                "authority": _authority_for(str(meta.get("write_scope", "none"))),
                "user_invocable": dc_id in USER_INVOCABLE_ROLES,
                "delegate_only": dc_id not in USER_INVOCABLE_ROLES,
                "canonical": f"ide-agents/canonical/{stem}.md",
                "projection": {
                    "engine": "daily-coder",
                    "source_agent": rel_agent,
                    "prompt_sha256": prompt_sha,
                    "agent_json_sha256": json_sha,
                },
            }
        )
    return entries


def _daily_coder_parent_manifest_entry() -> dict[str, Any]:
    path = CANONICAL_DIR / "daily-coder.md"
    entry: dict[str, Any] = {
        "name": "daily-coder",
        "authority": "bridge-parent",
        "user_invocable": True,
        "delegate_only": False,
        "canonical": "ide-agents/canonical/daily-coder.md",
        "projection": {"engine": "daily-coder", "hand_authored": True},
    }
    if path.is_file():
        entry["canonical_sha256"] = _sha256_file(path)
    return entry


def _manifest_preamble(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            lines.append(line)
        elif not line.strip() and not lines:
            continue
        else:
            break
    return "\n".join(lines) + ("\n" if lines else "")


def _manifest_dc_engine(entry: dict[str, Any]) -> str | None:
    projection = entry.get("projection")
    if isinstance(projection, dict):
        engine = projection.get("engine")
        return str(engine) if engine is not None else None
    return None


def _merge_manifest_dc_entries(dc_entries: list[dict[str, Any]]) -> None:
    if yaml is None:
        raise RuntimeError("PyYAML required (pip install pyyaml)")
    text = MANIFEST_PATH.read_text(encoding="utf-8") if MANIFEST_PATH.is_file() else ""
    preamble = _manifest_preamble(text)
    yaml_body = re.sub(r"\A(?:#.*\n)*", "", text)
    data = yaml.safe_load(yaml_body) or {}
    if not isinstance(data, dict):
        data = {}
    agents = data.get("agents")
    if not isinstance(agents, list):
        agents = []
    kept = [
        a
        for a in agents
        if isinstance(a, dict) and _manifest_dc_engine(a) != "daily-coder"
    ]
    merged = kept + [_daily_coder_parent_manifest_entry()] + dc_entries
    data["agents"] = merged
    data["pack_version"] = data.get("pack_version") or "0.3.0-daily-coder"
    if "daily_coder_import" not in data:
        data["daily_coder_import"] = {}
    data["daily_coder_import"]["role_count"] = len(dc_entries)
    data["daily_coder_import"]["script"] = "ide-agents/scripts/import_daily_coder_agents.py"
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)
    MANIFEST_PATH.write_text(preamble + body, encoding="utf-8")


def run_import(check: bool) -> int:
    role_dirs = _discover_roles()
    if len(role_dirs) != 16:
        print(
            f"Warning: expected 16 DC roles, found {len(role_dirs)} under {DC_AGENTS_ROOT}",
            file=sys.stderr,
        )
    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    mismatches: list[str] = []
    for dir_path in role_dirs:
        meta, prompt, dc_id, rel_agent = _load_role(dir_path)
        stem = _dc_id_to_stem(dc_id)
        if stem in HAND_AUTHORED_STEMS:
            continue
        prompt_sha = _sha256_file(dir_path / "prompt.md")
        json_sha = _sha256_file(dir_path / "agent.json")
        content = _render_canonical(
            stem=stem,
            dc_id=dc_id,
            meta=meta,
            rel_agent=rel_agent,
            prompt_sha=prompt_sha,
            json_sha=json_sha,
            prompt_summary=_prompt_summary(prompt, str(meta.get("job", "")).strip()),
        )
        out_path = CANONICAL_DIR / f"{stem}.md"
        if out_path.is_file():
            existing = out_path.read_text(encoding="utf-8")
            if existing != content:
                mismatches.append(str(out_path.relative_to(REPO_ROOT)))
                if not check:
                    out_path.write_text(content, encoding="utf-8")
        else:
            mismatches.append(str(out_path.relative_to(REPO_ROOT)))
            if not check:
                out_path.write_text(content, encoding="utf-8")

    dc_entries = _build_dc_manifest_entries(role_dirs)
    if check:
        if yaml is None:
            print("PyYAML required for --check", file=sys.stderr)
            return 2
        if mismatches:
            print("import --check: canonical out of date:", file=sys.stderr)
            for m in mismatches:
                print(f"  {m}", file=sys.stderr)
            return 1
        print("import --check: OK")
        return 0

    _merge_manifest_dc_entries(dc_entries)
    print(f"Wrote/updated {len(role_dirs)} DC role canonical file(s); MANIFEST agents merged.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit 1 if canonical differs from SSOT")
    args = parser.parse_args()
    if yaml is None and not args.check:
        print("Error: pip install pyyaml", file=sys.stderr)
        return 2
    return run_import(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
