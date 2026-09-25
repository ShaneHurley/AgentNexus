# Daily Coder Ecosystem

**A model-agnostic, artifact-driven orchestration runtime for a token-frugal AI coding assistant.**

This is a from-scratch orchestration system I designed and built: a small army of specialist AI agents (researcher, planner, implementer, test author, code reviewer, alignment checker, and more) coordinated by one accountable "master" decision-maker, all running on top of a transactional SQLite state machine with deterministic security enforcement, real cost accounting, human-in-the-loop approvals, and a live dashboard. It works with mock data for safe experimentation, or with real OpenAI, Anthropic, Gemini, OpenRouter, local (Ollama/vLLM-style), command-line, or HTTP-bridged models for real repository work.

I built this because most "agent frameworks" either trust the model too much (letting it call arbitrary tools, write anywhere, and burn unlimited tokens) or trust it too little (one giant prompt, no memory, no adaptivity). This project instead treats the *orchestration layer itself* as the product: the model proposes, the runtime disposes. Every tool call, dollar spent, file write, and repair cycle is enforced and logged by code, not by hoping the model behaves.

> **Cross-package docs:** See the workspace hub at [`../docs/README.md`](../docs/README.md) for code-accurate architecture, agent cognition, hooks/skills, and Research Forge integration.

> If you're reviewing this for a resume, portfolio, or interview: this repo demonstrates distributed-systems thinking (state machines, idempotency, atomic transactions, concurrency control), applied security engineering (deny-by-default policy gateways, SSRF protection, secret management), practical LLM-systems engineering (token budgeting, context compaction, multi-provider abstraction, tool-calling protocols), and full-stack delivery (CLI, REST API, dashboard, test suite, benchmarking harness). Core orchestration paths are implemented and tested; **mock-by-default** runs and portfolio-level gaps (e.g. GitHub PR create/push) are documented in the [workspace docs hub](../docs/README.md#supported-today-truth-table) — not hidden.

## Table of contents

- [Why this exists](#why-this-exists)
- [What it actually does](#what-it-actually-does)
- [Architecture at a glance](#architecture-at-a-glance)
- [The agent roster](#the-agent-roster)
- [The workflow, phase by phase](#the-workflow-phase-by-phase)
- [Security model](#security-model)
- [Cost, budget, and token economy](#cost-budget-and-token-economy)
- [Providers: bring your own model](#providers-bring-your-own-model)
- [Durable background jobs](#durable-background-jobs)
- [REST API and dashboard](#rest-api-and-dashboard)
- [Controlled self-improvement](#controlled-self-improvement)
- [Benchmarking](#benchmarking)
- [Quick start](#quick-start)
- [Full CLI reference](#full-cli-reference)
- [Repository layout](#repository-layout)
- [Testing and quality](#testing-and-quality)
- [Design principles](#design-principles)
- [Honest limitations](#honest-limitations)
- [What I'd build next](#what-id-build-next)
- [Technical reference](docs/TECHNICAL.md)

## Why this exists

Daily coding assistants that fan out to many LLM calls are easy to build and easy to make *expensive and unsafe*. The interesting engineering problem isn't "can an LLM write code" — it's:

- How do you let cheap, narrow agents do the grunt work while one strong reasoner keeps the whole plan coherent?
- How do you stop a model from writing outside the files it was told to touch, running an arbitrary shell command, or fetching an internal URL?
- How do you know, in dollars and tokens, exactly what a run cost — before, during, and after it happened?
- How do you let a human approve a plan once and then trust the system to execute it, without babysitting every step?
- How do you run a test suite that takes two hours without burning tokens or blocking the whole pipeline for two hours?
- How do you let the system evolve its own skills and prompts over time without it being able to quietly grant itself more power?

This project is my answer to each of those questions, built as working code rather than a whitepaper.

## What it actually does

Given a natural-language request (`"Add input validation to the signup form"`), the runtime:

1. **Sizes the task** deterministically (regex/heuristic first, an LLM sizer only when genuinely ambiguous) into a `TRIVIAL / CONTAINED / CROSS_CUTTING` route mapped to `S / M / L / XL` profiles, each with its own token, call, and fan-out budget.
2. **Routes to a workflow** — trivial fixes use `S_TRIVIAL` (skip research, brainstorm, test_author, and documenter; keep alignment for acceptance); larger tasks get bounded, parallel, read-only research lanes (each investigating a distinct angle: implementation sites, callers, existing tests, docs/config, edge cases, adjacent modules). Research batches may stop early when unknowns are already empty.
3. **Lets one master agent decide** — the master is the *only* role allowed to freeze scope, resolve contradictions, and choose an approach. Everyone else informs or challenges; nobody else can silently expand the task.
4. **Plans exact, atomic changes** — the planner emits a `change_plan` with typed change units (file, operation, exact region, verification command) and *zero* unresolved design questions. If anything is ambiguous, the plan is rejected before a single line of code is touched.
5. **Adversarially reviews the plan** — an independent `plan_reviewer` actively tries to disprove the plan's completeness and executability before any write happens.
6. **Pauses for human approval** — real repository writes do not happen until a human approves the reviewed plan hash, via CLI, REST API, or the dashboard. This is not optional in live mode.
7. **Implements in bounded chunks** — for larger plans, the implementer works through small, purpose-labeled chunks (2 change units at a time by default) rather than one giant open-ended edit, so drift and runaway scope are caught early.
8. **Writes tests, runs them, reviews the diff** — an independent test author, a separate test executor, and an adversarial code reviewer all inspect the actual diff and actual command output — never the author's self-report.
9. **Checks alignment** — a dedicated role confirms the work still serves the original request (kept even on `S_TRIVIAL` because acceptance requires it; a deterministic drift watchdog also catches runaway tool loops without an extra model call).
10. **Accepts or repairs** — a code-owned acceptance gate checks every recorded artifact (plan approval, test evidence, code review verdict, alignment verdict, scope) before a run is ever marked complete. On failure, a bounded repair loop (diagnose → on the last allowed cycle optionally escalate once to a frontier model → retry → stop when exhausted) kicks in — never an infinite retry storm.

Every one of those steps is backed by tests, schemas, and SQLite-recorded evidence — not vibes.

## Architecture at a glance

```
                         ┌───────────────────────────────┐
                         │   CLI  /  REST API + Dashboard │
                         └───────────────┬───────────────┘
                                         │
                              ┌──────────▼──────────┐
                              │     Orchestrator      │  ← the only place phases advance
                              │  (workflow.py, router) │
                              └──────────┬──────────┘
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
             ┌──────▼──────┐     ┌───────▼───────┐     ┌──────▼──────┐
             │ PolicyGateway │     │  BudgetManager │     │ SkillLibrary │
             │ (deterministic│     │ (reserve/settle│     │ (opt-in,     │
             │  enforcement) │     │  per call)     │     │  bounded)    │
             └──────┬──────┘     └───────┬───────┘     └─────────────┘
                    │                    │
             ┌──────▼──────┐     ┌───────▼───────┐
             │  ToolBroker   │     │  Provider(s)   │  ← OpenAI / Anthropic / Gemini /
             │ (deny-by-     │     │  registry      │    OpenRouter / local / command / HTTP
             │  default ACLs)│     └───────────────┘
             └─────────────┘
                    │
             ┌──────▼──────────────────────────────┐
             │      SQLite StateStore (authority)    │
             │ runs · events · artifacts · invocations│
             │ tool_calls · approvals · jobs · spend  │
             │ candidates · evaluations               │
             └──────────────────────────────────────┘
```

**The one hard rule underneath all of it:** SQLite is the *only* authoritative state. JSON artifacts are immutable evidence, never a second source of truth. Every phase transition, tool call, model invocation, approval decision, and dollar spent is written to SQLite inside an atomic transaction with an idempotency key, so a crash mid-run can always be safely resumed from the last committed state — never replayed, never duplicated.

## The agent roster

Every agent lives in its own folder (`agents/<role>/`) with three files:

| File | Purpose |
|---|---|
| `agent.json` | Model tier, tool allowlist, output schema, max output tokens, per-role tool-turn cap |
| `model.json` | Model reference and fallback policy |
| `prompt.md` | The role's full instruction set, written in a consistent control-vocabulary style (`OBSERVE / REFLECT / ACT / VALIDATE / STOP`) |

| Role | Job | Tier | Notes |
|---|---|---|---|
| `sizer` | Classify task size when the heuristic is ambiguous | lowest | Deterministic routing is tried first; this only fires on genuine ambiguity |
| `researcher` | Investigate one bounded angle, read-only | lowest | Runs in parallel lanes (1–6 depending on profile), each on a distinct angle |
| `brainstormer` | Propose out-of-the-box alternatives | mid | 1 lane by default; up to 3 parallel lanes only when the request explicitly asks for alternatives/comparisons |
| `master` | The **sole** decision authority — freezes intent, scope, invariants, approach | high | Everyone else advises; only this role can change scope |
| `test_designer` | Define observable acceptance criteria *before* implementation | mid | |
| `planner` | Produce atomic, exact-change tasks with zero unresolved questions | mid | Blocked from proceeding if any ambiguity remains |
| `plan_reviewer` | Adversarially try to disprove the plan | mid | Independent from the planner; reads the plan cold |
| `implementer` | Mechanically apply the frozen plan, one bounded chunk at a time | lowest | Cannot deviate from the file allowlist or invent scope |
| `test_author` | Write meaningful tests mapped to acceptance criteria, with negative controls | mid | Cannot be the same role as the test executor |
| `test_executor` | Run tests and interpret results skeptically | lowest→mid | Long suites run as durable background jobs — see below |
| `code_reviewer` | Review the actual diff adversarially, before hearing the author's explanation | high | Reads the diff first, always |
| `documenter` | Document only reviewed, observed changes | lowest | |
| `alignment_checker` | Confirm the work still serves the original request | lowest | Runs on all workflows including `S_TRIVIAL` (acceptance requires it); extra mid-pipeline boundaries on M/L/XL |
| `failure_diagnostician` | Attribute a gate failure to a single root cause from recorded evidence | mid | Feeds the bounded repair loop |
| `frontier_advisor` | One expensive, tightly-rationed model call for genuinely hard tie-breaks | frontier | At most once per run; last-chance repair cycle only (live + authorized) |
| `skill_curator` | Propose (never merge) reusable procedural skills after a run | lowest | Human approval is mandatory before anything is promoted |

## The workflow, phase by phase

```
INTAKE → SIZE → [RESEARCH] → [BRAINSTORM] → DECIDE → [TEST_DESIGN] → PLAN
   → PLAN_REVIEW → READY_TO_BUILD (human approval gate) → IMPLEMENT
   → TEST_AUTHOR → TEST_EXECUTE → CODE_REVIEW → DOCUMENT → ALIGNMENT
   → ACCEPTANCE → COMPLETE
```

Bracketed phases are conditional:

- **S** skips research and brainstorming entirely.
- **S_TRIVIAL** (S + trivial keywords such as typo/rename/comment) also skips `TEST_AUTHOR` and `DOCUMENT`, but keeps `ALIGNMENT`.
- **M (contained)** adds bounded research, still no brainstorming.
- **L / XL (cross-cutting / high-risk)** add wider research fan-out, brainstorming, and more boundary-alignment checkpoints.

Every phase transition is a real SQLite transaction (`BEGIN IMMEDIATE`), validated against an explicit state machine (`state_machine.py`) that defines exactly which phase can follow which — including recovery paths for `WAITING_HUMAN`, `WAITING_JOB`, `ESCALATED`, and `DIAGNOSE`, plus the `S_TRIVIAL` skip edges. Run *status* (`ACTIVE / WAITING_HUMAN / WAITING_JOB / BLOCKED / FAILED / COMPLETE / SIMULATED / CANCELLED`) is tracked independently of workflow *phase*, so the system always knows both "where" a run is and "why it's paused."

### Bounded repair, not infinite retries

If a gate fails (plan review, tests, code review, alignment), the orchestrator doesn't just crash or loop forever:

1. A `failure_diagnostician` attributes the failure to one root cause using only recorded evidence.
2. On the **last allowed repair cycle**, the system may make **one** authorized frontier call with a compressed decision brief so advice can feed the next retry (never the raw transcript).
3. The run re-enters the phase *before* the failing one, so the failing artifact is regenerated, not patched blindly.
4. When cycles are exhausted, the run halts **without** another frontier call.

### Task decomposition and the drift watchdog

For larger plans, the implementer doesn't get one giant open-ended task — it works through **bounded chunks** (2 change units at a time by default, configurable, capped at a maximum chunk count) with a clear purpose statement per chunk. A deterministic drift watchdog also runs *inside* every agent invocation, with zero extra model calls:

- After 10 minutes of active work on a single invocation, it injects a plain-text reminder of the task anchor and current subgoal — no separate LLM round-trip.
- If an agent repeats the *exact same* tool call more than twice without progress, the invocation is stopped rather than left to loop.

## Security model

Every model is treated as **untrusted**. Prompts communicate intent; only runtime code enforces capability.

- **`ToolBroker`** is deny-by-default: a role can only call a tool if it's explicitly in that role's allowlist in `config/tools.json`. There is no path from "the prompt asked for it" to "the tool ran."
- **`PolicyGateway`** wraps every role-originated tool call. It checks authorization, checks path policy, checks that repository writes have an *approved plan hash* on file, executes through the broker, redacts secrets from output, and records the outcome (allow / deny / blocked / error) as an immutable audit row — every single time, no exceptions.
- **Path jailing**: all filesystem paths are resolved (symlinks included) and checked against the repository root and a deny-glob list (`.git/**`, `**/.env`, `**/*secret*`, private keys, etc.) before any read or write.
- **Compare-and-swap writes**: overwriting an existing file requires the caller to supply the file's current SHA-256. If the file changed since it was last read, the write is rejected — this stops a stale model turn from silently clobbering a concurrent edit.
- **Command allowlisting**: only a fixed set of executable *names* (`python`, `pytest`, `git`, `npm`, etc.) can run, matched by resolved basename — not by trusting a path the model supplied.
- **SSRF-safe web retrieval**: URL fetches resolve DNS, reject private/loopback/link-local/reserved/multicast addresses, re-validate on every redirect hop, detect redirect cycles, verify the actually-connected peer (not just the DNS answer, which blocks DNS-rebinding attacks), cap response size, and only accept text/JSON content types.
- **Human approval before writes**: `READY_TO_BUILD` is a real gate. In live mode, the run pauses in `WAITING_HUMAN` until a human approves the exact reviewed plan hash — via `daily-coder approve`, the REST API, or the dashboard. Nothing is written to disk before that.
- **Secrets never touch SQLite or the API**: provider keys live in the OS keyring when available; only a backend name and a fingerprint are ever stored or returned. If no keyring exists, the system fails closed rather than silently writing plaintext.
- **Deterministic acceptance gate**: a run can never be marked complete because a model *said* it was done. `acceptance.py` independently checks the plan was approved, the diff stayed in scope, tests actually ran and passed, code review and alignment verdicts passed, and the repository revision was pinned — using only recorded SQLite/artifact evidence.

## Cost, budget, and token economy

Token spend is a first-class constraint here, not an afterthought.

- **Atomic reservation before every call**: `BudgetManager.reserve()` is called *before* any provider invocation — including every parallel research lane — so parallel fan-out can never burst past a profile's cap. Reservations are released and settled against actual provider-reported usage afterward.
- **Warn / checkpoint / hard-stop thresholds** (70% / 80% / 90% of budget) plus a reserved safety margin.
- **Daily spend ceilings** in tokens and USD (`config/default.json` → `limits`), enforced before a run is even allowed to start.
- **Real cost ledger**: every invocation records input/output tokens, estimated USD (from `config/pricing.json`, per model), latency, and status in SQLite — queryable via `daily-coder spend`, the REST `/api/metrics` endpoint, or the dashboard.
- **Bounded, deterministic tool-call context**: rather than resending an ever-growing tool-call history to a stateless provider on every turn, older tool results are compacted into evidence references (tool name, arguments, and a content hash) while the most recent results stay intact in full — this keeps multi-turn tool use from growing quadratically in tokens while still preserving enough context for the model to reason about what it already tried.
- **Cached, compact provider payloads**: role manifests, prompts, and JSON schemas are loaded once and cached per orchestrator instance; JSON sent to providers uses compact separators instead of pretty-printing; a single shared truncation limit is used everywhere a tool result is serialized.
- **Frontier rationing**: the most expensive model tier is capped at one authorized call per run (by profile), triggered only by a named condition (`high_risk_irreversible`, `two_failed_repair_cycles`, etc.) and fed a hand-compressed decision brief — never a raw weak-model transcript.
- **Local benchmarking**: `daily-coder benchmark` runs a fixed set of representative S/M/L/XL scenarios against the mock provider and reports median/p90 calls, tokens, and latency — with an optional `--baseline` comparison, so a harness change can be measured for real before it's trusted.

## Providers: bring your own model

One `Invocation` contract, many backends:

| Provider | What it is |
|---|---|
| `mock` | Offline contract exerciser — safe default, makes no real calls, never certifies real completion (`SIMULATED` status) |
| `openai` | OpenAI Chat Completions-compatible |
| `anthropic` | Anthropic Messages API |
| `gemini` | Google Gemini `generateContent` |
| `openrouter` | Any OpenRouter-hosted model, same OpenAI-compatible wire format |
| `local` | Any OpenAI-compatible local server (Ollama, vLLM, LM Studio, etc.) |
| `command` | Launch any executable; it receives one JSON object on stdin and returns one on stdout — bridge to literally any agent framework |
| `http` | Same JSON contract over HTTP — for connecting LangGraph, CrewAI, custom services, or anything that can speak HTTP |

All hosted providers share a real multi-turn tool-calling protocol: the model can return either a final JSON answer or a list of tool calls; the runtime executes tool calls through the `PolicyGateway`, appends bounded results, and gives the model another turn — up to a per-role turn cap. Idempotency keys are attached to hosted requests so transient retries can't silently double-bill or double-invoke.

Live providers require an explicit `--live` flag (never accidental spend) and a configured credential via `daily-coder secrets set`.

## Durable background jobs

Test suites that take minutes or hours don't block the pipeline or burn tokens waiting.

- Verification commands estimated to run longer than a threshold (default 120s, based on real historical duration percentiles) are launched as **detached background processes**, wrapped by a small runner that persists the real exit code atomically even if the parent process restarts.
- The run transitions to `WAITING_JOB` status. **Zero model calls happen while a job is pending** — resuming a waiting run just checks job state and returns immediately if it's still running.
- Job completion/cancellation is a compare-and-swap SQL update (`WHERE state IN ('pending','running')`), so a race between "the job just finished" and "someone cancelled it" can never corrupt the recorded verdict.
- Duration history (p50/p90/max) is tracked per command fingerprint, per repo, per platform — so the scheduler gets smarter about what counts as "long" over time.

## REST API and shared dashboard

`daily-coder serve` starts an optional, dependency-free (standard-library `http.server`) authenticated **REST API** — entirely optional; the CLI works identically without it. The interactive UI now lives in the sibling **`gui/`** folder (Python package `agent_dashboard`) so Daily Coder, Research Forge, and future agents share one control surface.

- Bearer-token authentication by default, with a printed one-time token.
- Bounded thread-pool execution for run resumption (never one unbounded thread per request).
- Metrics are computed with grouped SQL aggregation (not one query per run per role) and cached briefly to avoid hammering SQLite under repeated polling.
- Endpoints for runs, events, artifacts, invocations, tool calls, approvals, jobs, cost reports, secrets (write/delete only — never read back), evolution candidates, and an `/api/openapi.json` descriptor.
- Point a browser at `http://127.0.0.1:8866/` after starting the GUI from `gui/` (see that folder's README). Set `DAILY_CODER_API_TOKEN` to the token printed by `daily-coder serve`.

Multi-host / distributed execution is deliberately **not** enabled — `storage.py` defines the `RunRepository` and `JobQueue` interfaces a future Postgres/queue backend would need, and the stub implementations fail closed rather than silently pretending to coordinate across machines. Single-host SQLite is the fully supported, production path today.

## Controlled self-improvement

The system can propose improvements to its own prompts, skills, routing, or harness — but it can never promote them without a human.

- One bounded candidate at a time (`kind`, `target`, proposed text, rationale, provenance) — never a batch of changes.
- Candidates can only target prompt/skill/router/workflow files, never security policy, budgets, or approval code.
- Every candidate must pass an **automated gate** — a frozen-task check and a held-out check must both hold (`daily-coder evaluate`) — before it becomes `eligible`.
- Only then can a human `promote` it, which snapshots a rollback copy first and writes atomically (write to a temp file, then rename).
- `rollback` restores the pre-promotion version at any time.
- Skills themselves are loaded strictly: a plan that names a skill which doesn't exist or isn't active **fails immediately**, rather than silently proceeding with a partial skill set.

## Benchmarking

```bash
daily-coder benchmark --output baseline.json
# ...make a change to the harness...
daily-coder benchmark --baseline baseline.json
```

Runs four representative scenarios (trivial / contained / cross-cutting / high-risk) through the mock provider, confirms they route to the expected S/M/L/XL profile, and reports median and p90 calls, tokens, and latency — plus a percent-change comparison against a saved baseline, including an explicit flag if a change caused a success regression. This is how every optimization in this codebase was actually measured, not guessed at.

## Honest boundary

No generic repository can automatically authenticate every model provider, MCP server, company tool, or external service. This package gives the ecosystem-level registry and enforcement boundary; real integrations must be registered in `config/tools.json` and implemented as adapters. Disabled tools fail closed. “Model-agnostic” means adapters obey the included conformance contract, not that all providers behave identically.

## Quick start

**Requirements:** Python 3.10+

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .

daily-coder doctor      # sanity-check the install and tree
daily-coder validate    # verify every agent, schema, and manifest is internally consistent
daily-coder run --request "Add input validation" --repo /path/to/repo --provider mock
```

Try it with a real model:

```bash
daily-coder secrets set OPENAI_API_KEY <your-key>
daily-coder run --request "Fix the null check in signup.py" --repo . --provider openai --live
daily-coder pending                       # see the plan waiting on you
daily-coder approve <run_id>
daily-coder resume <run_id> --provider openai --live
```

Bridge to any other agent runtime or framework:

```bash
daily-coder run --request "Fix the bug" --repo . \
  --provider command --provider-command 'your-agent-adapter'
```

The adapter receives one JSON object on stdin and returns one JSON object on stdout — see `docs/provider_adapter.md` for the exact contract.

Start the API (for the shared hub):

```bash
daily-coder serve --provider mock
# → prints the local URL and a bearer token
# then start gui (python start.py) and open http://127.0.0.1:8866/
```

## Full CLI reference

| Command | Purpose |
|---|---|
| `run --request TEXT --repo PATH --provider NAME [--live]` | Start a new run |
| `resume RUN_ID --provider NAME [--live]` | Continue a run from its last committed state |
| `status RUN_ID` | Full authoritative run record, pending approvals, jobs |
| `runs [--limit N]` | Recent runs |
| `validate` | Check every agent/schema/tool manifest is consistent |
| `doctor` | Environment, tree, and provider/secret sanity check |
| `approve RUN_ID [--reject] [--note TEXT]` | Approve or reject a plan waiting on you |
| `pending` | List everything awaiting human approval |
| `jobs [--run-id ID] [--active]` | List durable background jobs |
| `job JOB_ID [--cancel]` | Poll or cancel a specific job |
| `secrets list \| set NAME VALUE \| delete NAME` | Manage provider credentials (never prints values back) |
| `spend [--run-id ID]` | Daily or per-run token/USD cost report |
| `skills` | List available skill packages |
| `candidates [--state STATE]` | List self-improvement candidates |
| `evaluate CANDIDATE_ID --frozen-command CMD --holdout-command CMD` | Run the automated promotion gate |
| `promote CANDIDATE_ID [--actor NAME]` | Human-approve an eligible candidate |
| `rollback CANDIDATE_ID [--actor NAME]` | Revert a promoted candidate |
| `serve [--host] [--port] [--token]` | Start the REST API (UI is in sibling `gui/`) |
| `benchmark [--output FILE] [--baseline FILE] [--repeats N]` | Measure the harness without spending credits |

## Repository layout

```
agents/            One folder per role: agent.json, model.json, prompt.md
schemas/           JSON Schema contracts every role output is validated against
skills/            Reusable procedural SKILL.md packages (opt-in, plan-selected)
config/            default.json, budgets.json, models.json, policies.json, pricing.json, tools.json
daily_coder/        The runtime
  orchestrator.py    Phase loop, decomposition, repair, escalation, watchdog
  workflow.py        Versioned S/M/L/XL phase graphs
  state_store.py     SQLite authority: runs, events, artifacts, invocations, jobs, approvals
  state_machine.py   Explicit allowed-transition rules
  budget.py          Reservation, settlement, thresholds, daily caps
  context.py         Role-scoped packet slicing, bounded tool-history projection
  policy.py          PolicyGateway — the enforcement boundary
  tool_broker.py      Deny-by-default tools: filesystem, repository, shell, tests
  web.py             SSRF-safe URL fetch + Brave Search
  acceptance.py      The deterministic completion gate
  jobs.py            Durable background test execution
  evolution.py       Gated self-improvement lifecycle
  skills.py          Strict, plan-selected skill loading
  benchmark.py       Repeatable local harness benchmark
  server.py          REST API (stdlib http.server)
  dashboard/         Thin pointer page → shared gui/ hub
  providers/         mock, openai, anthropic, gemini, command, http bridge, registry
tests/              Unit + contract tests for every module above
docs/               Architecture, security, operations, provider/tool adapter contracts
examples/           Sample request and repository policy
```

## Testing and quality

```bash
python -m unittest discover -s tests -v
python -m daily_coder validate
python -m compileall -q daily_coder tests
```

The test suite covers: state machine transitions and idempotent replay, budget reservation and thresholds under concurrency, tool broker permission/path/write-scope enforcement, provider wire-format contracts (OpenAI/Anthropic/Gemini) against a local fake HTTP server, the acceptance gate's pass/fail logic, secret storage fail-closed behavior, job compare-and-swap correctness, schema validation, skill strictness, and full mock end-to-end runs. Every change in this repo's history was validated against this suite before being accepted — including multiple independent adversarial code-review passes that found and fixed real bugs (an approval-flow return-type bug, a repair loop that could skip the phase it was supposed to retry, path-parsing edge cases in the REST API, and more).

## Design principles

1. Fan-out is conditional, never ceremonial — a one-line fix does not pay for a full investigation.
2. Agents exchange validated, schema-checked packets — never raw transcripts.
3. Only the master freezes scope and resolves design contradictions.
4. The implementer can never receive a plan with unresolved questions.
5. Tool access is enforced by code, never trusted to a prompt.
6. Reviewers are read-only and inspect primary evidence (the diff) before hearing commentary.
7. A frontier model is used only after a logged, named escalation trigger — at most once per run.
8. A skill or harness candidate cannot self-promote; measured verification and human approval are both required.
9. Token quality is optimized as expected verified value per token — not minimum tokens for their own sake.
10. Every material claim in a role's output is tagged `VERIFIED / INFERENCE / ASSUMPTION / HYPOTHESIS / UNKNOWN` — nothing is silently invented.

## Honest limitations

- No generic system can pre-authenticate every model provider, MCP server, or enterprise tool. Real integrations are registered in `config/tools.json` and implemented as adapters; anything not configured fails closed rather than pretending to work.
- Multi-host/distributed execution is an intentionally inert extension point, not a supported deployment today.
- Enterprise search, email, calendar, and external-write adapters remain disabled until credentials, schemas, and policy are explicitly supplied.
- Mock runs are clearly marked `SIMULATED` and never certify real repository correctness — that distinction is enforced by the acceptance gate itself, not just documentation.

## What I'd build next

- Phase-level (not just run-level) token/time envelopes, so a single runaway research lane can't consume a whole profile's budget.
- Dynamic early-stopping for research fan-out once acceptance-relevant unknowns are resolved, instead of always running every configured lane.
- A Postgres-backed `RunRepository` implementation to light up the already-defined multi-host contract.
- Live-provider token/cost benchmarking (today's benchmark harness is mock-only, by design, so it never spends real money).
- Retention and archival policies for artifacts, logs, and completed simulated runs.

---

*Built solo as a deep dive into agent orchestration, LLM-systems engineering, and applied security — from the state machine up.*
