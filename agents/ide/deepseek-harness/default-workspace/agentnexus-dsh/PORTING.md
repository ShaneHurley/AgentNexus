# Porting the AgentNexus IDE Agent Pack into DeepSeek Harness (DSH)

**Status:** working — all 41 agents installed, 6 presets selectable in the GUI
**Date:** 2026-09-30
**Runtime:** DSH `0.2.0-rc.2` (packaged Electron desktop app, profile `desktop`)
**Pack:** AgentNexus `pack_version: 0.1.0-research-stack`, `contract_version: 1.0`

---

## 1. Executive summary

We imported the [AgentNexus](file:///Users/shurley/Documents/AgentNexus) IDE agent pack into DSH so its
agents are available in **every session of the `desktop` profile**. Two mechanisms were required
because DSH has no directory-based agent loader:

| Pack concept | DSH mechanism | Count | Location |
|---|---|---|---|
| 6 user-facing orchestrators (KEEP-6) | Agent **presets** (Cordis YAML) | 6 | `~/.dsh/profiles/desktop/cordis.patch.yml` |
| 35 delegate-only roles | **Skills** (`SKILL.md` bundles) | 41 | `~/.dsh/skills/agentnexus/` |
| Pack contracts | Absolute-path references | 13 targets | `~/Documents/AgentNexus/agents/ide/…` |

Final state: **10 presets** in the roster (4 shipped + 6 imported) and **41 skills**, of which
6 are model-visible and 35 are marked `disable-model-invocation: true`.

---

## 2. Why two mechanisms (the central architectural finding)

**This is the single most important fact for anyone repeating this work.**

DSH's agent-preset registry documents plainly that it *"neither scans directories nor accepts
preset paths."* An agent in DSH is a **child-plugin composition declared as Cordis YAML**, not a
markdown file. Skills, by contrast, *are* discovered from filesystem roots.

Consequence for anyone porting an agent pack from Cursor / Claude Code / VS Code Copilot:

> **You cannot drop `.cursor/agents/*.md` or `.claude/agents/*.md` into DSH.**
> There is no directory that DSH scans for agent definitions, and no shipped plugin reads those
> formats. The nearest equivalents are presets (for user-selectable agents) and skills (for
> prompt-carrying roles).

The AgentNexus pack happens to split along exactly this line already: 6 `user_invocable` agents
and 35 `delegate_only` agents. We mapped them to the two mechanisms accordingly.

### Mapping rules used

| Pack field | DSH target | Notes |
|---|---|---|
| `user_invocable: true` | A preset per agent | Appears in the new-session picker |
| `delegate_only: true` **or** `user_invocable: false` | A skill with `disable-model-invocation: true` | Reachable by name via `subagent` tool, hidden from the model catalog |
| `description` | Preset `description` **and** SKILL.md frontmatter | Required by the skill provider |
| Body (`ROLE`/`AUTHORITY`/`MUST`) | `dsh-persona` `config.prefix` | Becomes the system prompt |
| `#file:ide-agents/...` refs | Rewritten to absolute paths | Logical → physical path fix (see §5) |
| `ide_bridge_command`, `handoffs` | **Not portable** | `ide-bridge` stays a separate CLI |

---

## 3. Relationship to the other IDE projections

The pack ships a sync pipeline that projects **one** canonical source into three IDE formats:

| IDE | Projection dir | Filename pattern |
|---|---|---|
| Cursor | `.cursor/agents/` | `{name}.md` |
| Claude Code | `.claude/agents/` | `{name}.md` |
| VS Code Copilot | `.github/agents/` | `{name}.agent.md` |

Per the pack's own README, these are **generated** — you edit `agents/ide/canonical/` and run
`python agents/ide/scripts/sync_ide_agents.py`. DSH is effectively a **fourth projection target**,
but it cannot use the same `.md`-copy mechanism.

### Comparison of what each target supports

| Capability | Cursor | Claude Code | VS Code Copilot | **DSH** |
|---|---|---|---|---|
| Per-agent markdown | ✅ | ✅ | ✅ | ❌ not supported |
| Per-agent tool allow/deny | ✅ `tools.deny` | ✅ `disallowedTools` | ✅ prompt+tools+handoffs | ⚠️ via preset plugin list |
| Handoffs between agents | ✅ | ✅ | ✅ `send: false` | ❌ use `subagent` tool |
| Slash-command invocation | ✅ `/name` | ✅ `/agents` | ✅ picker | ⚠️ preset picker, not a slash command |
| Read-only **enforcement** | ✅ hooks + frontmatter | ✅ frontmatter | ⚠️ soft | ❌ **prose only** (see §8) |
| Hot reload on edit | ✅ | ✅ | ✅ | ⚠️ skills yes, preset plugin lists need restart |

**Key portability warning:** `readonly: true` / `authority: read-only` is enforced by hooks or
frontmatter in the other IDEs. In DSH it is **narrative only** — a "read-only" preset still has
working write tools.

---

## 4. Exact changes made

### 4.1 Files created in the workspace

All tooling lives in
[agentnexus-dsh](README.md):

| File | Purpose |
|---|---|
| [build_skills.py](build_skills.py) | Converts `canonical/*.md` → `~/.dsh/skills/agentnexus/<name>/SKILL.md` |
| [build_patch.py](build_patch.py) | Builds the preset rows and persona text; contains the safety guards |
| [write_profile.py](write_profile.py) | Emits the final `cordis.patch.yml` with the correct insert/override split |
| [agentnexus.patch.yml](agentnexus.patch.yml) | Generated patch fragment (intermediate artifact) |
| [README.md](README.md) | Operational runbook and failure notes |

### 4.2 Skills installed

`~/.dsh/skills/agentnexus/<name>/SKILL.md` — 41 directories.

Frontmatter emitted:

```yaml
---
name: <agent-name>                     # must match the directory name
description: "<from canonical frontmatter>"   # required by the provider
disable-model-invocation: true         # only for delegate-only agents (35 of 41)
user-invocable: false                  # when the manifest says so
metadata:
  source: "AgentNexus/agents/ide/canonical"
  authority: "read-only"
  readonly: true
  delegate_only: true
---
```

### 4.3 Profile patch

`~/.dsh/profiles/desktop/cordis.patch.yml` — 7 top-level entries:

1. **6 override rows** — your pre-existing config (`agent-default-model`, `ui-settings-account`,
   `ui-chat`, `ui-settings`, `ui-conversation`) plus a rebuilt `preset-standard`.
2. **1 insert block** with the 6 `preset-agentnexus-*` rows.

`preset-standard` was rebuilt to add exactly one thing:

```yaml
- id: skill-filesystem
  name: '@deepseek-ai/dsh-skill-filesystem'
  config:
    customSkillDirs:
      - /Users/shurley/.dsh/skills/agentnexus
```

Its other 18 children were restated verbatim, and `build_patch.py` asserts that nothing else
changed before writing.

### 4.4 A patch replaces the whole `config`

From the shipped bundle's own comments:

> A patch replaces the targeted row's whole `config`, so each row below restates every key it owns.

This is why `preset-standard` is reproduced in full rather than partially patched. Missing a key
silently drops that capability.

---

## 5. The logical-vs-physical path trap

The canonical agents reference contracts like `#file:ide-agents/contracts/…`. These are
**logical** refs resolved in-process by `ai_agents_repo.resolve_ref` — the pack README says so
explicitly and warns *"do not rewrite these in canonical prompts."*

The **physical** v2 layout is `agents/ide/…`, not `ide-agents/…`. So a naive copy produces paths
that do not exist. We rewrote **13 unique** reference targets to absolute
`/Users/shurley/Documents/AgentNexus/agents/ide/…` paths, and `build_skills.py` **verifies each
target exists**, exiting non-zero on a dangling ref.

> **Trade-off:** config now depends on the AgentNexus repo living at that exact path. Moving the
> repo breaks the refs; re-run `build_skills.py` to re-point them.

---

## 6. Failure catalogue — the five bugs and their exact symptoms

Everything below was hit for real. Each entry gives the symptom, the cause, and the fix, because
the symptoms are **misleading** and will cost hours otherwise.

### Bug 1 — Presets silently missing from the roster

**Symptom:** six presets absent from Settings → Agent presets; **no error shown anywhere**.
**Misleading appearance:** looked like a stale config / needed restart. It was not.
**Cause:** the six new presets were written as bare `- id:` rows. A bare row **overrides an
existing row** and is skipped when nothing matches. From `dsh-app-boot`:

> Unknown targets and non-insert patches without a nonempty id are warned and skipped.

**Fix:** wrap new rows in `- insert: [...]`.
**How we proved it:** `Config.listConfigs` showed `include:ui-chat` (a genuine override in the same
file) resolving while `include:preset-agentnexus-researcher` returned *unknown entry id*. Same
file, so the file was being read — only the new rows were dropped.

### Bug 2 — `$.allowParallelInProgress missing required value` ← **the real "Failed to load"**

**Symptom:** all six cards rendered **"Failed to load"**; descriptions displayed correctly.
**Exact diagnostic (from the card tooltip):**

```
tool-todo (@deepseek-ai/dsh-tool-todo): invalid config:
- $.allowParallelInProgress missing required value (at allowParallelInProgress)
```

**Cause:** `dsh-tool-todo` declares `Config = z.object({ allowParallelInProgress: z.boolean().required() })`.
The field **cannot be omitted**, and we generated the row with no `config` at all. Because all six
presets mounted `tool-todo`, one bad row took down all six.
**Fix:** `config: { allowParallelInProgress: true }`.
**Audit result:** of every plugin used, **`tool-todo` is the only one with a required config field**
(`dsh-persona.prefix` is also required and was supplied).

> **Lesson:** a required-config omission fails the **entire preset**, not just that row. The card
> says "Failed to load" with no clue which row; the tooltip is the only place the row is named.

### Bug 3 — Assumed `workflowEngine` was the cause (it was not)

**What we believed:** that omitting `@deepseek-ai/dsh-workflow-ptc` while keeping `tool-workflow`
caused the failure, because `tool-workflow` reads `ctx.workflowEngine`.
**Reality:** the pairing *is* genuine hygiene — the audit would report
`waiting for workflowEngine` — but the shipped `standard` preset mounts those same rows and works,
so it was **not** the cause of "Failed to load."
**Status:** `workflow-ptc` is correctly present; the generator asserts the pairing. Documented here
so others do not chase it as a root cause.

### Bug 4 — Wrong physical path prefix

**Symptom:** refs pointing at non-existent `AgentNexus/ide-agents/…`.
**Cause:** logical refs (`ide-agents/…`) copied verbatim into a filesystem path.
**Fix:** map to `agents/ide/…` and verify existence (see §5).

### Bug 5 — `delegate_only` is not uniform in the manifest

**Symptom:** `adversarial-skeptic` would have been treated as user-facing.
**Cause:** several agents carry `user_invocable: false` **without** an explicit `delegate_only`.
**Fix:** treat any non-user-invocable agent as delegation-only.

### Diagnostic technique that actually worked

Static analysis of the config ruled out: parsing, `!!js` quoting, package names, subpath exports,
peer versions, preset schema, isolate blocks, and duplicate ids — all correct. What localized the
bug instantly was **bisection with single-purpose probe presets**:

| Probe | Contents | Result |
|---|---|---|
| A | `persona` only | ✅ loaded |
| B | `persona` + `agent-instructions` + `tool-fs` + `tool-todo` | ❌ **failed** |
| C | `persona` + `skill-filesystem` + `tool-skill` | ✅ loaded |
| D | `persona` + `delegation` group | ✅ loaded |

Only B failed, and B was the only probe containing `tool-todo`. **Build probes early.** The
registry deliberately keeps failed presets readable so their diagnostic is inspectable — use it
instead of inferring from source.

---

## 7. Verification commands

### Check the roster (authoritative, no restart)

```
Config.listConfigs with name=@deepseek-ai/dsh-agent-preset
```

Expected: **10 entries** — `standard`, `ptc`, `minimal`, `cordis`, plus six
`preset-agentnexus-*`.

### Check one row resolves

```
Config.listConfigs with entry=include:preset-agentnexus-researcher
```

*Unknown entry id* ⇒ the row was skipped (Bug 1). A schema result ⇒ the row is registered.

### Check the skill catalog

Inspect `~/.dsh/skills/agentnexus/` — expect 41 `<name>/SKILL.md`, each with `name` equal to its
directory and a non-empty `description`.

### Live vs restart

| Change | Takes effect |
|---|---|
| Adding a **new** preset row | Immediately, no restart |
| Changing a preset's **plugin list** | **Restart required** — `activate()` runs at boot |
| Adding/editing a **skill** | Immediately (roots are watched) |

---

## 8. Known limitations (important for other implementations)

1. **`readonly: true` is not enforced.** Enforced by hooks in Cursor and by frontmatter in Claude
   Code; in DSH it is only persona prose. A read-only preset retains working write tools. Use
   sandbox/permission settings if enforcement matters.
2. **Presets bind at session creation.** *"A live Agent's composition stays stable; new Agents can
   use an updated definition."* You **cannot** switch an existing session's preset — start a new one.
3. **No slash-command invocation.** Presets are chosen in the picker or as the saved default, not
   via `/deep-research`.
4. **Handoffs do not port.** `handoffs:` metadata is Cursor/Copilot-specific; use the `subagent`
   tool and name the target agent.
5. **`ide-bridge` remains external.** `ide_bridge_command` is inert in DSH; invoke the CLI through
   `bash`.
6. **Absolute paths into the AgentNexus repo.** Moving that repo breaks contract refs.
7. **Delegate-only skills are hidden**, so the model cannot discover them unprompted — a parent
   must name them explicitly.
8. **`agent-instructions` is loaded per preset.** Note the pack's own `AGENTS.md` chain still
   applies independently via `dsh-agent-instructions` (`maxBytes: 65536`).

---

## 9. Regeneration runbook

```bash
cd ~/Documents/deepseek-harness/default-workspace/agentnexus-dsh

# 1. canonical/*.md -> ~/.dsh/skills/agentnexus/<name>/SKILL.md
python3 build_skills.py --pack /Users/shurley/Documents/AgentNexus \
                        --out ~/.dsh/skills/agentnexus
#    dry run: add --check

# 2. Regenerate the preset fragment (runs the guards)
python3 build_patch.py

# 3. Write the profile patch with the correct insert/override split
python3 write_profile.py --check     # validate only
python3 write_profile.py             # write
```

`build_patch.py` needs the shipped preset extracted from the app bundle. It reads
`/tmp/dshx/preset-standard.yml`; re-extract before regenerating (see §10).

### Guards in `build_patch.py`

- Aborts if any `preset-standard` child changed other than `customSkillDirs`.
- Aborts if `tool-workflow` appears without `workflow-ptc`.
- Aborts if a row omits a known required config field (`REQUIRED_CHILD_CONFIG`).

### Backups

The profile directory holds timestamped backups from each stage:
`cordis.patch.yml.bak-20260930-231138` (original, pre-change),
`.bak-broken-232316` (bare-row version), `.bak-noprov-232502` (pre-`workflow-ptc`).

---

## 10. Inspecting a packaged DSH install

The desktop app ships as an **asar archive**, not a live checkout:

```
/Applications/DeepSeek Harness.app/Contents/Resources/app.asar
```

`@deepseek-ai/dsh/` inside my instructions is **not** a directory on disk. To read package sources:

```bash
npm_config_cache=/tmp/npmcache npx --yes @electron/asar list "<app.asar>" | grep dsh-agent-preset
npm_config_cache=/tmp/npmcache npx --yes @electron/asar extract-file "<app.asar>" \
  "dsh/node_modules/@deepseek-ai/dsh-agent-preset/README.md"
```

Useful facts discovered this way:

- Shipped presets live at `@deepseek-ai/dsh-web-app/presets/{standard,ptc,minimal,cordis}.patch.yml`.
- `package.json` → `dsh.bundle.patch` lists bundle patch order; the profile patch applies **last**.
- The `desktop` profile is guarded: `rejectElectronProfile` in `@deepseek-ai/dsh/lib/bin.js`
  refuses `--profile desktop` from the CLI, so you cannot boot it headlessly.
- `Config` inspect providers are the practical read surface; the HTTP API returns **401** without auth.

---

## 11. Reference links

### Upstream (DeepSeek Harness)

- [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) — main repository
- [README](https://github.com/deepseek-ai/deepseek-harness/blob/master/README.md)
- [Cordis tutorial 06 — Composition and HMR](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/cordis-tutorial/06-composition-and-hmr.md)
- [Configuration catalog](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/config-catalog.md)
- [`packages/preset`](https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/preset) — agent presets
- [`packages/preset/agent-preset-registry`](https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/preset/agent-preset-registry)
- [`packages/skill`](https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/skill) — skill providers
- [`packages/skill/skill-filesystem`](https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/skill/skill-filesystem)
- [`packages/boot/app-boot`](https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/boot/app-boot) — patch application
- [Subagent subsystem](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/subagent.md)
- [Documentation site](https://deepseek-harness.github.io/deepseek-harness/en/reference/cordis-api/registry)

### Local (this port)

| Artifact | Path |
|---|---|
| Port tooling + runbook | [`agentnexus-dsh/`](README.md) |
| Installed skills | `~/.dsh/skills/agentnexus/` |
| Profile patch | `~/.dsh/profiles/desktop/cordis.patch.yml` |
| Pack source | [`~/Documents/AgentNexus/`](file:///Users/shurley/Documents/AgentNexus) |
| Pack canonical agents | [`agents/ide/canonical/`](file:///Users/shurley/Documents/AgentNexus/agents/ide/canonical) |
| Pack manifest | [`agents/ide/MANIFEST.yml`](file:///Users/shurley/Documents/AgentNexus/agents/ide/MANIFEST.yml) |
| Pack sync script | [`agents/ide/scripts/sync_ide_agents.py`](file:///Users/shurley/Documents/AgentNexus/agents/ide/scripts/sync_ide_agents.py) |
| Pack IDE docs | [`docs/ide-agents/ide-agent-pack.md`](file:///Users/shurley/Documents/AgentNexus/docs/ide-agents/ide-agent-pack.md) |
| Pack hooks/skills doc | [`docs/ide-agents/hooks-and-skills.md`](file:///Users/shurley/Documents/AgentNexus/docs/ide-agents/hooks-and-skills.md) |

---

## 12. Checklist for porting a different agent pack into DSH

1. **Confirm there is no agent-directory loader.** There isn't. Plan for presets + skills.
2. Read the pack's manifest; split agents into user-facing vs delegate-only.
3. **Map user-facing agents → presets.** One `@deepseek-ai/dsh-agent-preset` row each, with a
   `dsh-persona` child carrying the instructions as `config.prefix`.
4. **Map delegate-only agents → skills** with `disable-model-invocation: true`.
5. **Put new rows inside `- insert:`.** Never as bare rows. (Bug 1)
6. **Supply every required config field** for each child plugin — read each plugin's
   `Config = z.object({...})` and note `.required()`. (Bug 2)
7. **Provide every service a row injects** within the same preset (e.g. `workflow-ptc` for
   `tool-workflow`). (Bug 3)
8. **Rewrite logical refs to real paths and verify they exist.** (Bug 4)
9. **Validate before writing**, then check the roster via `Config.listConfigs`.
10. **If a card says "Failed to load", build single-purpose probes** and read the tooltip. Do not
    infer from source.
