# Agent Ecosystem Overview

## Purpose

This document is the future contributor’s entry point to the repository. It explains what the ecosystem contains, which agents users invoke, which delegates are shared, where hard enforcement lives, and how browser, IDE, and runtime surfaces relate.

## Design in one sentence

Keep a small set of user-facing orchestrators, place reusable judgment tasks in a canonical shared-subagent library, keep deterministic computation and enforcement in platform services, and generate surface-specific adapters instead of copying role definitions.

## System layers

```text
User-facing entry points
├── IDE: deep-research, research-messenger, plan-prep,
│        use-master, daily-coder, researcher
└── Browser: self-contained everyday and engineering procedures

Orchestration layer
├── Research Forge
├── Daily Coder
└── future bounded domain workflows

Shared delegate library
├── source-inspector
├── evidence-synthesizer
├── artifact-style-enforcer
├── structured-data-extractor
├── data-evaluator
├── visualization-specifier
├── planner
├── plan-reviewer
├── evaluation-designer
├── execution-verifier
├── failure-diagnostician
└── documentation-curator

Deterministic platform services
├── policy gateway
├── state and ledger
├── router
├── schema validators
├── calculation and query runners
├── artifact registry
└── projection generators
```

## What is shared

A shared subagent has one reusable judgment responsibility, a versioned contract, and multiple authorized callers. It is not user-facing by default.

Shared agents may be used by Daily Coder, Research Forge, IDE orchestrators, and future personal skill workflows through typed packets. Each caller supplies a domain profile and a scoped task; the shared role does not gain broad access to the caller’s entire context.

## What stays domain-specific

Do not share roles whose safety, permissions, or verifier are materially different.

Examples that remain domain-specific:

* Code implementers with repository write allowlists.
* Research lanes with source-search permissions.
* Resume writers using private career facts.
* Experiment runners with live-provider or environment permissions.
* Browser personas that are intentionally self-contained and soft-enforced.

## Canonical shared roster

| Shared role | Single outcome | Typical callers | Status |
|---|---|---|---|
| `source-inspector` | Extract source-bound facts, structure, and locators | Research Forge, plan-prep, researcher, browser doc-reader adapter | Consolidate existing roles |
| `evidence-synthesizer` | Merge validated evidence while preserving contradictions and uncertainty | deep-research, research-messenger, career research | Consolidate existing roles |
| `artifact-style-enforcer` | Check an artifact against one declared style profile without changing meaning | Daily Coder, documentation, writing, career artifacts | New shared core |
| `structured-data-extractor` | Convert tables or files into a typed fact table with provenance | Research, analytics, spreadsheet workflows | New shared core |
| `data-evaluator` | Run defensible calculations and quality checks over a validated fact table | Research Forge, reports, student/lab data | New shared core |
| `visualization-specifier` | Convert approved results into chart- and table-ready specifications | Reports, dashboard, presentations | New shared core |
| `planner` | Produce atomic tasks with dependencies and verification | use-master, Daily Coder, browser planner adapter | Canonicalize existing role |
| `plan-reviewer` | Adversarially review a frozen plan | use-master, Daily Coder, browser reviewer adapter | Canonicalize existing role |
| `evaluation-designer` | Translate requirements into tests, checks, and negative cases | Daily Coder, Research Forge experiments, skills CI | Consolidate test-author patterns |
| `execution-verifier` | Execute authoritative checks and preserve raw results | Daily Coder, Research Forge experiments | Shared contract, domain adapters |
| `failure-diagnostician` | Localize the critical failed step and assign fault ownership | All runtimes | Canonicalize existing role |
| `documentation-curator` | Update reviewed documentation and evidence lineage | All runtimes | Consolidate documentation roles |

## Repeated responsibilities and disposition

| Existing overlap | Decision |
|---|---|
| Browser `doc-reader`, IDE `researcher`, planning recon, research extraction lanes | Share the `source-inspector` contract; retain surface-specific tools and permissions |
| Browser `planner` and runtime planner | One canonical planner contract; browser is a draft-only projection |
| Browser `plan-reviewer` and runtime plan reviewer | One canonical review rubric; browser cannot enforce runtime gates |
| Research synthesizer, information condenser, and report assembly | Share an evidence-packet schema; keep browser condenser as a lightweight persona |
| `voice-tone-chameleon`, documentation style checking, resume style, and code style review | Use one `artifact-style-enforcer` with versioned profiles |
| `data-silhouette-reader`, spreadsheet inspection, telemetry analysis, and report chart preparation | Use a composed data workflow, not one giant data agent |
| Test author and experiment pre-reviewer | Share `evaluation-designer`; domain fixtures and verifiers remain separate |
| Test executor and experiment runner | Share an execution-result schema; retain separate adapters and permissions |
| Documenter roles across pipelines | Use `documentation-curator` with repository-specific documentation profiles |

## The data workflow

The requested “data sheet spelunker” is deliberately implemented as a workflow:

```text
source file
  → structured-data-extractor
  → schema validation
  → deterministic calculation/query tool
  → data-evaluator
  → visualization-specifier
  → table, chart, dashboard, or report adapter
```

This separation prevents an extraction mistake from being disguised as an analytical conclusion. Downstream agents may only analyze the validated fact table, not the raw spreadsheet text.

## The style workflow

```text
candidate artifact + style profile + semantic constraints
  → artifact-style-enforcer
  → issue list + proposed patch + semantic-risk flags
  → domain verifier
  → caller accepts, revises, or rejects
```

Profiles include:

* `code-python`
* `code-typescript`
* `repository-docs`
* `technical-report`
* `professional-email`
* `resume`
* `presentation-copy`

The shared role enforces the selected profile. It does not invent a style or silently rewrite semantics.

## Authority order

1. Runtime policy, schema, and permission enforcement.
2. Canonical shared-agent contracts.
3. Canonical user-facing IDE agents.
4. Domain adapters and skills.
5. Generated IDE projections.
6. Browser prompt projections and operator guides.

A lower layer may narrow behavior but may never widen permissions or contradict a canonical contract.

## Quick navigation

* `shared_subagent_architecture.md` - exact shared-agent contracts and data schemas.
* `agent_ecosystem_improvement_plan.md` - migration, folder redesign, validation, and rollout.
* `design_rationale_and_session_synthesis.md` - decisions, alternatives, and trade-offs.
* `daily_career_agent_expansion_plan.md` - personal, study, and career capabilities using the shared library.

## Sources

Based on the supplied `agent_orchestration_master_spec.md`, `agent_orchestration_research_library.md`, `agent_orchestration_research_brief.md`, repository `README.md`, `AGENTS.md`, Browser Agent Pack README, and Research Forge README.
