# AI Agents — Documentation Hub

Welcome. This hub is the **code-accurate** entry point for the workspace at `ai_agents/`: three cooperating products plus a research corpus that informed their design.

| Package | Path | What it is |
|---------|------|------------|
| **Agent Dashboard** | [`agent-dashboard/`](../agent-dashboard/) | Shared GUI to see and steer registered backends |
| **Daily Coder Ecosystem** | [`daily-coder-ecosystem/`](../daily-coder-ecosystem/) | Artifact-driven coding orchestration (CLI + REST) |
| **Research Forge** | [`research-forge/`](../research-forge/) | Evidence-first research pipeline (Waves 0–6, mock-by-default) |
| **Research corpus** | [`Documentation/`](../Documentation/) | Specs and bibliography (planning authority, not runtime) |

**Requirements:** Python 3.10+ for all packages.

Copy [`.env.example`](../.env.example) for local secret variable names (no values committed).

---

## Supported today (truth table)

| Area | Shipped today | Not shipped / stub |
|------|----------------|---------------------|
| **Daily Coder providers** | `mock` default; live **gemini**, **openrouter**, openai, anthropic, local, command, http behind explicit live opt-in + secrets | Copilot-as-primary engine; embedded Copilot IDE |
| **Daily Coder git** | Local repo path on CLI/`--repo`; `repository.status` tools; optional `daily-coder github clone|repo|pulls` (allowlisted) | GitHub PR create/push; OAuth app UI |
| **Agent Dashboard** | Steer runs, start/stop Daily Coder `serve`, **provider dropdown** (default mock), **live confirm**, local repo HEAD/dirty; RF **resume** fail-closed (404 without state, 403 live gate), loads persisted Wave 1 state when present | In-GUI docs browser / theme switcher (vision) |
| **Research Forge** | Waves 0–6 **mock** adapters, experiments subsystem, CLI `run`/`doctor`/`validate`/`resume`/`status`, optional public GitHub code adapter | Live RF search at scale; treating mock as live |
| **CI** | Monorepo [`.github/workflows/ci.yml`](../.github/workflows/ci.yml): RF pytest + DC unittest + dashboard smoke | Optional docker sandbox for all CI jobs |
**Preferred live models (config path):** set secrets (`daily-coder secrets set …`), start with `--provider gemini` or `--provider openrouter --live`, or pick the same in the dashboard before **Start server**. See [`daily-coder-ecosystem/README.md`](../daily-coder-ecosystem/README.md) and [`config/pricing.json`](../daily-coder-ecosystem/config/pricing.json) for tier slugs.

**Wave 1 onboarding:** [wave1-mock-happy-path.md](./wave1-mock-happy-path.md)

---

## Table of contents

### System design (implementation truth)

| Document | Focus |
|----------|--------|
| [Architecture overview](./architecture-overview.md) | Cross-package topology, state authority, entry points |
| [Agent thought processes](./agents-thought-process.md) | Every role: why it exists, reasoning loop, I/O, failure modes |
| [Hooks, skills, and enforcement](./hooks-and-skills.md) | Runtime gates, skills library, what is *not* in the repo |
| [Research Forge deep dive](./research-forge-deep-dive.md) | Waves, lanes, contracts, scoring, scrutiny, Director, experiments |
| [Design lineage](./design-lineage.md) | Papers and ideas mapped to concrete mechanisms (explicit vs analogy) |
| [Build roadmap narrative](./build-roadmap.md) | How the system was phased and why (NOW/NEXT/EXPERIMENT bands) |
| [Wave 1 mock happy path](./wave1-mock-happy-path.md) | Short RF mock onboarding |
| [Glossary](./glossary.md) | Shared terms across packages |

### Package-local docs (still authoritative for detail)

| Location | Use when |
|----------|----------|
| [`daily-coder-ecosystem/docs/`](../daily-coder-ecosystem/docs/) | Ops, security, provider adapters, traceability |
| [`research-forge/docs/`](../research-forge/docs/) | Wave releases, experiments, agent invocation for experiments |
| [`agent-dashboard/docs/`](../agent-dashboard/docs/) | Dashboard-specific architecture |
| [`Documentation/`](../Documentation/) | Master spec, research library, gap planning |

### Visual map

Open beside chat: [Documentation & system map](file:///C:/Users/WZ69B7/.cursor/projects/c-Users-WZ69B7-Downloads-ai-agents/canvases/ai-agents-documentation-map.canvas.tsx)

---

## Quick start

**Dashboard (all agents):**

```bash
cd agent-dashboard
python start.py
```

Opens http://127.0.0.1:8866/

**Daily Coder:**

```bash
cd daily-coder-ecosystem
python -m pip install -e .
python -m daily_coder validate
python -m unittest discover -s tests -v
```

**Research Forge:**

```bash
cd research-forge
python -m pip install -e ".[dev]"
python -m research_forge doctor
python -m pytest -q
```

---

## Documentation principles used here

1. **SQLite / ledger / schema-valid JSON** are authoritative where the code says so; model prose never completes a run by itself.
2. **Mock-by-default** is explicit: simulated completion is not verified production behavior.
3. **Research corpus** (`Documentation/`) informed design; only mechanisms present in Python, config, or schemas are described as shipped.
4. Cross-links use relative paths from this `docs/` tree.

---

## Integrity note

The external research library in `Documentation/` is marked **PARTIAL** (abstract-level verification for many arXiv entries). Numbers in planning docs are transcribed from sources, not re-run as experiments in this workspace.
