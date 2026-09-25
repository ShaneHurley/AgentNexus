# ADR: Token-efficient agent topology (KEEP-6)

**Status:** Accepted  
**Date:** 2026-09  
**Supersedes:** None (complements numbered ADRs and session synthesis)

## Context

Orchestration cost is driven primarily by **fan-out and context stuffing**, not user-facing (UF) orchestrator count alone. Proposals to merge UF agents or expand Daily Coder’s `documenter` phase into personal/career work would add routing baggage, blur write boundaries, and recreate patterns already rejected in [SESSION_DESIGN_RATIONALE.md](SESSION_DESIGN_RATIONALE.md).

Personal daily and career procedures are specified as **on-demand skills** in [../personal-skills/README.md](../personal-skills/README.md) and [../personal-skills/SPEC.md](../personal-skills/SPEC.md)—not as additional IDE orchestrators.

## Decision

### KEEP-6 user-facing orchestrators

Retain exactly **six** user-facing IDE orchestrators as declared in [AGENTS.md](../../AGENTS.md) and [agents/ide/MANIFEST.yml](../../agents/ide/MANIFEST.yml):

| Agent | Role |
|-------|------|
| `deep-research` | Eight-phase evidence research |
| `research-messenger` | ASSEMBLE / ECOSYSTEM / COMBINED packets |
| `plan-prep` | Planning context report |
| `use-master` | Master DAG dispatch + bridge |
| `daily-coder` | Bridge-only parent for mutating runs |
| `researcher` | Read-only codebase recon |

There is **no** seventh UF agent (`/daily`, `/career`, or personal mega-orchestrator) in this topology.

### Skills-first personal capabilities

Student daily work, writing, and career artifacts (résumé tailoring, opportunity review, interview prep) stay **skills-first**: invoke [`agents/shared/skills/personal/career-tools/`](../../agents/shared/skills/personal/career-tools/) and related personal skills per [../personal-skills/README.md](../personal-skills/README.md). Résumé tone and formatting use shared style profiles (e.g. `resume-tailor` + résumé profile via `artifact-style-enforcer`)—not engineering orchestration phases.

### Reject Topology A — one or two mega UF agents

**Rejected:** Collapsing engineering UF agents into **1–2** “technical / non-technical” mega-agents.

**Rationale:** Mode-heavy prompts, plan/review/write role collapse, and persistent routing cost typically **increase** per-task tokens while harming quality boundaries. Aligns with “one universal agent” rejection in [SESSION_DESIGN_RATIONALE.md](SESSION_DESIGN_RATIONALE.md) §3.

### Reject Topology B — Daily / Career / Coding UF trio

**Rejected:** Adding a **Daily / Career / Coding** trio of UF orchestrators (or equivalent personal entry points).

**Rationale:** Duplicates browser and skill capabilities before usage proof; risks privacy and engineering boundary regressions. Documented alternative in session Stage 2 → Stage 3 correction ([SESSION_DESIGN_RATIONALE.md](SESSION_DESIGN_RATIONALE.md) §1).

### Reject documenter → résumé / career artifacts

**Rejected:** Routing résumé, CV, cover-letter, or career-oriented README work through Daily Coder’s **`documenter`** phase or IDE `documenter` projection.

**Rationale:** Documenter is **technical closeout only**—documentation of reviewed, observed engineering changes. Career artifacts need claim-auditor rules, personal-store boundaries, and résumé-specific profiles; expanding documenter scope invites fact invention and incorrect write authority.

**Instead:** [`agents/shared/skills/personal/career-tools/`](../../agents/shared/skills/personal/career-tools/) (see canonical [documenter.md](../../agents/ide/canonical/documenter.md) MUST NOT).

### Consolidate shared judgment via `agent-core/` only

Cross-cutting roles (style enforcement with profiles, planner/plan-reviewer contracts, personal-store helpers, writing lint) **consolidate in [`agents/shared/agent-core/`](../../agents/shared/agent-core/)**—not under `ide-agents/`, Daily Coder alone, or duplicated prompt copies per surface.

Surfaces (IDE projections, DC runtime, Research Forge, browser procedures, personal skills) consume shared contracts through **adapters and profiles**, per Decision A–B in [SESSION_DESIGN_RATIONALE.md](SESSION_DESIGN_RATIONALE.md) §2.

Token savings for this topology are pursued via context slicing (`ROLE_INPUTS`), budget hard-stops, progressive contract loading, and measured baselines—not UF count reduction or documenter scope expansion.

## Consequences

- UF count remains **six**; CI and docs must not introduce a seventh UF orchestrator without a new ADR.
- Résumé/career paths record **zero** `documenter` invocations.
- New shared roles require reuse across ≥2 orchestration systems and land in `agent-core/` first.
- Deferred: one-front-door / three-mode UX experiments until KEEP-6 token levers are measured (see token-efficiency plan).

## Related documents

| Document | Link |
|----------|------|
| Session design rationale | [SESSION_DESIGN_RATIONALE.md](SESSION_DESIGN_RATIONALE.md) |
| Personal skills operator guide | [../personal-skills/README.md](../personal-skills/README.md) |
| Personal skills specification | [../personal-skills/SPEC.md](../personal-skills/SPEC.md) |
| Career skills (résumé, interview, etc.) | [../../agents/shared/skills/personal/career-tools/](../../agents/shared/skills/personal/career-tools/) |
| IDE documenter projection | [../../agents/ide/canonical/documenter.md](../../agents/ide/canonical/documenter.md) |
| Root agent roster | [../../AGENTS.md](../../AGENTS.md) |
