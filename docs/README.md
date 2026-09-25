# Documentation hub

Code-accurate documentation for the **ai_agents** monorepo: three Python products, IDE agent projections, and a research corpus that informed their design.

**Authority order (when docs disagree):**

1. **Package source** — Python modules, configs, JSON schemas under each product tree  
2. **This hub** — curated cross-package docs in the folders below  
3. **[`archive/`](archive/)** — superseded or historical notes (not runtime truth)

**Requirements:** Python 3.10+ for all packages. Copy [`.env.example`](../.env.example) for local secret variable names (no values committed).

---

## Packages (runtime)

| Package | Path | Role |
|---------|------|------|
| GUI | [`gui/`](../gui/) | Shared GUI to steer registered backends (Python package `agent_dashboard`) |
| Daily Coder | [`agents/coding/daily-coder-ecosystem/`](../agents/coding/daily-coder-ecosystem/) | Artifact-driven coding orchestration (CLI + REST) |
| Research Forge | [`agents/research/research-forge/`](../agents/research/research-forge/) | Evidence-first research pipeline (mock-by-default) |
| **IDE agents** | [`agents/ide/`](../agents/ide/) | Canonical agents + [`ide-bridge`](../agents/ide/bridge/README.md) |
| **agent-core** | [`agents/shared/agent-core/`](../agents/shared/agent-core/) | Shared contracts, style profiles, writing-lint, personal-store |
| **Personal skills** | [`agents/shared/skills/`](../agents/shared/skills/) + [`docs/personal-skills/`](personal-skills/) | On-demand study / writing / career skills (no 7th UF agent) |

**Six user-facing IDE agents:** [`AGENTS.md`](../AGENTS.md) at repo root. Generated IDE files: `.cursor/agents/`, `.claude/agents/`, `.github/agents/`. Edit [`agents/ide/canonical/`](../agents/ide/canonical/) and run `python agents/ide/scripts/sync_ide_agents.py`.

### Browser channel (non-runtime)

| Pack | Path | Role |
|------|------|------|
| Browser RCC v3 | [`agents/shared/browser/`](../agents/shared/browser/) | Ten federated families + variants ([`MANIFEST.index.json`](../agents/shared/browser/MANIFEST.index.json)); router [`agents/daily-task/ROUTER.yaml`](../agents/daily-task/ROUTER.yaml); use `ide-bridge` for audited mutations |

---

## Table of contents

### [`personal-skills/`](personal-skills/)

| Document | Focus |
|----------|--------|
| [README](personal-skills/README.md) | Operator guide |
| [SPEC](personal-skills/SPEC.md) | Full personal/career specification |
| [Glean overlap](personal-skills/glean-overlap.md) | Plugin vs local skills |
| [Enforcement](personal-skills/enforcement.md) | Soft vs hard |
| [Overlap matrix](personal-skills/overlap-matrix.md) | Agents / browser / skills |

### [`shared-toolkit/`](shared-toolkit/)

| Document | Focus |
|----------|--------|
| [README](shared-toolkit/README.md) | Datasheet, structured data, claim audit, writing roles |
| [writing-improver](shared-toolkit/writing-improver.md) | Writing operational guide |

### [`decisions/`](decisions/)

| Document | Focus |
|----------|--------|
| [ADR: Token topology (KEEP-6)](decisions/ADR-TOKEN-TOPOLOGY-2026-09.md) | Reject mega-UF / Daily–Career UF; skills-first personal; documenter scope |
| [Session design rationale](decisions/SESSION_DESIGN_RATIONALE.md) | Design evolution, shared `agent-core/`, alternatives rejected |
| [ADR: Additive migration](decisions/0005-additive-migration.md) | Shared core before path moves |

### [`architecture/`](architecture/)

| Document | Focus |
|----------|--------|
| [Architecture overview](architecture/architecture-overview.md) | Cross-package topology, state authority, entry points |
| [Master build spec](architecture/agent_orchestration_master_spec.md) | Planning authority — Part D pipeline, roster, roadmap |
| [Build roadmap narrative](architecture/build-roadmap.md) | NOW / NEXT / EXPERIMENT phasing |
| [Design lineage](architecture/design-lineage.md) | Research ideas mapped to shipped mechanisms |

### [`orchestration/`](orchestration/)

| Document | Focus |
|----------|--------|
| [System map](orchestration/system-map.md) | Six + skills + toolkit |
| [Master-spec extract](orchestration/master-spec-extract.md) | A6–A11 / D.2–D.4 for personal layer |

### [`improvements/`](improvements/)

| Document | Focus |
|----------|--------|
| [Session synthesis](improvements/session-synthesis-2026-09.md) | How this slice was decided |
| [Planned improvements](improvements/planned-improvements.md) | Backlog |

### [`ide-agents/`](ide-agents/)

| Document | Focus |
|----------|--------|
| [IDE agent pack architecture](ide-agents/ide-agent-pack.md) | Projections, soft vs hard enforcement, bridge |
| [Hooks, skills, and enforcement](ide-agents/hooks-and-skills.md) | PolicyGateway vs Cursor hooks, DC/RF skills |

### [`research-forge/`](research-forge/)

| Document | Focus |
|----------|--------|
| [Research Forge deep dive](research-forge/research-forge-deep-dive.md) | Waves, lanes, contracts, experiments |

### [`guides/`](guides/)

| Document | Focus |
|----------|--------|
| [Agent thought processes](guides/agents-thought-process.md) | Per-role reasoning loops and I/O |
| [Wave 1 mock happy path](guides/wave1-mock-happy-path.md) | Short RF mock onboarding |
| [Resident context audit](guides/resident-context-audit.md) | Trim always-on `~/.cursor` rules, skills, plugins, MCP |
| [Glossary](guides/glossary.md) | Shared terms |

### [`research/`](research/) (planning corpus)

| Document | Focus |
|----------|--------|
| [REFERENCES.md](research/REFERENCES.md) | Bibliography by topic |
| [Research library](research/agent_orchestration_research_library.md) | Typed source library |
| [Research brief](research/agent_orchestration_research_brief.md) | Deep notes on original corpus |
| [GAP and cost plan](research/GAP_AND_COST_PLAN.md) | Gap / cost planning |
| [sources/](research/sources/) | Per-link cards and reading order |

Package-local docs remain authoritative for detail: [`agents/coding/daily-coder-ecosystem/docs/`](../agents/coding/daily-coder-ecosystem/docs/), [`agents/research/research-forge/docs/`](../agents/research/research-forge/docs/), [`gui/docs/`](../gui/docs/).

---

## Supported today (summary)

| Area | Shipped | Not shipped / stub |
|------|---------|---------------------|
| Daily Coder providers | `mock` default; live providers behind explicit opt-in + secrets | Copilot-as-primary engine |
| Research Forge | Waves 0–6 mock adapters, CLI, experiments subsystem | Live search at scale |
| IDE agents | Sync/import `--check` in CI; soft hooks + `ide-bridge` for audited writes | Hooks ≠ PolicyGateway |
| CI | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | — |

---

## Quick start

```bash
# Dashboard
cd gui && python start.py

# Daily Coder
cd agents/coding/daily-coder-ecosystem && pip install -e . && python -m daily_coder validate

# Research Forge
cd agents/research/research-forge && pip install -e ".[dev]" && python -m research_forge doctor

# IDE agent sync (from repo root)
python agents/ide/scripts/sync_ide_agents.py --check
```

---

## Archive

Stale or superseded material: [`archive/`](archive/) (includes former root `PASTREADME`, rough RF plan, audit matrices). **`docs/archive/` is a historical snapshot** — paths there are not maintained for v2; use this hub and package docs for current behavior.
