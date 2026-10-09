# Slingshot Orchestration Audit — 2026-10

**Question.** What must improve in the AgentNexus orchestration, which skills/subagents are missing, and where should we stop building and adopt someone else's solution?

**Evidence base.** Repo internals (`AGENTS.md`, `docs/orchestration/system-map.md`, `docs/research/GAP_AND_COST_PLAN.md`, `docs/research/sources/priority_additions_by_plan_gap.md`, `docs/research/agent_orchestration_research_brief.md`), plus a 2026 framework sweep (LangGraph 1.x, CrewAI 1.14, Microsoft Agent Framework 1.0 GA, OpenAI Agents SDK GA, Google ADK 2.0, MCP under Linux Foundation stewardship, A2A 150+ adopters).

**Caveat.** Scholar plugin quota was exhausted this cycle; academic grounding relies on the repo's own verified research library (28+ sources with fetch-status marks), which is unusually strong. Re-run a scholar pass next billing cycle to close the loop.

---

## 1. Verdict in one paragraph

Your design instincts are right: bounded master + compressed delegation packets + external ledger + policy gates + human-gated skills is exactly where the 2026 literature landed. The orchestration's *conceptual architecture* needs no rescue. The gap is **plumbing and proof**: you are hand-rolling four subsystems (durable execution, tool connectivity, inter-agent transport, observability) that the industry has now standardized, and you have no measurement loop that would tell you whether your fan-out beats a single strong agent. Adopt the standards, keep the judgment layer, and build the eval harness before adding a single new agent.

---

## 2. Where to admit defeat (adopt, don't build)

| # | Subsystem | Adopt | Why building loses |
|---|---|---|---|
| D1 | **Durable execution / checkpointing** | LangGraph checkpointer or Microsoft Agent Framework Workflows (both 1.0 GA, MIT) | You already re-implemented pause/resume twice (SQLite in daily-coder, JSON `resume_token` in research-forge) with divergent semantics. Time-travel debugging, node caching, and interrupt/resume are solved problems; your versions will never catch up. |
| D2 | **Tool surface** | **MCP** servers behind your PolicyGateway | MCP moved to Linux Foundation stewardship with Anthropic/OpenAI/Google/Microsoft/AWS backing. Hand-rolled adapters per vendor are dead weight. Keep PolicyGateway as the *gate in front of* MCP — that gate is your moat, the transport is not. |
| D3 | **Cross-ecosystem delegation (your R8)** | **A2A protocol** (agent cards) for daily-coder ↔ research-forge | "MCP for tools, A2A for agents" is now the industry shorthand with 150+ adopting orgs. Bespoke `delegate_to_researcher` tools will strand you; A2A cards also make your agents callable *by* other people's orchestrators. |
| D4 | **Observability** | OpenTelemetry spans + an off-the-shelf viewer (LangSmith, Arize Phoenix, or OTel+Grafana) | Your ledger is a great source of truth but has no trace UI. PHMForge-style stage metrics (retrieval / invocation / sequencing / execution) require span-level data you currently don't emit. |
| D5 | **Provider transport** | One OpenAI-compatible path (OpenRouter) or LiteLLM; delete the other vendor adapters | GAP_AND_COST_PLAN already caps this at "no additional vendors." Go further: five hand-maintained adapters is where bugs like R2's three orchestrator crashes breed. |
| D6 | **Multi-agent debate / group chat** | Don't build, don't adopt | Collaboration Gap + problem-drift evidence (already in your library) says master-mediated compressed handoffs win. CrewAI/AutoGen-style peer chat costs ~20 LLM calls for a 4-agent/5-round debate and drifts. Your instinct to skip it is confirmed. |
| D7 | **Eval harness** | Existing agent-eval tooling (pass-all-k, SWE-bench-style tasks, Promptfoo/DeepEval for regression) | "One Success Isn't Reliability" and "There Is No Neutral Harness" (both in your library) require repeated-trial, pinned-config evals. Bespoke graders will be gamed by your own skill curator. |

**What to keep building (your genuine differentiation):** PolicyGateway + budget enclosures, claim/evidence ledger with claim-audit tags, the sizing gate, context slicer, and the human-gated skill lifecycle. Nobody ships that combination off the shelf; the frameworks assume you'll bring it.

---

## 3. Missing subagents (gaps in the current 41-role canonical roster)

Ordered by expected impact. Names reference your canonical folder convention.

1. **`single-agent-baseline-runner`** (Tier A, Gap G1). Every fanned-out run must also (or first) run a strong single-agent baseline; if the fan-out doesn't beat it on cost-per-verified-pass, the route collapses. Nothing in the roster currently *measures* whether orchestration helped. This is the slingshot's scoring judge.
2. **`silent-failure-detector`** (Gap G2/G5). You have `failure-diagnostician` for *hard* gate failures, but nothing scans trajectories for anomalies before master synthesis (arxiv 2511.04032 in your own library). Runs that "COMPLETE" with rotted intermediate state are your most expensive failure mode.
3. **`concurrency-controller`** (deterministic, not LLM). Worktree isolation per implementer + write-intent conflict detection (2608.18092). Two implementers editing overlapping files currently rely on luck and compare-and-swap after the fact.
4. **`memory-consolidator`** (gated, post-run only). You have durable stores but no consolidation pass. Your library is explicit: continuous LLM rewrite of memory degrades; gated consolidation with rollback is the only safe form. Pair with a **deprecation budget** — skills accrete (only 4.3% of real-world skill edits consolidate anything).
5. **`skill-provenance-auditor`** (Gap G4). SkillScope-style least-privilege checks, quarantine, clean-session carryover tests before any skill enters the hot path. EvoMal/Practice-Makes-Unsafe make this a security role, not a hygiene role.
6. **`router-learner`** (deferred, Gap G3). Log `features → model → cost → verifier outcome` now (schema-only change); learn routing only after the safe baseline exists. Build the *logging* in Wave 2, the *learning* never-before-Wave-3.

Roles you have that SOTA says to **watch, not expand**: `brainstormer` (fabrication check exists, good — keep it one pass), research lane fan-out (keep N from profile; evidence is +81% to −70% by task).

---

## 4. Missing skills (the `agents/shared/skills/` library)

Current: 5 shared (claim-auditor, datasheet-extractor, structured-data-evaluator, visualization-specifier, writing-improver) + 5 personal. Conspicuously absent for a *coding/research orchestrator*:

| Skill | Type | Justification |
|---|---|---|
| `verification-commands` | shared | GitHub's 2,500-repo study: runnable commands with full flags early in context is the highest-leverage instruction content. Each specialist should get `pytest -v`, `npm run build`-style anchors, not prose. |
| `rollback-and-revert` | shared | Cursor's "revert and refine the plan, don't argue in the thread" as a procedural skill; pairs with `change_plan.rollback` field you already specified in Wave 2.3. |
| `handoff-packet-composer` | shared | The Handoff Tax paper: escalation with a fresh compressed decision brief, never the weak trajectory. This is your slingshot mechanism — it should be a skill with a schema, not a prompt habit. |
| `eval-task-author` | shared | Writes held-out, machine-checkable tasks with pass-all-k acceptance; feeds D7. |
| `mcp-tool-discovery` | shared | grep/BM25-first, vector-RAG-as-escalation tool discovery (CONTEXTBENCH / Is Grep All You Need). Tool discovery failure alone costs −21.3 pp (PHMForge). |
| `budget-spend-report` | shared | Renders `cost_per_verified_pass` from the ledger; makes the cost doctrine legible after every run. |

All six follow your evidence-backed rules: procedural checklists, subtask-grained, human-merged, never auto-promoted.

---

## 5. The three moves that matter most

1. **Build the measurement loop before any new agent** (D4 + D7 + `single-agent-baseline-runner`). Right now you cannot prove the slingshot outperforms one strong model on the same task — and the scaling-science paper says extra agents *hurt* when the single agent is already strong. Instrument first.
2. **Swap bespoke transport for MCP + A2A** (D2 + D3). This converts R8 from a maintenance liability into a standard interface, and makes PolicyGateway the thing you *add* to the standard instead of the thing you *instead of* the standard.
3. **Consolidate the runtimes onto one durable-execution core** (D1). Two divergent pause/resume implementations is how idempotency bugs (your R2 Bug A) happen. One checkpointer, both ecosystems.

---

## 6. Suggested sequencing

- **Now:** D5 (adapter consolidation), D4 (OTel spans in PolicyGateway — cheapest observability win), skill `verification-commands`, logging schema for `router-learner`.
- **Next:** D1 (pick LangGraph checkpointer or MAF Workflows; pilot on research-forge whose state is simpler), D2 (MCP behind the gateway), `silent-failure-detector`.
- **Then:** D3 (A2A cards for both ecosystems → completes R8 properly), D7 harness + `single-agent-baseline-runner`, `concurrency-controller`.
- **Defer (matches your Wave 3):** router learning, skill self-evolution beyond proposal+human-merge, any group-chat topology.

**Definition of done for this round:** you can answer, per run, "fan-out beat baseline by X at $Y per verified pass, with zero unauthorized writes" — from the ledger, without reading transcripts.
