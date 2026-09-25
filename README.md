# AI Agents

A portfolio monorepo for **evidence-first research**, **artifact-driven coding**, **IDE-portable agent projections**, and **skills-first personal work** — with one dashboard to steer engineering runs.

**Python 3.10+** across packages.

---

## Start here (four top folders)

| Folder | Purpose |
|--------|---------|
| [`agents/`](agents/) | All agent engines, IDE pack, browser harnesses, skills, and shared contracts |
| [`gui/`](gui/) | Local dashboard — start Daily Coder / Research Forge and watch runs |
| [`docs/`](docs/) | Architecture, ADRs, operator guides |
| [`tests/`](tests/) | Cross-cutting tests (personal skills, writing, toolkit) |

### Inside `agents/`

| Child | Purpose |
|-------|---------|
| [`agents/ide/`](agents/ide/) | Canonical IDE agents, contracts, `ide-bridge`, sync/import scripts |
| [`agents/research/`](agents/research/) | Research Forge + research browser families |
| [`agents/coding/`](agents/coding/) | Daily Coder + coding browser families |
| [`agents/daily-task/`](agents/daily-task/) | Browser router + lifestyle / mission-control families |
| [`agents/shared/`](agents/shared/) | Skills, schemas, `agent-core`, browser `_shared` harness, layout package |

**Invoke in the IDE:** six orchestrators in [`AGENTS.md`](AGENTS.md). Personal work uses skills under [`agents/shared/skills/`](agents/shared/skills/) — not a seventh orchestrator.

**Layout contract:** [`agents/shared/ai_agents_repo/`](agents/shared/ai_agents_repo/) resolves physical paths for legacy and v2 trees; marker [`.ai-agents-layout`](.ai-agents-layout) is `v2` (agents hub).

**IDE / CI surfaces (repo root):** [`.cursor/`](.cursor/), [`.claude/`](.claude/), and [`.github/`](.github/) stay at the root so editors and GitHub Actions discover agents, hooks, and workflows. Canonical sources live under [`agents/ide/`](agents/ide/); run sync to refresh projections.

---

## Quick start

**Dashboard (recommended):**

```bash
cd gui
python start.py    # Windows: start.bat
```

Opens http://127.0.0.1:8866/

**IDE agents (from repo root):**

```bash
pip install -e agents/shared/ai_agents_repo
pip install -e agents/ide/bridge
python agents/ide/scripts/sync_ide_agents.py --check
```

**Agent core + personal skills:**

```bash
pip install -e ./agents/shared/agent-core
python -m agent_core validate-registry
```

**Verify locally:**

```bash
pip install pyyaml
pip install -e ./agents/shared/ai_agents_repo
python -m ai_agents_repo.validate --phase F0
python agents/ide/scripts/import_daily_coder_agents.py --check
python agents/ide/scripts/import_rf_agents.py --check
python agents/ide/scripts/sync_ide_agents.py --check
python -m unittest discover -s agents/ide/tests -v
```

---

## Using the six IDE orchestrators

Only these six are user-facing. There is **no** `/daily`, `/career`, or seventh orchestrator — student/career work uses on-demand skills.

**How to invoke (all six):**

| IDE | How |
|-----|-----|
| **Cursor** | Agent picker / `@` agent, or slash name (e.g. `/deep-research`) from [`.cursor/agents/`](.cursor/agents/) |
| **VS Code Copilot** | Agents dropdown — [`.github/agents/<name>.agent.md`](.github/agents/) |
| **Claude Code** | `/agents` — [`.claude/agents/<name>.md`](.claude/agents/) |

Short roster: [`AGENTS.md`](AGENTS.md). Deep per-IDE setup: [`agents/ide/README.md`](agents/ide/README.md).

### `deep-research`

| | |
|--|--|
| **When** | Exhaustive, multi-lane evidence research before a decision |
| **Authority** | Permanently **read-only** (search / read / score / recommend only) |
| **Next action** | Parent runs the eight-phase workflow; sole invoker of lane subagents; hand off scored packets to `research-messenger` |

### `research-messenger`

| | |
|--|--|
| **When** | You already have a scored research packet and need the human report + 17 handoffs |
| **Authority** | **Read-only** — assemble only; never research or invoke agents |
| **Next action** | Modes: ASSEMBLE / ECOSYSTEM / COMBINED |

### `plan-prep`

| | |
|--|--|
| **When** | Need enterprise / repo context before Master or architecture planning |
| **Authority** | **Read-only** planning context report (Glean MCP when configured; local docs/code fallback) |
| **Next action** | Optional scaffold: `ide-bridge plan-prep scaffold`; hand off to `use-master` |

### `use-master`

| | |
|--|--|
| **When** | Dispatch a Master mission DAG (plan then controlled execution) |
| **Authority** | Parent dispatcher — **no native file edits**; mutations only via specialists + `ide-bridge` |
| **Next action** | Delegates `master-orchestrator`, then bridge into Daily Coder for audited runs |

### `daily-coder`

| | |
|--|--|
| **When** | Mutating coding work that must go through PolicyGateway / plan approval |
| **Authority** | **Bridge-only parent** — never emulate the phase DAG in chat |
| **Next action** | `ide-bridge daily-coder run --request "..."` `--repo <path>` then `approve` / `resume`; `ide-bridge doctor` for health |

### `researcher`

| | |
|--|--|
| **When** | Bounded read-only codebase / repo recon (Daily Coder researcher projection) |
| **Authority** | **Read-only** (no write scope) |
| **Next action** | Investigate one angle; escalate mutating work to `/daily-coder` + bridge |

---

## Other AI surfaces

### GUI dashboard

```bash
cd gui
python start.py    # http://127.0.0.1:8866/
```

Steers registered backends (Daily Coder, Research Forge, daily-task). Does **not** replace PolicyGateway.

### Daily Coder CLI

```bash
cd agents/coding/daily-coder-ecosystem
pip install -e .
python -m daily_coder validate
```

Artifact-driven coding orchestration (CLI + REST). Prefer IDE `/daily-coder` + `ide-bridge` for audited IDE to runtime runs.

### Research Forge CLI

```bash
cd agents/research/research-forge
pip install -e ".[dev]"
python -m research_forge doctor
```

Evidence pipeline (mock-by-default). Bridge: `ide-bridge research-forge run|resume`. Distinct from IDE `/deep-research` (read-only orchestrator).

### Browser paste families

```bash
python agents/daily-task/driver.py --list
python agents/daily-task/driver.py <family> [--variant]
```

Ten federated families (lifestyle, coding, research). Soft / propose-only; audited repo writes still need `/daily-coder` + `ide-bridge`. See [`agents/daily-task/README.md`](agents/daily-task/README.md).

### Personal and shared skills

On-demand skills under [`agents/shared/skills/`](agents/shared/skills/) — not slash orchestrators. Operator guide: [`docs/personal-skills/README.md`](docs/personal-skills/README.md). Career writes: `python -m agent_core.personal_store` (soft-confirm, outside git).

---

## IDE setup (summary)

From repo root:

```bash
pip install -e agents/shared/ai_agents_repo
pip install -e agents/ide/bridge
pip install pyyaml
python agents/ide/scripts/import_daily_coder_agents.py --check
python agents/ide/scripts/import_rf_agents.py --check
python agents/ide/scripts/sync_ide_agents.py --check
```

| IDE | Generated projections |
|-----|------------------------|
| Cursor | [`.cursor/agents/`](.cursor/agents/) (+ [`.cursor/hooks/`](.cursor/hooks/)) |
| VS Code Copilot | [`.github/agents/*.agent.md`](.github/agents/) |
| Claude Code | [`.claude/agents/`](.claude/agents/) |

Edit only [`agents/ide/canonical/`](agents/ide/canonical/), then re-sync. **Detailed setup for each IDE:** [`agents/ide/README.md`](agents/ide/README.md). Architecture: [`docs/ide-agents/ide-agent-pack.md`](docs/ide-agents/ide-agent-pack.md).

**Soft ≠ hard:** Cursor hooks and frontmatter denylists are **soft** assist. Mutating Daily Coder / live Research Forge work requires [`ide-bridge`](agents/ide/bridge/README.md) (`IDE_BRIDGE_ACTIVE=1`) and Python PolicyGateway. Personal career data uses `personal-store` with visible diff + `--confirm` (soft-confirm), not the engineering gateway. Browser paste packs are soft.

---

## Repository layout

```
ai_agents/
├── agents/          # ide, research, coding, daily-task, shared (+ ai_agents_repo)
├── gui/
├── docs/
├── tests/
├── .cursor/ .claude/ .github/   # IDE/CI projections (generated from agents/ide)
├── .ai-agents-layout .env.example
├── AGENTS.md
└── README.md
```