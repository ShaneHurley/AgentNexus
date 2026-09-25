# Original Corpus — Source Cards (S01–S26)

**Audience.** Next agent planning the daily-driver orchestration.
**Rule.** Keep the link. Prefer design implications over paraphrase. Do not treat `ABS` numbers as production facts until full text is read.
**Citation integrity.** The label *Plans Don't Persist…* was adjacent to `2605.21902` in the supply list; that URL is *Planning in the LLM Era*. The Plans Don't Persist paper is **[arXiv:2606.22953](https://arxiv.org/abs/2606.22953)** (`S17b` below). Both cards are retained.

---

## S01 — How to write a great agents.md

- **URL:** https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/
- **Type:** Vendor/practitioner study · **Depth:** `FULL` · **Date:** 2025-11-19 (upd. 2025-11-25)
- **Contributes:** Analysis of 2,500+ public agent instruction files. Effective agents are **narrow specialists**, not vague helpers. Instruction surface: commands, testing, structure, style, git, boundaries. Prefer exact commands and examples. Three-tier controls: Always / Ask first / Never.
- **Method:** Repository-file analysis + templates (not a controlled benchmark).
- **Load-bearing findings:**
  - Put frequently used commands, flags, and validation **early**.
  - Name stack, versions, paths, write scopes, prohibited areas.
  - Start with one narrow job; expand after observed failure patterns.
- **Unfavorable / limits:** Copilot-oriented; no published controlled link from file features → task success.
- **Implication:** Every worker gets a compact operating contract: role, inputs, tools, checks, output schema, ask/approval boundary, forbidden scope.

---

## S02 — Writing effective tools for agents

- **URL:** https://www.anthropic.com/engineering/writing-tools-for-agents
- **Type:** First-party engineering · **Depth:** `FULL` · **Date:** 2025-09-11
- **Contributes:** Tool = contract between deterministic software and nondeterministic agent. Fewer, clearer, **workflow-level** tools beat piles of API wrappers. Prototype → multi-call held-out evals → transcript inspection → iterate schemas/descriptions.
- **Load-bearing findings:**
  - Prefer `search_logs` / `get_customer_context` over list/get chains.
  - Namespace tools; semantic IDs; concise vs detailed response modes; pagination; actionable errors.
  - Measure accuracy, runtime, call count, tokens, tool errors — not answer accuracy alone.
- **Unfavorable / limits:** Internal evals not fully public; optimal schemas are model/task dependent.
- **Implication:** Small namespaced tool catalog + trajectory eval suite before expanding the surface.

---

## S03 — Best practices for coding with agents (Cursor)

- **URL:** https://cursor.com/blog/agent-best-practices
- **Type:** Vendor guide · **Depth:** `FULL` · **Date:** 2026-01-09
- **Contributes:** Harness = instructions + tools + model (tune per model). Plan-first for meaningful work; context hygiene; short static rules; dynamic skills; verifiable targets; review; isolated worktrees for parallel agents.
- **Load-bearing findings:**
  - Skip heavyweight planning for trivia; use plans for substantial work.
  - Fresh context at task boundaries when conversation noise hurts focus.
  - Parallel workers need isolation + controlled merge/review.
  - Long loops need iteration caps and machine-checkable completion.
- **Unfavorable / limits:** Cursor-specific; multi-model claims lack public controlled study here.
- **Implication:** Editable/resumable plan artifacts; isolate parallel lanes; cap loops; verifier before merge.

---

## S04 — Building effective agents (Anthropic)

- **URL:** https://www.anthropic.com/engineering/building-effective-agents
- **Type:** First-party engineering · **Depth:** `FULL` · **Date:** 2024-12-19 (partially dated)
- **Contributes:** Workflows (predefined paths) vs agents (dynamic tool/step choice). Start simplest; add complexity only when measured outcomes justify cost/latency/error compounding. Patterns: chaining, routing, parallelization, orchestrator–workers, evaluator–optimizer, autonomous agents.
- **Load-bearing findings:**
  - Deterministic workflows for well-defined tasks; open-ended agents only for unpredictable paths.
  - Orchestrator–worker fits unpredictable subtask structure.
  - Need environmental ground truth, human checkpoints, stopping conditions.
  - Frameworks can obscure prompts/responses and hurt debugging.
- **Implication:** Complexity ladder: single call → workflow → router → bounded orchestrator–worker → autonomous loop **only if measured**.

---

## S05 — AutoDesign: Meta-Harness Optimization

- **URL:** https://arxiv.org/pdf/2608.13560 · https://arxiv.org/abs/2608.13560
- **Type:** Academic preprint · **Depth:** `ABS` (full PDF often failed in prior retrieval) · **Date:** 2026-08-13
- **Contributes:** Meta-harness optimizer uses rollout feedback to improve a code-agent harness (paper→poster). PosterBench; reported gains across model–agent configs.
- **Reported (verify in full text):** DesignHarness lifts score ~54.99→67.39; example run ~253 tool calls / 11 edits / ~40 min / <$3.
- **Implication:** Treat harness as optimizable artifact; gate self-modification with held-out eval + reversible versioning. **Domain is posters — transfer carefully.**

---

## S06 — Hitchhiker's Guide to Agentic AI

- **URL:** https://arxiv.org/pdf/2606.24937 · https://arxiv.org/abs/2606.24937
- **Type:** Practitioner reference / book-length · **Depth:** `ABS`/`PARTIAL` · **Date:** 2026-06-22 (v2 2026-07-27)
- **Contributes:** Full-stack map: substrate, alignment, reasoning, training, RAG, memory, harnesses, context, loops, skills, MCP, A2A, multi-agent, eval, UI, deployment. Quality = whole stack, not one layer.
- **Implication:** Use as **taxonomy and reading map**, not sole evidence for one topology.

---

## S07 — Agents All the Way Down

- **URL:** https://arxiv.org/pdf/2606.11869 · https://arxiv.org/abs/2606.11869
- **Type:** Methodology / case study · **Depth:** `FULL` · **Date:** 2026
- **Contributes:** Substrate understanding + building-block fluency; cycle: prototype → harvest/ship → agent-tests-agent. Small transparent loops; deterministic pre-tool hooks; versioned skills; session-keyed CLI agents; compose via stable CLI contracts.
- **Load-bearing findings:**
  - Authorization in host dispatch/hooks, **not prompts**.
  - Specialists behind stable CLI = composable, testable, independently deployable.
  - CLI composition needs resource caps, typed handoffs, tracing, recursion limits.
- **Unfavorable / limits:** One EdTech case; no matched framework A/B.
- **Implication:** Stable worker contracts; deterministic policy outside the model; behavioral scenario tests.

---

## S08 — From QA to Task Completion (Harness Survey)

- **URL:** https://arxiv.org/pdf/2606.20683 · https://arxiv.org/abs/2606.20683
- **Type:** Survey · **Depth:** `ABS` (brief also has fuller treatment) · **Date:** 2026-06-14
- **Contributes:** Agent = foundation model + execution harness. Bottleneck may be model, harness, or coupling. Harness planes: observation, context, control, action, state, verification.
- **Implication:** Organize runtime around those **six planes** explicitly.

---

## S09 — PHMForge (industrial prognostics / MCP tools)

- **URL:** https://arxiv.org/pdf/2604.01532 · https://arxiv.org/abs/2604.01532
- **Type:** Benchmark · **Depth:** `FULL` · **Date:** v3 2026-08-24
- **Contributes:** 99 expert scenarios, 39 algorithm-grounded MCP tools. Separates protocol / retrieval / invocation / reasoning / orchestration failures. Deterministic trace evaluators.
- **Load-bearing findings:**
  - Best frontier ~**80.8% pass@1** still below unsupervised threshold cited.
  - Orchestration/sequencing dominate residuals (~**23%** incorrect sequencing).
  - MCP tools >> text RAG for quantitative RUL; withholding domain tools collapses completion.
  - Removing ground-truth verification inflates completion with false positives.
  - Unknown-tool discovery mode **−21.3 pp**.
- **Unfavorable / limits:** Circularity risk (tools share lineage with ground truth); partial IAA coverage.
- **Implication:** Score retrieval, invocation, **sequencing**, verification separately; require executable checks for safety-critical outputs.

---

## S10 — SkillAdam

- **URL:** https://arxiv.org/pdf/2609.08944 · https://arxiv.org/abs/2609.08944
- **Type:** Preprint · **Depth:** `ABS` · **Date:** 2026-09-08
- **Contributes:** Adam-like discrete skill-document optimization: persistent optimization memory + volatility-driven edit budget.
- **Implication:** Never let one run rewrite shared skills; edit ledger + bounded diffs + held-out gates.

---

## S11 — SkillGLoW

- **URL:** https://arxiv.org/pdf/2609.02217 · https://arxiv.org/abs/2609.02217
- **Type:** Experimental · **Depth:** `FULL` · **Date:** 2026-09
- **Contributes:** Global skill docs go generic; flat per-task pools go noisy. Cluster into **procedural families**, compress shared priors, regenerate instance detail, commit only non-degrading updates.
- **Reported:** ~+17.2 hard-task avg vs no-skill; library ~**3.6×** more compact; commit gates matter.
- **Implication:** One validated prior per family; regenerate locals; reject regressing updates.

---

## S12 — Who Maintains Agent Skills?

- **URL:** https://arxiv.org/pdf/2609.05677 · https://arxiv.org/abs/2609.05677
- **Type:** Observational · **Depth:** `FULL` · **Date:** 2026-09-04
- **Contributes:** 5 public skill repos; 873 commits; 143 skill files; 254 substantive edits. Maintenance **human-governed**, often AI-assisted.
- **Load-bearing findings:**
  - **100%** substantive edits authored/merged via named human account.
  - ~**62%** AI co-author trailer (repo variance large).
  - Dominated by additions/corrections, not autonomous replacement.
- **Implication:** Named ownership, PR review, rationale, versioning, rollback. AI proposes; humans govern.

---

## S13 — Break It Down, Pass It On

- **URL:** https://arxiv.org/pdf/2608.20274 · https://arxiv.org/abs/2608.20274
- **Type:** Experimental · **Depth:** `FULL` · **Date:** 2026-08-20
- **Contributes:** Task-level vs subtask-level skill induction; text vs code skills.
- **Load-bearing findings:**
  - Task-level skills often **hurt** vs no-memory.
  - Subtask-level text procedures transfer more reliably.
  - Specificity/abstractness alone do not predict success — combined utility does.
- **Implication:** Reusable memory at **subtask/procedure** granularity; validate retrieval before inject.

---

## S14 — Demystifying Agent Skills

- **URL:** https://arxiv.org/pdf/2608.14036 · https://arxiv.org/abs/2608.14036
- **Type:** Experimental · **Depth:** `ABS`/`FULL` in library · **Date:** 2026-08-14
- **Contributes:** Skills act mainly as **procedural anchors**, not knowledge injection. ~8k trials.
- **Reported:** Skills beat workflow memory ~+6.06; procedural_anchor ~65.7% vs knowledge_injection ~4.5%; use precision collapses 29.6%→3.3% as pool 5→100.
- **Implication:** Skill retrieval is a first-class evaluated subsystem; bound pool width; check fit to current state.

---

## S15 — SkillGenBench

- **URL:** https://arxiv.org/pdf/2605.18693 · https://arxiv.org/abs/2605.18693
- **Type:** Benchmark · **Depth:** `ABS` · **Date:** 2026-05-18
- **Contributes:** Isolates skill **generation** (repo/doc → standardized skill) under pinned harnesses. Task-conditioned vs task-agnostic tracks.
- **Implication:** Judge generated skills by **execution** in pinned harness, not prose quality alone.

---

## S16 — CRAFT: Learn the Schema, Execute the Plan

- **URL:** https://arxiv.org/pdf/2607.22642 · https://arxiv.org/abs/2607.22642
- **Type:** Enterprise preprint · **Depth:** `ABS` · **Date:** 2026-06-24
- **Contributes:** Two-stage post-training to avoid stuffing schemas every turn; validated trajectories + plan–code consistency.
- **Reported:** ~+9.6 composite; ~9× fewer input tokens; schema-discovery loops down ~5×.
- **Implication:** Compile stable proprietary schemas into training/validated plans rather than repasting docs.

---

## S17 — Planning in the LLM Era

- **URL:** https://arxiv.org/pdf/2605.21902 · https://arxiv.org/abs/2605.21902
- **Type:** Position · **Depth:** `FULL` · **Date:** 2026-05-21
- **Contributes:** Single-shot LLM planning + limited search remain unsound/incomplete/expensive. Prefer LLMs to **construct** symbolic planners/policies that are validated and reused.
- **Implication:** Move stable planning logic into tested planner components; LLM generates/repairs them, does not improvise every plan.

---

## S17b — Plans Don't Persist `(RESOLVED)`

- **URL:** https://arxiv.org/abs/2606.22953 · https://arxiv.org/html/2606.22953
- **Type:** Empirical · **Depth:** `FULL` (in research brief) · **Date:** 2026
- **Note:** Supplied by **title only** next to the wrong PDF (`2605.21902`). Resolved by title search to Mehta & Datta (Snowflake AI Research). Confirm with owner if needed.
- **Contributes:** Plan signal in hidden state collapses rapidly across action–observation steps; naive context eviction catastrophic; pinning plan alone insufficient — recent actions/observations are also load-bearing.
- **Implication (paired with S18):** External plan file + periodic re-injection of plan slice **and** recent state; type-aware compaction; ledger is SoR.

---

## S18 — From Plan to Action

- **URL:** https://arxiv.org/abs/2604.12147 · https://arxiv.org/pdf/2604.12147
- **Type:** Empirical · **Depth:** `ABS`/`FULL` in library · **Date:** 2026-04
- **Contributes:** 21,120 SWE-agent trajectories; success ≠ plan adherence. Explicit plans help; periodic reminders help; **poor plan worse than no plan**.
- **Implication:** Persist + re-surface approved plans; plan-quality review; allow evidence-triggered replanning (not blind lock-in).

---

## S19 — Self-Questioning Language Models

- **URL:** https://arxiv.org/pdf/2508.03682 · https://arxiv.org/abs/2508.03682
- **Type:** Research · **Depth:** `FULL` · **Date:** v4 2025-09-09
- **Contributes:** Proposer–solver self-play RL; majority vote proxy vs unit-test verification for code.
- **Implication:** Self-generated adversarial scenarios for test suites **only** with independent/deterministic verification.

---

## S20 — DeepLens Diagnosis Agent

- **URL:** https://arxiv.org/pdf/2607.22555 · https://arxiv.org/abs/2607.22555
- **Type:** Technical report · **Depth:** `ABS` · **Date:** 2026
- **Contributes:** Five-stage clinical workflow; process constraints can outweigh model scale (7B harnessed vs frontier).
- **Reported:** Top-1 ~23.99% → ~60.14% with workflow.
- **Implication:** Stage-specific artifacts + evidence triangulation for high-stakes paths; benchmark ≠ deployment authorization.

---

## S21 — Harnessing Pre-Resolution Signals (Milkyway / forecasting)

- **URL:** https://arxiv.org/pdf/2604.15719 · https://arxiv.org/abs/2604.15719
- **Type:** WIP · **Depth:** `ABS` · **Date:** v3 2026-05-08
- **Contributes:** Persistent editable harness for unresolved forecasts; pre-resolution vs post-resolution learning.
- **Implication:** Keep provisional lessons separate from validated rules; promote only after outcome review.

---

## S22 — Communicate–Predict–Act

- **URL:** https://arxiv.org/pdf/2604.08727 · https://arxiv.org/abs/2604.08727
- **Type:** Benchmark · **Depth:** `ABS` · **Date:** 2026-04-09
- **Contributes:** Social-intelligence metrics beyond scalar score (influence, transparency, adaptability).
- **Implication:** Evaluate inter-agent communication quality, not only task completion / role labels. **Analogy only for enterprise MAS.**

---

## S23 — AgentIdeaBench

- **URL:** https://arxiv.org/pdf/2609.07611 · https://arxiv.org/abs/2609.07611
- **Type:** Benchmark · **Depth:** `FULL` · **Date:** 2026-09-07
- **Contributes:** Static curated refs vs active literature exploration for scientific ideation.
- **Load-bearing findings:**
  - Active exploration exposes more headroom; retrieval improves grounding/feasibility/clarity — **not measured originality**.
  - Weak models can lose under tool access; strong models gain (capability × tools interaction).
- **Implication:** Research agent: retrieve+verify before ideation; score originality separately; match tool budget to model tier.

---

## S24 — When AI Designs AI

- **URL:** https://arxiv.org/pdf/2608.17471 · https://arxiv.org/abs/2608.17471
- **Type:** Empirical · **Depth:** `FULL` · **Date:** 2026-08-18
- **Contributes:** Agent-designed methods mostly recombine human design spaces; occasional strong scores ≠ novelty.
- **Reported:** ~96.8% inside human-derived spaces; nearly half exact match of an existing human design.
- **Implication:** Brainstormer needs lineage + novelty checks; do not equate best-score search with innovation.

---

## S25 — IDEAgent (quality–diversity ideation)

- **URL:** https://arxiv.org/pdf/2607.22375 · https://arxiv.org/abs/2607.22375
- **Type:** Preprint · **Depth:** `ABS` · **Date:** 2026-07-24
- **Contributes:** Ideation as joint quality+diversity search; lineages; compare to completed/ancestor/rejected ideas.
- **Implication:** Track proposal lineages and rejected ideas; optimize portfolio Yield, not only top score.

---

## S26 — Measuring the Gap Between Human and LLM Research Ideas

- **URL:** https://arxiv.org/pdf/2607.01233 · https://arxiv.org/abs/2607.01233
- **Type:** Preprint · **Depth:** `ABS` · **Date:** 2026-07-01
- **Contributes:** LLM ideas concentrate on bridge/synthesis patterns; humans span wider taste.
- **Implication:** Human agenda-setting + diversity constraints; `NO BETTER ALTERNATIVE FOUND` is valid.

---

## Quick index

| ID | Title | Link | Depth |
|---|---|---|---|
| S01 | agents.md lessons | https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/ | FULL |
| S02 | Writing tools for agents | https://www.anthropic.com/engineering/writing-tools-for-agents | FULL |
| S03 | Cursor agent best practices | https://cursor.com/blog/agent-best-practices | FULL |
| S04 | Building effective agents | https://www.anthropic.com/engineering/building-effective-agents | FULL |
| S05 | AutoDesign | https://arxiv.org/abs/2608.13560 | ABS |
| S06 | Hitchhiker's Guide | https://arxiv.org/abs/2606.24937 | PARTIAL |
| S07 | Agents All the Way Down | https://arxiv.org/abs/2606.11869 | FULL |
| S08 | QA→Task Completion survey | https://arxiv.org/abs/2606.20683 | ABS |
| S09 | PHMForge | https://arxiv.org/abs/2604.01532 | FULL |
| S10 | SkillAdam | https://arxiv.org/abs/2609.08944 | ABS |
| S11 | SkillGLoW | https://arxiv.org/abs/2609.02217 | FULL |
| S12 | Who Maintains Agent Skills? | https://arxiv.org/abs/2609.05677 | FULL |
| S13 | Break It Down, Pass It On | https://arxiv.org/abs/2608.20274 | FULL |
| S14 | Demystifying Agent Skills | https://arxiv.org/abs/2608.14036 | ABS/FULL |
| S15 | SkillGenBench | https://arxiv.org/abs/2605.18693 | ABS |
| S16 | CRAFT | https://arxiv.org/abs/2607.22642 | ABS |
| S17 | Planning in the LLM Era | https://arxiv.org/abs/2605.21902 | FULL |
| S17b | Plans Don't Persist | https://arxiv.org/abs/2606.22953 | FULL |
| S18 | From Plan to Action | https://arxiv.org/abs/2604.12147 | ABS/FULL |
| S19 | Self-Questioning LMs | https://arxiv.org/abs/2508.03682 | FULL |
| S20 | DeepLens | https://arxiv.org/abs/2607.22555 | ABS |
| S21 | Pre-Resolution Signals | https://arxiv.org/abs/2604.15719 | ABS |
| S22 | Communicate–Predict–Act | https://arxiv.org/abs/2604.08727 | ABS |
| S23 | AgentIdeaBench | https://arxiv.org/abs/2609.07611 | FULL |
| S24 | When AI Designs AI | https://arxiv.org/abs/2608.17471 | FULL |
| S25 | IDEAgent | https://arxiv.org/abs/2607.22375 | ABS |
| S26 | Human vs LLM research ideas | https://arxiv.org/abs/2607.01233 | ABS |
