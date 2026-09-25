# Agent Orchestration Research Brief

**Purpose.** Source-by-source breakdown of 28 practitioner and research references, laid out for the next agent that will design a **new agent orchestration system** for this repo (master/specialist subagents, delegation packets, context management, tool/MCP surface, instruction + skill files).

**How to read this.** Every source keeps its link, a fetch-status honesty marker, its core claims with concrete numbers, and a short list of *actionable orchestrator rules*. Start with the synthesis at the top, then go to the specific sources that back a decision you are about to make. Do not treat any bullet as verified beyond its stated fetch status.

**Fetch-status legend.**
- `VERIFIED` — full text or substantial body retrieved and read.
- `PARTIAL` — abstract/snippets only; numeric claims not confirmed.
- `UNREACHABLE` — could not be retrieved; content deliberately left blank rather than guessed.

---

## Part 0 — Synthesis for the orchestration designer

### The eight load-bearing conclusions

1. **The harness, not the model, is the main lever.** Same-model swings of tens of points recur across sources: SWE-bench Verified swings tens of points by harness alone (QA→Task Completion survey); Terminal-Bench 2.0 within-model harness spread median **13.6%**; WebArena GPT-4o **13.1% → 54.6%** with a better scaffold; a 7B medical model goes **23.99% → 60.14%** purely from a five-stage pipeline (DeepLens).
2. **Plans do not persist in the model — they must live outside it and be re-injected.** Plan signal in hidden state drops **4.1× in a single action-observation step** and is effectively gone by step+5 (Plans Don't Persist). Independently, re-injecting the plan **every 5 trajectory steps** improves both compliance and success (From Plan to Action). Treat chat history as a cache; the plan file is the source of truth.
3. **Naive context eviction is catastrophic, and pinning the plan does not save you.** ALFWorld success **56.7% → 22.0%** (−34.7 pp) under naive eviction, and plan-protected and probe-gated re-surfacing were statistically indistinguishable from naive. Recent actions and observations are as load-bearing as the plan text.
4. **Instruction/skill artifacts are operational memory with a maintenance cost.** Real SKILL.md repos show **100%** of substantive edits human-authored or human-merged, ~5-day touch cadence, and only **4.3%** of edits consolidating or deprecating anything — skills accrete by default. Automated curators measured **no** average downstream benefit (Δ = −0.09 on 1–5).
5. **Granularity of delegation and skills decides whether memory helps or hurts.** Whole-task skills *reduce* success (−1.2 pp text, −4.1 pp code); subtask-level skills help (+1.9 pp), and subtask decomposition helps even with no memory at all (24.8% vs 22.1%). Procedural-family consolidation beats flat retrieval (+11.2 pp vs +5.0 pp, SkillGLoW).
6. **Skills stabilize execution; they do not inject knowledge.** Mechanism labels: **procedural_anchor 65.7%** vs **knowledge_injection 4.5%**. Execution-layer failures fall 37.3% → 23.5%; environment failures 5.3% → 0.2% (Demystifying Agent Skills). So write checklists, tool order, and verification steps — not encyclopedias.
7. **Every self-improving loop in the literature has an acceptance gate.** AutoDesign changes **exactly one harness component per iteration** and requires train-improves-AND-dev-does-not-regress; SkillGLoW's commit gate accepted 19/26 and preserved **+14.7 pp vs +9.6 pp** if candidates were auto-admitted; Milkyway allows **≤1 validated patch per checkpoint**. Ungated self-edit is the failure mode.
8. **Failures are mostly orchestration failures, so measure them separately.** PHMForge: the strongest config reaches **80.8% pass@1** and *orchestration* errors dominate — frontier models are better at *calling* tools than *sequencing* them. Tool discovery alone costs **−21.3 pp**. Measure retrieval, invocation, sequencing, and execution as distinct stages.

### Direct design implications for this repo

| Decision | Backed by | Recommendation |
|---|---|---|
| Plan storage | Plans Don't Persist; From Plan to Action; Cursor | External plan file rewritten by master; re-inject plan slice + current subgoal every N steps |
| Delegation unit | Break It Down, Pass It On; GitHub agents.md | One specialist per subtask with explicit read/write path scope and a single primary outcome |
| Instruction files | GitHub agents.md; Demystifying Agent Skills | Runnable commands early, version-pinned stack facts, Always / Ask-first / Never tiers, procedural checklists |
| Tool surface | Anthropic writing-tools; PHMForge | Small set of namespaced workflow tools, concise/detailed response modes, pagination, teaching error messages |
| Self-improvement | AutoDesign; SkillGLoW; SkillAdam; Milkyway | One bounded patch per cycle, held-out dev gate, persistent issue tracker, explicit deprecation budget |
| Verification | Anthropic building-effective-agents; CRAFT; DeepLens | Machine-checkable gate between phases; block the patch specialist until repro artifacts exist |
| Static domain facts | CRAFT | Externalize CARLA APIs / Linux paths / scenario schema into validated artifacts, not per-turn prompt stuffing (**~9×** input-token reduction achieved) |
| Metrics | QA→Task Completion; PHMForge | Report score *with* harness identity, tool privileges, retry/timeout policy; use pass-all-3 for safety-critical paths |

### Known tensions the next agent must resolve

- **Automated skill curation:** the skill-optimization papers (SkillAdam, SkillGLoW, Milkyway, AutoDesign) report gains, while the maintenance study of real repos found no average benefit and universal human gating. Resolve toward *proposal + human merge*, not autonomous writes.
- **MCP vs CLI:** PHMForge and the Hitchhiker manuscript assume MCP as the standard surface; Agents All the Way Down argues CLI composition avoids persistent tool-registry token cost. Both are defensible; pick per tool volatility.
- **More phases is not better:** From Plan to Action found that adding "best practice" phases (regression tests, summaries) can *degrade* performance when misaligned with the model's own strategy. Measure before mandating.
- **Tool access can hurt weak models:** AgentIdeaBench found the weakest quartile *lost* 0.18 points under active tool use while the strongest gained 0.76. Match tool budget to model tier.

---

## Part 1 — Practitioner guides

### GitHub Copilot `agents.md` (2,500+ repos)
- **Link:** https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/
- **Fetch status:** VERIFIED
- **What it is:** GitHub Blog post by Matt Nigh (Nov 19, 2025; updated Nov 25, 2025) on Copilot custom agents in `.github/agents/*.md`.
- **Core thesis:** Effective agents are narrow specialists with an explicit operating manual, not vague "helpful assistants." Success comes from persona, executable commands, stack specifics, examples, and hard boundaries. Instruction files should grow iteratively after observed failures, not through big upfront specs.
- **Key findings / claims:**
  - Vague prompts like "You are a helpful coding assistant" fail; role-specific prompts (a test engineer who never modifies source) work.
  - Put **commands early** with full flags: `pytest -v`, `npm run build`, not bare tool names.
  - **Code examples beat prose** for style — one real snippet outperforms three paragraphs of description.
  - **Boundaries** matter; "Never commit secrets" was the most common helpful constraint.
  - Specify stack with **versions**: "React 18, TypeScript, Vite, Tailwind" not "React project."
  - Top-tier files cover six areas: commands, testing, project structure, code style, git workflow, boundaries.
  - Recommended starter agents: `@docs-agent`, `@test-agent`, `@lint-agent`, `@api-agent`, `@dev-deploy-agent`, each with scoped write paths.
  - Three-tier boundary pattern: **Always do / Ask first / Never do**.
  - `@test-agent` example boundary: write to `tests/` only; **never remove failing tests** without user authorization.
  - "Start minimal" with agent name, one-sentence description, persona — expand when the agent errs.
- **Concrete design rules for an orchestrator:**
  - Register each specialist with a **single primary outcome** and explicit read/write directory scopes.
  - Inject **runnable verification commands** into every specialist's context before tool use.
  - Route via **named personas** rather than one general coding agent.
  - Enforce **Always / Ask first / Never** tiers in instruction files and block "Never" paths in tooling where possible.
  - Treat instruction files as **living docs** updated after repeated mistakes.
  - Require **version-pinned stack facts** so routing and edits stay consistent.
- **Caveats / limits:**
  - Specific to the Copilot `agents.md` convention, not Cursor subagents.
  - Pattern analysis of public repos, not controlled experiments.
  - Examples skew JS/TS web stacks; CARLA Python/Electron needs translation.

### Anthropic — Writing tools for agents
- **Link:** https://www.anthropic.com/engineering/writing-tools-for-agents
- **Fetch status:** VERIFIED
- **What it is:** Anthropic engineering post (Sep 11, 2025) on designing MCP/API tools for agents, with evaluation loops and agent-assisted tool refactoring.
- **Core thesis:** Tools are contracts between **deterministic systems and non-deterministic agents**, not developer APIs. Tool quality (selection, naming, response shape, descriptions) often dominates prompt tuning. Improve via prototype → realistic eval tasks → metric analysis → iterate.
- **Key findings / claims:**
  - Agents may hallucinate tool use, skip tools, or choose wrong strategies; design must assume variance.
  - Strong eval tasks are multi-step and realistic (schedule meeting + attach notes + book room); weak tasks are single lookups.
  - Run evals with simple `while`-loop agentic cycles; optionally require reasoning blocks before tool calls.
  - Track **accuracy, runtime, tool-call count, token use, tool errors**; redundant calls signal pagination problems.
  - Their web search tool spuriously appended `2025` to queries until the description was fixed.
  - **Few high-impact workflow tools** beat many thin API wrappers (`schedule_event` vs `list_users`+`list_events`+`create_event`).
  - Prefer `search_*` / `get_*_context` over dumping full lists into context.
  - **Namespace tools** by service/resource (`asana_projects_search`); prefix vs suffix naming measurably shifts eval performance.
  - Return **semantic fields** (`name`, `file_type`) over raw UUIDs.
  - Support `response_format`: `concise` | `detailed` — example showed **206 vs 72 tokens** (~⅓).
  - Default tool response cap in Claude Code: **25,000 tokens**; use pagination with actionable truncation messages.
  - Tool-description edits alone drove SOTA SWE-bench Verified gains for Claude Sonnet 3.5.
  - Use agents to batch-refactor tool implementations from eval transcripts; hold out a test set.
- **Concrete design rules for an orchestrator:**
  - Curate a **small set of workflow-native tools** aligned to eval scenarios, not 1:1 REST mirrors.
  - **Namespace** everything (`carla_scenario_validate`, `bridge_replay_search`) to reduce wrong-tool selection.
  - Standardize **concise vs detailed** outputs and default pagination for logs, maps, trajectories.
  - Build an eval harness measuring tool-call efficiency, not just task success.
  - Write tool specs like junior-dev docstrings: examples, edge cases, unambiguous names (`user_id` not `user`).
  - Review **raw trajectories**; omissions matter more than stated reasoning.
- **Caveats / limits:**
  - References Anthropic-internal Slack/Asana tools and Claude-specific behaviors.
  - Assumes access to eval infrastructure and representative data.
  - Token limits will drift as models change.

### Cursor — Agent best practices
- **Link:** https://cursor.com/blog/agent-best-practices
- **Fetch status:** VERIFIED
- **What it is:** Cursor blog by Lee Robinson (Jan 9, 2026) on harness design, planning, context, rules/skills, parallel agents, and review loops.
- **Core thesis:** Productivity comes from treating the **harness** (instructions + tools + model) as the unit of optimization. Plan before coding, manage context deliberately, give verifiable goals, and isolate multi-step work. Extend behavior via **Rules** (always-on) and **Skills** (on-demand), not giant static prompts.
- **Key findings / claims:**
  - Cursor tunes the harness per model because models differ (`grep` vs dedicated search; post-edit lint habits).
  - **Plan Mode** (`Shift+Tab`): research → clarify → plan with file paths → wait for approval; save to `.cursor/plans/`.
  - If output diverges, **revert and refine the plan** rather than arguing in a long thread.
  - Let agents **pull context via search**; tagging irrelevant files hurts focus. Use `@Branch`, `@Chats` for scoped continuity.
  - Start **new conversations** at feature boundaries; long threads accumulate noise after summarization.
  - **Rules** in `.cursor/rules/`: commands, patterns, pointers to canonical files — not copied style guides.
  - **Skills** (`SKILL.md`): dynamic workflows, `/commands`, and **hooks** (stop hook loops until scratchpad says `DONE`, `MAX_ITERATIONS = 5`).
  - TDD pattern: failing tests first → commit tests → implement to green without modifying tests.
  - **Parallel agents** via git **worktrees**; running multiple models on one prompt and picking the best helps hard tasks.
  - **Cloud agents** for background fixes/tests/docs; **Debug Mode** for races, perf, regressions.
  - High performers write specific prompts, iterate setup slowly, review diffs, and supply verifiable signals.
- **Concrete design rules for an orchestrator:**
  - Split **master planner** (approval gate, file-level plan) from **execution specialists** with scoped write paths.
  - Persist plans and handoffs in durable markdown for session resets and subagent pickup.
  - Keep always-on rules minimal; load heavy playbooks as on-demand skills.
  - Use isolation primitives (worktrees/sandboxes) for parallel specialists; merge only after verification passes.
  - Implement **stop hooks / eval loops** that run until objective checks pass, with a hard iteration cap.
  - Reset or fork context at feature boundaries instead of replaying full transcripts.
- **Caveats / limits:**
  - Cursor-specific UX (Plan Mode, Bugbot, cloud agents, nightly Skills/hooks).
  - A cited planning study is mentioned without methodology detail.
  - Parallel multi-model patterns multiply cost.

### Anthropic — Building effective agents
- **Link:** https://www.anthropic.com/engineering/building-effective-agents
- **Fetch status:** VERIFIED
- **What it is:** Anthropic engineering guide (Dec 19, 2024) distinguishing agentic **workflows** from **agents**, with composable patterns and agent-computer-interface (ACI) guidance. The page notes the tooling landscape has since changed.
- **Core thesis:** Start with the simplest solution, often a single augmented LLM call with retrieval and examples. Add agentic complexity only when it measurably helps. Production winners use composable patterns rather than heavy frameworks that hide prompts and hinder debugging.
- **Key findings / claims:**
  - **Workflows** run LLM+tools on predefined code paths; **agents** dynamically direct their own process and tool use.
  - Agents trade latency and cost for flexibility; many apps need retrieval + in-context learning, not autonomy.
  - Framework warning: abstraction obscures prompts/responses — understand the underlying code.
  - Building block is the **augmented LLM** (retrieval, tools, memory); MCP cited for third-party integration.
  - **Prompt chaining** with programmatic gates between steps when accuracy beats speed.
  - **Routing** to specialized prompts/tools, including easy→Haiku / hard→Sonnet model routing.
  - **Parallelization** via sectioning (independent subtasks) and voting (multiple reviewers/guardrails).
  - **Orchestrator-workers** for unpredictable subtasks such as multi-file coding and multi-source search.
  - **Evaluator-optimizer** loop when clear criteria exist and iterative critique helps.
  - Full agents need environmental ground truth each step, checkpoints, stop conditions, and sandbox testing — compounding errors are the risk.
  - Three principles: maintain simplicity, show planning transparently, craft the ACI.
  - Appendix: their SWE-bench agent spent more time optimizing **tools** than prompts (absolute paths fixed relative-path failures).
  - Tool formats should sit close to the training distribution; use poka-yoke argument design.
  - Strongest domains are customer support and coding (verifiable success, tool integration, human oversight).
- **Concrete design rules for an orchestrator:**
  - Default to **routing + specialist workflows**; reserve fully autonomous loops for open-ended, trusted environments.
  - Use **orchestrator-workers** when the file touch set is unknown upfront.
  - Add **evaluator-optimizer** passes where explicit rubrics exist (tests, schema validation, scenario contracts).
  - Keep orchestration code-visible: prompts, gates, stop conditions.
  - Invest in ACI as much as prompts: naming, examples, absolute paths, recovery-teaching errors.
  - Escalate single call → workflow → agent only with eval gains.
- **Caveats / limits:**
  - Published Dec 2024; authors note subsequent tooling shifts.
  - Examples lean on customer anecdotes and SWE-bench/computer-use references.
  - Architectural patterns, not a drop-in library.

---

## Part 2 — Plans, context, and planning architecture

### From Plan to Action: How Well Do Agents Follow the Plan?
- **Link:** https://arxiv.org/abs/2604.12147
- **Fetch status:** VERIFIED (`/abs` fetch timed out once, succeeded on retry; supplemented with the v3 HTML)
- **What it is:** ASE '26 paper (DOI 10.1145/3832783.3834400) by Liu, Dehghan, Ganhotra, Hirzel, Jabbarvand — empirical study of **plan compliance** in programming agents.
- **Core thesis:** Agents are told to follow **N→R→P→V** plans (Navigate, Reproduce, Patch, Validate), but plans are advisory and compliance is uneven. Without measuring compliance, success may reflect contamination or memorized workflows. Good plans help; misaligned or bloated plans hurt worse than no plan; periodic reminders help on long horizons.
- **Key findings / claims:**
  - **21,120 SWE-agent trajectories**, 4 LLMs (GPT-5 mini, DeepSeek-V3, DeepSeek-R1, Devstral-small), SWE-bench Verified + Pro, 8 plan settings.
  - Metrics: **PPC** (phase coverage), **POC** (order via longest increasing subsequence), **PPF** (penalizes out-of-plan phases), combined **PC = (PPC·POC·PPF)^(1/3)**.
  - Trajectories abstracted into phase strings (compliant `NR₂PV₃PV` vs skip-heavy `N→P` failures).
  - **With no plan**, agents fall back on internalized workflows and success rate drops.
  - The standard plan improves resolution for all models; compliance correlates with success for some (significant for Devstral-small and DeepSeek-R1).
  - **Removing a phase from instructions hurts** even when agents frequently skipped that phase anyway.
  - A subpar plan still beats no plan; early extra "best practice" phases can **degrade** performance if misaligned.
  - **Periodic reminder**: re-inject the plan **every 5 steps** — fewer violations, better success.
  - SWE-bench Pro compliance averages **~13% lower** than Verified; agents skip reproduction and lean on existing regression tests.
  - Automated phase mapping validated on 320 actions, Fleiss' **κ = 0.99**.
- **Concrete design rules for an orchestrator:**
  - Encode explicit phases (explore → reproduce → patch → verify) and log **phase-labeled trajectories** for compliance auditing.
  - **Re-inject the active plan** on a fixed step interval during long fixes, not only at session start.
  - Don't stuff extra best-practice phases into master prompts without measuring.
  - Keep a concise default plan even when it seems redundant — absent plans invite incomplete memorized workflows.
  - Use **geometric-mean compliance scoring** so a skipped validation can't hide behind good coverage.
  - Gate the patch specialist until navigation/repro artifacts exist.
- **Caveats / limits:**
  - SWE-agent + GitHub issue benchmarks, not multi-agent runtime orchestration.
  - Compliance/success link is correlational.
  - Specific 2025–2026 frontier models.

### Plans Don't Persist: Why Context Management Is Load Bearing for LLM Agents
- **Link:** https://arxiv.org/abs/2606.22953 (HTML: https://arxiv.org/html/2606.22953) — located by title search; the user supplied no URL
- **Fetch status:** VERIFIED (HTML)
- **What it is:** arXiv paper by Aman Mehta and Anupam Datta (Snowflake AI Research) on representational persistence of agent plans under context management; ALFWorld and HotpotQA, Llama-3.1-70B plus reasoning variants.
- **Core thesis:** Standard LLM agents treat plans as **context-time** objects re-read from the window, not durable hidden state. Evicting plan tokens is unsafe, and pinning or re-surfacing the plan alone does not fix compression once recent working state is lost.
- **Key findings / claims:**
  - **Replay pairing**: matched trajectories with and without the plan in history; plan signal measured as hidden-state cosine distance.
  - Llama-3.1-70B plan signal **0.453** at step+1, a **4.1× drop** within one action-observation step; ~0.027 by step+5. HotpotQA decays **12.4×** faster.
  - Layer **L32** peak; Ridge probe R²=0.875; AUROC 0.999 (authors flag step-index leakage, R²=0.978, as a confound).
  - The probe leads behavioral plan deviation by a median of **5 steps** in 74.2% of deviating tasks.
  - **Reasoning-trace confound**: R1 `<thinking>` re-derives the plan; strict stripping recovers **+163%** in-sample / **+153%** held-out step+1 signal.
  - Compression stress (30 ALFWorld tasks × 5 runs, keep_recent=4): naive eviction **56.7% → 22.0%** success (**−34.7 pp**, p<0.001).
  - `plan_protected` and `probe_gated` variants **do not recover** vs naive (p≈0.89 / 0.67); probe-gated re-surfacing fired ~6.1× per run and still failed.
- **Concrete design rules for an orchestrator:**
  - Never assume master plans "live in the model" once written — re-inject concise plan slices every N steps or on phase change.
  - Pin **constraints + current subgoal + tool schema**, not just the opening plan paragraph.
  - For reasoning models, strip or isolate `<thinking>` blocks in diagnostics and cross-run comparisons.
  - Context policy must preserve **recent action/observation state**; plan-only pinning is insufficient at tight budgets.
  - Use an external plan store (file or structured state object) rewritten explicitly by the orchestrator; chat history is a cache, not truth.
- **Caveats / limits:**
  - Claims are representational, not behavioral-optimality; steering interventions were largely null.
  - ALFWorld/HotpotQA agents; probe transfer needs per-domain recalibration.
  - Plan-content vs length/position confound not fully isolated.

### Planning in the LLM Era (IBM position paper)
- **Link:** https://arxiv.org/abs/2605.21902
- **Fetch status:** VERIFIED
- **What it is:** Position paper by Katz, Kokel, Srinivas, Sohrabi (IBM Research) on shifting LLMs from inference-time planners to **construction-time** planner generators.
- **Core thesis:** Single-shot and LLM-in-the-loop search planners are unsound, incomplete, and wasteful at scale. Reliable agents should compile domain-specific planners or policies once, verify them, and run them cheaply at inference, with LLMs used mainly offline.
- **Key findings / claims:**
  - Hybrid ReAct/ToT-style search with LLM-implemented successor and goal functions loses soundness and completeness when search is bounded.
  - Three construction-time paradigms: **NL2Search** (Python successor/goal/heuristic code, AutoToS), **NL2PDDL** (formal models for classical planners), **NL2Policy** (generalized policy code).
  - Frontier LLMs can approach LAMA coverage on some domains but degrade under obfuscation and use far more compute.
  - NL2PDDL progress is still weak on partial observability, object creation, API glue, and multi-page responses.
  - Policy-code generation fits procedural glue, sensing-acting interleave, and hierarchical macros best.
  - Recommends cross-category integration: policy code for macros plus NL2Search/NL2PDDL for search-heavy subproblems.
  - Open gaps: automatic state-feature discovery, global model-space search, and AutoToS's linear single-candidate generation.
- **Concrete design rules for an orchestrator:**
  - Have the master compile **verified** domain modules offline; specialists invoke them with minimal per-step re-planning.
  - For CARLA-like horizons: macro policies for repeated subflows (spawn, bridge, GUI server), search/formal planners for combinatorial scenario layout.
  - Invest in validator feedback loops (VAL, unit tests, execution) at construction time, not prompt retry at runtime.
  - Avoid unbounded LLM search in hot loops; prefer pre-generated heuristics and checklists.
  - Make the **state representation contract** between subagents explicit.
- **Caveats / limits:**
  - Position paper, no new empirical benchmark.
  - Evidence is largely classical/PDDL planning; transfer to stochastic CARLA runtime needs judgment.
  - Prescribes planner generation philosophy, not multi-agent formats.

---

## Part 3 — Harness engineering and meta-optimization

### QA → Task Completion (harness engineering survey)
- **Link:** https://arxiv.org/pdf/2606.20683
- **Fetch status:** VERIFIED (long survey; substantial body read)
- **What it is:** arXiv survey (June 2026) by Jianyuan Guo et al. (CityU HK, Sydney, PKU, TokenRhythm); catalog at https://github.com/ggjy/Awesome-Agent-Engineering.
- **Core thesis:** Agent quality is a property of **⟨model, harness⟩**, not the model alone. Bottlenecks migrate across four paradigms: prompt → context/workflow → **harness engineering** → agent-native training and co-evolution. A harness has six coupled responsibilities: Observation, Context, Control, Action, State, Verification/Governance.
- **Key findings / claims:**
  - Static benchmarks (MMLU-Pro, GPQA) saturate while SWE-bench, WebArena, OSWorld, Terminal-Bench remain far from solved.
  - **SWE-agent** ACI redesign improves coding agents at fixed model — the foundational harness evidence.
  - SWE-bench Verified: the same backbone can swing **tens of points** by harness; **mini-SWE-agent (~100 LOC)** is near OpenHands on Opus 4.5 (**76.8% vs 77.6%**).
  - Terminal-Bench 2.0 within-model harness spreads often **>10%** (Opus 4.6 **58.0–76.4%**, Gemini 3.1 Pro **59.4–80.2%**); median spread **13.6%**.
  - WebArena: GPT-4o **13.1%** model-only vs **54.6%** with WebOperator (**41.5 pp** span).
  - Repeated principles: legibility, mechanical enforcement, verification-in-the-loop, explicit artifacts (plans, logs, diffs).
  - Proposes **value-aware optimization** combining success with cost, latency, risk, reliability, and process quality.
- **Concrete design rules for an orchestrator:**
  - Map each task to a **harness pressure profile** (horizon, environment type, autonomy level) before picking patterns.
  - Co-design observation and action interfaces; don't optimize prompts alone.
  - For coding/terminal domains, invest in verifier loops plus timeout/retry governance.
  - Report scores **with harness identity**, tool privileges, retry/timeout policy, and runtime stats.
  - When composing models, treat the control loop as a router: planner/executor/verifier with separate contexts and permissions.
- **Caveats / limits:**
  - Synthesis over heterogeneous public leaderboard rows, not uniform factorial experiments.
  - Vendor scaffold numbers are upper envelopes.
  - Evolution-first taxonomy, not a deployment cookbook.

### AutoDesign (meta-harness optimization)
- **Link:** https://arxiv.org/pdf/2608.13560
- **Fetch status:** VERIFIED
- **What it is:** arXiv preprint (2026) by Luo et al. (Meituan, MBZUAI, PKU, Tsinghua and others) introducing **AutoDesign** and **PosterBench**.
- **Core thesis:** Long-horizon design is **meta-harness optimization**: a fixed LLM sits inside a design harness that an outer meta-harness improves from rollouts and human-aligned evaluation. Inner loop = designer + critic on one output; outer loop = rollout → evaluate → propose one bounded harness edit → train+dev acceptance gate.
- **Key findings / claims:**
  - Harness decomposed into five parts: **Context/Memory, Tools/Specs, Execution Runtime, Orchestration, Evaluation/Feedback**.
  - PosterBench Main Track (100 papers): AutoDesign **78.32** vs Claude Design **70.87** (+7.45) under matched Claude Code + Claude 4.8.
  - PosterBench-mini: the harness raises average **54.99 → 67.39** (+12.4%) across seven agent/model configs; best mini score **81.46**.
  - Outer loop changes **one component per iteration**; dev set hidden from the optimizer; **54 harness updates** over 7 days, **224 subagents**, 123+ iterations.
  - Autonomous run example: **253 tool calls**, 11 editing turns, ~40 minutes, under **$3**.
  - Human study: **933** judgments; Bradley–Terry **64.0%** (95% CI 55.2–77.8%); **74.4%** human agreement when the benchmark margin is ≥20 points.
  - Seven-dimension rubric with weights (Readability 25, Layout 20, Density 15, ...) plus record-level ceilings and gates.
- **Concrete design rules for an orchestrator:**
  - Split the **task loop** (artifact revision) from the **system loop** (harness revision), with separate evaluators.
  - Allow **exactly one harness component** change per outer iteration for attributable credit.
  - Gate persistence: train improves **and** dev does not regress; keep an optimization record with checkpoints for rollback.
  - Use parallel subagents to inspect trajectories, then a code-editor role to implement the chosen patch.
  - Pair rule-based blocking checks with model critique on rendered previews; cap inner refinement (K=12 in their harness).
- **Caveats / limits:**
  - Primary validation is paper-to-poster; slides/web/video are pilots.
  - Optimization-time evaluator can bias results without frozen reference tasks and human audits.
  - Heavy reliance on proprietary models and vendor pricing.

### Milkyway (pre-resolution harness evolution)
- **Link:** https://arxiv.org/pdf/2604.15719
- **Fetch status:** VERIFIED
- **What it is:** Multi-institution paper (Wei, Gao, Han, Chen, Zhu, Zheng et al.; USTC, Zhongguancun Academy, Tsinghua IIIS) on a future-prediction agent with a persistent editable harness, evaluated on **FutureX** and **FutureWorld**.
- **Core thesis:** Outcome labels after resolution give weak process credit assignment. Revisiting the same unresolved question before resolution yields **pre-resolution signals** from temporal contrasts (evidence drift, missed verification, overconfidence), converted into bounded harness patches on typed axes **F/E/U** (factor tracking, evidence handling, uncertainty), with a post-resolution Check auditing provisional guidance.
- **Key findings / claims:**
  - Milkyway (GPT-5.4) FutureX weighted overall **60.85** vs best self-evolving baseline **53.80** (+7.05); FutureWorld **69.05** vs **60.84** (+8.21).
  - vs best single-run baseline: +3.30 (FutureX), +2.78 (FutureWorld).
  - Matched rolling cells: typed harness gains **+14.0 / +16.9 / +13.0 / +15.5** vs no-harness **+0.9 to +7.8**; beats generic memory by **+8.0 to +9.1** pp.
  - **≤1 validated patch per checkpoint**; only the harness persists — checkpoint notes are transient.
  - Shared scaffold: 200K token cap, 50 tool calls per checkpoint; scored questions revisited 3×.
  - Pre-resolution signal combines prediction divergence with procedural diagnostic findings.
- **Concrete design rules for an orchestrator:**
  - Persist **typed procedural guidance**, not raw trajectories or answers, across revisits.
  - Derive updates from **fixed-schema checkpoint notes** compared over time, not free-form history.
  - Cap writes to one bounded add/revise/deprecate patch per cycle, with validation.
  - Split the **executing agent** from the **harness editor**.
  - Use a post-hoc Check to retain, refine, or deprecate provisional entries.
- **Caveats / limits:**
  - Quantified evidence is within-question; cross-question reuse not separately measured.
  - Assumes scheduled revisits before resolution.

### Hitchhiker's Guide to Agentic AI
- **Link:** https://arxiv.org/pdf/2606.24937
- **Fetch status:** PARTIAL (abstract/snippets only — the PDF returned no extractable body and `https://arxiv.org/html/2606.24937v1` returned HTTP 500)
- **What it is:** arXiv 2606.24937v2 (submitted 22 Jun 2026, revised 27 Jul 2026), cs.AI, by **Haggai Roitman**; practitioner-oriented book-length manuscript (version 1.3).
- **Core thesis:** Reliable agentic systems require understanding every layer of the stack — LLM substrate, alignment/reasoning, harness/runtime, coordination protocols, evaluation, deployment — rather than optimizing one layer. The second half centers on harness design, loop engineering, and multi-agent coordination.
- **Key findings / claims (abstract scope only, not verified against the body):**
  - Foundations: SFT, LoRA, MoE, compression, inference optimization.
  - Alignment and reasoning: RLHF, PPO, DPO variants, GRPO, reward modeling, CoT, test-time scaling.
  - Agentic stack: trajectory-based RL, RAG and Agentic RAG, memory types (in-context, external, episodic, semantic).
  - Harness design and context management; **generate-verify-retry** and **adaptive budget control**.
  - **MCP**, agent skills, **A2A**, and multi-agent topologies (centralized, decentralized, hierarchical).
  - Closes with frameworks, agentic UI, evaluation methodology, and production deployment.
- **Concrete design rules for an orchestrator (inferred from scope, not from retrieved evidence):**
  - Treat harness + loop policy + memory + tools as first-class design objects alongside model choice.
  - Standardize inter-agent and tool boundaries via MCP and A2A rather than ad hoc connectors.
  - Build loops around verify-retry with explicit budget control for long horizons.
  - Evaluate with agentic task methodology, not QA-only metrics.
- **Caveats / limits:**
  - **Body not retrieved.** Treat everything above as table-of-contents level. Re-fetch before relying on it.

### Agents All the Way Down (custom agent methodology)
- **Link:** https://arxiv.org/pdf/2606.11869
- **Fetch status:** VERIFIED
- **What it is:** arXiv preprint (2026) by Marc Alier Forment, Juanan Pereira, Francisco José García-Peñalvo, María José Casañ (UPC, UPV/EHU, USAL); methodology distilled from AAC on the LAMB EdTech platform (~200 educator-creators, production since April 2026 per the paper).
- **Core thesis:** Custom in-app agents need a framework-free end-to-end practice: two one-time preconditions (substrate, building blocks) then a repeating **P3→P4→P5** cycle. Multi-agent orchestration is **CLI composition** once agents ship as CLIs (the "Turtle" pattern); builders/orchestrators with durable memory are "Splinters," deployable session-memory agents are "Turtles."
- **Key findings / claims:**
  - Five phases: P1 Substrate, P2 Building blocks, P3 Prototype with a general-purpose agent, P4 Ship as CLI, P5 Agent-tests-agent.
  - Custom vs general-purpose distinguished on six axes: domain prompt/skills, private tools, in-app deployment, security allow-lists, cost-shaped model mix, brand/audit/compliance.
  - Cache discipline: prefix order **tools → system → messages**; tool/system stability is critical for provider cache hits (~**10×** input discount cited).
  - MCP vs CLI cost model: MCP pays a persistent tool registry plus schemas; a CLI baseline avoids that overhead (ratios flagged as practitioner-sourced).
  - P5 is behavioral scenario testing driven by a general-purpose agent, complementing unit/integration/E2E tests.
  - Single primary case study; transfer to other LAMB subprojects reported as in progress.
- **Concrete design rules for an orchestrator:**
  - Prototype with a general-purpose builder, then **freeze** the deployable artifact as a CLI with explicit allow-lists and **dispatcher-side authorization**, not prompt-only security.
  - Run scenario suites where a general-purpose agent invokes the custom CLI and judges traces and outputs.
  - Compose multi-agent systems by shelling out to specialist CLIs (supervisor/worker, fan-out, handoffs) instead of mandatory framework graphs.
  - Optimize prompt cache: immutable tools at init, stable system per session, append-only messages; keep volatile state out of system.
  - Prefer a minimal dependency closure; adopt frameworks only after P1/P2 when team/process gains dominate.
- **Caveats / limits:**
  - No controlled comparison against framework-based teams; largely one-team EdTech evidence.
  - MCP/CLI cost numbers are practitioner reports, not in-paper measurements.
  - Cross-session memory for production learning agents is explicitly out of scope.

### CRAFT (Learn the Schema, Execute the Plan)
- **Link:** https://arxiv.org/abs/2607.22642
- **Fetch status:** VERIFIED
- **What it is:** arXiv industry paper (Amazon Advertising) on post-training enterprise coding agents for schema-grounded analytics.
- **Core thesis:** Stable domain schema and tool-use patterns belong in **weights plus structured plans**, not repeated prompt stuffing. Two-stage training: schema-stripped PLAN SFT, then execution-shaped GRPO that aligns tool use, plan-code consistency, and multi-turn behavior.
- **Key findings / claims:**
  - Tri-Gate filter: 100K+ exploratory trajectories → **15.1K accepted** (42.1K execution failures, 20.5K empty outputs, 22.3K reasoning mismatches removed).
  - Removes ~50K-token DDL from inference: **~9× input-token reduction** (0.11× baseline); schema-discovery loops 1.0× → 0.62× (SFT) → **0.20×** (SFT+RL).
  - vs schema-stuffed baseline: Agent Score **+9.6 pp**, consistency **+4.1 pp**, multi-turn coherence **+4.2 pp**.
  - PLAN SFT alone: +2.6 pp score but **−1.4 pp** consistency — plans alone are initialization, not alignment.
  - Multi-turn retention **+7.8 pp**, progression **+9.4 pp** after RL; execution +7.1 pp, plan-code alignment +8.4 pp.
  - Reward mix: outcome (execution/tests) + process (tool structure) + consistency (plan-code) + bounded judge.
  - Scope: 25 schema-linked entities, 30 agentic workflows; near-zero regression on IFEval, GSM8K, GPQA.
- **Concrete design rules for an orchestrator:**
  - Externalize stable domain facts (CARLA APIs, Linux paths, scenario schema) into validated artifacts plus lightweight tool docs, not full schema every turn.
  - Require an explicit **plan block** separate from executable actions; score delegation packets for plan-code consistency.
  - Filter trajectories by execution verification (syntax/API/empty-output gates) before any LLM judge.
  - Target feedback at tool-call structure and multi-turn retention, not just final answer correctness.
- **Caveats / limits:**
  - Absolute scores confidential; only deltas vs an internal baseline.
  - Advertising analytics domain; enterprise-specific GRPO infrastructure.
  - Process reward does not yet optimize infra/runtime cost.

### DeepLens Diagnosis Agent (harnessing small models)
- **Link:** https://arxiv.org/pdf/2607.22555
- **Fetch status:** VERIFIED
- **What it is:** John Snow Labs paper (Bayeshi, Kocaman, Talby et al.) on a five-stage medical diagnosis agent around JSL Medical Small 7B v2 plus RAG, on DiagnosisArena (915 held-out cases).
- **Core thesis:** Accuracy under uncertainty is largely a **workflow** problem, not a parameter-count problem. A small model in a constrained multi-stage pipeline (extract → retrieve → candidates → quote-anchored triangulation → guarded final decision) beats frontier generalists, and structured intermediate artifacts make reasoning auditable.
- **Key findings / claims:**
  - **60.14%** top-1 vs **23.99%** for the same 7B single-shot — **+36.15 pp** from workflow alone.
  - Beats Claude Sonnet 4.5 (**50.44%**, +9.70 pp) and Gemini 3 Pro Preview (**50.97%**, +9.17 pp on partial eval).
  - Cost **$0.0072/case** (~24K tokens, ~24s on A100) vs Sonnet 4.5 $0.0110 and Gemini 3.1 Pro $0.0128.
  - The base 7B averages 88.2% on nine standard medical benchmarks but 23.99% on DiagnosisArena; a 32B vanilla model gets 22.19%.
  - Stages: fact lock-in, patient-level RAG (Semantic Scholar + a 200M+ record KB), pattern triggers, ~4 constrained candidates scored 1–10, quote-anchored evidence memo with an **exact-match quote filter**, and a final label that must match a candidate.
  - Deterministic inference (temperature 0, top_p 1.0); supportive steps degrade gracefully.
  - Dual LLM judges agree 86–87%; on 10 GPT-5.2 failures the agent fixed 8/10.
- **Concrete design rules for an orchestrator:**
  - **Separate extraction from inference**; downstream steps may only use a validated fact table.
  - Treat RAG as supportive; final commits must cite locked facts, not retrieval narratives.
  - Enforce **machine-checkable gates** between stages (bounded scores, dedup, quote verification).
  - Log stage artifacts and retrieval titles for reproducibility and failure attribution.
  - Prefer deterministic sampling plus schema repair when using small or fragile models.
- **Caveats / limits:**
  - Medical diagnosis domain; judges are LLMs.
  - Gemini 3 Pro Preview evaluated on 464/915 cases due to quota limits.

---

## Part 4 — Skills, instruction files, and memory

### Demystifying Agent Skills
- **Link:** https://arxiv.org/abs/2608.14036
- **Fetch status:** VERIFIED
- **What it is:** arXiv analysis (Jiang et al.; Princeton, Stanford, USC, JHU and others) of *when* SKILL.md-style skills help, via controlled experiments plus a trajectory taxonomy.
- **Core thesis:** Skills mainly **stabilize execution** (procedural anchoring), not inject missing facts. Success requires representation, retrieval, invocation, and adaptation as separate stages; aggregate pass rates hide failure modes.
- **Key findings / claims:**
  - 8,135 normalized trials; 238 open codes → 12 modes in 3 categories (taxonomy validation κ=0.952).
  - Skills vs workflow memory from the same trajectories: **+6.06 pp** (95% CI [+0.76, +11.36]); oracle success 61.9% skill vs 55.9% workflow vs 59.1% raw.
  - Mechanism labels: **procedural_anchor 65.7%** vs **knowledge_injection 4.5%**.
  - Execution-layer failures **23.5%** (skill) vs 37.3% (raw) vs 33.3% (workflow); environment failures fall to **0.2%** from 5.3%.
  - Workflow memory causes timeout/budget exhaustion 10.6% vs 1.7% raw and 4.4% skill — verbose traces are costly.
  - Skill misapplication appears: guidance misapplied or ignored **10.0%** with skills vs 0.8% raw.
  - Retrieval (SkillsBench, pools 5–100): embedding top-1 precision 88.3% → 76.9%; explicit selection 70.0% → 63.7%; **actual-use precision 29.6% → 3.3%** while downstream success rises slightly 36.4% → 39.3%.
  - Similar distractors hurt most (70.5% → 53.4% at k=100); invoking the exact ground-truth skill is neither necessary nor sufficient.
  - Matched Codex runs: skill peaks ~75–79% vs workflow ~37–45% on Terminal-Bench mixtures.
- **Concrete design rules for an orchestrator:**
  - Distill trajectories into compact procedural checklists (setup, tool order, verification), not raw logs.
  - Instrument the whole pipeline: retrieval precision, parseable invocation, verifier outcome — not end success alone.
  - Design routing to be hard-negative aware; semantic confusability matters more than pool size.
  - Expect invocation and adaptation failures even with the right skill present; add applicability gates and shallow-invocation detectors.
  - When swapping harness, prefer distilled SKILL.md over workflow traces.
- **Caveats / limits:**
  - Terminal/software benchmarks; different backbone in RQ4 than RQ1–3, so authors discourage cross-RQ absolute comparison.
  - Skills placed as environment resources, not always fully inlined.
  - Algorithmic/logic errors persist (~7–11%) regardless.

### Break It Down, Pass It On (cross-task skill transfer)
- **Link:** https://arxiv.org/abs/2608.20274
- **Fetch status:** VERIFIED
- **What it is:** arXiv study (Yiyang Feng et al., Stony Brook) on when induced skills help or hurt across tasks; code at https://github.com/Zesearch/skill-transfer-llm-agents.
- **Core thesis:** Cross-task transfer depends more on *how* skills are induced than on having memory at all. Subtask-level text skills balance specificity and abstractness; whole-task skills often become harmful distractors.
- **Key findings / claims:**
  - Controlled 2×2: induction level (task vs subtask) × format (text vs code); shared prompts; AppWorld, OfficeBench, KramaBench; 11 models.
  - Task-level + skills **lowers** average success vs no memory: **−1.2 pp** (text), **−4.1 pp** (code), up to −7.4 pp on one benchmark.
  - Subtask-level + skills **raises** it: **+1.9 pp** (text), +0.5 pp (code); 22.1% → **26.7%** for text subtask vs 20.9% task+text.
  - Text beats code at both levels (+2.9 pp subtask, +1.4 pp task).
  - Subtask-level with **no memory** already beats task-level (**24.8% vs 22.1%**) — decomposition alone helps.
  - **Skill utility = specificity × abstractness** (all-MiniLM-L6-v2, τ=0.1); neither factor alone predicts success; the product tracks success bins (14.0% → 24.5% task-level; 22.8% → 31.0% subtask-level across utility quintiles).
  - Spearman ρ +0.095 (task) and +0.075 (subtask) between retrieved utility and success (p<10⁻¹⁰).
  - Giving a task-level agent subtask-induced skills beats its own task-level skills on every benchmark.
- **Concrete design rules for an orchestrator:**
  - Delegate specialists per subtask boundary; induce and store one skill per subtask, not per full trajectory.
  - Prefer text workflow skills over code skills for cross-task reuse unless execution is truly identical.
  - Pre-flight skill libraries with utility scoring before injecting into context — no execution required.
  - Cap retrieval (top-k, similarity thresholds) and dedupe near-duplicate descriptions; memory can negative-transfer.
  - Use a planner/executor/summarizer loop so subtask context stays bounded while skills accumulate.
- **Caveats / limits:**
  - Tool/office/data-science sandboxes, not CARLA.
  - Utility metric is correlational; adversarial skill injection out of scope.
  - Weakest small models deferred out of main tables.

### Who Maintains Agent Skills?
- **Link:** https://arxiv.org/abs/2609.05677
- **Fetch status:** VERIFIED
- **What it is:** arXiv empirical study (Chen Shen and Estevam Hruschka, Megagon Labs) mining git histories of five public SKILL.md repositories (Oct 2025 – Jun 2026).
- **Core thesis:** Public agent-skill maintenance is a **human-governed, AI-assisted** loop under version control, not an autonomous pipeline. Automated curators should be measured against that real process, not synthetic evolution baselines.
- **Key findings / claims:**
  - Corpus: 873 commits, 143 `SKILL.md` files, 254 substantive post-creation edits.
  - **100%** of substantive edits authored or merged by named humans; 62% carry AI co-author trailers, with sharp org-level bimodality.
  - Maintenance is ~60% enhancement / ~38% corrective; dominant operations are content expansion (72) and factual correction (56).
  - 85% of edits touch instruction bodies; 56% touch embedded code; **consolidation/deprecation is only 4.3%** (11/254).
  - Median ~5 days between commits per skill; 32/120 skills grew more than 10% in resident tokens.
  - A pre-registered "rule-likeness" axis failed reliability (inter-LLM κ = −0.02).
  - Powered transfer test (13 skills, 143 tasks): maintained minus earliest quality Δ = **−0.09** on a 1–5 scale (95% CI [−0.28, +0.10]) — no evidence of average downstream benefit.
  - Cites human-authored skills at **74.5%** success vs **≤31.1%** for automated methods (endpoint comparison only).
- **Concrete design rules for an orchestrator:**
  - Route skill/instruction changes through human merge or release gates; autonomous edits are proposals.
  - Budget explicit **consolidation and retirement** — skills accrete by default.
  - Triage curator output by operation type (add vs fix), not edit size or AI-trailer presence.
  - Don't use commit failure provenance as primary supervision; trigger coding is unstable.
  - Evaluate automated curators by replay against human edit histories.
- **Caveats / limits:**
  - Purposive sample of five orgs; shares are descriptive, not population rates.
  - Labels are LLM-coded and shift substantially under cross-family recode.
  - The maintenance-benefit null is harness-specific.

### SkillAdam (Adam-style skill evolution)
- **Link:** https://arxiv.org/pdf/2609.08944
- **Fetch status:** VERIFIED
- **What it is:** arXiv preprint (2026) by Gaoyuan Li et al. (Renmin University of China + Tencent); optimizes Markdown skill documents for frozen GPT-5.5 / Claude Sonnet 4.5 agents.
- **Core thesis:** Self-evolving skills need optimizer state like **Adam**: an **Evolving Issue Tracker** (first-moment analogue) for stable direction plus a **volatility-driven edit budget** (second-moment analogue) to limit destructive wide edits when case-level improvements disagree.
- **Key findings / claims:**
  - Seven benchmarks: SearchQA, SpreadsheetBench, OfficeQA, DocVQA, LiveMath, ALFWorld, DeepPlanning (10 slices).
  - Short-horizon: **87.5 / 81.1 / 72.1 / 92.3 / 67.7** vs SkillOpt 87.3 / 80.7 / 72.1 / 91.2 / 66.9.
  - Long-horizon: ALFWorld **89.6%**; DeepPlanning average **28.3%** vs SkillOpt **21.7%** (+6.7 pp); DP-Travel **11.7% vs 1.7%**.
  - DeepPlanning optimization cost: **−67.3% tokens**, **−68.8% API requests** while gaining +6.7 pp.
  - Cross-model transfer to GPT-5.4-mini: average **67.8% vs 63.1%**; retention **81.3% vs 76.2%**.
  - Ablations: removing the edit budget drops DP-Avg 28.3 → 21.7; removing both mechanisms → **19.2%**.
  - Judge quality mean **3.88 vs 3.30** on a 1–5 scale.
- **Concrete design rules for an orchestrator:**
  - Maintain **persistent issue memory** (problem, status, prior fix attempts and outcomes) across optimization iterations.
  - Scale each patch by case-level improvement variance; shrink the edit budget when updates help some cases and hurt others.
  - Evaluate candidate and current skill on the **same mini-batch**; gate accepts with benchmark-specific metrics.
  - Initialize skills from trajectory batches, not one-shot authoring.
  - Treat skills as discrete parameters optimized by rollout feedback while the execution agent stays frozen.
- **Caveats / limits:**
  - Mostly no-harness direct-chat settings.
  - DeepPlanning uses a different backbone than the other benchmarks.
  - The Adam analogy is functional, not gradient-based; acceptance rules vary per benchmark.

### SkillGLoW (procedural-family skill library)
- **Link:** https://arxiv.org/pdf/2609.02217
- **Fetch status:** VERIFIED
- **What it is:** arXiv preprint (2026) by Ao Yan, Zhang Xin, Jiawei Du, Joey Tianyi Zhou (NUS + IAIC Singapore); **GLoW = Global–Local Weave** for continual skill libraries on heterogeneous long-horizon streams.
- **Core thesis:** One global skill doc over-generalizes and per-task pools don't transfer; the reusable unit is a **procedural family**. Local skills (per task, regenerated) feed consensus clustering → compression → global priors, committed only through a verifier-grounded gate. Runtime context = recalled prior ⊕ fresh local skill.
- **Key findings / claims:**
  - Terminal-Bench-Pro (32), SWE-bench Verified (20), ALFWorld (42), LiveMathematicianBench (53) × 3 models = 12 continual runs.
  - Global priors: **+17.2 pp** on hard tasks vs no-skill, **+18.0** with local regeneration; positive on all 12 runs (Wilcoxon p=0.000488).
  - Beats SkillOpt in **15/21** cells; SkillOpt wins mainly on ALFWorld where a shared action space makes a single doc sufficient.
  - Library is **3.6× smaller** than a per-task pool; base-only single doc averages +2.0 pp; flat retrieval **+5.0 pp** vs family consolidation **+11.2 pp**.
  - **Commit gate:** 19/26 accepts, 7 rejects; the gate preserved **+14.7 pp** vs **+9.6 pp** under auto-admission.
  - Transfer: ALFWorld valid_unseen (60 tasks) **73.9% → 83.9%**; SWE unseen **40.0% → 45.6%**.
  - Recall via Qwen3-Embedding-8B, cosine threshold **0.45**, fail-closed to the base prior.
- **Concrete design rules for an orchestrator:**
  - Store two layers: frozen **family priors** (procedure skeleton + failure modes) and ephemeral **local skills** from the current trajectory.
  - Cluster skill cards by **procedure signature**, not task topic text; use consensus clustering for stable K.
  - Commit library revisions only if deployed execution value beats the max of standing-library and no-skill anchors minus ε=0.02.
  - Do **not** append local skills to the long-term library; re-derive them each episode and update priors offline.
  - Prefer family granularity over one master instruction file or naive per-instance retrieval.
- **Caveats / limits:**
  - Small fixed task sets (32–53 per benchmark), not open-ended traffic.
  - The gate uses soft metrics while headlines emphasize hard success.
  - Cross-domain prior survival and cross-model library handoff untested.

### SkillGenBench
- **Link:** https://arxiv.org/abs/2605.18693
- **Fetch status:** VERIFIED
- **What it is:** arXiv benchmark (Zhou et al., QuantaAlpha and others) isolating **skill generation** from execution; 187 tasks; https://github.com/QuantaAlpha/SkillGenBench.
- **Core thesis:** Skill quality must be evaluated as a **generator → artifact → fixed executor** pipeline. Self-generated skills are often worse than no skill, and task-agnostic library distillation is especially hard.
- **Key findings / claims:**
  - Two regimes: task-conditioned (skill written after the task is known) vs task-agnostic (library before hidden tasks); sources are code repos or long documents.
  - pass@3 with a fixed MiniMax-2.5 executor, 1800s/instance: best average **SkillSeekers 14.4% (code repo) / 25.0% (doc)** vs **No Skill 13.8% / 23.4%**.
  - A naive prompt can beat heavier pipelines on weak backbones; gains depend on generator × backbone × source interaction.
  - Code repo tasks 10.8–14.4% vs doc 21.4–25.0% — recovering implicit repo structure is harder.
  - Task-agnostic generation often underperforms task-conditioned and sometimes no-skill (negative transfer from plausible but wrong procedures).
  - **Static completeness ≠ executability**: SkillNet scores highest statically (59.1) but SkillSeekers (44.6 static) wins dynamically.
  - Failure taxonomy: code repo → runtime/dependency (53%); code doc → interface/schema (85%); domain docs → state/rule (44%) and numeric/formula (37%).
  - Generation budget helps up to ~24K–64K tokens, then saturates.
- **Concrete design rules for an orchestrator:**
  - Split the **authoring agent** (distill skill from repo/docs) from the **runtime agent** (execute under a pinned harness), and benchmark curators the same way.
  - Prefer task-conditioned synthesis for one-off scenarios; treat org-wide libraries as high-risk without held-out verification.
  - Require deterministic execution checks before promoting a generated skill to a shared registry.
  - Tune generators per source type: repo skills need env/dependency grounding, doc skills need contract/schema fidelity.
  - Use static rubrics only as diagnostics; pass@execution is the gate.
- **Caveats / limits:**
  - 187 constructed tasks, not CARLA-specific.
  - All dynamic evaluation uses one executor model.
  - Pipeline-heavy task construction with partial human verification.

---

## Part 5 — Tools, protocols, and multi-agent evaluation

### PHMForge (MCP industrial agent benchmark)
- **Link:** https://arxiv.org/pdf/2604.01532
- **Fetch status:** VERIFIED
- **What it is:** arXiv preprint (2026) by Yusheng Li et al. (Columbia, IBM, Georgia Tech); **PHMForge** benchmark for Prognostics and Health Management agents over MCP.
- **Core thesis:** Industrial agent evaluation must separate **protocol fluency**, **instrumentation quality**, and **tool retrieval** from domain reasoning. PHMForge uses 39 MCP tools wrapping real PHM algorithms on 99 SME-authored scenarios with deterministic verifiers and a trajectory-level failure taxonomy.
- **Key findings / claims:**
  - 99 scenarios, 39 tools, three MCP servers (Prognostics, Maintenance, Battery Prognostics with 17 tools).
  - Strongest: Claude Code + Opus 4.6 → **80.8% pass@1**, roughly 4.2–20.4 pp below the ~85% unsupervised deployment threshold cited.
  - ReAct + Llama 4 Maverick reaches 80.0% on a 25-scenario stratified subset; **orchestration errors dominate** failures — frontier models call tools better than they sequence them.
  - **Unknown-Tools mode: −21.3 pp pass@1** when agents must discover datasets and tools.
  - MCP vs text-RAG ablation (Li-ion, Opus 4.6): RUL pass-all-3 **100% → 20%**; mean pass@1 **80.6% → 48.6%** on operator queries (p=0.002).
  - Removing domain MCP tools: **80.8% → 25%** completion; cross-equipment transfer **84.1% → 42.7%**.
  - Inter-annotator agreement Krippendorff's α 0.74–0.82; LLM judge vs human α=0.61 (rejected for canonical scoring).
  - Full-suite cost about **$20–$50** API per (framework, model).
- **Concrete design rules for an orchestrator:**
  - Expose tools via MCP with **algorithm-grounded implementations**, not stubs, so failures attribute to reasoning.
  - Evaluate **tool retrieval** separately from tool invocation (tools-provided vs unknown-tools modes).
  - Log trajectory-level categories: reasoning, tool-invocation, orchestration, plus sequencing accuracy.
  - Use **pass-all-3** consistency for safety-critical settings, not pass@1 alone.
  - Prefer executable tool chains over RAG-over-telemetry when tasks require numeric computation.
- **Caveats / limits:**
  - Scenario authors and tool authors overlap — Goodhart/ceiling risk.
  - The battery subset lacks dual-rater agreement; some categories rely on threshold judgments.
  - MCP round-trips add latency and tokens; the frontier evaluation used a manual harness.

### COMPACT social intelligence arena
- **Link:** https://arxiv.org/pdf/2604.08727
- **Fetch status:** VERIFIED
- **What it is:** Shoresh, Kraus, Loewenstein (Hebrew University, Bar-Ilan, Safra Center) study of LLM social intelligence in mixed cooperative-competitive games via the **Communicate–Predict–Act (COMPACT)** protocol.
- **Core thesis:** Social competence in multi-agent settings is measurable beyond a single Elo scalar. Forcing communicate → predict others' actions → act yields traces that decompose into socio-cognitive metrics, and those metrics predict outcomes better than identity alone. Communication is essential — without it, differentiation collapses.
- **Key findings / claims:**
  - 8 models (24B–1T), 5 games × 4 player counts × 2 framings → **928 games**.
  - Global Elo spread 1420–1603 (GPT-5 top at 1603); global Elo ROC-AUC **0.67**, per-game 0.69, latent multi-factor 0.67–0.70.
  - Socio-cognitive logistic model ROC-AUC **0.75** (fixed weights) and **0.82** (per-game weights).
  - **Influence** and **predictability/transparency** rank highest in feature importance; Theory-of-Mind prediction accuracy and planning rank lower; amenability is negative.
  - Intra-agent metric correlation ~0.28 across game categories vs inter-agent ~0.007.
  - Without communication, performance differences largely wash out.
  - The lowest-Elo agent still beats the highest in ~25% of pairwise matchups.
- **Concrete design rules for an orchestrator:**
  - Add an explicit **communication phase** before action in multi-agent flows, not only tool calls.
  - Log **predictions of peer behavior** to measure coordination quality and calibrate delegation.
  - Score agents on **influence and clarity of intent**, not only planning depth.
  - Treat social skill as multi-dimensional; avoid a single scalar for specialist routing.
  - Use dyadic metrics when assigning negotiator vs executor roles.
- **Caveats / limits:**
  - Influence/planning/learning partly scored by an LLM judge.
  - Synthetic games, no human players in the main experiments.

---

## Part 6 — Exploration, ideation, and self-design behavior

> These four sources are the least directly applicable to orchestration plumbing, but they carry one transferable warning: **agents explore narrowly unless the harness forces breadth**, and **static evaluation hides the differences that matter once tools are live**.

### AgentIdeaBench (static vs active scientific ideation)
- **Link:** https://arxiv.org/pdf/2609.07611
- **Fetch status:** VERIFIED
- **What it is:** HKUST + NVIDIA benchmark (Mo, Zheng, Song, See et al.) comparing **Static** (curated papers) vs **Active** (Semantic Scholar SEARCH/FETCH with a 10-call budget) ideation across 33 matched LLMs, 40 densely scored subfields, 5 disciplines, with literature-verified critics.
- **Core thesis:** Static one-pass synthesis saturates at the frontier and mis-measures agentic ability. Active exploration exposes ~2× faster improvement against model cutoff, 4.4× between-model variance, and capability-gated gains concentrated in feasibility and clarity, not originality.
- **Key findings / claims:**
  - Active improves **+1.16/year** vs Static **+0.54/year** on the knowledge-cutoff axis (~2.1× slope).
  - Top-8 Static models span **0.39** points; the same models span **1.39** under Active.
  - Mean Active−Static **+0.34**; 19/28 models improve; weakest quartile **−0.18**, strongest **+0.76** (r = +0.69 with static ability).
  - Per-dimension: feasibility **+1.21**, clarity +0.63, specificity +0.58, originality **−0.14** (not significant).
  - Replay control: Replay−Static +0.08 (n.s.) but Active−Replay **+0.26** — process and interaction dominate passive refeed.
  - Search budget chosen from a sweep of {1,2,5,10,15,20}; most plateau between 5 and 10 calls.
- **Concrete design rules for an orchestrator:**
  - Benchmark orchestrators with **agent-controlled retrieval**, not pre-curated context packs.
  - **Match tool budgets to model tier** — weak models can lose under active tool use.
  - Separate grounding metrics (feasibility, clarity) from novelty metrics.
  - Use **replay ablations** to test whether gains come from process or content.
- **Caveats / limits:**
  - Active bundles retrieval, multi-turn behavior, and tool competence together.
  - Scores come from LLM critics anchored to landmark papers.

### When AI Designs AI (algorithmic design spaces)
- **Link:** https://arxiv.org/pdf/2608.17471
- **Fetch status:** VERIFIED
- **What it is:** Yang, Yang, Peng, Luo, Gao, Kan, Zhan (ICT CAS / BenchCouncil / Northwestern) empirical study mapping human vs agent-designed ML methods into task-specific design spaces (6 tasks, 327 human references, 72 agent×task×reference configs).
- **Core thesis:** Agents sometimes hit human SOTA but rarely explore beyond human-derived algorithmic coordinates. Wins are sparse and task-specific; design is mostly recombination, with little external literature search despite tool access.
- **Key findings / claims:**
  - **10/72** configs meet or exceed human SOTA, on only 3/6 tasks; 8/10 wins on one dataset.
  - **45.3%** of agent methods are Hamming distance 0 from some human method; **73.7%** within one module; **96.8% in-space**, 3.2% out-of-space.
  - **95.3%** of module choices reuse values seen in human references; only 4.7% are new.
  - Median **3.5** distinct coordinates explored despite up to 10 iterations; top-5 coordinates hold 59.7% of methods.
  - 88.0% of module choices in SOTA-reaching runs use human-observed values; **all 10** SOTA configs use ensemble prediction.
  - Prepared references: 20/36 improve, 15/36 hurt; only **5.4%** of provided references were accessed; only 2/60 configs did a task-specific web search.
- **Concrete design rules for an orchestrator:**
  - Represent agent outputs in an explicit **module coordinate space** for audit, not just final metrics.
  - Force **literature/tool exploration checkpoints** — agents default to pretraining priors and ensemble templates.
  - Measure **exploration breadth** (distinct coordinates), not only best-of-N performance.
  - Treat reference bundles as optional and require citation/use logging.
- **Caveats / limits:**
  - Six ML engineering tasks; design spaces are human-constructed, which bounds the out-of-space interpretation.
  - A more exploratory baseline (MLEvolve) roams further but lands far from human methods.

### IDEAgent (quality–diversity ideation search)
- **Link:** https://arxiv.org/pdf/2607.22375
- **Fetch status:** VERIFIED
- **What it is:** NTU DeCLaRe Lab (Gumma, Majumder, Sinhahajari, Poria; under review Aug 2026) multi-agent framework treating ideation as **Quality–Diversity search**, with a **Yield** metric over 32 CS topics in 8 domains.
- **Core thesis:** Ideation should optimize a **portfolio** of ideas that are simultaneously non-obvious, sound, clear, and pairwise diverse. Lineages, archives (active/historical/rejected), repair and refinement, and signature-based diversity judging beat sequential memory or one-shot shared-thought generation.
- **Key findings / claims:**
  - Yield(NB≥7, gate) **1.094** vs best baseline **0.281** (~3.89×); Yield(NB≥6) **2.312** vs 0.531 (~4.35×).
  - Topics reaching Yield≥1 at the strict gate: **27/32** vs 8/32; ≥2 ideas: 23/32 vs 11/32.
  - Budget B=10 seeds, archive capacity 10, up to K_aux=2 auxiliary drafts per seed (10–30 ideator calls).
  - Qualification gate: NB, S, C ≥ 60; diversity floor τ_D=60; repair margin δ=20; soundness panel of **5** judges.
  - **One-Shot baseline Yield = 0** at the gates despite high pairwise diversity — shared thinking contaminates quality.
  - Repair saved 28/30 near-miss lineages; refinement replaced the parent in 82% of 182 refined lineages.
- **Concrete design rules for an orchestrator:**
  - Optimize **Yield** (max clique under quality plus pairwise diversity thresholds), not mean single-item score.
  - Maintain active / historical / rejected-pattern archives with compact signatures for comparison.
  - Route near-misses through exactly one repair; refine qualified items with blinded parent-child checks.
  - Use sequential seeds with lightweight memory rather than full shared chain-of-thought across parallel branches.
  - Use a multi-judge panel (≥5) for disputed routing.
- **Caveats / limits:**
  - Proprietary judges; open models failed internal consistency in pilots.
  - CS topics only; hyperparameters not rigorously tuned.

### TasteGap (human vs LLM research-taste distributions)
- **Link:** https://arxiv.org/pdf/2607.01233
- **Fetch status:** VERIFIED
- **What it is:** Chen (Chicago), Zhao and Cohan (Yale) study of **IdeaLand/IdeaSeed**: 11,683 human papers vs 9 LLM families on the same reconstructed prior-work contexts, using a two-axis taste taxonomy (7 opportunity patterns × 7 method paradigms).
- **Core thesis:** LLM ideation is not just individually plausible but **distributionally narrow** relative to human papers — heavy bias toward bridge/framing motivations and synthesis/unification methods, lower normalized entropy — and thinking mode *sharpens* the template rather than broadening taste.
- **Key findings / claims:**
  - Human normalized entropy **0.926** (opportunity) / 0.920 (method) vs best LLM **0.758**; TVD vs human 0.348–0.521 on the opportunity axis.
  - Human **12.1%** "bridge" opportunities vs LLMs **47.1–64.2%**; human 5.1% synthesis methods vs LLMs 22.5–38.7%.
  - Thinking mode: Qwen3-8B bridge 49.7% → **71.1%**, synthesis 38.7% → 52.2%, TVD 0.382 → **0.590**.
  - Archetype verb "integrate": **34.2%** of model operations vs **2.35%** human (log-odds 3.07).
  - Cross-model idea similarity (0.8316) exceeds human-model similarity (~0.72–0.78).
  - Annotator κ 0.81–0.93 on a 150-paper calibration set; full-paper context *worsens* distributional match vs abstract-only.
- **Concrete design rules for an orchestrator:**
  - Monitor **label histograms** of proposed approaches, not only per-item rubric scores.
  - Penalize or resample default templates (bridge + synthesis) when move diversity matters.
  - Do not assume extended reasoning expands diversity — it can amplify defaults.
  - Condition generations on the same prior-work set when comparing options fairly.
- **Caveats / limits:**
  - Human "ideas" are reverse-engineered from published papers.
  - Large-scale taxonomy labeling is model-assisted, not fully human.

---

## Part 7 — Source index and retrieval status

| # | Source | Link | Status |
|---|---|---|---|
| 1 | GitHub Copilot agents.md lessons | https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/ | VERIFIED |
| 2 | Anthropic — Writing tools for agents | https://www.anthropic.com/engineering/writing-tools-for-agents | VERIFIED |
| 3 | Cursor — Agent best practices | https://cursor.com/blog/agent-best-practices | VERIFIED |
| 4 | Anthropic — Building effective agents | https://www.anthropic.com/engineering/building-effective-agents | VERIFIED |
| 5 | AutoDesign / PosterBench | https://arxiv.org/pdf/2608.13560 | VERIFIED |
| 6 | Hitchhiker's Guide to Agentic AI | https://arxiv.org/pdf/2606.24937 | **PARTIAL** |
| 7 | Agents All the Way Down | https://arxiv.org/pdf/2606.11869 | VERIFIED |
| 8 | QA → Task Completion survey | https://arxiv.org/pdf/2606.20683 | VERIFIED |
| 9 | PHMForge | https://arxiv.org/pdf/2604.01532 | VERIFIED |
| 10 | SkillAdam | https://arxiv.org/pdf/2609.08944 | VERIFIED |
| 11 | SkillGLoW | https://arxiv.org/pdf/2609.02217 | VERIFIED |
| 12 | Who Maintains Agent Skills? | https://arxiv.org/pdf/2609.05677 | VERIFIED |
| 13 | Break It Down, Pass It On | https://arxiv.org/pdf/2608.20274 | VERIFIED |
| 14 | Demystifying Agent Skills | https://arxiv.org/pdf/2608.14036 | VERIFIED |
| 15 | SkillGenBench | https://arxiv.org/pdf/2605.18693 | VERIFIED |
| 16 | CRAFT | https://arxiv.org/pdf/2607.22642 | VERIFIED |
| 17 | Plans Don't Persist | https://arxiv.org/abs/2606.22953 | VERIFIED (URL resolved by title search) |
| 18 | Planning in the LLM Era | https://arxiv.org/pdf/2605.21902 | VERIFIED |
| 19 | From Plan to Action | https://arxiv.org/abs/2604.12147 | VERIFIED |
| 20 | Self-Questioning Language Models | https://arxiv.org/pdf/2508.03682 | VERIFIED |
| 21 | DeepLens Diagnosis Agent | https://arxiv.org/pdf/2607.22555 | VERIFIED |
| 22 | Milkyway | https://arxiv.org/pdf/2604.15719 | VERIFIED |
| 23 | COMPACT social intelligence | https://arxiv.org/pdf/2604.08727 | VERIFIED |
| 24 | AgentIdeaBench | https://arxiv.org/pdf/2609.07611 | VERIFIED |
| 25 | When AI Designs AI | https://arxiv.org/pdf/2608.17471 | VERIFIED |
| 26 | IDEAgent | https://arxiv.org/pdf/2607.22375 | VERIFIED |
| 27 | TasteGap | https://arxiv.org/pdf/2607.01233 | VERIFIED |

### Appendix — Self-Questioning Language Models (training-side outlier)
- **Link:** https://arxiv.org/pdf/2508.03682
- **Fetch status:** VERIFIED
- **What it is:** arXiv preprint "Self-Questioning Language Models" (CMU, Deepak Pathak group); site self-questioning.github.io. Included for completeness — this is RL training research, not orchestration.
- **Core thesis:** LLMs can improve reasoning without curated Q/A data via **asymmetric self-play**: a proposer generates problems from a single topic prompt, a solver attempts them, both trained with RL using majority vote (small generator-verifier gap) or unit-test pass rate (large gap, coding). Proposer reward targets **Goldilocks difficulty**.
- **Key findings / claims:**
  - Only input is one topic prompt; no example problems or labels.
  - Solver reward is agreement with the majority of N samples; proposer reward is 1 iff the majority count is strictly between 0 and N.
  - Coding: proposer emits 5 unit tests; solver reward is fraction passed; proposer rewarded on strictly-partial pass rates.
  - Qwen2.5-3B-Instruct: multiplication **0.791 → 0.948** (+15.7 pts); linear equations **0.440 → 0.600** (+16 pts).
  - Qwen2.5-Coder-3B on a Codeforces subset: **0.320 → 0.391** (+7.1 pts).
  - **Proposer update frequency of 5 steps** worked best; never updating the proposer hurt coding badly.
  - Online one-at-a-time generation beat a pre-generated 6,400-question batch (less diversity).
  - Limitations acknowledged: prompt tuning still needed, no safety filter on generated questions, majority vote can reinforce systematic errors.
- **Concrete design rules for an orchestrator:**
  - Pair task-generating and task-solving roles with **asymmetric rewards** matched to verifiability (tests vs vote vs human gate).
  - Reward proposers for **calibrated difficulty**, not maximum hardness.
  - Prefer incremental curriculum generation over static bulk synthetic banks.
  - Use executable verifiers (pytest, scenario contract checks) where verification is cheaper than generation.
  - Update proposer policy slowly so solvers stabilize before difficulty ramps.
  - Treat consensus-only rewards as unsafe for safety-critical simulator work without external anchors.
- **Caveats / limits:**
  - Small Qwen models on math/code micro-domains.
  - Unsupervised rewards risk reinforcing errors.
  - Prompt engineering remains a manual bottleneck.

---

## Verification notes for the next agent

- **One source is not usable as cited:** the Hitchhiker's Guide (`2606.24937`) yielded no extractable body; only abstract-level scope is recorded. Re-fetch before citing any specific claim from it.
- **One link was title-only:** "Plans Don't Persist" had no URL in the request; it resolved to `arXiv 2606.22953`. Confirm that is the intended paper.
- **Everything else was retrieved and read.** No source was left as UNREACHABLE, and no numbers in this brief were inferred where retrieval failed.
- **Numbers are transcribed from the sources, not independently reproduced.** Cross-source comparisons (for example harness spread vs skill gain) mix benchmarks and models and should not be treated as controlled comparisons.
