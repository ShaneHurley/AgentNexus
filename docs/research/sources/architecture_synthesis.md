# Cross-Source Architecture Synthesis

**Audience.** Next agent investigating/planning the daily-driver orchestration.
**Authority.** Design proposals only — not authorization to deploy or spend.
**Full executable contract.** [`../agent_orchestration_master_spec.md`](../agent_orchestration_master_spec.md) Part D.

---

## Executive decision (from corpus)

| Field | Value |
|---|---|
| Status | `PARTIAL` — original 26 processed; large secondary library exists; many items abstract-only |
| Best-supported shape | Bounded orchestrator around few specialists + external run ledger + deterministic policy gates + compact semantic tools + trajectory eval |
| Feasible now | Worker contracts, state/evidence ledger, policy gates, tool schemas, held-out harness — **before** framework choice or topology expansion |
| Main uncertainty | Target domain, permissions, safety tier, cost/latency budgets, baseline performance (blocking) |
| Strongest unfavorable finding | Plans, skills, retrieval, and extra agents can **reduce** performance when low-quality, irrelevant, overgrown, or weakly governed |

---

## Recommended control loop

1. **Intake / size** — Classify risk, reversibility, domain, predictability. Short-circuit trivia.
2. **Simplest adequate mode** — Deterministic workflow → router → bounded orchestrator–worker → autonomous loop only with strong environmental feedback.
3. **External plan + task DAG** — Dependencies, budgets, acceptance tests, approval checkpoints. Re-surface plan slice before major actions; allow evidence-triggered replanning.
4. **Dispatch specialists** — Typed, least-privilege contracts; only needed context and tools.
5. **Append-only run ledger** — Sources, tool results, decisions, failures, UNKNOWNs. Chat is a cache.
6. **Verify** — Deterministic checks when possible; independent review when judgment is unavoidable.
7. **Integrate** — By claim/evidence ID; preserve disagreement; adversarial review; at most one targeted correction wave.
8. **Hard stops** — Success, budget, iteration, blocker, or policy. Model never owns hard safety limits.

---

## Proposed logical components

| Component | Responsibility | Key control |
|---|---|---|
| Intake/router | Classify task, risk, mode | Deterministic risk/permission rules |
| Planner | Task DAG, contracts, checkpoints, tests | Plan-quality review; versioned plan |
| Orchestrator (master) | Schedule bounded work; own decisions | Concurrency, recursion, time, token, cost budgets |
| Specialists | One bounded outcome each | Least privilege; schema-valid outputs |
| Context manager | Smallest relevant state slice | Provenance, freshness, conflict, token budgets |
| Run ledger | Persist plans, evidence, outputs, decisions | Append-only events; stable IDs |
| Tool gateway | Semantic workflow tools | Allow-lists, approval, redaction, rate limits, idempotency |
| Verifier/evaluator | Outcomes + trajectory failure classes | Held-out tasks; deterministic checks; repeats |
| Skill registry | Procedural-family skills | Human ownership; commit gates; rollback; retrieval eval |
| Integrator/reviewer | Merge evidence; challenge claims | Independent review; contradiction preservation |
| Alignment checker | Drift vs user intent at phase gates | Cheap; pattern-match to task anchor |

---

## Context and state design

- **Separate durable state from prompt context.** Durable: approved plan, task status, evidence ledger, decision log, tool outputs, budgets, UNKNOWNs. Prompt: task-specific projection.
- **Plans are versioned artifacts** with assumptions, evidence, acceptance tests, revision reasons. Reminders improve compliance; **poor plans are worse than no plan**.
- **Raw observations ≠ summaries.** Retrieve originals by stable ID.
- **Skills = procedural guidance**, not fact store. One validated prior per family; instance detail at runtime; evaluate retrieval separately.
- **Provisional lessons ≠ validated rules.** Promote only after held-out/outcome review.

---

## Tool and worker design

- Few semantic workflow tools over dozens of thin wrappers; consolidate chains in deterministic code.
- Namespace by service/resource; natural IDs; concise/detailed modes; paginate/filter by default.
- Enough context for next decision — not raw dumps. Errors explain corrective action.
- Authorization, boundaries, secrets, approvals, recursion, resources in **host code**.
- Worker contract: objective, inputs, allowed tools, forbidden scope, output schema, completion evidence, failure/UNKNOWN behavior, acceptance criteria.

---

## Evaluation blueprint

- Baselines: single call → single agent → deterministic workflow → orchestrated system.
- Realistic multi-step held-out tasks; pass@1 and pass-all-k; preserve complete traces.
- Score: outcome, plan compliance, evidence completeness, tool selection/args, sequencing, discovery, verification, latency, tokens, cost, policy.
- Failure classes: planning, retrieval/discovery, tool selection, invocation/schema, sequencing/state, verification, integration, policy, infrastructure.
- Negative cases: irrelevant skills, misleading plans, distractor tools, stale state, conflicting evidence, partial failures, timeouts, runaway delegation, injection, approval bypass.
- Do not rely only on LLM judges for high-stakes paths.

---

## Contradictions (must not paper over)

| Tension | Resolution bias for this plan |
|---|---|
| Simplicity vs learned harnesses | Empirical escalation; measure before complexity |
| Plan persistence vs plan harm | External plan + quality review + evidence-triggered replan |
| Few tools vs rich domain compute | Hide algorithms behind few task-level interfaces |
| Autonomous skill evolution vs human governance | Propose + test + named human merge |
| Research performance vs originality | Retrieve/ground; score novelty separately; allow "nothing found" |
| Benchmark success vs deployment | Field survival / held-out trajectory eval before trust |

---

## Mapping onto the intended ecosystem

| User intent | Corpus constraint |
|---|---|
| Fan-out cheap recon first | Validated **if** lanes independent, read-only, citation-dense; still must beat strong single-agent baseline |
| Master alone decides | Strongly supported (small-agent collab gains live in orchestrator reasoning) |
| Hot-swap models per specialist folder | Supported (⟨Instruction, Context, Tools, Model⟩ minting) |
| Exact zero-wiggle implementer tasks | Supported (plan precision enables weak executors; poor plans hurt) |
| Adversarial plan/code review | Supported; score usefulness/SNR, not issue count |
| Brainstormer out-of-box | Supported with lineage + fabrication check + adversarial master appraisal |
| Alignment / drift control | Mandatory (plan decay + problem drift + collaboration gap) |
| Token-frugal + rare frontier | Supported via routing, compressed escalation briefs, reasoning-off defaults |

---

## Suggested build sequence (summary)

1. **NOW:** target tasks/risks/baseline; ledger; deterministic gates; typed contracts; eval harness; compact tools.
2. **NEXT:** compare fixed workflow vs bounded 3-specialist orchestrator on identical held-out tasks.
3. **NEXT:** governed skills only after retrieval/regression detection works.
4. **EXPERIMENT:** quality–diversity ideation branch with human novelty review.
5. **DEFER:** autonomous shared-skill rewrite, deep recursive delegation, unconstrained A2A chat, production side effects without target safety evidence.

---

## Blocking unknowns (resolve before architecture lock)

| ID | Gap |
|---|---|
| G01 | Exact target tasks, risk tier, tool permissions, latency/cost budgets |
| G05 | Safety/privacy/audit rules for data crossing worker boundaries |
| G03 | Baseline single-agent / workflow performance to beat |
| G02 | Which abstract-only papers change design after full-text review |
| G04 | Shared state, idempotency, retries, approval, recovery across process failure |
| G06 | Skill retrieval accuracy as library grows in **this** domain |
