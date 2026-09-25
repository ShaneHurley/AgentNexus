# Build roadmap narrative

A chronological story of how the `ai_agents` workspace grew — aligned with **directories and version notes in code**, not a fictional release timeline.

---

## Phase 0 — Research corpus and specification

**Where:** [`docs/research/`](../research/) and [`docs/architecture/`](./agent_orchestration_master_spec.md)

**What happened:** A large orchestration research library and master spec were consolidated so implementers could trace decisions to sources. The hub README defines authority order: master spec first, then REFERENCES, sources hub, full library.

**Why:** Building agents without a shared evidence base produces prompt-only policy that drifts. The corpus is explicitly **PARTIAL** for full-text verification — honest scope for portfolio readers.

**Outcome:** [`agent_orchestration_master_spec.md`](./agent_orchestration_master_spec.md) remains planning authority; runtime code lives elsewhere.

---

## Phase 1 — Daily Coder scaffold and deterministic core

**Where:** [`daily-coder-ecosystem/`](../../agents/coding/daily-coder-ecosystem/)

**What happened:**

1. **Role folders** — `agents/*/prompt.md`, `agent.json`, `model.json` for sixteen roles.
2. **Python orchestrator** — `Orchestrator` with SQLite state, artifact store, workflow version **2.1**.
3. **Enforcement first** — `ToolBroker`, `PolicyGateway`, `acceptance.evaluate` before expanding agent count.
4. **Skills as data** — ten `skills/*/SKILL.md` files loaded by name from plans only.
5. **Tests** — `python -m unittest discover -s tests`.

**Pivots:**

- Chose **single-host SQLite** over distributed queue (stubs fail closed per architecture doc).
- **`SIMULATED` vs `COMPLETE`** distinguishes mock provider runs from live verification.

**Lessons:**

- Pinning `ORIGINAL_REQUEST` and plan hashes prevented “helpful” scope expansion in tests.
- Parallel research lanes required budget reservation before thread pool launch (orchestrator `_research`).

---

## Phase 2 — Agent Dashboard

**Where:** [`gui/`](../gui/)

**What happened:** Unified GUI on port **8866** with adapters for Daily Coder and Research Forge (`registry.py`, `adapters/`).

**Why:** Multiple CLIs are hard to steer during long runs; dashboard is a **thin** layer — no second orchestrator.

**Launcher:** `start.py` / `start.bat` with venv bootstrap (root README).

---

## Phase 3 — Research Forge Waves 0–4

**Where:** [`research-forge/src/research_forge/`](../../agents/research/research-forge/src/research_forge/)

**What happened:**

| Wave | Capability added |
|------|------------------|
| 0 | Doctor, fixtures, dry-run, replay |
| 1 | Sequential clarify→compose DAG (`Wave1Orchestrator`) |
| 2 | Fan-out lanes, curator, saturation |
| 3 | Scrutiny: methods, skeptic, falsification, audit |
| 4 | Ideation portfolio, lineage, fabrication checks |

**Design choice:** **Mock-by-default** adapters so CI and portfolio demos never imply live research without gates.

**Config evolution:** Per-wave YAML under [`research-forge/config/`](../../agents/research/research-forge/config/).

---

## Phase 4 — Director, handoffs, Wave 6 platform

**Where:** `wave5/`, `wave6/`

**What happened:**

- **Wave 5** — Token-bounded Director packets, challenge path, handoff taxonomy for comparing raw vs structured briefs.
- **Wave 6** — Adapter SDK, routing experiments, proposal workflow, maintenance tooling (drift, disaster recovery).

**Why:** Research outputs needed a **single accountable synthesis role** (Director) without throwing away structured evidence from earlier waves.

---

## Phase 5 — Local experiments (`0.7.0+experiments`)

**Where:** [`research_forge/experiments/`](../../agents/research/research-forge/src/research_forge/experiments/), docs [`EXPERIMENTS.md`](../../agents/research/research-forge/docs/EXPERIMENTS.md)

**What happened:** Human-gated, **token-free** experiment pipeline (Creator / Pre-Reviewer / Runner / Post-Reviewer) separated from Wave 4’s design-only `ExperimentArchitect`.

**Decision reference:** IMPLEMENTATION_STATUS cites **RF-DEC-14** = local token-free experiments.

**Lesson:** Execution belongs in a deterministic runner; LLM interprets only after observations exist.

---

## Phase 6 — Documentation hub (this tree)

**Where:** [`docs/`](../docs/)

**What happened:** Code-accurate hub, agent cognition docs, Forge deep dive, lineage map, canvas system overview.

**Relationship to older docs:** Package-level docs (`daily-coder-ecosystem/docs/`, `research-forge/docs/`) remain authoritative for ops; this hub cross-links and removes drift at portfolio level.

---

## Improvement bands (2026 roadmap)

Labels match the scored improvement packet; **code wins** over aspirational spec.

### NOW (shipped in this pass)

| ID | Item |
|----|------|
| REC-05 | Monorepo CI (RF + Daily Coder + dashboard) — [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) |
| REC-08 | RF CLI tests for missing-run / resume flows |
| REC-PROV-GO | `.env.example`, hub docs, OpenRouter/Gemini pricing slugs |
| REC-DASH-PROV | Dashboard provider dropdown → `serve --provider` (default **mock**) |
| REC-DASH-LIVE-CONFIRM | Dashboard live-provider confirm checkbox (+ `confirm()` fallback) before Start/Restart |
| REC-GH-LOCAL | Dashboard shows local repo path + git HEAD/dirty when available |
| REC-01a/b | Durable RF `RunState` + CLI `resume`/`status` |
| REC-02 | [security-review-checklist.md](../../agents/research/research-forge/docs/security-review-checklist.md) |
| REC-10 | Root env template (overlaps REC-PROV-GO) |
| REC-13 | [Wave 1 mock happy path](./wave1-mock-happy-path.md) |
| REC-07 | Truth table in [docs hub](./README.md#supported-today-truth-table) |
| REC-GH-CLONE | `daily-coder github clone` allowlisted into `allowed_repo_roots` |
| REC-GH-READ | `github.repo.metadata` / `github.pull.list` tools + `github repo`/`pulls` CLI |
| REC-06 | Dashboard RF adapter resume fail-closed + live gate + HTTP 202/404/403/502 (tests in `gui/tests/test_research_forge_resume.py`) |
| REC-04 | Optional `RF_EXPERIMENT_SANDBOX=docker` for unittest benchmarks |
| REC-COP-BRIDGE | Experiment doc [COPILOT_BRIDGE_EXPERIMENT.md](../../agents/research/research-forge/docs/COPILOT_BRIDGE_EXPERIMENT.md) |
| REC-RF-GH-ADAPTER | `PublicGitHubCodeRepositoryAdapter` (opt-in; mock default) |

### NEXT

| ID | Item |
|----|------|
| REC-DASH-LIVE-REGISTRY | Derive dashboard `LIVE_PROVIDERS` from `daily_coder.providers.registry` (avoid drift); prefer CI equality assert in `test_live_providers_sync.py` before SSOT import |
| REC-DASH-TOKEN-ENV | Serve Daily Coder token via env/file instead of argv (**hub** `AGENT_DASHBOARD_TOKEN` is separate — memory-only in S3a) |
| REC-DASH-RF-RESUME-GATE | *(shipped this pass)* Dashboard RF resume: load state before mutate; `wave_1_live` preflight |
| REC-DASH-RF-RESUME-TEST | *(shipped this pass)* Dashboard resume unit + HTTP tests (missing state, live deny) |
| REC-CI-RUFF-MYPY | Align root CI with optional ruff/mypy (package-local today) |
| REC-DASH-AGENTS-OVERFLOW | Agents sidebar: stop truncating description/status mid-word (Research Forge card clips at right edge; wrap or ellipsis with full text on hover/title) |
| REC-DASH-AGENTS-STATUS-LAYOUT | Agents cards: keep description and backend status on separate readable lines (today “ready — …” reads mashed into the summary) |
| REC-DASH-AGENTS-LOCAL-HINT | Research Forge “no server needed” hint: place inside the card / actions row so it is not an orphaned label under the list |

### EXPERIMENT

| ID | Item |
|----|------|
| **Vision (EXPERIMENT)** | Personal **simple GUI editor** to steer the stack (dashboard evolution) |
| **Vision (EXPERIMENT)** | Prettier **theme switcher** / theme packs for the dashboard |
| **Vision (EXPERIMENT)** | **In-app docs browser** for hub and package docs |
| **Vision (EXPERIMENT)** | Product that **fully integrates** this stack into itself (future self-integration surface) |
| REC-COP-BRIDGE | Continue Copilot SDK/CLI spike measurements vs native orchestrator |

### DEFER

| ID | Item |
|----|------|
| REC-03 | Live RF search adapters at scale (beyond opt-in code adapter) |
| REC-GH-PR | GitHub PR create/push without human gates |

### DO_NOT_ADOPT

| ID | Item |
|----|------|
| REC-12 | Postgres / distributed queue as default |
| REC-COP-REPLACE | Copilot as **primary** orchestration engine |
| REC-COP-IDE | Embed Copilot IDE inside Agent Dashboard |

### Easy wins discovered while implementing

- Provider + git metadata on dashboard run rows without new Daily Coder API fields (adapter normalization + local `git`).
- `set_provider` backend action so operator can pick Gemini/OpenRouter before **Start server** without editing `agents.json`.
- Monorepo CI reuses each package’s existing test entrypoints (no new harness).

### Preferred live providers (operator default path)

**Gemini** and **OpenRouter** are first-class in Daily Coder [`providers/registry.py`](../../agents/coding/daily-coder-ecosystem/daily_coder/providers/registry.py); use secrets + `--live` or the dashboard provider select — still **mock** until explicitly chosen.

---

## Future / not shipped (explicit)

| Item | Evidence |
|------|----------|
| Postgres / distributed Daily Coder jobs | architecture.md deployment section — **DO_NOT_ADOPT** for now |
| Live research adapters at scale | IMPLEMENTATION_STATUS + security checklist |
| GitHub PR create/push / OAuth app UI | **DEFER** [REC-GH-PR](#defer) — clone/read/metadata shipped under REC-GH-CLONE / REC-GH-READ |
| Cursor IDE hooks in repo | present (soft layer) — see [hooks-and-skills.md](../ide-agents/hooks-and-skills.md) |
| Auto-promotion of skill patches | `human_promotion_required` in config |

---

## How to read this alongside the master spec

Use **master spec** for intended end-state and roster completeness; use **[architecture overview](./architecture-overview.md)** and package code for **what runs today**. When they differ, code wins until intentionally updated.

---

## Cross-links

- [Documentation hub](../README.md)
- [Design lineage](./design-lineage.md)
- [Architecture overview](./architecture-overview.md)
