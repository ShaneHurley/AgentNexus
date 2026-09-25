# Agent thought processes

Every **Daily Coder** role shares the same cognitive skeleton defined in its `prompt.md`: **OBSERVE → REFLECT → ACT → VALIDATE**, with `ORIGINAL_REQUEST` as an immutable anchor and schema-only JSON output. The orchestrator (`Orchestrator._invoke` in [`daily_coder/orchestrator.py`](../../agents/coding/daily-coder-ecosystem/daily_coder/orchestrator.py)) supplies a bounded packet, enforces tool turns from [`config/default.json`](../../agents/coding/daily-coder-ecosystem/config/default.json), and validates responses against [`schemas/`](../../agents/coding/daily-coder-ecosystem/schemas/).

Research Forge uses **Python role classes** and mock fixtures for many “agents”; the deep-research *skill* (external to this repo) describes a richer multi-lane pattern aligned conceptually with Wave 2 fan-out — see [Research Forge deep dive](./research-forge-deep-dive.md).

---

## Shared orchestration context

| Mechanism | What the agent “sees” | Code |
|-----------|------------------------|------|
| Packet rebuild | Digests, not raw prior transcripts | `_rebuild_packet` in orchestrator |
| Tool access | Role allowlist only | `ToolBroker.authorize` |
| Writes | Blocked until plan approved | `PolicyGateway`, `_ready_to_build` |
| Verdict gates | Repair loop on fail | `_gate`, `_repair` |
| Completion | Never from model prose | `acceptance.evaluate` |

---

## Control roles (no `agents/` folder)

These are implemented in code, not LLM prompts.

### Intake & sizing

| Phase | Actor | Reasoning | Output |
|-------|--------|-----------|--------|
| `INTAKE` | Orchestrator | Hash request; start audit trail | Transition to `SIZE` |
| `SIZE` | `sizer` role + router | Classify effort; pick workflow key (`S`, `M`, `L`, …) | `sizing` artifact → profile |

**Failure modes:** Budget daily cap (`BudgetManager.check_daily`); invalid schema → repair or halt.

### Ready to build & acceptance

| Phase | Actor | Reasoning | Output |
|-------|--------|-----------|--------|
| `READY_TO_BUILD` | Orchestrator | Pin `plan_hash`; require human approval in live mode | Wait or proceed |
| `ACCEPTANCE` | `acceptance.evaluate` | Deterministic checklist | `pass` / `fail` / `simulated` |
| `COMPLETE` | Orchestrator | Optional evolution hook | Status `COMPLETE` or `SIMULATED` |

**Design rationale:** Separates *intent to write* from *evidence that work matched plan* — analogous to human code review gates, implemented without trusting LLM self-report.

---

## Daily Coder LLM roles

### `master` (phase `DECIDE`)

| | |
|--|--|
| **Exists because** | Single design authority; prevents silent scope creep from research or brainstorm outputs. |
| **Inputs** | Packet with research/brainstorm digests, sizing, `ORIGINAL_REQUEST`. |
| **Output schema** | `decision.schema.json` — acceptance criteria, approach, constraints. |
| **Reasoning** | Freeze scope and invariants; tag epistemic status on claims (VERIFIED, INFERENCE, …). |
| **Failure modes** | Missing criteria → acceptance gate failure later; schema invalid → invoke retry/repair. |

Prompt: [`agents/master/prompt.md`](../../agents/coding/daily-coder-ecosystem/agents/master/prompt.md).

### `researcher` (phase `RESEARCH`)

| | |
|--|--|
| **Exists because** | M/L/XL work needs repo-grounded evidence before planning. |
| **Inputs** | One **angle** per lane (`RESEARCH_ANGLES` in orchestrator); optional `repo_map` from read-only listing in live mode. |
| **Output** | `research_card.schema.json` per lane; aggregated in `research` artifact. |
| **Parallelism** | Thread pool batches up to `max_parallel_agents`; early stop via `context.should_stop_research`. |
| **Failure modes** | Tool denial; empty cards prolong lanes until budget/angles exhausted. |

Prompt: [`agents/researcher/prompt.md`](../../agents/coding/daily-coder-ecosystem/agents/researcher/prompt.md).

**Note:** This is **codebase research**, not open-web deep research (that is Research Forge’s domain).

### `brainstormer` (phase `BRAINSTORM`)

| | |
|--|--|
| **Exists because** | L/XL and divergent requests benefit from structured alternatives before `DECIDE`. |
| **Inputs** | Packet + angle (`BRAINSTORM_ANGLES`). |
| **Lane count** | 1–3 based on keywords and profile budget. |
| **Output** | Options list; master still decides. |

Prompt: [`agents/brainstormer/prompt.md`](../../agents/coding/daily-coder-ecosystem/agents/brainstormer/prompt.md).

### `test_designer` (phase `TEST_DESIGN`)

| | |
|--|--|
| **Exists because** | Acceptance requires test evidence for non-trivial changes when configured. |
| **Output** | Whether tests are required, strategy, commands — feeds acceptance checks. |

### `planner` (phase `PLAN`)

| | |
|--|--|
| **Exists because** | Converts decision into scoped, reviewable change units and file allowlist. |
| **Skills** | Loads only plan-named skills via `SkillLibrary.load` (bounded bodies). |
| **Gate** | Unresolved questions → repair to `PLAN` or `DECIDE`. |

### `plan_reviewer` (phase `PLAN_REVIEW`)

| | |
|--|--|
| **Exists because** | Independent check before human approval and any writes. |
| **Gate** | `verdict != pass` → `_repair` targeting `PLAN`. |

### `implementer` (phase `IMPLEMENT`)

| | |
|--|--|
| **Exists because** | Executes plan slices with tool use under CAS/content-hash rules. |
| **Chunking** | L/XL profiles split `change_units` per `decomposition` config. |
| **Gate** | `blocked` stops chunk chain; test/code review may send back to implement. |

### `test_author` / `test_executor` (phases `TEST_AUTHOR`, `TEST_EXECUTE`)

| | |
|--|--|
| **Exists because** | Separate authoring vs execution; long tests become **jobs** (`JobManager`) without holding a provider slot. |
| **Gate** | Failed tests → repair to `IMPLEMENT`. |

### `code_reviewer` (phase `CODE_REVIEW`)

| | |
|--|--|
| **Exists because** | Independent review of diff/evidence before docs/alignment. |
| **Live extra** | `repository.diff` when available. |

### `documenter` (phase `DOCUMENT`)

| | |
|--|--|
| **Exists because** | User-facing/docs updates tracked as artifacts (skipped on `S_TRIVIAL`). |

### `alignment_checker` (phase `ALIGNMENT`)

| | |
|--|--|
| **Exists because** | Verifies work still matches decision criteria and plan intent. |
| **Required** | When `acceptance.require_alignment_pass` is true (default). |

### `failure_diagnostician` (phase `DIAGNOSE`)

| | |
|--|--|
| **Exists because** | Structured diagnosis when repair cycles exhaust or escalation triggers. |
| **Invoked from** | `_repair` / frontier escalation paths in orchestrator. |

### `frontier_advisor` (escalation)

| | |
|--|--|
| **Exists because** | Authorize higher model tier with compressed brief (`escalation.py`). |
| **Not a phase** | Invoked when policy allows frontier spend. |

### `skill_curator` (post-run evolution)

| | |
|--|--|
| **Exists because** | Propose skill/prompt patches from verified runs — **never auto-promotes** (`EvolutionManager`, human promotion required). |
| **Trigger** | `_post_run_evolution` every N complete live runs when enabled. |

---

## Research Forge logical agents

These are primarily **Python classes** with deterministic mock behavior unless live adapters are approved.

### Wave 1 — sequential research DAG

| Step | Component | Role |
|------|-----------|------|
| clarify | `IntakeClarifier` | Scope and ambiguities |
| charter | `CharterPlanner` | Research questions, depth |
| search/read/extract | adapters + `EvidenceExtractor` | Source records, evidence cards |
| verify | `CitationVerifier` | Citation integrity |
| compose | `ReportComposer` | Structured report |

Orchestrator: [`wave1/orchestrator.py`](../../agents/research/research-forge/src/research_forge/wave1/orchestrator.py), phases tuple `PHASES`.

### Wave 2 — fan-out lanes

| Component | Role |
|-----------|------|
| `LandscapeMapper` | Non-overlapping lanes from charter |
| `SourceScout` | Mock/search-backed discovery |
| `SourceCurator` | Weighted selection (`config/scoring.yaml`) |
| `SaturationEngine` | Stop when marginal gain low |

Orchestrator: [`FanOutOrchestrator`](../../agents/research/research-forge/src/research_forge/wave2/fanout.py).

### Wave 3 — scrutiny

| Component | Role |
|-----------|------|
| `MethodsReviewer` | Methods flags per source |
| `ContradictionMapper` | Evidence matrix + gaps |
| `AdversarialSkeptic` | Objection rounds; **cannot search** |
| `FalsificationDesigner` | Tests that could disprove claims |
| `ResearchAuditor` | Sampled audit; may block acceptance |

Orchestrator: [`ScrutinyOrchestrator`](../../agents/research/research-forge/src/research_forge/wave3/orchestrator.py).

### Wave 4 — ideation portfolio

| Component | Role |
|-----------|------|
| `IndependentIdeator` | Parallel candidate ideas |
| `FabricationChecker` | Blocks promotion if unsupported |
| `PortfolioFusion` | Merge/de-dupe |
| `LineageGraph` | Idea ancestry |
| `PromotionRules` | Evidence-indexed promotion |

Orchestrator: [`IdeationOrchestrator`](../../agents/research/research-forge/src/research_forge/wave4/orchestrator.py).

### Wave 5 — Director

| Component | Role |
|-----------|------|
| `DirectorPacketBuilder` | Token-bounded packet with selection log |
| `PrincipalResearchDirector` | Policy-bound synthesis role |
| `HighStakesClassifier` / `ChallengeAuthorizer` | Challenge path for high-stakes outputs |
| `DirectorOutputValidator` | Schema and fidelity checks |

Orchestrator: [`DirectorOrchestrator`](../../agents/research/research-forge/src/research_forge/wave5/orchestrator.py).

Handoff strata (raw vs packet vs brief): [`wave5/handoff.py`](../../agents/research/research-forge/src/research_forge/wave5/handoff.py) — evaluation taxonomy, not Daily Coder dispatch.

### Wave 6 — adapters & routing

Plugin SDK ([`wave6/sdk/`](../../agents/research/research-forge/src/research_forge/wave6/sdk/)), learned routing experiments, proposal workflow — maintenance and extension layer.

### Local experiment agents

| Agent | Class | Purpose |
|-------|-------|---------|
| Creator | `ExperimentCreator` | Proposal with `token_budget: 0` |
| Pre-Reviewer | `ExperimentPreReviewer` | Deterministic gate |
| Runner | `ExperimentRunner` | Typed kinds only |
| Post-Reviewer | `ExperimentPostReviewer` | Interpret results as `LOCAL_OBSERVATION` |

See [`experiments/`](../../agents/research/research-forge/src/research_forge/experiments/) and [EXPERIMENTS.md](../../agents/research/research-forge/docs/EXPERIMENTS.md).

---

## External skill: deep-research (Cursor)

Not shipped inside this repo, but **conceptually paired** with Research Forge:

- Six independent scout **lanes** map to Wave 2’s fan-out + deep-research skill §2.
- Claim-level integration maps to evidence matrices and Wave 3 scrutiny.
- **Research Messenger** skill produces 17 role handoffs — analogous to Daily Coder’s multi-role pipeline but **read-only** and assembly-only.

References: `~/.cursor/skills/deep-research/SKILL.md`, `~/.cursor/skills/research-messenger/SKILL.md`.

---

## Agent Dashboard

Not an LLM agent — adapters surface backend health and runs. Registry loads configured agents from JSON; see [`agent_dashboard/registry.py`](../gui/agent_dashboard/registry.py).

---

## Cross-links

- [Architecture overview](../architecture/architecture-overview.md)
- [Hooks, skills, and enforcement](../ide-agents/hooks-and-skills.md)
- [Research Forge deep dive](./research-forge-deep-dive.md)
