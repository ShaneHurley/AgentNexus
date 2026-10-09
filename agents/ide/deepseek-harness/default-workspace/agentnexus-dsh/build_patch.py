#!/usr/bin/env python3
"""Generate the AgentNexus preset rows and the profile patch fragment.

Two things this must get right:

1. `preset-standard` is patched, and a patch REPLACES the target row's whole
   `config`. So this script reads the SHIPPED standard.patch.yml, adds
   `customSkillDirs` to its existing skill-filesystem child, and re-emits every
   other key verbatim. It then diffs its own output against the shipped config
   to prove nothing was dropped.

2. Persona text is taken from the canonical agent bodies. `dsh-persona` renders
   `prefix` as the system prompt, so the agent's ROLE/AUTHORITY/MUST content is
   exactly what belongs there.
"""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import yaml

PACK = Path("/Users/shurley/Documents/AgentNexus")
CANON = PACK / "agents" / "ide" / "canonical"
SHIPPED_STANDARD = Path("/tmp/dshx/standard.patch.yml")
OUT_DIR = Path("/Users/shurley/Documents/deepseek-harness/default-workspace/agentnexus-dsh")
SKILL_DIR = Path("/Users/shurley/.dsh/skills/agentnexus")

KEEP6 = [
    "deep-research",
    "research-messenger",
    "plan-prep",
    "use-master",
    "daily-coder",
    "researcher",
]
FM = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", re.DOTALL)
FILE_REF_RE = re.compile(r"#file:ide-agents/([A-Za-z0-9_./-]+)")
BARE_REF_RE = re.compile(r"(?<![#\w/])ide-agents/([A-Za-z0-9_./-]+)")


class JsExpr(str):
    """A Cordis `!!js` loader expression, preserved verbatim through round-trip."""


def _js_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:js", str(data))


yaml.SafeLoader.add_constructor(
    "tag:yaml.org,2002:js", lambda loader, node: JsExpr(loader.construct_scalar(node))
)
yaml.SafeDumper.add_representer(JsExpr, _js_representer)


class LiteralStr(str):
    """Marks a string for block-scalar emission so prompts stay readable."""


def _literal_representer(dumper, data):
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="|")


yaml.add_representer(LiteralStr, _literal_representer, Dumper=yaml.SafeDumper)


def load_body(name: str) -> tuple[dict, str]:
    text = (CANON / f"{name}.md").read_text(encoding="utf-8")
    m = FM.match(text)
    fm = yaml.safe_load(m.group(1)) or {}
    body = m.group(2)

    def sub(match):
        return str(PACK / "agents" / "ide" / match.group(1))

    body = FILE_REF_RE.sub(sub, body)
    body = BARE_REF_RE.sub(sub, body)
    return fm, body.strip()


def persona_prefix(name: str) -> str:
    fm, body = load_body(name)
    desc = " ".join((fm.get("description") or "").split())
    header = (
        f"You are the AgentNexus `{name}` agent.\n\n"
        f"{desc}\n\n"
        "The instructions below come from the AgentNexus IDE agent pack and are "
        "authoritative for this session. Where they name sibling agents "
        "(for example a delegate-only role), delegate with the subagent tool "
        "using that agent's name; the corresponding skill is named after it. "
        "Contract files live under an absolute path inside the AgentNexus "
        "repository and are readable directly.\n"
    )
    return f"{header}\n{body}\n"


def build_preset_rows() -> list[dict]:
    rows = []
    for idx, name in enumerate(KEEP6):
        rows.append(
            {
                "id": f"preset-agentnexus-{name}",
                "name": "@deepseek-ai/dsh-agent-preset",
                "config": {
                    "id": f"agentnexus-{name}",
                    "order": 10 + idx,
                    "name": f"AgentNexus: {name}",
                    "description": " ".join(
                        (load_body(name)[0].get("description") or "").split()
                    ),
                    "plugins": [
                        {
                            "id": "persona",
                            "name": "@deepseek-ai/dsh-persona",
                            "config": {
                                "prefix": LiteralStr(persona_prefix(name)),
                                "suffix": "Your working directory is {{cwd}}.",
                            },
                        },
                        {
                            "id": "agent-instructions",
                            "name": "@deepseek-ai/dsh-agent-instructions",
                            "config": {"maxBytes": 65536},
                        },
                        {"id": "tool-fs", "name": "@deepseek-ai/dsh-tool-fs"},
                        {
                            "id": "tool-fs-search",
                            "name": "@deepseek-ai/dsh-tool-fs-search",
                            "config": {"sampleOverCapGlobResults": False},
                        },
                        {
                            "id": "tool-bash",
                            "name": "@deepseek-ai/dsh-tool-bash",
                            "disabled": JsExpr("process.platform === 'win32'"),
                        },
                        {
                            "id": "tool-pwsh",
                            "name": "@deepseek-ai/dsh-tool-pwsh",
                            "disabled": JsExpr("process.platform !== 'win32'"),
                        },
                        {
                            "id": "skill-filesystem",
                            "name": "@deepseek-ai/dsh-skill-filesystem",
                            "config": {"customSkillDirs": [str(SKILL_DIR)]},
                        },
                        {"id": "tool-skill", "name": "@deepseek-ai/dsh-tool-skill"},
                        # `allowParallelInProgress` is `z.boolean().required()` in
                        # dsh-tool-todo. Omitting it fails activation with
                        # "$.allowParallelInProgress missing required value".
                        {"id": "tool-todo", "name": "@deepseek-ai/dsh-tool-todo",
                         "config": {"allowParallelInProgress": True}},
                        {
                            "id": "tool-web",
                            "name": "@deepseek-ai/dsh-tool-web",
                            "config": {"fetch": True, "searchTimeoutMs": 60000},
                        },
                        {"id": "tool-ask-user", "name": "@deepseek-ai/dsh-tool-ask-user"},
                        {"id": "delegation", "name": "cordis:group", "group": True,
                         "isolate": {"workflowEngine": True},
                         "config": [
                             {"id": "tool-subagent-control",
                              "name": "@deepseek-ai/dsh-tool-subagent-control"},
                             {"id": "tool-subagent-list-agents",
                              "name": "@deepseek-ai/dsh-tool-subagent-control/list-agents"},
                             {"id": "tool-subagent", "name": "@deepseek-ai/dsh-tool-subagent",
                              "config": {"provider": "spawn", "toolName": "subagent",
                                         "modelSelectionSettings": True,
                                         "backgroundMode": "continuable"}},
                             {"id": "tool-subagent-fork", "name": "@deepseek-ai/dsh-tool-subagent",
                              "config": {"provider": "fork", "toolName": "subagent_fork",
                                         "backgroundMode": "continuable"}},
                             # `workflow-ptc` SUPPLIES ctx.workflowEngine, which is what
                             # `tool-workflow` reads. Omitting it leaves tool-workflow
                             # permanently "waiting for workflowEngine", which fails the
                             # whole preset's activation audit.
                             {"id": "workflow-ptc", "name": "@deepseek-ai/dsh-workflow-ptc",
                              "config": {"provider": "spawn"}},
                             {"id": "tool-workflow", "name": "@deepseek-ai/dsh-tool-workflow"},
                             {"id": "tool-ralph", "name": "@deepseek-ai/dsh-tool-ralph",
                              "disabled": True,
                              "config": {"subagentProvider": "spawn", "maxRounds": 64}},
                         ]},
                    ],
                },
            }
        )
    return rows


def main() -> int:
    shipped = yaml.safe_load(SHIPPED_STANDARD.read_text(encoding="utf-8"))
    std_row = None
    for entry in shipped:
        for row in entry.get("insert", []):
            if row.get("id") == "preset-standard":
                std_row = row
    if std_row is None:
        sys.exit("could not find preset-standard in shipped patch")

    original_plugins = copy.deepcopy(std_row["config"]["plugins"])

    # Patch the EXISTING skill-filesystem child in place; keep every sibling.
    patched = copy.deepcopy(original_plugins)
    hits = 0
    for child in patched:
        if child.get("id") == "skill-filesystem":
            cfg = child.setdefault("config", {})
            cfg["customSkillDirs"] = [str(SKILL_DIR)]
            hits += 1
    if hits != 1:
        sys.exit(f"expected exactly one skill-filesystem child, found {hits}")

    # Prove nothing else changed.
    a = copy.deepcopy(original_plugins)
    b = copy.deepcopy(patched)
    for lst in (a, b):
        for child in lst:
            if child.get("id") == "skill-filesystem":
                child.pop("config", None)
    if a != b:
        sys.exit("standard preset children changed beyond customSkillDirs; aborting")
    print(f"standard preset: {len(original_plugins)} children preserved verbatim")

    # Guard against the failure that broke the first attempt: a child row that
    # reads a service nothing in the same preset supplies stays "waiting for X"
    # forever, and the preset's activation audit fails. `tool-workflow` needs
    # ctx.workflowEngine, which only `workflow-ptc` provides.
    for row in presets:
        children = {c.get("id") for c in row["config"]["plugins"] if isinstance(c, dict)}
        for group in row["config"]["plugins"]:
            if group.get("name") == "cordis:group":
                children |= {c.get("id") for c in group.get("config", []) if isinstance(c, dict)}
        if "tool-workflow" in children and "workflow-ptc" not in children:
            sys.exit(f"{row['id']}: tool-workflow present without workflow-ptc "
                     "(workflowEngine would never resolve)")
    print("delegation groups: workflow-engine provider present")

    # Required-config guard. A Schemastery `z.boolean().required()` field that a
    # row omits fails that row's activation, which fails the whole preset with
    # "invalid config: $.field missing required value". Keep in sync with the
    # shipped presets.
    REQUIRED_CHILD_CONFIG = {"tool-todo": ("allowParallelInProgress",)}
    for row in presets:
        for child in row["config"]["plugins"]:
            for key in REQUIRED_CHILD_CONFIG.get(child.get("id"), ()):
                if key not in (child.get("config") or {}):
                    sys.exit(f"{row['id']}/{child['id']}: missing required config.{key}")
    print("required child config: present")

    std_override = {
        "id": "preset-standard",
        "name": "@deepseek-ai/dsh-agent-preset",
        "config": {**std_row["config"], "plugins": patched},
    }

    presets = build_preset_rows()
    fragment = [std_override] + presets

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    header = (
        "# AgentNexus IDE agent pack (profile-wide).\n"
        "#\n"
        "# Row 1 patches the shipped `preset-standard` to add one custom skill\n"
        "# directory; every other key of that preset is restated verbatim from\n"
        "# the shipped bundle (a patch replaces the whole `config`).\n"
        "#\n"
        "# Rows 2-7 declare one preset per KEEP-6 user-facing orchestrator.\n"
        "# The 35 delegate-only roles are NOT presets: they are skills under\n"
        "# ~/.dsh/skills/agentnexus, reachable through the subagent tool.\n"
        "#\n"
        "# Regenerate with agentnexus-dsh/build_skills.py + build_patch.py.\n"
    )
    text = header + yaml.safe_dump(
        fragment, sort_keys=False, allow_unicode=True, width=100, default_flow_style=False
    )
    dest = OUT_DIR / "agentnexus.patch.yml"
    dest.write_text(text, encoding="utf-8")
    print(f"wrote {dest} ({len(text)} bytes, {len(fragment)} rows)")
    print("preset ids:", ", ".join(r["config"]["id"] for r in presets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
