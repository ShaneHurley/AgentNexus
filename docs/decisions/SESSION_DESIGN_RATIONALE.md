# Design Rationale and Session Synthesis

## Purpose

This document records the decisions, alternatives, evidence, and trade-offs developed during the design session. It is a decision summary, not a hidden-reasoning transcript.

## 1. How the design evolved

### Stage 1 - Broad personal-agent brainstorming

The initial idea space included daily planning, computer-engineering tutoring, travel, writing, style, productivity, and career support.

Useful conclusion: many recurring personal tasks are real candidates for reusable procedures.

Problem discovered: turning every useful procedure into an agent creates selection friction, persistent prompt cost, overlapping responsibilities, and unclear authority.

### Stage 2 - Personal Daily and Career orchestrator

The next design introduced a Daily Orchestrator above Career, Learning, Writing, Travel, and Engineering domains.

Useful conclusions retained:

* Typed handoffs.
* Evidence-backed career facts.
* Privacy separation.
* Resume lineage.
* Approval boundaries.
* Small domain-specific workflows.

Problem discovered: a new personal runtime and new IDE entry points duplicated existing browser capabilities and orchestration infrastructure before usage proved the need.

### Stage 3 - Skill-first correction

The design shifted to a bounded five-to-eight-skill library, existing browser roles, user-owned calendars/tasks/notes, and a compact career skill family.

Useful conclusion: default to skills for repeated procedures and promote only when persistent state, long-running isolation, or cross-skill routing is demonstrated.

### Stage 4 - Shared-subagent architecture

The current request exposed another source of duplication: the same bounded judgment roles appear across Daily Coder, Research Forge, IDE projections, browser procedures, data workflows, and documentation.

Final direction:

* Keep user-facing orchestrators few.
* Keep personal procedures as skills.
* Consolidate reusable judgment into shared delegate contracts.
* Keep deterministic computation and policy outside agents.
* Use adapters and profiles instead of prompt copies.

## 2. Major decisions

### Decision A - Shared roles are canonical outside any one runtime

A neutral `agent-core/` avoids making Daily Coder, Research Forge, IDE agents, or browser prompts the owner of cross-cutting roles.

### Decision B - Surface adapters narrow authority

Runtime, IDE, browser, and skill projections share meaning but not permissions. Browser remains draft-only; IDE writes remain bridge-controlled; runtime policy remains authoritative.

### Decision C - Style is one outcome with profiles

Writing style, documentation style, resume tone, and coding conventions share the outcome “conform artifact to declared profile without semantic change.” They can use one shared role with profile-specific rules.

Factual review, code correctness, and style enforcement remain separate.

### Decision D - The data role is a workflow, not a mega-agent

A useful data capability must:

1. Extract faithfully.
2. Validate structure.
3. Calculate reproducibly.
4. Evaluate quality and meaning.
5. Specify an appropriate display.

These stages use separate contracts so mistakes are visible and testable.

### Decision E - Existing planner and reviewer roles should be canonicalized

The planner and plan-reviewer concepts already appear in runtime and browser systems. New copies would worsen drift. Share the contract and retain surface-specific adapters.

### Decision F - Browser personas are not runtime agents

Browser roles optimize portability and self-contained instructions. They may map to shared schemas and profiles, but they do not gain runtime persistence or enforcement claims.

### Decision G - Repository readability is an architecture requirement

Future contributors should be able to answer:

* What do I invoke?
* What delegates exist?
* Which file is canonical?
* What is generated?
* Where are permissions enforced?
* How do I add or retire a role?

The folder structure and docs must answer these without reading research documents first.

## 3. Alternatives considered

### One universal agent

Rejected because it combines planning, execution, review, writing, research, and data work under one context and permission surface.

### Many specialized user-facing agents

Rejected because discovery and routing degrade as the catalog grows, and most roles should be delegate-only.

### Put every shared role under `ide-agents/`

Rejected because IDE agents are a surface and bridge package, while shared runtime contracts need a neutral home.

### Put every shared role under Daily Coder

Rejected because Research Forge, personal skills, and browser adapters should not depend on a coding runtime.

### One “data-sheet spelunker” agent

Rejected as a single role. Accepted as a user-facing name for a composed extraction → calculation → evaluation → visualization workflow.

### One style agent that freely rewrites everything

Rejected. Accepted as a constrained reviewer/patch proposer with explicit profiles and semantic invariants.

### Rewrite the whole repository layout immediately

Rejected. The target layout is documented, but migration starts by adding `agent-core/` and navigation docs while preserving package paths.

## 4. Shared-role selection test

A responsibility belongs in the shared library when:

* Two or more orchestration systems need it.
* It has the same primary outcome across callers.
* Differences can be expressed as profiles or adapters.
* A typed packet can isolate context.
* The role can be tested independently.

It remains domain-specific when:

* Tool permissions materially differ.
* The verifier is domain-specific.
* The role owns sensitive data unavailable to other callers.
* Sharing would produce a large mode-heavy prompt.

It becomes a deterministic service when:

* Correctness can be expressed as code, schema, policy, query, or renderer behavior.
* Repeatability matters more than language judgment.

## 5. Improvements by ecosystem area

### Daily Coder

* Consume canonical planner, plan-reviewer, style, evaluation, execution, diagnosis, and documentation roles.
* Keep implementers and code-review authority domain-specific.
* Preserve `ide-bridge` and PolicyGateway for writes.

### Research Forge

* Consume source inspection, evidence synthesis, data extraction/evaluation, visualization, and documentation roles.
* Keep research-wave control and experiment permissions domain-specific.

### IDE agents

* Keep the six user-facing names stable.
* Delegate to shared contracts through adapters.
* Generate projections from canonical sources; never edit projections directly.

### Browser agents

* Preserve the 13 everyday and six engineering procedures.
* Reuse shared status and packet schemas where helpful.
* Keep self-contained messages and draft-only authority.

### Personal, study, and career capabilities

* Remain skills rather than new orchestrators by default.
* Use the shared style enforcer for professor email, resumes, and reports.
* Use the shared data workflow for lab results and spreadsheets.
* Use Research Forge for evidence-heavy career decisions.

### Dashboard

* Display shared-role identity, caller, status, artifact lineage, and verification.
* Do not become the owner of domain logic or write directly to state stores.

## 6. Decisions intentionally deferred

* Exact package import strategy for `agent-core/`.
* Whether browser projections become generated artifacts.
* Which existing prompts are semantically equivalent after code-level inspection.
* Storage technology for the shared registry and ledger.
* Whether data evaluation should be one role or split further by statistical complexity.
* Whether style patches should be applied by the caller or a separate mechanical editor.
* Timing of top-level folder moves.

## 7. Next evidence needed

* Full current specialist inventory from repository source.
* Caller-to-role invocation traces.
* Prompt and contract similarity analysis.
* Frozen evaluation tasks for each duplicate pair.
* Spreadsheet/data fixtures with known answers.
* Contributor navigation test with someone unfamiliar with the repository.
* Cross-surface permission and status parity results.

## 8. Final design principles

1. Few user-facing entry points.
2. Shared judgment, domain-specific authority.
3. Deterministic computation outside language models.
4. Extract before interpreting.
5. Style enforcement never substitutes for factual or correctness review.
6. Typed packets instead of shared transcripts.
7. Profiles and adapters instead of copied agents.
8. Canonical contracts plus generated or validated projections.
9. Migration by compatibility layers, not a flag-day rewrite.
10. Every new role must demonstrate reuse and measurable value.

## Sources

Based on all supplied orchestration, research, repository, IDE, browser, and Research Forge documents, plus the revised Daily/Career capability specification created during this session.
