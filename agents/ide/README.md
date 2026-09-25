# IDE agent pack

Canonical **six user-facing orchestrators** (KEEP-6) plus delegate roster, contracts, PolicyGateway policy, and **`ide-bridge`** for audited writes into Daily Coder and Research Forge.

**Entry points:** [`MANIFEST.yml`](MANIFEST.yml) · [`canonical/`](canonical/) (edit here) · [`scripts/sync_ide_agents.py`](scripts/sync_ide_agents.py) · [`bridge/README.md`](bridge/README.md) · [`../../docs/ide-agents/ide-agent-pack.md`](../../docs/ide-agents/ide-agent-pack.md) · root [`AGENTS.md`](../../AGENTS.md).

There is **no** `/daily`, `/career`, or seventh user-facing orchestrator. Personal work uses skills under [`agents/shared/skills/`](../shared/skills/).

---

## Prerequisites

- **Python 3.10+**
- Work from the **repo root** (`ai_agents/`) unless a command says otherwise
- Layout marker [`.ai-agents-layout`](../../.ai-agents-layout) must be `v2` (physical hub: `agents/ide/`)

---

## Install

```bash
pip install -e agents/shared/ai_agents_repo
pip install -e agents/ide/bridge
pip install pyyaml
```

Optional (personal skills / agent-core):

```bash
pip install -e agents/shared/agent-core
python -m agent_core validate-registry
```

---

## Canonical workflow (do not hand-edit projections)

1. Edit agents only under [`canonical/`](canonical/) (or update Daily Coder / Research Forge SSOT and re-import).
2. From repo root, refresh imports and projections:

```bash
python agents/ide/scripts/import_daily_coder_agents.py --check
python agents/ide/scripts/import_rf_agents.py --check
python agents/ide/scripts/sync_ide_agents.py --check   # dry-run
python agents/ide/scripts/sync_ide_agents.py           # write projections
```

3. Projections land in:
   - Cursor: [`.cursor/agents/<name>.md`](../../.cursor/agents/)
   - Claude Code: [`.claude/agents/<name>.md`](../../.claude/agents/)
   - VS Code Copilot: [`.github/agents/<name>.agent.md`](../../.github/agents/)

**Never** hand-edit those generated files. Sync banners may say `ide-agents/scripts/...` — that is a **logical** label; the physical script path is `agents/ide/scripts/...`.

### Logical vs physical paths

| Kind | Example | Meaning |
|------|---------|---------|
| **Physical (shell / markdown links)** | `agents/ide/bridge`, `python agents/ide/scripts/sync_ide_agents.py` | Real directories on disk in v2 |
| **Logical (`#file:` / skill_refs)** | `#file:ide-agents/contracts/...` | Resolved in-process to `agents/ide/...` via `ai_agents_repo.resolve_ref` — **do not** rewrite these in canonical prompts |

---

## User-facing orchestrators (KEEP-6)

| Agent | Slash | Authority |
|-------|-------|-----------|
| `deep-research` | `/deep-research` | Read-only; sole lane invoker |
| `research-messenger` | `/research-messenger` | Read-only assemble (17 handoffs) |
| `plan-prep` | `/plan-prep` | Read-only planning context |
| `use-master` | `/use-master` | Dispatcher; no native file edits |
| `daily-coder` | `/daily-coder` | Bridge-only parent for mutating DC runs |
| `researcher` | `/researcher` | Read-only codebase recon |

All other agents in `MANIFEST.yml` are **delegate-only** (`user_invocable: false`).

---

## Setup by IDE

### Cursor

1. Open this repo as the workspace root.
2. Run the **Install** and **Canonical workflow** commands above.
3. Confirm projections exist under [`.cursor/agents/`](../../.cursor/agents/) (41 agents after a full sync).
4. **Invoke:** open the agent picker or type `/deep-research`, `/plan-prep`, `/use-master`, `/daily-coder`, `/researcher`, or `/research-messenger`.
5. **Hooks (soft):** [`.cursor/hooks.json`](../../.cursor/hooks.json) runs scripts under [`.cursor/hooks/`](../../.cursor/hooks/). Policy JSON lives in [`policy/`](policy/) (`readonly-agents.json`, `write-allowlist-agents.json`, `secret-deny-globs.json`). Hooks assist least-privilege; they are **not** Daily Coder PolicyGateway.
6. **Optional user skills:** place personal copies under `~/.cursor/skills/` (e.g. deep-research / research-messenger skills). Repo skills live under [`agents/shared/skills/`](../shared/skills/).
7. **Mutating work:** use `/daily-coder` and run `ide-bridge …` (see below). Parent chat may edit for pack development; audited DC/RF runs still require the bridge.

### VS Code Copilot

1. Open this repo in VS Code with Copilot Chat / agent features enabled.
2. Run **Install** + **Canonical workflow** so [`.github/agents/*.agent.md`](../../.github/agents/) exist.
3. **Invoke:** Agents dropdown → pick a user-invocable agent (`deep-research`, `plan-prep`, etc.).
4. **Handoffs** (e.g. plan-prep → use-master → daily-coder) may use `send: false` — that is a **soft human gate**, not PolicyGateway.
5. Copilot projections are **prompt + tools + handoffs only**. They are **not** a substitute for Daily Coder or Research Forge runtimes. Live `READY_TO_BUILD` still needs `ide-bridge daily-coder approve` and plan_hash.
6. Repo does not ship Copilot-native hook scripts; treat Cursor hooks docs as the soft-intent reference.

### Claude Code

1. Open this repo in Claude Code.
2. Run **Install** + **Canonical workflow** so [`.claude/agents/`](../../.claude/agents/) exist.
3. **Invoke:** `/agents` and select a user-facing agent.
4. Readonly agents get `disallowedTools` in the projection (from sync). There are **no** `.claude/hooks` in this repo — rely on frontmatter + bridge for mutating work.
5. Same KEEP-6 roster and bridge rules as Cursor.

---

## ide-bridge (hard path for side effects)

Install (from repo root):

```bash
pip install -e agents/ide/bridge
```

| Command | Purpose |
|---------|---------|
| `ide-bridge doctor` | DC/RF CLI presence + daily-coder doctor |
| `ide-bridge plan-prep scaffold` | Empty planning context template |
| `ide-bridge daily-coder run\|approve\|resume` | Mutating DC work (mock default) |
| `ide-bridge research-forge run\|resume` | RF waves (mock default) |

Exit codes: `0` COMPLETE (live acceptance), `1` SIMULATED/mock-success, `2` PARTIAL, `3` BLOCKED, `4` policy denied.

Sets `IDE_BRIDGE_ACTIVE=1` for child processes so IDE hooks can allow bridge-mediated work. Full notes: [`bridge/README.md`](bridge/README.md).

---

## Soft vs hard enforcement

| Layer | Authority |
|-------|-----------|
| **Hard** | Daily Coder / Research Forge PolicyGateway + ledger — via `ide-bridge` |
| **Soft** | Cursor hooks, frontmatter deny-lists, Copilot handoffs (`send: false`), browser paste packs |
| **Soft-confirm** | `personal-store` (visible diff + `--confirm`; career data outside git) |

Details: [`docs/ide-agents/hooks-and-skills.md`](../../docs/ide-agents/hooks-and-skills.md).

---

## Verify

```bash
python agents/ide/scripts/import_daily_coder_agents.py --check
python agents/ide/scripts/import_rf_agents.py --check
python agents/ide/scripts/sync_ide_agents.py --check
python -m unittest discover -s agents/ide/tests -v
```

Unit tests cover Cursor hooks: [`tests/`](tests/).

---

## Related docs

- Architecture: [`docs/ide-agents/ide-agent-pack.md`](../../docs/ide-agents/ide-agent-pack.md)
- Hooks and skills: [`docs/ide-agents/hooks-and-skills.md`](../../docs/ide-agents/hooks-and-skills.md)
- Root how-to: [`README.md`](../../README.md)
- Roster index: [`AGENTS.md`](../../AGENTS.md)