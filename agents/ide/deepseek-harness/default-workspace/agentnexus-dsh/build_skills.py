#!/usr/bin/env python3
"""Convert AgentNexus canonical agent definitions into DSH skill bundles.

Reads  <AgentNexus>/agents/ide/canonical/*.md  (the pack's edit source) and
writes <out>/<name>/SKILL.md  where <out> is a DSH skill root.

Mapping decisions:
  * frontmatter `name` + `description` are required by dsh-skill-filesystem.
  * `user_invocable: true`  -> skill is both model- and user-invocable.
  * delegate_only agents    -> `disable-model-invocation: true`, preserving the
    pack's intent that the model must not reach them directly.
  * `#file:ide-agents/<rest>` refs and `skill_refs` entries are rewritten to
    absolute AgentNexus paths, since resolve_ref() only exists in the
    AgentNexus runtime.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML required: pip install pyyaml")

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", re.DOTALL)
# `#file:ide-agents/xyz` and bare `ide-agents/xyz` are LOGICAL refs: the physical
# tree in layout v2 is `agents/ide/xyz` (README: "logical vs physical paths").
FILE_REF_RE = re.compile(r"#file:ide-agents/([A-Za-z0-9_./-]+)")
BARE_REF_RE = re.compile(r"(?<![#\w/])ide-agents/([A-Za-z0-9_./-]+)")
PHYSICAL_PREFIX = ("agents", "ide")


def load_canonical(path: Path):
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, None, text
    fm = yaml.safe_load(m.group(1)) or {}
    return fm, m.group(2), text


def rewrite_refs(body: str, pack_root: Path) -> tuple[str, int, list[str]]:
    """Point logical ide-agents/... refs at their real absolute paths.

    Returns the rewritten body, the substitution count, and any refs whose
    physical target does not exist (so the caller can fail loudly instead of
    shipping dangling paths).
    """
    count = 0
    missing: list[str] = []

    def sub(match: re.Match) -> str:
        nonlocal count
        count += 1
        target = pack_root.joinpath(*PHYSICAL_PREFIX, match.group(1))
        if not target.exists():
            missing.append(str(target))
        return str(target)

    body = FILE_REF_RE.sub(sub, body)
    body = BARE_REF_RE.sub(sub, body)
    return body, count, missing


def build_description(fm: dict) -> str:
    desc = (fm.get("description") or "").strip()
    desc = " ".join(desc.split())
    return desc


def yaml_scalar(value: str) -> str:
    """Emit a frontmatter-safe scalar, quoted only when needed."""
    if value and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.,:/()\-]*", value):
        return value
    return json.dumps(value)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True, help="AgentNexus repo root")
    ap.add_argument("--out", required=True, help="DSH skill root to write")
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    pack_root = Path(args.pack).expanduser().resolve()
    out_root = Path(args.out).expanduser().resolve()
    canonical = pack_root / "agents" / "ide" / "canonical"
    manifest_path = pack_root / "agents" / "ide" / "MANIFEST.yml"

    if not canonical.is_dir():
        sys.exit(f"canonical dir not found: {canonical}")

    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    by_name = {a["name"]: a for a in manifest.get("agents", [])}

    written, skipped, total_refs = [], [], 0
    missing_refs: list[tuple[str, str]] = []
    for path in sorted(canonical.glob("*.md")):
        if path.name == "README.md":
            skipped.append((path.stem, "canonical README, not an agent"))
            continue

        fm, body, _ = load_canonical(path)
        if fm is None or not fm.get("name"):
            skipped.append((path.stem, "no frontmatter/name"))
            continue

        name = fm["name"]
        entry = by_name.get(name, {})
        description = build_description(fm)
        if not description:
            skipped.append((name, "empty description (required by skill provider)"))
            continue

        # Preserve the pack's delegation intent in the skill's own surface flags.
        # The manifest is not uniform: several agents carry `user_invocable: false`
        # without an explicit `delegate_only`, and the KEEP-6 are the only
        # user-facing entries. Anything not user-invocable is delegation-only.
        user_invocable = entry.get("user_invocable", fm.get("user_invocable", True))
        delegate_only = bool(entry.get("delegate_only")) or user_invocable is False
        readonly = fm.get("readonly")

        body_out, refs, missing = rewrite_refs(body, pack_root)
        total_refs += refs
        missing_refs.extend((name, m) for m in missing)

        lines = ["---", f"name: {name}", f"description: {yaml_scalar(description)}"]
        if delegate_only:
            lines.append("disable-model-invocation: true")
        if user_invocable is False:
            lines.append("user-invocable: false")
        meta = {
            "source": "AgentNexus/agents/ide/canonical",
            "authority": entry.get("authority", fm.get("authority")),
            "readonly": readonly,
            "delegate_only": delegate_only,
        }
        meta = {k: v for k, v in meta.items() if v is not None}
        lines.append("metadata:")
        for k, v in meta.items():
            lines.append(f"  {k}: {json.dumps(v)}")
        lines.append("---")
        lines.append("")

        header = [
            f"# {name}",
            "",
            f"> Imported from the AgentNexus IDE agent pack (`agents/ide/canonical/{name}.md`).",
            "> That file is the edit source; regenerate this skill rather than editing it here.",
            "",
        ]
        content = "\n".join(lines) + "\n".join(header) + body_out.lstrip("\n")

        dest = out_root / name / "SKILL.md"
        if not args.check:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        written.append((name, dest, len(content)))

    mode = "CHECK (no writes)" if args.check else "WRITE"
    print(f"== {mode} ==")
    print(f"pack     : {pack_root}")
    print(f"out      : {out_root}")
    print(f"written  : {len(written)}   refs rewritten: {total_refs}")
    for name, dest, size in written:
        rel = dest.relative_to(out_root) if out_root in dest.parents else dest
        print(f"  + {rel}  ({size} bytes)")
    if skipped:
        print(f"skipped  : {len(skipped)}")
        for name, why in skipped:
            print(f"  - {name}: {why}")
    if missing_refs:
        print(f"DANGLING REFS: {len(missing_refs)}")
        for name, target in missing_refs:
            print(f"  ! {name}: {target}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
