#!/usr/bin/env python3
"""Emit the AgentNexus profile patch with the correct insert/override split.

The loader rule (dsh-app-boot, `applyPatch`):

    "Unknown targets and non-insert patches without a nonempty id are warned
     and skipped."

So a NEW row must live inside `- insert: [...]`. A bare `- id:` row only ever
OVERRIDES an existing row. The first attempt emitted the six new presets as
bare rows, so the loader warned and skipped all six -- which is why they never
appeared in the roster while `preset-standard` (a real override target) worked.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from build_patch import (  # noqa: E402
    JsExpr,
    LiteralStr,
    build_preset_rows,
    persona_prefix,
    load_body,
)

PROFILE = Path("/Users/shurley/.dsh/profiles/desktop/cordis.patch.yml")
SHIPPED_STANDARD = Path("/tmp/dshx/preset-standard.yml")
SKILL_DIR = Path("/Users/shurley/.dsh/skills/agentnexus")

# Rows the user already owned, reproduced verbatim and kept first.
BASE_ROWS = [
    {
        "id": "agent-default-model",
        "name": "@deepseek-ai/dsh-agent-default-model",
        "config": {
            "provider": "deepseek-account",
            "model": "deepseek-flash",
            "reasoningEffort": "off",
        },
    },
    {
        "id": "ui-settings-account",
        "name": "@deepseek-ai/dsh-client-ui-settings-account",
        "config": {
            "version": 1,
            "step": "done",
            "purpose": "development",
            "process": "detailed",
            "completion": "completed",
            "usage": "detailed",
            "developerTools": True,
        },
    },
    {
        "id": "ui-chat",
        "name": "@deepseek-ai/dsh-client-ui-chat",
        "config": {"transcriptView": "detailed", "performanceUsage": "detailed"},
    },
    {"id": "ui-settings", "name": "@deepseek-ai/dsh-client-ui-settings",
     "config": {"enabled": True}},
    # The app itself appended this one; preserve it.
    {"id": "ui-conversation", "name": "@deepseek-ai/dsh-client-ui-conversation",
     "config": {"busyEnter": "steer"}},
]

HEADER = """\
# Your patch layer for this dsh profile, applied after every bundle layer:
# a top-level YAML array of loader patch entries (id-targeted config
# overrides, disables, and insert lists; `!!js` expressions allowed).
#
# IMPORTANT: a bare `- id:` row OVERRIDES an existing row and is skipped with a
# warning when nothing matches. NEW rows must go inside `- insert: [...]`.
# The six AgentNexus presets below are new, so they are inserted, not overridden.
"""


def build_standard_override() -> dict:
    shipped = yaml.safe_load(SHIPPED_STANDARD.read_text(encoding="utf-8"))
    std = None
    for entry in shipped:
        for row in entry.get("insert", []):
            if row.get("id") == "preset-standard":
                std = row
    if std is None:
        sys.exit("preset-standard not found in shipped patch")

    plugins = yaml.safe_load(yaml.safe_dump(std["config"]["plugins"]))
    hits = 0
    for child in plugins:
        if child.get("id") == "skill-filesystem":
            child.setdefault("config", {})["customSkillDirs"] = [str(SKILL_DIR)]
            hits += 1
    if hits != 1:
        sys.exit(f"expected 1 skill-filesystem child, found {hits}")
    return {
        "id": "preset-standard",
        "name": "@deepseek-ai/dsh-agent-preset",
        "config": {**std["config"], "plugins": plugins},
    }


def main() -> int:
    standard = build_standard_override()
    new_presets = build_preset_rows()

    document = BASE_ROWS + [standard, {"insert": new_presets}]

    text = HEADER + yaml.safe_dump(
        document, sort_keys=False, allow_unicode=True, width=100,
        default_flow_style=False,
    )

    # --- self-checks -------------------------------------------------------
    class J(str):
        pass

    yaml.SafeLoader.add_constructor(
        "tag:yaml.org,2002:js", lambda l, n: J(l.construct_scalar(n))
    )
    reloaded = yaml.safe_load(text)

    overrides = [r["id"] for r in reloaded if "insert" not in r]
    inserted = [r["id"] for r in reloaded if "insert" in r for r in r["insert"]]
    print(f"override rows : {len(overrides)} -> {overrides}")
    print(f"inserted rows : {len(inserted)} -> {inserted}")

    assert overrides == [r["id"] for r in BASE_ROWS] + ["preset-standard"], overrides
    assert len(inserted) == 6, inserted
    assert len(set(overrides + inserted)) == len(overrides + inserted), "duplicate ids"

    # Every inserted preset must declare id + plugins.
    for entry in reloaded:
        for row in entry.get("insert", []):
            cfg = row.get("config", {})
            assert cfg.get("id"), f"{row['id']}: missing config.id"
            assert isinstance(cfg.get("plugins"), list), f"{row['id']}: bad plugins"

    if "--check" in sys.argv:
        print("\n--check: valid, not written")
        return 0

    PROFILE.write_text(text, encoding="utf-8")
    print(f"\nwrote {PROFILE} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
