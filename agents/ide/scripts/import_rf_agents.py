#!/usr/bin/env python3
"""Generate delegate-only canonical IDE agents from research-forge/agents/*/manifest.yaml.

Usage (from repository root):
  python ide-agents/scripts/import_rf_agents.py
  python ide-agents/scripts/import_rf_agents.py --check
  python ide-agents/scripts/import_rf_agents.py --verbose

SSOT for role contracts remains research-forge/; this script only projects thin IDE bodies.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

from _repo_layout import REPO_ROOT, ide_pack_root, rf_root  # type: ignore[import-not-found]

IDE_PACK_ROOT = ide_pack_root()
RF_ROOT = rf_root()
RF_REPO_PREFIX = RF_ROOT.relative_to(REPO_ROOT).as_posix()
RF_AGENTS_ROOT = RF_ROOT / "agents"
CANONICAL_DIR = IDE_PACK_ROOT / "canonical"
MANIFEST_PATH = IDE_PACK_ROOT / "MANIFEST.yml"


def _rf_rel(*parts: str) -> str:
    return "/".join((RF_REPO_PREFIX, *parts))

# Canonical stem -> agent directory name under research-forge/agents/
REQUIRED_PROJECTIONS: tuple[tuple[str, str], ...] = (
    ("intake-clarifier", "intake_clarifier"),
    ("charter-planner", "charter_planner"),
    ("source-scout", "source_scout"),
    ("evidence-extractor", "evidence_extractor"),
    ("citation-verifier", "citation_verifier"),
    ("report-composer", "report_composer"),
    ("adversarial-skeptic", "adversarial_skeptic"),
    ("principal-director", "principal-director"),
)

WAVE_BY_ROLE_ID: dict[str, int] = {
    "intake_clarifier": 1,
    "charter_planner": 1,
    "evidence_extractor": 1,
    "citation_verifier": 1,
    "report_composer": 1,
    "source_scout": 2,
    "adversarial_skeptic": 3,
    "principal_research_director": 5,
}

ROLE_SUMMARY: dict[str, str] = {
    "intake_clarifier": "Evaluate research_request completeness; emit clarification_result or proceed.",
    "charter_planner": "Freeze research_charter from an clarified request.",
    "source_scout": "Lane-bounded progressive search producing scout_result (Wave 2 library).",
    "evidence_extractor": "Extract evidence_card from source_record; no recommendations field.",
    "citation_verifier": "Verify claims on evidence_card; RF claim_status enums only.",
    "report_composer": "Compose/serialize research_packet for downstream waves.",
    "adversarial_skeptic": "Challenge research_packet claims (Wave 3); no search tools by default.",
    "principal_research_director": "Synthesize director_synthesis from director_packet (Wave 5).",
}


@dataclass(frozen=True)
class RfAgentSource:
    stem: str
    agent_dir: Path
    manifest_path: Path
    manifest: dict[str, Any]
    manifest_sha256: str


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required (pip install pyyaml)")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def _resolve_sources() -> list[RfAgentSource]:
    sources: list[RfAgentSource] = []
    for stem, dir_name in REQUIRED_PROJECTIONS:
        agent_dir = RF_AGENTS_ROOT / dir_name
        manifest_path = agent_dir / "manifest.yaml"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Missing manifest for {stem}: {manifest_path}")
        raw = manifest_path.read_bytes()
        manifest = _load_yaml(manifest_path)
        sources.append(
            RfAgentSource(
                stem=stem,
                agent_dir=agent_dir,
                manifest_path=manifest_path,
                manifest=manifest,
                manifest_sha256=_sha256_bytes(raw),
            )
        )
    return sources


def _wave_limits_block(role_id: str) -> str:
    wave = WAVE_BY_ROLE_ID.get(role_id, 0)
    lines = [
        "## Research Forge wave honesty (IDE limits)",
        "",
        "- **Wave 1 (bridge-supported):** `ide-bridge research-forge run --wave1 --request <json>` runs the sequential Python orchestrator (clarify → charter → search/read → extract → verify → compose). Use `ide-bridge research-forge resume <run_id>` for paused clarifications. Mock-by-default; `--live` only when RF decision gates allow.",
        "- **Waves 2–6 (not chat-emulated):** Roles such as `source_scout`, `adversarial_skeptic`, and `principal_research_director` are implemented in Research Forge libraries/orchestrators — the IDE agent is a **read-only delegate**. Do not replay experiment pre/post gates or ledger events in chat.",
        f"- **This role's RF wave:** Wave {wave} (`role_id`: `{role_id}`). IDE chat does not substitute for that orchestrator.",
        "",
    ]
    return "\n".join(lines)


def _manifest_contract_block(manifest: dict[str, Any]) -> str:
    parts: list[str] = ["## I/O (from manifest.yaml)", ""]
    for key in (
        "role_id",
        "interface_version",
        "input_schema",
        "output_schema",
        "budget_profile",
        "tools",
        "forbidden_fields",
    ):
        if key in manifest and manifest[key] is not None:
            val = manifest[key]
            if isinstance(val, list):
                parts.append(f"- `{key}`: {', '.join(repr(x) for x in val)}")
            else:
                parts.append(f"- `{key}`: `{val}`")
    parts.append("")
    parts.append("Claim enums for RF ledger outputs: see `#file:ide-agents/contracts/claim-enum-map.md`.")
    parts.append("")
    return "\n".join(parts)


def _render_canonical(source: RfAgentSource) -> str:
    manifest = source.manifest
    role_id = str(manifest.get("role_id", source.stem.replace("-", "_")))
    summary = ROLE_SUMMARY.get(role_id, f"Research Forge role `{role_id}` (delegate-only projection).")
    wave = WAVE_BY_ROLE_ID.get(role_id, "?")

    frontmatter = {
        "name": source.stem,
        "description": (
            f"Delegate-only — Research Forge `{role_id}` (Wave {wave}). "
            "Prefer ide-bridge research-forge for Wave 1+; do not invent ledger events."
        ),
        "readonly": True,
        "authority": "read-only",
        "contract_version": "1.0",
        "user_invocable": False,
        "skill_refs": [
            "ide-agents/contracts/claim-enum-map.md",
            _rf_rel("agents", source.agent_dir.name, "manifest.yaml"),
        ],
        "ide_bridge_command": "ide-bridge research-forge run|resume",
        "rf_role_id": role_id,
        "rf_source_manifest_sha256": source.manifest_sha256,
    }

    body_parts = [
        f"# {source.stem.replace('-', ' ').title()}",
        "",
        "## ROLE",
        "",
        summary,
        "",
        "**Delegate only** from a Research Forge orchestrator or an explicit parent — not user-facing.",
        "",
        "## AUTHORITY",
        "",
        "Read-only in the IDE. Side effects and ledger events belong to Research Forge via **`ide-bridge`**, not chat prose.",
        "",
        "## MUST",
        "",
        "- Prefer **`ide-bridge research-forge run`** (Wave 1 mock default) when executing RF work that mutates run state or emits ledger events.",
        "- Preserve RF schema names and claim enums at boundaries (`claim-enum-map.md`).",
        "- Stop with `BLOCKED` / `PARTIAL` when the bridge or RF CLI reports failure — never claim COMPLETE from IDE text alone.",
        "",
        "## MUST NOT",
        "",
        "- Invent ledger events, verifier outcomes, or experiment gate results in chat.",
        f"- Duplicate Research Forge **experiment** pre/post review gates as ad-hoc chat skeptics (`{_rf_rel('docs', 'EXPERIMENTS-AGENTS.md')}`).",
        "- Emulate Waves 2–6 orchestration with native IDE writes or unconstrained shell.",
        "",
        _wave_limits_block(role_id),
        _manifest_contract_block(manifest),
        "## IDE bridge",
        "",
        "```text",
        "ide-bridge research-forge run --request request.json [--wave1] [--live]",
        "ide-bridge research-forge resume <run_id> [--answer CLQ-ID=value] [--live]",
        "ide-bridge doctor",
        "```",
        "",
        "Mock-by-default. `--live` is gated by Research Forge decision files — same as the `research-forge` CLI.",
        "",
        "## Examples",
        "",
        f"- **Good:** Parent runs bridge Wave 1; this role's contract is satisfied by RF Python modules for `{role_id}`.",
        "- **Anti-pattern:** Chat role-play that emits fake `evidence_card` or `VERIFIED` tags without RF runtime.",
        "",
    ]

    if yaml is None:
        raise RuntimeError("PyYAML is required")
    fm_text = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).rstrip()
    return f"---\n{fm_text}\n---\n\n" + "\n".join(body_parts)


def _load_manifest_doc() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        return {}
    return _load_yaml(MANIFEST_PATH) if yaml else {}


def _merge_manifest_agents(doc: dict[str, Any], sources: list[RfAgentSource]) -> None:
    agents = doc.get("agents")
    if not isinstance(agents, list):
        agents = []
    by_name: dict[str, dict[str, Any]] = {}
    for entry in agents:
        if isinstance(entry, dict) and entry.get("name"):
            by_name[str(entry["name"])] = entry

    for src in sources:
        role_id = str(src.manifest.get("role_id", src.stem))
        by_name[src.stem] = {
            "name": src.stem,
            "authority": "read-only",
            "user_invocable": False,
            "projection": "delegate-only",
            "source": _rf_rel("agents", src.agent_dir.name, "manifest.yaml"),
            "source_sha256": src.manifest_sha256,
            "rf_role_id": role_id,
            "rf_wave": WAVE_BY_ROLE_ID.get(role_id),
            "import_script": "ide-agents/scripts/import_rf_agents.py",
        }

    doc["agents"] = sorted(by_name.values(), key=lambda x: str(x.get("name", "")))
    doc["pack_version"] = doc.get("pack_version") or "0.4.0-rf-import"
    imports = doc.get("imports")
    if not isinstance(imports, dict):
        imports = {}
    imports["research_forge"] = {
        "script": "ide-agents/scripts/import_rf_agents.py",
        "agent_count": len(sources),
        "required_stems": [s[0] for s in REQUIRED_PROJECTIONS],
    }
    doc["imports"] = imports


def _update_readonly_policy(stems: list[str]) -> None:
    import json

    policy_path = IDE_PACK_ROOT / "policy" / "readonly-agents.json"
    if not policy_path.is_file():
        return
    data = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return
    agents = data.get("agents")
    if not isinstance(agents, list):
        agents = []
    names = list(dict.fromkeys([*agents, *stems]))
    data["agents"] = names
    policy_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_import(check: bool, verbose: bool) -> int:
    if yaml is None:
        print("Error: PyYAML required (pip install pyyaml)", file=sys.stderr)
        return 2

    sources = _resolve_sources()
    mismatches: list[str] = []

    for src in sources:
        out_path = CANONICAL_DIR / f"{src.stem}.md"
        content = _render_canonical(src)
        if out_path.is_file():
            if out_path.read_text(encoding="utf-8") != content:
                mismatches.append(str(out_path.relative_to(REPO_ROOT)))
                if not check:
                    out_path.write_text(content, encoding="utf-8")
        else:
            mismatches.append(str(out_path.relative_to(REPO_ROOT)))
            if not check:
                out_path.write_text(content, encoding="utf-8")

    manifest_doc = _load_manifest_doc()
    if not manifest_doc:
        manifest_doc = {
            "pack_version": "0.4.0-rf-import",
            "contract_version": "1.0",
            "projections": {},
            "sync": {},
            "agents": [],
        }
    _merge_manifest_agents(manifest_doc, sources)

    new_manifest_text = yaml.safe_dump(manifest_doc, sort_keys=False, allow_unicode=True)
    if MANIFEST_PATH.is_file():
        existing = MANIFEST_PATH.read_text(encoding="utf-8")
        if existing.rstrip() != new_manifest_text.rstrip():
            mismatches.append(str(MANIFEST_PATH.relative_to(REPO_ROOT)))
            if not check:
                MANIFEST_PATH.write_text(new_manifest_text, encoding="utf-8")
    else:
        mismatches.append(str(MANIFEST_PATH.relative_to(REPO_ROOT)))
        if not check:
            MANIFEST_PATH.write_text(new_manifest_text, encoding="utf-8")

    if not check:
        _update_readonly_policy([s.stem for s in sources])

    if verbose:
        for src in sources:
            print(f"  {src.stem} <- {src.manifest_path.relative_to(REPO_ROOT)} ({src.manifest_sha256[:12]}…)")

    if check:
        if mismatches:
            print("import_rf_agents --check: out of date:", file=sys.stderr)
            for m in mismatches:
                print(f"  {m}", file=sys.stderr)
            return 1
        print("import_rf_agents --check: OK")
        return 0

    print(f"Wrote/updated {len(sources)} RF canonical agent(s); MANIFEST and readonly policy refreshed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit 1 if outputs differ")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    return run_import(check=args.check, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
