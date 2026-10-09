# AgentNexus → DSH bridge

Imports the [AgentNexus](file:///Users/shurley/Documents/AgentNexus) IDE agent pack into DSH
so its agents are usable from **every session in the `desktop` profile**.

> **New here, or porting a different agent pack?** Read
> **[PORTING.md](PORTING.md)** — the full write-up: architecture rationale, the
> five bugs hit (with exact diagnostics), verification commands, a portability
> comparison against Cursor / Claude Code / VS Code Copilot, and a porting
> checklist. This README is the short operational runbook.

## What was installed

| Piece | Location | Count |
|---|---|---|
| Skills (all canonical agents) | `~/.dsh/skills/agentnexus/<name>/SKILL.md` | 41 |
| Agent presets (KEEP-6) | `~/.dsh/profiles/desktop/cordis.patch.yml` rows `preset-agentnexus-*` | 6 |
| `customSkillDirs` on `preset-standard` | same file, `preset-standard` row | 1 |

## Why two mechanisms

DSH has **no directory-based agent loader**. `dsh-agent-preset-registry` documents that
"the registry neither scans directories nor accepts preset paths" — an agent in DSH is a
child-plugin composition declared as Cordis YAML. Skills, by contrast, *are* scanned from
filesystem roots by `dsh-skill-filesystem`.

So the pack splits along the line the pack itself already draws:

- **The 6 user-facing orchestrators (KEEP-6)** become real presets, selectable in the
  session picker. Each mounts a `dsh-persona` row whose `prefix` carries that agent's
  canonical ROLE/AUTHORITY/MUST text, plus a working tool set (fs, bash, web, skill,
  todo, ask-user, delegation).
- **The 35 delegate-only roles** become skills. They are reachable as named agents via
  the `subagent` tool, but are flagged `disable-model-invocation: true` so the model
  cannot pull them into its own catalog — preserving the pack's `delegate_only` intent.

## Regenerating

Both scripts are idempotent. Run from this directory:

```bash
# 1. canonical/*.md  ->  ~/.dsh/skills/agentnexus/<name>/SKILL.md
python3 build_skills.py --pack /Users/shurley/Documents/AgentNexus \
                        --out ~/.dsh/skills/agentnexus
# dry run: add --check

# 2. regenerate agentnexus.patch.yml (presets + standard-preset override)
python3 build_patch.py
```

`build_patch.py` reads the **shipped** `standard.patch.yml` out of the app bundle at
`/tmp/dshx/standard.patch.yml` and re-emits its 19 plugin children verbatim, adding only
`customSkillDirs`. It aborts if any other child changed. Refresh that extraction first if
the app has been updated.

After regenerating the patch fragment, merge it into the profile:

```bash
# rows 1..4 of cordis.patch.yml are yours; rows 5..11 are AgentNexus
$EDITOR ~/.dsh/profiles/desktop/cordis.patch.yml
```

## Handled details

- **`#file:ide-agents/...` refs are logical, not physical.** In layout v2 the real tree is
  `agents/ide/...`, so 66 refs were rewritten to absolute `AgentNexus/agents/ide/...`
  paths. `build_skills.py` verifies each rewritten target exists and exits non-zero on a
  dangling ref rather than shipping a broken path.
- **`delegate_only` is not uniform in `MANIFEST.yml`.** Several agents carry
  `user_invocable: false` with no explicit `delegate_only` (e.g. `adversarial-skeptic`).
  Any non-user-invocable agent is treated as delegation-only.
- **A patch replaces the target row's whole `config`**, which is why `preset-standard` is
  restated in full and why the build script diffs before writing.
- **`!!js` loader expressions round-trip.** The script registers a PyYAML constructor and
  representer for `tag:yaml.org,2002:js` so `process.platform` conditions survive.
- **Required frontmatter.** `name` and `description` are mandatory for the skill provider;
  the canonical README is skipped, and a missing description fails loudly.

## Loader rules that bit this setup

Three distinct behaviors made the presets first appear missing, then "Failed to load".

**1. New rows must live inside `- insert:`.** From `dsh-app-boot`:

> Unknown targets and non-insert patches without a nonempty id are warned and skipped.

A bare `- id:` row **overrides** an existing row. Six brand-new presets written as bare
rows matched nothing, so all six were silently skipped.

**2. A required child config field fails the whole preset.** This was the actual cause of
every "Failed to load" card:

```
tool-todo (@deepseek-ai/dsh-tool-todo): invalid config:
- $.allowParallelInProgress missing required value (at allowParallelInProgress)
```

`dsh-tool-todo` declares `Config = z.object({ allowParallelInProgress: z.boolean().required() })`,
so the field cannot be omitted. Because every preset mounted `tool-todo`, one bad row took
all six down. `build_patch.py` now asserts required child config via
`REQUIRED_CHILD_CONFIG`. An audit of every plugin used here found **`tool-todo` is the only
one with a required config field**; `dsh-persona`'s `prefix` is required too, and is supplied.

**3. Rows inject services that must be provided in-composition.** `dsh-tool-workflow` reads
`ctx.workflowEngine`, supplied by `@deepseek-ai/dsh-workflow-ptc`; the preset audit reports a
row that waits forever as `waiting for workflowEngine`. The generator asserts that pairing.
Note this was real hygiene, not the cause of the failures in (2).

### How to find which row is broken

Add single-purpose probe presets and read the tooltip on the failing card — the registry
renders the offending row and field. That is what localized (2) after static analysis of the
config had ruled everything else out. The four probes used were: persona-only, persona+basic
tools, persona+skills, persona+delegation. Only the one containing `tool-todo` failed.

## Verifying a change took effect

Check the roster, not the card:

```
Config.listConfigs with name=@deepseek-ai/dsh-agent-preset
```

Then confirm one row resolves by entry id (`include:preset-agentnexus-researcher`).
New rows are picked up live; **changed plugin lists need a restart**, because
`activate()` runs at boot.

## Activation

The profile is a **startup** profile: DSH reads `cordis.patch.yml` when the process boots.
**Restart DSH** to load the new presets and skill root. Existing sessions keep their
current composition; new sessions can pick an `AgentNexus: <name>` preset.

Backup of the pre-change patch: `cordis.patch.yml.bak-<timestamp>` in the profile dir.

## Known limitations

- Contract refs point at absolute paths inside the AgentNexus repo. Moving or renaming
  that repo breaks them; re-run `build_skills.py` to re-point.
- The presets grant ordinary DSH tools. AgentNexus `readonly: true` is expressed in the
  persona prose only — it is **not** enforced. A read-only agent can still be asked to
  edit files, and nothing in DSH stops it. Enforce with sandbox/permission settings if
  that matters.
- `ide_bridge_command` and handoff metadata are not portable; `ide-bridge` remains a
  separate CLI you invoke through `bash`.
- The delegate-only skills are hidden from the model catalog, so the model cannot
  discover them on its own; a parent must name them.
