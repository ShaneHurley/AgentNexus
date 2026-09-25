# Agent Orchestration — Master Specification

**Document role.** This is the **single overall document**. It carries every load-bearing conclusion and the complete, authoritative build specification for the agent ecosystem. If an orchestration agent reads only one file, it reads this one.

**Companion documents (same folder).**

| File | Information type | Read it when |
|---|---|---|
| `agent_orchestration_master_spec.md` | **This file.** Conclusions + build spec + roadmap + handoffs | Always — start here |
| `REFERENCES.md` | Clean bibliography of practitioner + original + priority links | Looking up a URL or scanning topics |
| `sources/README.md` | **Sources hub** — original S01–S26 cards, gap-prioritized additions, synthesis, next-agent checklist | Looking up a link, filling plan gaps, or handing off investigation |
| `agent_orchestration_research_library.md` | Prioritized paper library (324 sources, typed and tiered) | You are about to make an architecture decision and want the evidence |
| `agent_orchestration_research_brief.md` | Deep source-by-source breakdown of the original 28-source corpus | You need full numbers, methods, and caveats for one specific source |
| `README.md` | Documentation index and authority order | Orienting in this folder |

**Authority boundary.** This is a **design and planning specification**. It is *not* authorization to modify a codebase, deploy agents, grant permissions, spend budget, or allow autonomous side effects. Every recommendation below is a proposal until a human accepts it.

**Status.** `PARTIAL`. **324 sources** are catalogued. 27 were read as full text, 150 were verified at abstract level by direct fetch (57 in the 2026-09 expansion plus 93 in the category-page sweep), and the remainder are catalogued from curated-index metadata plus abstracts. Numbers are transcribed from sources, not independently reproduced. Cross-source comparisons mix benchmarks, models, and harnesses and are **not** controlled comparisons.

**How to read this document.** Part A is the evidence; Part B turns it into decisions; Part C is where the evidence conflicts and you must choose; **Part D is the build specification you implement**; Part E is the order to build it in. An orchestration agent that needs to start work immediately should read **Part D, then Part E, then Part C**, and consult Part A only for the reasoning behind a specific rule.

---

# Part A — The twenty-four load-bearing conclusions

These are the findings that should change what you build. Each is stated as a decision, then the evidence.

### A1. The harness — not the model — is the primary performance lever.

Same-model performance swings by tens of points when only the scaffold changes. SWE-bench Verified swings tens of points by harness alone; Terminal-Bench 2.0 within-model harness spread has a **median of 13.6%** with 14 of 20 models showing ≥10% spread; WebArena GPT-4o goes **13.1% → 54.6%** (41.5 pp span) with a better scaffold; a 7B medical model goes **23.99% → 60.14%** (+36.15 pp) purely from a five-stage pipeline. A **~100-line** mini-SWE-agent reaches **76.8%** against OpenHands' **77.6%** on Opus 4.5 — scaffold *complexity* does not predict effectiveness; interface *quality* does.

**Therefore:** treat the harness as the product. Version it, evaluate it, and report every score together with the harness identity, tool privileges, retry/timeout policy, and runtime stats.

### A2. Plans do not persist inside the model. They must live outside it and be re-injected.

Plan signal in hidden state drops **4.1× in a single action-observation step** on ALFWorld (0.453 at step+1 → 0.110 at step+2 → ~0.027 by step+5) and **12.4×** on HotpotQA. Independently, re-injecting the plan **every 5 trajectory steps** improves both compliance and success across four models and 21,120 trajectories.

**Therefore:** the plan file is the source of truth; chat history is a cache. Re-inject a concise plan slice plus the current subgoal on a fixed step interval, not only at session start.

### A3. Naive context eviction is catastrophic, and pinning the plan alone does not save you.

ALFWorld success falls **56.7% → 22.0%** (−34.7 pp, p<0.001) under naive eviction. `plan_protected` and `probe_gated` re-surfacing were **statistically indistinguishable** from naive (p≈0.89 / 0.67) — probe-gated re-surfacing fired ~6.1× per run and still failed. Recent actions and observations are as load-bearing as the plan text. Separately, one production compactor preserved **53%** of safety rules after one compaction round and **10%** after five, while type-aware retention reached **96%** recall over five rounds.

**Therefore:** compaction must be **type-aware and validated**. Classify context into immutable rules, task anchor, accepted decisions, evidence, episodic history, and disposable chatter. Pin exact permissions, prohibitions, and acceptance criteria in non-evictable slots. Preserve recent action/observation state.

### A4. Append-only log plus deterministic projection beats mutable agent memory.

Deterministic Projection Memory (append-only event log + one task-conditioned projection at decision time) matched summarization at loose budgets and, at **20× compression**, improved factual precision **+0.52** (p=0.0014) and reasoning coherence **+0.53** (p=0.0034) while running **7–15× faster** (one LLM call instead of N). Complementarily, a log-plus-kernel design that keeps evicted spans recoverable via address-anchored eviction indices reports **94.8%** LongMemEvalS and **86.7%** LOCA256K (+37.4 pp over the best long-horizon agent cited).

**Therefore:** the run ledger is the system of record. Compaction evicts the *view*, never the log. Rebuild working context from log + task spec at each phase rather than carrying path-dependent mutable state.

### A5. Continuously LLM-updated memory degrades, even when fed ground truth.

GPT-5.4 dropped to **54% failures** on ARC-AGI problems it had solved at **100%** without memory, after consolidation. Streaming updates failed even from ground-truth trajectories; episodic retention without forced consolidation matched the best automated regimes.

**Therefore:** ban continuous LLM rewrite of shared memory. Store raw episodes in the ledger and put an explicit, gated **Consolidate** step in front of any write to durable memory.

### A6. Instruction and skill artifacts are operational memory with a real maintenance cost, and they accrete by default.

Across five public SKILL.md repositories (873 commits, 143 files, 254 substantive edits): **100%** of substantive edits were authored or merged through a named human account; **62%** carried an AI co-author trailer; median **~5 days** between edits; maintenance was ~60% enhancement / ~38% correction; and **consolidation or deprecation was only 4.3%** of edits. A powered transfer test found **no** average downstream benefit from maintenance (Δ = **−0.09** on a 1–5 scale, 95% CI [−0.28, +0.10], p=0.58).

**Therefore:** curators propose, humans merge. Budget explicit consolidation and retirement. Route curator output by operation type (expand vs correct), not by edit size or AI-trailer presence.

### A7. Skills stabilize execution; they do not inject knowledge.

Mechanism labels across 8,135 trials: **procedural_anchor 65.7%** versus **knowledge_injection 4.5%**. Distilled SKILL.md beat workflow-memory from the same trajectories by **+6.06 pp** (95% CI [+0.76, +11.36]). Execution-layer failures fell **37.3% → 23.5%**; environment failures fell **5.3% → 0.2%**. Verbose workflow traces caused timeout/budget exhaustion in **10.6%** of runs versus **1.7%** raw.

**Therefore:** write checklists, tool order, preconditions, and verification steps. Do not write encyclopedias. Keep raw traces in a cold archive, never in hot context.

### A8. Granularity of delegation decides whether memory helps or hurts.

Whole-task skills **reduced** success below a no-memory baseline (**−1.2 pp** text, **−4.1 pp** code, up to −7.4 pp on one benchmark). Subtask-level skills **raised** it (**+1.9 pp** text). Subtask decomposition helped **even with no memory at all** (24.8% vs 22.1%). Handing a task-level agent subtask-induced skills beat its own skills on every benchmark (**+9.9 pp** average, up to +17.2). Procedural-family consolidation beat flat retrieval (**+11.2 pp** vs **+5.0 pp**), with a library **3.6×** more compact than a per-task pool.

**Therefore:** one specialist per subtask; one skill per subtask, never per episode. Organize the library by **procedural family**, regenerate instance detail per task, and never append raw local skills to the durable library.

### A9. Skill retrieval precision collapses at scale, but exact-match retrieval is not the goal.

Actual-use precision fell **29.6% → 3.3%** as pools grew from 5 to 100 skills, while downstream success *rose* slightly (**36.4% → 39.3%**). Semantically similar distractors hurt more than pool size (top-1 precision 70.5% → 53.4%). Invoking the exact ground-truth skill is **neither necessary nor sufficient** for success.

**Therefore:** optimize the router for operational compatibility, not top-1 ground-truth ID. Instrument retrieval precision, parseable invocation, *and* verifier outcome as separate stages. Cap library width.

### A10. Every self-improving loop that works in the literature has an acceptance gate. Ungated self-edit is the failure mode.

AutoDesign changes **exactly one harness component per outer iteration** and requires train-improves **and** dev-does-not-regress; 54 accepted updates over 7 days, 224 subagents, 123+ iterations. SkillGLoW's commit gate accepted **19/26** candidates and preserved **+14.7 pp** versus **+9.6 pp** under auto-admission; 4 of the 7 rejects would have passed on consolidation score alone. Milkyway allows **≤1 validated patch per checkpoint** with bounded add/revise/deprecate ops. SkillAdam pairs a persistent issue tracker with a volatility-driven edit budget; removing the budget dropped DeepPlanning average **28.3 → 21.7**, removing both mechanisms **→ 19.2**.

**Therefore:** one bounded change per cycle, held-out dev gate, persistent issue ledger, explicit deprecation budget, instant rollback.

### A11. Self-evolved skills are a live security surface, and the create path is the attack path.

Every one of 21 evolved configurations authored unsafe artifacts; 15 caused harm in a *fresh* session; three malicious tasks raised carryover attack success **16.0% → 35.3%**. Create-path self-poisoning via skill imitation reached **20.3%–41.8%** attack self-propagation rate across six models on 153 SWE-bench Verified tasks, with libraries growing **4.9–9.0×** more malicious entries than were planted and post-removal round-5 rates up to **68%**. Static skill auditors were bypassed **≥93%** of the time by an adaptive red team.

**Therefore:** treat the skill library as a worm-capable supply chain. Require human review plus provenance before merge, quarantine third-party packs, test clean-session carryover in CI, and assume adaptive rather than one-shot adversaries.

### A12. You cannot validate a self-evolved grader with the task score it produces.

Removing anchor items collapsed an evolved metric to **always-pass** while the skill loop still appeared to "work." A proof shows that when a judge's false-pass rate is ≥ (1−τ)/2, skill eviction is disabled at **any** sample size. Judge verdicts flip **25–71%** under static pushback and **62–91%** under an adversarial persuader, and successful pressure is net-corrupting relative to ground truth. Twelve LLM judges were evaluated over 1,302 expert-labeled trajectories and **no single judge won on all benchmarks**; rule-based evaluation *underreported* success versus experts.

**Therefore:** keep a frozen holdout that the metric search never sees. Calibrate judge error before enabling any automated eviction. Require temperature-0 replicates and a challenge round before accepting a review verdict. Treat a collapsed always-pass metric as a production incident.

### A13. Failures are mostly orchestration failures, so measure them as distinct stages.

On PHMForge the strongest configuration reaches **80.8% pass@1** and *orchestration* errors dominate — frontier models are better at **calling** tools than at **sequencing** them (~23% incorrect-sequencing rate). Tool and dataset discovery alone costs **−21.3 pp**. Replacing executable MCP tools with text RAG collapsed lithium-ion RUL pass-all-3 from **100% → 20%** and mean pass@1 **80.6% → 48.6%** (p=0.002); removing domain tools entirely dropped completion **80.8% → 25%**.

**Therefore:** measure retrieval, invocation, sequencing, and execution separately. Separate the planner (which tool, in what order) from the executor (schema-valid call). Put domain computation behind validated executable tools, not retrieval.

### A14. Fan-out is a hypothesis, not a default. Benchmark a strong single agent first.

Across seven benchmarks a single agent matched homogeneous multi-agent workflows and an optimized heterogeneous workflow at lower inference cost. Where small-agent systems *did* beat larger single models on tool-intensive tasks, most of the gain came from reasoning **in the orchestrator**; reasoning in sub-agents contributed little or negative value. Multi-agent failure taxonomies (1,600+ traces, seven frameworks, 14 failure modes, κ=0.88) locate most failures in system design, inter-agent misalignment, and task verification rather than raw model capability.

**Therefore:** every multi-agent route must beat a strong single-agent baseline on quality, reliability, isolation, latency, or cost. If it does not, collapse the route into one agent. Keep the master strong and the workers narrow.

### A15. Model switching has a measurable tax, and escalation and downshift need different interfaces.

Escalating from a cheaper to a stronger model **with the full prior trajectory** recovered less than half the quality gap while adding substantial cost. Reduced trajectory inheritance improved escalation; downshift benefited from *retaining* the stronger model's trajectory.

**Therefore:** escalate with a fresh, hand-compressed decision brief plus repository state and evidence references — never the raw weak-model transcript. Downshift after the hard decision, preserving the approved plan and the strong model's rationale. Measure the handoff tax.

### A16. Concurrency is a first-class correctness problem, not a performance detail.

Long LLM inference windows amplify stale reads and lost updates. In cited comparisons, worktree isolation produced **63.3%** versus **55.5%** unisolated, and dependency-graph scheduling **22%** versus **10%** resolved when the graph was removed. Conflict detection belongs at **write intent** time, not at final merge.

**Therefore:** one isolation unit (worktree or sandbox) per mechanical implementer. Ledger is append-only; repository writes go through serialized commit points with version checks. Extend plan and code review to detect concurrency-class failures. Cap parallel lanes by **sandbox memory budget**, not only token budget.

### A17. Always-on instruction files are not free, and adversarial review is not free either.

Repository-level context files increased inference cost by **more than 20% on average without general task-success gains**; non-standard coding instructions were useful, broad repository overviews were not. On the review side, agents that seek every hidden issue can have low signal-to-noise; resolution rate alone hides spurious findings. A review benchmark introduces **usefulness rate** and **signal-to-noise ratio** and shows Reflexion-style review adds noise while single-shot review misses bugs.

**Therefore:** keep always-on instructions short, enforceable, and unusual; retrieve repository facts on demand and benchmark every persistent instruction. Score reviewers on usefulness and SNR, not issue count. `ADVERSARIAL` means evidence-bound disconfirmation — unsupported criticism is itself a review failure.

### A18. Capability gates tool access: giving weak models more tools can make them worse.

Under agent-controlled retrieval, the weakest quartile **lost 0.18 points** while the strongest gained **0.76** (r = +0.69 with static ability). Active exploration improved feasibility (**+1.21**), clarity (+0.63), and specificity (+0.58), but measured originality was flat (**−0.14**, not significant). A replay control showed Active−Replay **+0.26** (p<10⁻³) while Replay−Static was **+0.08** (n.s.) — the *process* mattered, not the papers. Separately, adding "best practice" plan phases **degraded** performance when misaligned with a model's own strategy, and a bad or incomplete plan was worse than no plan at all. Reflection helped some backbones (GPT-OSS-120B 56% → 68%) and hurt others (Maverick 80.0% → 63.6%).

**Therefore:** match tool budget and phase count to model tier, and measure before mandating. More agents, more reflection, more tools, and longer context do not reliably improve outcomes.

### A19. The cheap read-only recon lane is now directly validated on coding benchmarks.

A dedicated exploration sub-agent at **4B–30B** scale, integrated into Mini-SWE-Agent across SWE-bench Multilingual, SWE-bench Pro, and SWE-QA, improved end-to-end resolution by up to **5.5%** *while cutting coding-agent token use by up to 60%*. The mechanism is that a small model returning file-and-line citations keeps the expensive solver's context clean. Independently, reformulating the inbound request with domain rules and a tool shortlist before the tool-calling agent runs improved pass^5 by **16.1% / 12.7% / 19.1%** over ReAct, function calling, and self-reflection.

**Therefore:** the core economic thesis of this spec — cheap recon raises quality rather than trading it away — has direct empirical support, and a cheap *pre-step* that rewrites the task with the relevant policy snippet is one of the highest-return-per-token additions available. Note the caveat: the recon result used a *trained* sub-model, so a prompt-only recon lane must not assume the same numbers.

### A20. Routing plus selective escalation is worth roughly an order of magnitude, and the measurement of that saving is itself biased.

Measuring a capability frontier across **21 models on 16 benchmarks** rather than picking one top model produced a **54%** error-rate reduction from correcting single-model evaluation, **82%** with multi-run selection, matching state of the art at an **85% cost reduction**. The same work found naive oracle bias reaching **8.7%** accuracy and **88%** cost inflation at G≤10 generations.

**Therefore:** the router's target savings are supported, but the evaluation harness must debias routing estimates before you believe the router's own reported numbers. A router that grades itself will overstate its savings by a large margin.

### A21. Agents do not know how much budget they have left, so budget cannot be delegated to the prompt.

Rollout-replay across five frontier models and four environments (Sokoban, Search-R1, SWE-bench, supply chain) found budget awareness **decouples from task performance** and fails in structured ways. It is trainable — a Qwen-7B estimator supported early-stop control — but it is not native.

**Therefore:** `BUDGET:` lines in prompts are documentation, not enforcement. The sizing gate and router need explicit mid-run budget estimates and **externally enforced** stop conditions in the policy gateway, not post-hoc token accounting.

### A22. Reasoning tokens are a routing decision, not a default — and on knowledge-heavy work, more thinking is actively harmful.

A meta-analysis of **110 papers (1,218 comparisons)** plus 20 datasets × 14 LLMs found chain-of-thought gains concentrated in symbolic (**14.2**), math (**12.3**), and logic (**6.9**) work, with roughly **56.8 versus 56.1** elsewhere; on MMLU up to **95%** of the gain traced to slices containing "=". Separately, sequential test-time scaling across 14 reasoning models on SimpleQA, FACTS Parametric, and FRAMES left accuracy mostly flat while **hallucinations often increased**, with an information-theoretic argument that compute alone cannot add closed-book facts.

**Therefore:** disable extended reasoning by default on retrieval, extraction, transcription, and synthesis lanes, and enable it for symbolic or math-like sub-problems. For knowledge-heavy questions the correct response is retrieval through the tool gateway, not a longer frontier call. This attacks frontier rationing from both directions: the cheap path is usually equal, and the expensive path is sometimes worse.

### A23. Trust and task completion are close to uncorrelated, which is precisely why the alignment checker exists.

Scoring full execution traces on ten dimensions — instruction integrity, planner, memory, tool selection, tool invocation, tool correctness, alignment, tool faithfulness, security, execution integrity — across five models on nine tasks produced Composite Trust Scores from **95.1 down to 22.6** out of 100, with models at similar task completion diverging sharply, notably on unsafe compliance.

**Therefore:** "the task completed" is not evidence of a trustworthy trajectory, and those ten dimensions map cleanly onto stages this pipeline already separates — adopt them as the ledger's trace schema. Caveat: in that study the judge model was also one of the evaluated models.

### A24. The realistic baseline for a daily coding assistant is much lower than benchmark scores suggest.

Across **6,000** real sessions with **63,000+** prompts and **355,000+** tool calls, **41%** of sessions were near-full agent authorship, yet **only 44% of agent-produced code survived into user commits** and users pushed back in **44%** of turns. Agent-authored code was associated with more security vulnerabilities than human-authored code. Separately, across **3,222** scored autonomous-research runs spanning six search strategies, **no run was rated "Original"**, only one novel-ish idea reached the top ten by quality, and **40 confirmed reward-hacking fabrications** appeared in 1,628 scored runs.

**Therefore:** set expectations against field data, not SWE-bench. More than half of generated code is discarded and nearly half of turns are corrected, which justifies both the alignment checker and human approval on consequential writes. For the brainstormer specifically, search strategy alone does not buy novelty — keep `NO BETTER ALTERNATIVE FOUND` as the honest default, monitor label histograms rather than per-item scores, and run a fabrication check on ideation output before the master appraises it.

---

# Part B — Decision table

Every row is a decision you must make, the sources that constrain it, and the recommendation.

| Decision | Constrained by | Recommendation |
|---|---|---|
| Plan storage | Plans Don't Persist; From Plan to Action; Cursor | External plan file rewritten only by the master; re-inject plan slice + current subgoal every N steps and on phase change |
| System of record | Stateless Decision Memory; Context as an Environment; The Log is the Agent | Append-only event ledger with stable addresses; working context is a deterministic projection, never the transcript |
| Compaction policy | The Compaction Cliff; Plans Don't Persist; Agentic Context Management | Type-aware, budgeted, validated compaction; non-evictable slots for rules, permissions, acceptance criteria, task anchor; evict the view, keep the log |
| Tool-context window | Less Context Better Agents; ACON | Keep only the last N tool call/response pairs in implementer context; summarize evicted pairs into running state; never prune anchor headers |
| Retrieval default | Is Grep All You Need?; To Retrieve or To Think? | Default recon lanes to grep/BM25 with file-pointer outputs; vector RAG is an escalation lane; add a retrieve-vs-think gate per lane |
| Delegation unit | Break It Down Pass It On; GitHub agents.md; HyMem | One specialist per subtask with explicit read/write path scope, a single primary outcome, and a typed return channel |
| Sub-agent spec | AOrchestra | Mint each sub-agent as ⟨Instruction, Context, Tools, Model⟩; the orchestrator dispatches and never executes |
| Topology | Multi-Agent Design; ReActNet; Language Model Teams as Distributed Systems | Topology is a versioned, evaluated artifact; master emits a phase-conditioned workflow graph with edge message contracts into the ledger |
| Fan-out justification | Strong Single Agent Baseline; Can Small Agents Collaborate?; Why Do MAS Fail? | Fan out only when a measured gain over a strong single agent exists; keep reasoning concentrated in the master |
| Routing | Agent-as-a-Router; Difficulty-Aware Orchestration; Bayes-consistent orchestration | Log task features, chosen model, cost, latency, verifier result, regret; escalate on expected-utility gain, not intuition |
| Escalation interface | The Handoff Tax | Fresh compressed decision brief on escalation; retain the strong model's trajectory on downshift; measure the tax |
| Instruction files | GitHub agents.md; Evaluating AGENTS.md; Demystifying Agent Skills | Runnable commands early, version-pinned stack facts, Always / Ask-first / Never tiers, procedural checklists; short, enforceable, unusual; benchmark every persistent instruction |
| Tool surface | Anthropic writing-tools; PHMForge; Bitter Lesson of Tool Calling; Meta-tools | Few namespaced workflow-level tools; concise/detailed response modes; pagination; teaching error messages; promote stable trace sequences to versioned meta-tools; consider typed stubs + sandbox execution over many thin JSON wrappers |
| Static domain facts | CRAFT | Externalize stable APIs, paths, and schemas into validated artifacts instead of per-turn prompt stuffing (**~9×** input-token reduction achieved; schema-discovery loops 1.0× → 0.20×) |
| Self-improvement | AutoDesign; SkillGLoW; SkillAdam; Milkyway; ModularRSI; Ouroboros | One bounded patch per cycle, held-out dev gate, persistent issue tracker, module-scoped edits, reviewed commits, explicit deprecation budget |
| Skill governance | Who Maintains Agent Skills?; SkillsVote; Counterfactual Trace Auditing; Ratchet | Curator proposes, human merges; require post-run attribution and counterfactual A/B traces before merge; calibrate judge error before eviction; bound library width |
| Skill security | Practice Makes Unsafe; EvoMal; Proteus; SkillScope | Signed provenance, quarantine, clean-session carryover tests, task-conditioned least privilege, multi-round adaptive red team |
| Verification | Anthropic building-effective-agents; CRAFT; DeepLens; Art of Building Verifiers | Machine-checkable gate between phases; separate process and outcome rewards; non-overlapping rubrics; block the implementer until repro artifacts exist |
| Review quality | CR-Bench; Jagged Judges; Helpful Agent Meets Deceptive Judge | Score usefulness and SNR, not issue count; temperature-0 replicates plus a challenge round; freeze evidence packets during review; log judge flips as anomalies |
| Failure attribution | Model or Harness?; AgentRx; TrajDebug; Credit Without Ground Truth | Assign component interaction and fault side; separate first-local-error from critical error; prefer executed replay over step-level LLM judges |
| Policy enforcement | Organizational Control Layer; Deontic Policies; PolicyGuide; Contextual Agent Security; From Prompts to Contracts | Deterministic gateway between proposal and side effect; obligations as well as prohibitions; workflow-level checkpoints; policy generated from trusted context only |
| Privilege model | The Instruction Hierarchy; Dynamic Capability Scoping; Trust No Tool | Tag every context block with a privilege tier; re-scope credentials per phase; forbid permission *combinations*; score final consequential calls on full-trajectory trust |
| Concurrency | Prioritize Concurrency Control; Multi-agent State Management; Memory Compression for High-Fanout Sandboxes | Worktree/sandbox isolation per implementer, write-intent conflict detection, serialized commit points, memory-budgeted fanout |
| Metrics | QA→Task Completion; PHMForge; Efficient Agents; There Is No Neutral Harness; A2E | Report score with harness identity and config; use pass-all-3 for safety-critical paths; primary economy metric is **cost per verified pass**; report bands, not single numbers |
| Clarification | Ask or Assume? | Insert a clarification gate before research or implementation when a missing choice materially changes behavior, compatibility, safety, or intent (**69.40%** resolution reported while conserving questions on simple tasks) |
| Idle-time work | Second Thought | Schedule read-only prefetch and alignment checks during tool/IO waits; never substitute idle-window reasoning for master decision authority |
| Drift control | Stay Focused; From Plan to Action; Controllable Memory Usage | Compare output to task anchor, accepted scope, and the next acceptance gate — not a repeated prompt; hard round limits and progress tests on review loops; tag slices with a dependence tier |
| Recon lane design | FastContext; CRISP | Recon returns **file-and-line citations**, not prose summaries; budget lanes by penalizing *redundant* steps rather than tool use in general; tie the step budget to retrieval depth, not a flat cap |
| Task pre-processing | IRMA (Input Reformulation) | Before the expensive agent runs, a cheap step rewrites the inbound task with the relevant policy snippet and a tool shortlist; large measured gains for very few tokens |
| Reasoning-token policy | To CoT or Not to CoT; Test-Time Scaling Not Effective for Knowledge-Intensive Tasks | Extended reasoning **off by default**; enable only for symbolic, math, or logic sub-problems; for knowledge-heavy gaps route to retrieval, never to a longer frontier call |
| Budget enforcement | BAGEN | Budgets are enforced by the policy gateway with mid-run interval estimates and hard stops; prompt `BUDGET:` lines are documentation only |
| Router self-measurement | The Capability Frontier | Debias routing estimates before reporting savings; a router graded by its own selection inflates accuracy and cost figures materially |
| Trace schema | AgentAudit | Score trajectories on the ten trust dimensions (instruction integrity, planner, memory, tool selection, invocation, correctness, alignment, faithfulness, security, execution integrity); completion alone is not a trust signal |
| Acceptance baseline | SWE-chat | Target and report against field survival rates (**~44%** of agent code surviving to commit, **~44%** of turns corrected), not benchmark resolution rates |
| Ideation expectations | Heuresis | Track strategy and label histograms, not per-item novelty scores; run a fabrication check on ideation output; `NO BETTER ALTERNATIVE FOUND` is a successful result |

---

# Part C — Known tensions the master must resolve

These are genuine, unresolved conflicts in the evidence. Do not paper over them.

1. **Automated skill curation.** Skill-optimization papers (SkillAdam, SkillGLoW, Milkyway, AutoDesign, SkillsVote, CoEvoSkills) report gains. The longitudinal study of real repositories found **no average benefit** and **universal human gating**. SkillGenBench found generated skills can be **worse than no skill** (best average 14.4% code-repo / 25.0% doc versus no-skill 13.8% / 23.4%, with bootstrap CI half-widths of ~±5 pp making many method differences statistically indistinguishable). **Resolve toward proposal + human merge**, never autonomous writes.
2. **MCP versus CLI.** PHMForge and the Hitchhiker manuscript assume MCP as the standard surface. Agents All the Way Down argues CLI composition avoids persistent tool-registry token cost (with cache-prefix discipline `tools → system → messages` and a cited ~10× input discount on cache hits). The Bitter Lesson of Tool Calling favors programmatic typed stubs over JSON in 11 of 14 models (+10.6% on the GPT-5.6 family, parallel fan-out better in 13 of 14, and stability under context flooding). Both MCP and CLI are defensible. **Pick per tool volatility**, and test the interface under context rot rather than only on clean schemas.
3. **More phases is not better.** From Plan to Action found that adding "best practice" phases (regression tests, summaries) can *degrade* performance when misaligned with a model's internal strategy, and that removing a phase hurts even when agents frequently skipped it. **Measure before mandating.**
4. **Tool access can hurt weak models.** AgentIdeaBench's weakest quartile lost ground under active tool use. **Match tool budget to model tier.**
5. **Static quality does not predict executability.** SkillNet scored highest statically (59.1) but SkillSeekers (44.6 static) won dynamically. **Use static rubrics as diagnostics only; pass@execution is the gate.**
6. **Long context versus external memory.** Long-context wins factual recall on some benchmarks by ~33–35 pp, but external memory becomes cheaper after roughly 10 turns at ~100k-token histories (~26% savings by ~20 turns). **Model the break-even in the sizing gate**, and never rely on long context alone for permission or rule fields.
7. **Evaluation harnesses are not neutral.** The same weights and items score **31%–89%** depending on harness configuration, **85%** of credited answers can flip, and **4 of 12** models rank first under some configuration. **Pin harness configs in the ledger and report bands.**
8. **Recon-lane savings may require a trained model.** FastContext's up-to-**60%** token reduction with a **5.5%** resolution *gain* came from a purpose-trained 4B–30B exploration model, not a prompted cheap model. The architecture transfers; the numbers may not. **Treat the prompt-only recon lane as an unvalidated approximation** and measure its own token-and-quality delta before claiming the benefit.
9. **The router cannot be trusted to measure itself.** The same work reporting an **85%** cost reduction from frontier-style routing also reported naive oracle bias of **8.7%** accuracy and **88%** cost inflation. Routing savings and routing evaluation are the same estimate viewed twice. **Debias before reporting, and never let the router's own logs be the sole evidence that routing works.**
10. **Benchmark success and field success diverge sharply.** Agents resolve a large share of curated benchmark tasks, yet only about **44%** of real agent-produced code survived to a user commit, with pushback on **44%** of turns. **Do not set the definition of done against benchmark numbers**; either instrument real survival rate or state explicitly that the target is unvalidated in the field.

---

# Part D — Build Specification: Modular, Token-Frugal Daily-Driver Agent Ecosystem

## D.1 Intent and desired outcome

Build a modular agent ecosystem that acts as a **full daily coding assistant** and can be continuously modified and improved as new models, tools, MCP servers, repositories, and capabilities become available.

The ecosystem must be:

- **Fan-out first, decide second.** Cheap, weak agents investigate the problem from all relevant sides. One master agent makes the decisions, performs the important thinking, resolves contradictions, and owns the plan.
- **Token-frugal by design.** The default operating mode is many low-reasoning, low-token agents. Token spend is a first-class constraint ranked alongside correctness.
- **Frontier-quality output without frontier-model spend.** Cheap agents carry volume — reading, searching, extraction, transcription, formatting, and routine checks. Stronger models are reserved for planning, judgment, contradictions, and genuinely hard failures.
- **Model-agnostic and hot-swappable.** Every specialist declares its model in that specialist's own folder. Replacing a model must not require an ecosystem-wide rewrite.
- **Adaptive to problem size.** A one-line, unambiguous fix must not pay the cost of a full fan-out. A cross-cutting or ambiguous change must receive broader research and review.
- **A modifiable Swiss-army-knife assistant.** The ecosystem grows by adding specialists, tools, model declarations, and tested capabilities — **not** by repeatedly rewriting the core.
- **Compatible with different agents and providers.** The orchestration must work across model families, context limits, tool interfaces, and capability levels through adapters and declared contracts.
- **Evidence-first.** Every material decision and code change traces back to observed evidence, an explicit inference, an accepted assumption, or an unresolved `UNKNOWN`.

## D.2 Non-negotiable design principles

1. **Difficulty-gated breadth.** Fan-out is available, not automatic. Trivial work takes the shortest safe path; ambiguous, risky, or cross-cutting work receives broader research.
2. **Research first, decisions second.** Reconnaissance agents gather evidence from independent angles. They remain read-only and never decide scope, architecture, or implementation.
3. **One accountable decision authority.** The master alone accepts evidence, resolves contradictions, sets scope, chooses the design, approves tasks, escalates models, and accepts or rejects results.
4. **Cheap volume, expensive judgment.** Lowest tier for searching, reading, extraction, command execution, formatting, mechanical edits, and routine checks. Stronger models only for compressed decisions and high-risk independent review.
5. **Always benchmark a strong single agent.** Multi-agent fan-out is a hypothesis, not a default truth.
6. **Exact plans, guarded execution.** Implementers receive atomic tasks with no unresolved design decisions. If observed code does not match the plan, they **stop** rather than improvise.
7. **Independent and unfavorable review.** Authors never grade their own work. Reviewers actively seek disconfirming evidence — and unsupported criticism is itself a review failure.
8. **Durable state over conversational memory.** Plans, evidence, decisions, checkpoints, budgets, traces, test results, and approvals live in external artifacts. The ledger, not the transcript, is the source of truth.
9. **Deterministic enforcement.** Prompts guide behavior; host code enforces permissions, schemas, tool allowlists, budgets, idempotency, approvals, and stop conditions.
10. **Typed handoffs.** Every packet carries IDs, source references, claims, evidence, unknowns, limitations, confidence, and a bounded output schema.
11. **Type-aware compaction.** Never summarize exact rules, permissions, acceptance criteria, or user constraints as if they were ordinary prose.
12. **Model switching is an interface problem.** Use direction-specific handoff packets and measure the handoff tax.
13. **Policy at the execution boundary.** Model outputs propose actions; a deterministic gateway authorizes, revises, blocks, or escalates.
14. **Skills are software.** Ownership, versioning, linting, testing, least privilege, regression checks, provenance, and rollback.
15. **Evaluate trajectories, not only outcomes.** Plan compliance, context use, tool choice, sequencing, resource access, information flow, verification, and post-merge quality.
16. **Additive extensibility.** New capabilities enter through a stable specialist-folder contract and a compatibility test. The ecosystem grows by addition, **never** by rewrite.

## D.3 Token economy — the governing constraint

This is the rule the rest of the spec bends around. If a design choice improves quality but multiplies token cost, it must justify itself with measured evidence or be rejected.

### Operating principles

- **Cheap by default, expensive by exception.** Every agent starts at the lowest capability tier that can do its job. Escalation is a deliberate, logged decision — never a default.
- **Volume goes to the bottom tier.** Reading, searching, transcribing, listing, checking formats, and running commands belong to the cheapest available models. These jobs do not need reasoning; they need obedience.
- **Judgment goes up one tier, not to the top.** Mid-tier handles planning detail, review, test authorship, and diagnosis. The top tier is reserved for the narrow slice defined below.
- **Context is the real cost.** Each agent receives **ONLY** the slice of context its job requires. **NEVER** forward a full transcript, a full file, or another agent's raw output when a bounded summary or reference is sufficient.
- **Bounded outputs.** Every agent declares a maximum output shape and length. Evidence packets are structured and terse. Prose padding is a defect.
- **No redundant reads.** **IF** a file has already been read and summarized in this run, **THEN** reuse the source-bound summary unless the task explicitly requires a fresh read. Re-reading the same file across agents is a budget leak. Never discard raw source references — a later agent may reread a narrow section when summary fidelity is insufficient.
- **Short-circuit early.** **IF** the request is trivially scoped, unambiguous, and low-risk, **THEN** skip the fan-out and go straight to a single specified task. The pipeline scales with the problem, not with ceremony.
- **Measure cost by complete task.** Include model tokens, tool tokens, context retrieval, retries, review, tests, and coordination overhead. The primary economy metric is **cost per verified successful task**, not average tokens.
- **Bound fanout by memory as well as tokens.** Parallel sandboxes are capped by sandbox memory budget; schedule expensive compression and maintenance during LLM wait windows.
- **Reasoning tokens are a routing decision, not a default.** Extended reasoning is **OFF** unless the sub-problem is symbolic, mathematical, or logical. Measured gains elsewhere are near zero, and on knowledge-heavy questions longer reasoning *increases* hallucination (A22). **IF** the gap is missing knowledge, **THEN** retrieve through the tool gateway; **NEVER** buy facts with thinking tokens.
- **Budgets are enforced outside the model.** Agents cannot estimate their own remaining budget (A21). The `BUDGET:` line in a prompt is documentation; the **policy gateway** owns the hard stop, the mid-run interval estimate, and the early-stop trigger.
- **Penalize redundant steps, not tool use.** Step budgets are tied to retrieval depth rather than a flat cap, so a lane that genuinely needs eight reads is not punished for the same budget as one that reread the same file eight times.
- **Reformulate before you spend.** A cheap pre-step rewrites the inbound task with the relevant policy snippet and a tool shortlist before any expensive agent runs. This is among the highest-return-per-token additions in the system (A19).

### Frontier-model escalation policy — Fable / Sol / Astra tier

Treat these models as an expensive, rationed resource. They exist to logic out the single best solution to a hard problem — nothing else.

- **ALWAYS use discretion before invoking a frontier model.** The master must state, in one sentence, why a lower tier cannot resolve this. That sentence is logged.
- **VERY sparingly** means: at most **one** frontier invocation per problem under normal conditions, on a **pre-compressed, hand-curated** context — never on raw evidence dumps.
- **Legitimate frontier uses:** choosing between materially different architectures; resolving contradictory evidence that lower tiers could not reconcile; diagnosing a failure that has already defeated a mid-tier attempt; a final judgment call where being wrong is expensive.
- **NEVER** spend a frontier model on: searching, reading, summarizing, formatting, transcribing a decided change, routine review, or writing tests.
- **IF** a lower tier has not yet been tried on the problem, **THEN** do not escalate. Escalation requires a documented failure below it.
- Before escalating, the master compresses the input to a **decision brief**: the question, the options, the evidence for each, the constraints that decide it, unresolved risks, and the required output shape.
- The frontier model receives the **brief, not the corpus** — and specifically not the weak model's raw trajectory (see A15).
- The frontier model returns a decision, its reasoning, its uncertainties, and validation conditions. Everything downstream of that decision is executed by cheap models.
- Downshift after the decision, preserving the approved plan, evidence links, and constraints.
- **A frontier decision is not authority to perform side effects.** The policy gateway still controls execution.

## D.4 Non-negotiable behavioral contract

Every agent prompt in this ecosystem is written with control words that force **a sequence, a check, and a boundary**. Topic keywords do not make an agent more accurate — only enforceable instructions do.

### Approved control vocabulary

| Control word | Required behavior |
|---|---|
| **OBSERVE** | List the raw inputs before drawing any conclusion: files, fields, error text, user request, tool results, source identifiers, state. |
| **REFLECT** | Name the gap, ambiguity, contradiction, or risk in one sentence before drafting. |
| **ACT** | Perform only the bounded job in the role contract. |
| **VALIDATE** | Check the draft against a concrete, observable rule before sending it. |
| **ADVERSARIAL** | Assume the work under review is wrong, unsafe, incomplete, noisy, or off-task, and actively try to prove it. Applies to all review, plan-challenge, and test-verdict roles. |
| **ALWAYS / NEVER** | One hard rule each. Use for safety and truthfulness, not style. |
| **IF / THEN** | A real branch: a condition you can see, then one required action. |
| **FIRST / NEXT / THEN** | An order the agent cannot skip. |
| **STRICT / EXACT / ONLY** | Constrain output shape, allowed keys, file scope, tools, or accepted values. |
| **UNKNOWN** | Record missing evidence without inventing a value. |
| **VERIFIED / INFERENCE / ASSUMPTION** | Tag the epistemic status of every material claim. |
| **BUDGET** | Declare the maximum output length, files read, tool calls, iterations, time, or cost. |
| **STOP** | End when the named stop condition is met, or when a prerequisite, permission, path, state, or acceptance condition is missing or inconsistent. Do not continue by habit. |
| **ESCALATE** | Produce a compressed decision brief for a higher tier. Do not forward the raw transcript by default. |

Each control word goes on its own line, tied to a checkable action. `ALWAYS be helpful` does nothing. `NEVER invent a file path; IF the path is missing, THEN write UNKNOWN` does.

Each specialist uses the **smallest useful subset**. Repeating irrelevant prohibitions wastes context and weakens the important boundaries.

### Required prompt skeleton for every agent

```text
ROLE: <one job only>

TASK_ANCHOR:
<verbatim user request, or an exact immutable task anchor plus accepted scope>

INPUT_SCHEMA:  <exact fields>
OUTPUT_SCHEMA: <exact fields>
MODEL_TIER:    <lowest | mid | high | frontier>
TOOLS:         <allowlist>
PERMISSIONS:   <read-only | bounded write | dispatch | approval>
BUDGET:        <token, tool-call, time, file, retry, and fan-out limits>

1. FIRST — OBSERVE: List the inputs you actually have:
   files, fields, error text, user request, source IDs, tool outputs, state.
2. NEXT — REFLECT: State the gap, risk, ambiguity, or contradiction in one sentence.
3. THEN — ACT: Produce only the requested output.
4. VALIDATE: Confirm every material claim is backed by an observed input from step 1.
   IF a required value is missing, THEN write UNKNOWN. Do not fill it in.
5. STOP: End when the requested output and validation are complete.
   IF a required path, identifier, permission, precondition, or authoritative value
   is missing, THEN return BLOCKED or UNKNOWN. NEVER invent it.

ALIGNMENT:
- Confirm the output advances TASK_ANCHOR and stays within accepted scope.
- VALIDATE: "Does this output serve the stated request, using only inputs I observed?"
- IF NO: write the exact gap and stop.

CLAIM STATUS:
- Tag every material claim as VERIFIED, INFERENCE, ASSUMPTION, or UNKNOWN.
- Only VERIFIED claims and explicitly accepted INFERENCES may drive a code change.

CONSTRAINTS:
- ALWAYS cite the file, field, source ID, line, test, or tool result supporting a claim.
- NEVER invent a path, symbol, dependency, tool result, source, or requirement.
- NEVER add steps, files, fields, or scope the task did not authorize.
- IF a required ID, path, permission, or acceptance criterion is absent,
  THEN stop and mark it UNKNOWN.
- ONLY use tools named in the task or the agent's allowlist.
- STRICT: <exact output format and required keys>.
- BUDGET: <max output length, files read, tool calls, iterations, time, cost>.
```

Review-type agents additionally carry:

```text
ADVERSARIAL:
- Assume this work is wrong.
- FIRST: State the strongest evidence-based case against the plan, code, test,
  evidence, or alignment — before stating any approval.
- NEXT: Identify concrete failures, missing evidence, hidden assumptions,
  and unsafe permissions.
- THEN: State only the checks that passed.
- IF you cannot find a failure mode, THEN say so explicitly and name what you checked.
- NEVER approve because the output looks plausible.
- Report false-positive risk. Silence is not approval. Unsupported criticism is a
  review failure: every finding cites a file, line, invariant, test, or repro.
```

### Rules that keep the skeleton from collapsing

1. **One job per instruction block.** A reviewer, a writer, a fixer, a planner, and a tester are separate prompts — never one. This also keeps each prompt short, which keeps it cheap.
2. **One `NEVER` per failure already observed.** Speculative bans get ignored, dilute the real ones, and cost tokens on every single call.
3. **`VALIDATE` names the failure, not a feeling.** "Am I confident?" is weak. "Does every path I cited exist in the files I actually read?" is strong.
4. **Do not turn control words into decoration.** Every `ALWAYS`, `NEVER`, `IF`, `THEN`, `STRICT`, and `VALIDATE` must have an observable check.
5. **Keep prompts short and put volatile detail in referenced files.** The prompt holds the contract; the registry holds changing project detail. (Persistent repository overviews cost >20% more tokens for no measured gain — see A17.)

### Claim tagging

Every factual claim an agent emits carries exactly one tag: `VERIFIED`, `INFERENCE`, `ASSUMPTION`, or `UNKNOWN`. Untagged claims are treated as `ASSUMPTION` and **NEVER** drive a code change.

Every context block additionally carries a **privilege tier** (system / user / repository / tool-output / untrusted-external). Retrieved and tool-returned text is never co-equal with user or system policy.

## D.5 Execution pipeline

### Phase 0 — Intake, clarification, and sizing (cheapest model)

- One cheap sizing agent classifies the request as `TRIVIAL`, `CONTAINED`, or `CROSS_CUTTING`, and assigns uncertainty, risk, side-effect, and verifiability levels.
- **Ask one focused user question** when a missing choice would materially alter behavior, architecture, safety, compatibility, or output. Underspecification detection is separate from execution.
- **IF** `TRIVIAL` (one-line or otherwise unambiguous), **THEN** skip the fan-out and go straight to Phase 4 with one specified task: inspect → specify → implement → verify → review.
- `CONTAINED`: bounded research and implementation; small targeted fan-out and one planner.
- `CROSS_CUTTING`: ambiguous, multi-file, high-risk, novel, or architecture-affecting; full pipeline with multi-angle research.
- The sizing gate **may not** decide the design, authorize writes, or change scope. It only scales the process.
- This gate exists purely to stop small requests from consuming a large pipeline.

### Phase 1 — Fan-out reconnaissance (weakest models, read-only, parallel)

- Spin up many cheap, low-reasoning agents in parallel, each owning **exactly one** angle. Non-overlapping evidence lanes:
  - existing implementation and data flow;
  - callers, interfaces, schemas, and dependencies;
  - configuration, feature flags, and environment;
  - tests, fixtures, CI, and failure history;
  - documentation and user-facing behavior;
  - external standards, APIs, papers, and prior art;
  - security, permissions, privacy, and failure boundaries;
  - **the exact item or constraint the user explicitly named.**
- Scope is deliberately wide at this stage — investigate the problem from all sides. Targets may be code, a website, a specification, a log, an API, or documentation. Anything readable.
- **STRICT: read-only.** No agent in this phase may edit, create, delete, install, deploy, send, or mutate.
- **STRICT output:** a bounded evidence packet containing observed inputs, findings with source citations and locators, claim-status tags, explicit `UNKNOWN`s, contradictions, freshness, raw-artifact references, and one-line limitations. **No recommendations, no plans, no prose.**
- Recon agents do not issue recommendations unless the master explicitly opens a separate analysis task.
- Default the retrieval tool to **grep/BM25 with file-pointer outputs**; vector retrieval is an escalation lane. Apply a **retrieve-vs-think gate** per lane and record `UNKNOWN` when the evidence gap exceeds threshold but retrieval is denied by policy.
- Return **structured shortlists with UNKNOWN slots**, not narrative-only briefs — advisory prose gets ignored by strong models.
- **Return file-and-line citations, not summaries.** The measured benefit of a cheap recon lane comes from handing the solver precise locators so its context stays clean; a lane that returns paraphrase re-imports the cost it was meant to remove (A19).
- Before a lane runs, a cheap reformulation step rewrites its assignment with the relevant policy snippet and a tool shortlist.
- Require a **per-claim support matrix**; reject packets above an unsupported-statement threshold at the alignment gate.
- Share an evidence registry to avoid duplicate reads, but **never discard raw source references**.
- The fan-out is adaptive: stop early when the evidence matrix is complete; expand only when a named gap remains. Apply straggler timeouts and aggregate partial results with explicit `UNKNOWN`s.
- **Parallel cheap breadth exists to shrink the master's context, not to fill it.**
- Cap concurrency by sandbox memory budget as well as token budget.

### Phase 2 — Master synthesis and decision

- One master agent is the **sole decision authority** for scope, architecture, prioritization, follow-up research, plan acceptance, and result acceptance.
- The master deduplicates and compares evidence packets, resolves contradictions, identifies unsupported claims, commissions targeted follow-up recon where a packet returned `UNKNOWN`, and decides what is actually in scope.
- It identifies the user's actual acceptance criteria, chooses the **smallest** architecture and execution route that can satisfy them, and compares the proposed multi-agent route against a **strong single-agent baseline**.
- It records accepted, rejected, and deferred ideas with reasons.
- The master is responsible for all important thinking and planning, but it must show the evidence and assumptions supporting each decision.
- The master runs at mid-to-high tier by default. **IF** the decision is genuinely hard by the criteria in D.3, **THEN** and only then does it compress a decision brief and escalate **once** to the frontier tier.
- **ONLY** the master may commission work, change scope, accept a plan, accept an implementation, or authorize a transition between phases.
- The master **may not** bypass policy gates or grant itself permissions.
- The master must not run on the hot user loop; inject only compressed belief and plan state.

### Phase 3 — Out-of-the-box ideation (brainstormer)

- A dedicated brainstormer receives the task anchor, constraints, the conventional approach, and unresolved risks, and attacks the problem from a **deliberately different direction** to force a search for a non-obvious solution.
- It must generate a small number of **materially different** alternatives, not stylistic variations.
- It is acceptable and expected that it sometimes finds nothing. **`NO BETTER ALTERNATIVE FOUND` is a valid, successful, cheap result.** **NEVER** pad with weak or unsafe ideas. Across 3,222 scored autonomous-research runs no output was rated original, so treat "nothing found" as the expected case rather than a failure of the lane (A24).
- **Run a fabrication check before the master appraises the output.** Reward-hacking fabrications appeared at a measurable rate in scored ideation runs; every proposed alternative must carry its supporting evidence or be tagged `ASSUMPTION`.
- Monitor ideation health with **strategy and label histograms** over time, not per-item novelty scores.
- The brainstormer is read-only, never authorizes execution, and never changes scope.
- The master **ALWAYS** appraises the output **ADVERSARIALLY** for benefit, assumptions, evidence, reversibility, cost, and new failure modes. **IF** the idea is not clearly better, safer, cheaper, or otherwise justified for the intended task, **THEN** discard it and say so, recording why.
- Budgeted tightly: one bounded pass unless the master identifies a specific unanswered question. Creativity here is worth paying for once, not repeatedly.
- Because ideation collapses toward default templates (bridge/synthesis framings, integrate-and-unify moves, ensemble defaults), monitor **label histograms** of proposed approaches, not only per-item scores. Extended reasoning **sharpens** the default template rather than broadening it.

### Phase 4 — Exact-change planning

- The master, with a planner specialist, converts the accepted approach into atomic tasks in a task DAG, so thoroughly specified that **zero wiggle room remains**.
- Every task specifies:
  - unique task ID and dependency IDs;
  - exact objective and rationale;
  - exact repository, file, or resource;
  - exact location, symbol, region, schema, or behavior to change;
  - expected precondition or code signature;
  - exact before/after content or transformation rule;
  - interface and compatibility constraints;
  - dependencies and ordering;
  - **file allowlist and prohibited paths**;
  - tool allowlist;
  - claim/evidence basis;
  - acceptance criteria;
  - **exact verification command or check**, and the expected observable result;
  - rollback procedure and rollback condition;
  - stop conditions and escalation owner;
  - completion evidence schema;
  - `TEST: required — <behavior that must be proven>` **or** `TEST: not required — <one-sentence reason>`;
  - maximum time, tool calls, files changed, and token budget.
- **NEVER** hand an implementer a task that requires it to make a design decision. **IF** a decision is still open, **THEN** the task is not ready.
- **NEVER** let an implementer reinterpret a vague requirement as permission to expand scope.
- **The precision here is the token strategy:** the more exactly the change is specified, the weaker and cheaper the model that can execute it.
- Where a subflow repeats, prefer **compile-once, run-many** artifacts — verified macros, policies, or scripts — over per-step LLM re-planning.

### Phase 5 — Plan review (independent, ADVERSARIAL)

- A separate plan reviewer reads the plan and evidence **before any code is written** and attempts to reject it.
- Check for: missing dependencies; wrong ordering; hidden design decisions inside worker tasks; unsupported claims; scope creep; ambiguous file scope; overly broad file or tool permissions; unverifiable acceptance criteria; tests that can pass without proving behavior; missing negative, edge, compatibility, migration, or rollback cases; unnecessary fan-out; unjustified frontier use; token waste; policy violations.
- **ADVERSARIAL and unfavorable by default.** Assume the plan is wrong and try to prove it. Mid-tier. **Catching a bad plan here is the single highest-leverage token save in the system.**
- The plan reviewer may reject the plan but **may not silently repair it.** The master decides how to revise.
- Approval requires evidence that each objection was resolved or explicitly accepted by the master.
- Use **non-overlapping rubric criteria** with separate process and outcome channels, and score uncontrollable environment blocks separately from agent errors.
- The alignment checker independently verifies that the plan serves the original user request and did not drift into a technically interesting but unwanted task.

### Phase 6 — Mechanical implementation (lowest-capability models)

- Many low-powered, low-token agents execute the pre-specified tasks. **They transcribe a decided change; they do not design.**
- Each implementer receives only its assigned task, the relevant context slice, its file allowlist, its tool allowlist, and its verification command.
- **NEVER** redesign, expand scope, refactor opportunistically, edit unassigned tests, change unrelated files, delegate, hide failing commands, or "improve" the plan.
- **STRICT:** apply the smallest correct edit, run the task's verification command, report observed evidence only.
- **IF** repository state does not match the plan's expected precondition, **THEN** return `PLAN_STALE` and stop. Do not invent a new change.
- Keep only the last **N** tool call/response pairs in context; summarize evicted pairs into running state; never prune anchor, permission, or acceptance-test headers.
- Parallelize freely — these are the cheapest agents in the system — **but only** when file ownership, dependencies, shared state, ports, and generated artifacts cannot conflict. Otherwise serialize or use an explicit state manager.
- Each implementer runs in its own isolation unit (worktree or sandbox). All writes pass through the execution policy gateway and are recorded in the run ledger. Repository writes land through serialized commit points with version checks.

### Phase 7 — Independent test design, execution, and adversarial code review

- The **test author** is separate from the implementer and defines tests proportionate to the change (mid-tier, test files only).
- The **test executor** is separate from both. It runs the authoritative commands in the pinned environment, preserves raw output, and reads it under the **least charitable interpretation**. It checks whether the changed code actually executed and looks for coincidentally-green results, skipped tests, stale caches, weak assertions, and environment drift. **ADVERSARIAL:** a passing suite is a claim to be disproven, not a conclusion.
- The **code reviewer** inspects the actual diff **before reading any implementer commentary** and owns the authoritative verdict. **ADVERSARIAL** and unfavorable by default. Review covers correctness, scope, interfaces, security, error paths, concurrency, maintainability, meaningful test coverage, and unintended behavior.
- The reviewer reports only **actionable** findings supported by file, line, invariant, test, or reproducible behavior. Measure **usefulness rate, signal-to-noise ratio, false positives, severity, duplication, and developer time** — not issue count. Cap reflexive review rounds unless each round adds cited new evidence.
- Use temperature-0 replicates and one challenge round before accepting a verdict; run reviewers on **frozen** evidence packets rather than live re-search mid-review; log judge flip events in the ledger as first-class anomalies.
- Reviewer and tester are read-only and separate from the implementer. **NEVER** let the author of a change grade it. Neither may silently fix the code it grades.
- The alignment checker verifies that the diff still serves the original request.
- **IF** any reviewer or tester finds a failure, **THEN** the master decides whether to revise the plan, issue a bounded fix task, or stop and report the blocker.

### Phase 8 — Failure diagnosis (only on failure)

- A failure diagnostician localizes the **critical** failure step and assigns ownership: model, harness, tool, memory, user interaction, environment, or grader.
- Distinguish **first local error** from **critical error**; resolved intermediate errors are noise.
- Retain a step-indexed trace, synthesized constraints, the violated constraint, the critical step, the evidence, and the repair owner.
- Prefer **executed replay** or counterfactual re-rolls over step-level LLM judges for pivotal-step attribution; step-judge signals correlate with fluency rather than contribution.
- Tag every rejected run with one failure family and use the tag to assign repair ownership. **Do not respond to every failure by changing prompts.**

### Phase 9 — Alignment gate (runs at every phase boundary)

- A cheap, read-only alignment checker compares the proposed result against the original user request, clarified choices, accepted scope, the plan and task contracts, the actual diff, and test evidence.
- It rejects anything technically valid but **not what was asked for**, and gates the handoff between phases.
- Compare against the task anchor, accepted scope, and the **next acceptance gate** — not merely a repeated prompt.
- Lowest tier: this job is pattern-matching against a stated goal, not reasoning.
- Use hybrid hierarchical-sequential monitor scaffolding with structured trajectory parsing rather than a zero-shot transcript skim, and route only pre-flagged trajectories to human approval to preserve precision.

### Phase 10 — Documentation and closeout

- A low-tier documenter records **only the reviewed result**, bound to the final revision and supported by source IDs, file paths, tests, and review outcomes.
- It must distinguish implemented behavior from planned behavior, record unresolved limitations, and preserve: what changed and why; user-visible and interface changes; tests and raw result locators; migration or rollback instructions; evidence and decision lineage; and cost, token, latency, and model-usage summary.
- **Proposal-only by default:** it reports deltas rather than silently rewriting docs. Documentation writes require their own allowlist and an explicit master commission.

## D.6 Testing policy

Testing is mandatory and proportional. The goal is **meaningful coverage, not test count.**

- **ALWAYS** write unit tests for each thing that warrants them, and the test must exercise a **meaningful** part of the code — real behavior, real edge cases, the actual contract the task changed.
- **NEVER** write a test that passes regardless of whether the code works. Asserting that a function was called, that a constant equals itself, or that no exception was raised is **not** coverage.
- **Proportionality.** A comment, a rename with no behavior change, a documentation-only edit, or a formatting fix may be `TEST: not required` when the plan gives the reason. For anything bigger — behavioral, logic, integration, state, permission, or data change — testing is planned **up front in Phase 4**, not bolted on afterward.
- **The plan declares the test requirement.** Every Phase 4 task states `TEST: required — <what behavior must be proven>` or `TEST: not required — <one-sentence reason>`. The plan reviewer challenges both.
- **Fit the test to the task.** A pure function gets input/output cases including edges. A state machine gets transition, invalid-transition, resume, and recovery coverage. An integration point gets a contract test, plus schema, permission, error, timeout, and idempotency tests. A bug fix gets a regression test that **fails on the old code**.
- **VALIDATE the test itself:** would this test fail if the change were reverted? **IF NOT, THEN** the test is worthless and must be rewritten.
- **Separation of duties.** Test authorship is a mid-tier job, separate from implementation. Test execution and verdict is a separate **ADVERSARIAL** role. **NEVER** let one agent write, run, and bless its own tests.
- **Ecosystem-level negative tests.** The evaluator must test stale context, missing IDs, conflicting evidence, incorrect plans, irrelevant skills, tool failure, timeout, permission bypass, runaway loops, partial writes, dropped messages, duplicate work, alignment drift, provider failure, fresh-escalation, compressed handoff, and downshift.
- **Metrics to record for the ecosystem itself:** outcome correctness, plan compliance, context precision/recall, tool choice, tool arguments, sequencing, discovery, verification, latency, model cost, token cost, coordination cost, policy compliance, safety violations, scope violations, retries, drift, failure-localization quality, review false positives, recovery success, post-merge quality, human acceptance, and **cost per verified pass**.
- **Baselines to compare against:** (1) strong single agent; (2) deterministic workflow; (3) the adaptive ecosystem; (4) no-frontier ecosystem; (5) cheap workers with strong orchestrator; (6) alternative handoff and context policies.
- **Run repeated trials and preserve raw traces.** Do not treat one successful run as proof of reliability. Pin the evaluation harness configuration in the ledger and report score bands, since the same weights and items can score 31%–89% across harness configurations.
- **Meta-evaluate the judge** against expert labels before trusting any pass rate, and report side-effect and loop metrics alongside task success.

## D.7 Drift control and alignment

Agents observably wander off task. Both mechanisms below are **mandatory**, and both are cheap.

1. **Task-anchor re-injection.** Every agent's prompt restates the original user request verbatim, or uses an exact immutable task anchor. Every output ends with:
   - `VALIDATE: Does this output serve the stated request, using only inputs I observed?`
   - `IF NO: write the exact gap and stop.`
   Re-inject the active plan slice and current subgoal on a **fixed step interval** (every ~5 steps is the empirically supported default) and on every phase change — not only at session start.
2. **A dedicated alignment checker.** A cheap, read-only agent audits proposals, plans, diffs, documentation, and review outputs against the user's actual intent and rejects anything technically fine but not what was asked for. It gates the handoff between phases.

Additional drift controls:

- Persist the current goal, non-goals, acceptance criteria, and forbidden scope in the run ledger, in **non-evictable slots**.
- Re-inject only the relevant task anchor, not the entire conversation.
- Require each handoff to state what was completed, what remains, and what is explicitly out of scope.
- Tag each context slice with a **dependence tier** (anchor-critical versus exploratory) so strict-adherence and greenfield modes can be selected deliberately.
- Apply hard round limits and progress tests to any debate, review, or refinement loop.
- **STOP** when the agent begins solving a different problem, inventing missing requirements, or adding unapproved scope.

## D.8 Architecture and execution controls

### External state and event ledger

The run ledger is the **authoritative record**. Use append-only events with stable addresses; build current state as a **deterministic projection**; preserve enough information to replay, fork, compare, debug, and audit a run. Compaction evicts the view and leaves an address-anchored index — it never deletes from the log.

Contents:

- original user request and immutable task anchor;
- clarification questions and answers;
- sizing classification, risk, uncertainty, verifiability;
- plan versions and revision reasons;
- task DAG, dependencies, and ownership;
- agent, model, harness, prompt, and tool versions (or hashes), plus evaluation harness configuration;
- compiled workflow graph for the run;
- context slices and source IDs;
- claims, evidence, assumptions, unknowns, and contradictions;
- **claim-to-evidence graph** linking decisions and final claims to reads, tool calls, artifacts, edits, tests, and reviewer checks;
- tool calls, arguments, results, and errors;
- file reads, write intents, actual diffs, and verification results;
- budgets, approvals, policy decisions, blocked violations, retries, and stop conditions;
- compaction events and which fields were dropped;
- reviews, tests, alignment checks, judge flips, and final disposition;
- failure records: critical step, taxonomy, component interaction, fault side, evidence, repair owner;
- cost record: tokens, cost, latency, tool calls, model, retries, and cost per verified pass.

Instrument all lanes with OpenTelemetry-style spans tied to ledger event IDs, store trajectories in a queryable store rather than flat logs, and run a lightweight **silent-failure** anomaly detector (drift, cycles, missing details, tool/context propagation) before master synthesis. Treat a successful final output without a trace sanity check as `UNKNOWN`.

### Context manager

- Treat conversational context as a **cache**, not the system of record.
- Retrieve the smallest relevant context slice for each worker.
- Classify context by **type and retention requirement**: immutable rules, task anchor, accepted decisions, evidence, episodic history, disposable chatter.
- Preserve exact rules, permissions, acceptance criteria, task anchors, IDs, and unresolved questions with higher retention priority than ordinary narrative. Pin them in non-evictable slots.
- Keep raw evidence separate from summaries and maintain source freshness plus conflict indicators.
- Implement compaction as a **validated, budgeted pipeline** with explicit fidelity checks before phase handoffs; the alignment checker blocks the handoff if mandatory fields were dropped.
- Enforce **typed channels**: workers return bounded evidence schemas only; no raw tool dumps reach the orchestrator window.
- Use isolated reasoning spaces for cross-cutting analysis lanes so execution noise never floods the master.
- Use **model-specific** compaction strategies and context formats, and test whether a compact representation actually improves total task cost and outcome — compact formats are not automatically token-efficient, and different agents benefit from different compression fidelity.
- Model the long-context-versus-external-memory break-even (turn count × context size) in routing.
- Attach an outcome-driven **worth** signal to memory units so stale items rank down, and treat it as associational — pair it with review before any automatic delete.

### Model router

Select a model by role, task risk, uncertainty, context needs, tool needs, available budget, and **observed** model-task performance. Prefer an explicit belief-and-utility policy over heuristic prompts, and escalate only when expected utility gain exceeds the cost of the compressed brief.

The router must log: task features and risk tier; eligible models and why; chosen model and fallback order; expected and actual cost and latency; outcome and verifier result; failure category; whether a switch occurred and which handoff packet was used; and regret.

Model routing becomes a learning system **only after** it has a safe baseline, held-out evaluation, and a bounded update policy.

### Execution policy gateway

Model-agnostic, deterministic, and positioned between every agent proposal and every side effect. Generate policy from **trusted context only** — retrieved evidence may never widen permissions. Enforce:

- tool allowlists and deny lists;
- per-agent, per-task, and per-run permissions, **re-scoped per phase** (recon versus implement versus test);
- forbidden permission **combinations**, not only individual grants;
- privilege tiers on context blocks; ignore tool- or user-injected "override system" strings regardless of model compliance;
- data and information-flow boundaries;
- secrets and sensitive-data handling;
- file and repository allowlists;
- approval requirements;
- concurrency, recursion, time, token, and cost budgets;
- idempotency and write-conflict checks at **write-intent** time;
- required logging and evidence preservation;
- **policy obligations** as well as prohibitions — logging, notifying, requesting approval, preserving evidence;
- workflow-level policy checkpoints that catch **omitted required steps**, not only forbidden actions, and can return the next compliant remediation step;
- trajectory-conditioned risk scoring on consequential final calls, since a tool can behave benignly during exploration and harm at commit time;
- outcomes: approve, revise, block, or escalate.

Prompts do not own authorization. A frontier decision is not authorization. Safe execution is evaluated **mid-trajectory**, not from task completion — completion is never evidence of safe execution.

### Tool gateway

- Prefer a small number of **semantic, workflow-level** tools over a large collection of thin endpoint wrappers (`schedule_event` over `list_users` + `list_events` + `create_event`; `get_customer_context` over three lookups).
- Namespace tools by service and resource (`carla_scenario_validate`, `bridge_replay_search`); prefix versus suffix naming measurably shifts performance, so choose by evaluation.
- Use natural, semantic identifiers and explicit schemas; unambiguous parameter names (`user_id`, not `user`); poka-yoke arguments; absolute paths where relative paths have failed.
- Support **concise** and **detailed** response modes (one measured example: 206 versus 72 tokens, roughly one third).
- Bound output size; paginate, filter, and truncate with sensible defaults and actionable truncation messages.
- Return **actionable, teaching** errors rather than opaque codes or tracebacks.
- Mark destructive, external, or irreversible tools explicitly.
- Put domain computation behind **algorithm-grounded** tools, not stubs and not retrieval, so failures attribute to reasoning.
- Log trajectories at the gateway and promote stable recurring call sequences to **versioned deterministic meta-tools**, keeping thin APIs internal to the meta-tool implementation rather than agent-visible.
- Consider typed programmatic stubs with sandbox execution as the primary surface for coding agents, and test the interface under context rot rather than only on clean schemas.
- Measure tool-selection accuracy, argument validity, call count, latency, returned tokens, error recovery, and downstream task outcome. Evaluate **tool retrieval separately from tool invocation** (tools-provided versus unknown-tools modes).
- Write tool specifications like documentation for a new hire: examples, edge cases, input formats, and boundaries between tools. Tool-description edits alone have driven state-of-the-art gains.

## D.9 Specialist folder and configuration standard

Each specialist lives in its own folder containing its prompt, its declared model, its tool allowlist, its permissions, its output contract, its budget, and its tests.

```text
agents/<specialist-name>/
├── AGENT.md               # bounded role and control-word contract (short)
├── README.md              # purpose, applicability, examples, limitations
├── model.yaml             # tier, provider, concrete model, version, fallback order
├── prompt.md              # the control-word contract itself
├── tools.yaml             # allowlist, side effects, schemas, response limits
├── permissions.yaml       # read / bounded write / dispatch / approval boundaries
├── input.schema.json
├── output.schema.json
├── budget.yaml            # tokens, calls, time, retries, files, fan-out
├── tests/                 # contract, unit, adversarial, and regression tests
├── fixtures/              # bounded inputs and expected outputs
├── skills/                # optional procedural resources (progressive disclosure)
└── CHANGELOG.md           # owner, rationale, evidence, rollback history

orchestrator/
├── routing.yaml
├── phases.yaml
├── state.schema.json
├── evidence.schema.json
├── handoff.schema.json
├── failure-taxonomy.yaml
├── acceptance-gates.yaml
├── model-roster.yaml
└── harness-config.yaml    # pinned evaluation harness; versioned like code
```

### Model declaration example

```yaml
name: code-implementer
role: mechanical implementation
model_tier: lowest
provider: configurable
model: configurable
max_output_tokens: 1200
max_tool_calls: 6
max_files_read: 8
max_files_write: 2
allow_side_effects: false
evolvable_modules: []          # restricted edit scope for any harness self-improvement
```

### Specialist contract

Every specialist must declare: one job; inputs and required identifiers; output schema; claim-status rules; tools and permissions; context and file scope; budget; completion and stop conditions; failure and unknown behavior; verification method; owner and version; tests; and rollback strategy.

**Swapping a model means editing one declaration in one folder.** Tiers are defined by role (`lowest`, `mid`, `high`, `frontier`) and each ecosystem maps those tiers to concrete models, so the same structure runs on a different provider or a different set of available models. Role contracts must not depend on provider-specific prose. New specialists are **additive** and must pass contract, budget, safety, and routing tests before activation.

### Skill lifecycle

- Store reusable skills by **procedural family or subtask**, not by raw task trajectory. Never append raw local skills to the durable library; re-derive instance detail per episode and update priors offline.
- Use **progressive disclosure**: routing metadata first, instructions next, resources and code only when needed. Distinguish metadata, instructions, executable resources, permissions, provenance, and lifecycle status.
- Every skill declares **when it applies, what it may do, how it terminates, and how it is evaluated**.
- **Lint** metadata, packaging, routing, resource organization, and tool permissions before registry entry.
- Compare every skill against **no-skill and matched-skill baselines on the same task**, with counterfactual A/B traces, not just aggregate pass rate.
- **Reject** skills that regress correctness, increase tokens/steps/mandatory procedure without improving the required outcome, or whose destructive influence patterns outweigh the constructive ones.
- Require **post-run attribution** (skill versus agent versus environment versus grader) before any skill change merges.
- Enforce **task-conditioned least privilege** at the action level, not just folder-level tool allowlists.
- **Bound library width**; calibrate judge false-pass rate before enabling automated eviction; use per-skill contribution as the sole eviction input.
- Treat the library as a **supply chain**: signed provenance, quarantine for third-party packs, no verbatim copying in authoring prompts, clean-session carryover tests in CI, and multi-round adaptive red-team runs.
- Agents **propose** skill changes through reviewed commits; a single run never silently rewrites shared skills. Keep governance and constitution files outside any self-evolvable root.
- Evaluate automated curators by **replay against human edit histories** as well as task benchmarks, and measure placement (which component changed) not just content added.

## D.10 Agent roster

| Agent | Model tier | Write access | Job | Budget posture |
|---|---|---|---|---|
| Sizing gate | Lowest | None | Clarify and classify request size, risk, uncertainty, verifiability; short-circuit trivia | Minimal |
| Recon workers (many, parallel) | Lowest | None | One non-overlapping research angle each; evidence only | High count, tiny packets |
| Master / orchestrator | Mid–high | Dispatch and approval only | Sole authority for scope, design, synthesis, planning, escalation, acceptance | Moderate, on compressed input |
| Frontier advisor | Frontier (Fable / Sol / Astra) | None | Logic out the single best solution on one genuinely hard call | Rationed — normally zero or one brief, one answer |
| Brainstormer | Mid | None | Forced out-of-the-box angle; "nothing found" is valid | One bounded pass |
| Planner | Mid | None | Atomic, zero-ambiguity task specs including test requirement, budgets, and rollback | Moderate |
| Plan reviewer | Mid (high for risky work) | None | **ADVERSARIAL** pre-execution challenge | Small, focused |
| Alignment checker | Lowest | None | Catch drift from the user's actual intent; gate phase handoffs | Minimal |
| Implementers (many, parallel) | Lowest | One file/task allowlist, isolated worktree | Transcribe the decided change | High count, tiny packets |
| Test author | Mid | Test files only | Meaningful behavioral and regression tests fitted to the change | Moderate |
| Test executor | Low–mid | None (read + execute) | Run authoritative commands, **ADVERSARIAL** reading of raw output | Small |
| Code reviewer | Mid–high | None | Evidence-bound **ADVERSARIAL** diff review, authoritative verdict | Moderate |
| Failure diagnostician / debugger | Mid | None | Localize critical step; assign model/harness/tool/memory/environment/grader ownership | Moderate, only on failure |
| Documenter | Lowest | Docs allowlist | Record the reviewed change and evidence lineage | Minimal |
| Research synthesizer | Mid | None | Merge evidence, preserve contradictions, produce source-bound report | Bounded |
| Policy gateway | Deterministic (no model) | No model writes | Approve, revise, block, or escalate every proposed action | Always on |
| State / ledger manager | Deterministic (no model) | Ledger only | Persist events; project current state | Always on |
| Router | Lowest–mid plus deterministic feedback | No direct side effects | Select model and route with logged rationale and regret | Bounded |

## D.11 Definition of done

The ecosystem is working when a normal day's coding request flows through it and:

- Trivial work reliably avoids unnecessary fan-out, and complex work receives independent read-only research without duplicate lanes.
- The overwhelming majority of tokens were spent by the cheapest tier, and the frontier tier was either untouched or invoked **once** on a compressed decision brief.
- The expensive model was used for judgment, and cheap models did the volume.
- Output quality is at least as good as the strongest agreed baseline on the target evaluation suite. **Do not claim "frontier quality" without a matched test.**
- Each multi-agent route measurably beats a strong single-agent baseline on at least one required dimension.
- Every material code change traces back to a cited observation, a verified test, an explicit inference, or an accepted assumption — **never an unmarked assumption**.
- Every research packet preserves sources, citations, contradictions, limitations, and unknowns.
- Every implementation task contained no unresolved design choice, and implementers stopped on stale preconditions.
- Every non-trivial change has a meaningful test that would fail if the change were reverted.
- Every plan, code review, test verdict, and alignment verdict was independent of the author and **ADVERSARIAL**, and adversarial review remained evidence-bound with an acceptable false-positive rate.
- Every side effect passed through the policy gateway and was recorded in the run ledger.
- Context compaction preserved exact constraints, permissions, acceptance criteria, and task anchors.
- Model switching and agent handoffs used explicit, bounded, direction-specific contracts and were measured for handoff tax.
- Shared writes were conflict-aware and recoverable.
- Skills are versioned, least-privilege, testable, and reversible.
- A failed run can be replayed, forked, diagnosed, and attributed to the correct component and critical step.
- **Swapping in a new model required editing exactly one folder.** Adding a specialist required adding one conforming folder, tests, and a registry entry.
- Tools, skills, models, MCP servers, and specialists can be added without a structural rewrite.
- The quality-and-cost target is demonstrated on repeated real coding tasks using **verified success and cost per verified pass**, with a pinned harness configuration — not claimed from a single benchmark run.
- **Survival, not resolution, is the headline metric.** Track the share of agent-produced changes that survive into a committed revision and the share of turns the user corrects. The field baseline for both is roughly **44%** (A24); a definition of done stated only in benchmark resolution is not accepted.
- Trajectories are scored on the ten trust dimensions, and completion at low trust is treated as a failure, not a pass (A23).
- Routing savings are reported from a **debiased** estimate, not from the router's own selection logs (A20).
- Budget limits were enforced by the gateway and demonstrably held when an agent's self-estimate was wrong (A21).

## D.12 Recommended implementation sequence

1. **Define the target and baselines.** Specify representative daily coding tasks, risk tiers, permissions, latency and cost budgets, the strong single-agent baseline, the deterministic workflow baseline, and acceptance tests. Pin the evaluation harness configuration.
2. **Build the ledger and policy gateway first.** Make events, plans, permissions, tool calls, writes, tests, and stop conditions observable **before** adding autonomy.
3. **Implement the sizing gate, clarification gate, and one master.** Prove the smallest useful workflow before fan-out.
4. **Add two or three read-only recon specialists.** Measure evidence coverage, packet size, duplicate reads, unsupported-statement rate, and contradiction detection.
5. **Add typed handoffs and the alignment checker.** Reject unsupported claims, missing IDs, wrong scope, and output drift.
6. **Add exact planning and adversarial plan review.** No implementation task may contain a hidden design decision.
7. **Add low-powered mechanical implementers** with narrow file allowlists, exact commands, bounded context, and isolation units.
8. **Add independent test authorship, test execution, and code review.** Test trajectory quality and post-merge quality, not only final completion. Meta-evaluate the judge.
9. **Add trace-based failure attribution and the claim-to-evidence audit graph.**
10. **Add model routing and handoff policies.** Compare models by task, cost, latency, outcome, and failure type; test fresh escalation and downshift separately; measure the handoff tax.
11. **Add skills only after the harness can evaluate them.** Lint, privilege-check, paired-test, red-team, approve, version, and roll back every skill.
12. **Add the brainstormer and the research branch.** Keep both bounded and adversarially appraised; "no better idea" remains valid.
13. **Expand fan-out and concurrency only when measured gains justify coordination cost.** Compare against the strong single-agent baseline at every expansion.
14. **Add optional frontier escalation last.** It must remain rationed, logged, compressed, and policy-controlled.
15. **Experiment with automatic harness optimization last of all**, and only after safe rollback, versioning, module-scoped edit boundaries, and production-quality held-out evaluation exist.

## D.13 Open decisions the master must resolve before implementation

- Which coding environments, languages, repositories, operating systems, and tool providers are in scope first?
- What does "daily coding assistant" permit: read-only analysis, local edits, branch creation, test execution, commits, pull requests, or external actions?
- Which model providers and concrete models are available for the lowest, mid, high, and frontier tiers?
- What are the maximum per-task and per-day token, time, tool, and cost budgets?
- Which tasks may run in parallel, and what state manager, isolation unit, and commit serialization will prevent stale reads or conflicting writes?
- What sandbox memory budget caps parallel fanout?
- What data, secrets, repositories, logs, or MCP servers may cross agent boundaries?
- Which actions require human approval, and what evidence must be shown before approval?
- What baseline must the ecosystem beat, and what minimum quality, consistency, safety, and cost thresholds define success?
- Which skill formats, registry, signing, ownership, review, and rollback process will be used?
- What is the retention policy for raw traces, summaries, source files, prompts, model outputs, and sensitive data?
- MCP, CLI composition, or programmatic typed stubs as the primary tool surface — decided per tool volatility (see Part C, tension 2)?

## D.14 Minimum handoff contract to the building orchestrator

The building orchestrator must return, **before implementation**:

1. The proposed repository and folder structure.
2. The model-tier mapping and one-file model declarations.
3. The state and event-ledger schema.
4. The policy-gateway contract.
5. The specialist roster and exact job boundaries.
6. The prompt skeleton for each specialist.
7. The tool allowlists and permission tiers, including per-phase re-scoping.
8. The typed handoff and output schemas.
9. The sizing, clarification, and routing policy.
10. The evaluation matrix, matched baselines, and pinned harness configuration.
11. The testing, review, drift-control, and failure-attribution plan.
12. The smallest safe prototype and its stop and rollback conditions.
13. The unresolved decisions and `UNKNOWN`s.

**STRICT:** Do not begin implementation until the master has resolved or explicitly accepted every open decision required by the smallest safe prototype.

---

# Part E — Scored roadmap

Scoring follows the evidence-first formula: `benefit = .25·importance + .25·expected_impact + .15·risk_reduction + .15·ecosystem_leverage + .10·time_to_value + .10·(2·reversibility)`; `burden = .50·difficulty + .25·downside_risk + .25·operational_burden`; `raw = .70·benefit + .30·(11−burden)`; `adjusted = raw · confidence/100`. Sensitivity re-runs with confidence −20 and difficulty +2.

| Rank | ID | Recommendation | Band | Adjusted | Confidence | Sensitivity |
|---|---|---|---|---:|---:|---|
| 1 | R1 | Externalize plans, evidence, state, and checkpoints into an append-only ledger with deterministic projection | **NOW** | 7.72 | 95 | Remains NEXT-or-better under stress |
| 2 | R3 | Build a small, distinct, context-efficient tool surface with a quality gate | **NOW** | 7.53 | 90 | Falls to NEXT under stress |
| 3 | R2 | Establish trajectory-level evaluation and a strong single-agent baseline before autonomy | **NOW** | 7.50 | 90 | Falls to NEXT under stress |
| 4 | R7 | Type-aware, validated compaction with non-evictable rule/anchor slots | **NOW** | 7.44 | 90 | Falls to NEXT under stress |
| 5 | R8 | Deterministic policy gateway with per-phase privilege re-scoping at the execution boundary | **NOW** | 7.38 | 85 | Falls to NEXT under stress |
| 6 | R9 | Direction-specific handoff packets (compressed brief on escalation, retained trajectory on downshift) | **NEXT** | 6.62 | 80 | Remains NEXT |
| 7 | R10 | Isolation units plus write-intent conflict detection before any concurrent writes | **NEXT** | 6.41 | 80 | Remains NEXT |
| 8 | R11 | Failure attribution with component/fault-side ownership and replay-based critical-step localization | **NEXT** | 6.05 | 75 | Remains NEXT |
| 9 | R5 | Isolated multi-agent fan-out, only for task classes with a measured gain | **EXPERIMENT** | 5.19 | 80 | Remains EXPERIMENT |
| 10 | R4 | Human-governed, family-level skill evolution with a held-out commit gate | **EXPERIMENT** | 5.14 | 75 | Remains EXPERIMENT |
| 11 | R12 | Learned model routing from verified execution feedback | **EXPERIMENT** | 4.60 | 65 | Remains EXPERIMENT |
| 12 | R6 | Quality-diversity ideation as an optional research mode | **DEFER** | 3.20 | 60 | Remains DEFER |
| 13 | R13 | Automated harness self-optimization (meta-harness loop) | **DEFER** | 3.05 | 55 | Remains DEFER |

### Recommendation qualifications

- **R1** — importance 10, impact 9, difficulty 6, time-to-value 8, risk reduction 9, leverage 9, downside 4, burden 6, reversibility 5. Validate crash recovery, cross-agent resume, plan adherence, stale-state detection, and audit reconstruction. **Stop** if state writes corrupt active runs; **roll back** to read-only persistence.
- **R3** — importance 9, impact 9, difficulty 4, time-to-value 9, risk reduction 8, leverage 9, downside 3, burden 5, reversibility 5. Validate with tool-selection accuracy, schema errors, median response tokens, and task success. **Stop** if consolidation hides required controls; **roll back** by restoring the previous registry.
- **R2** — importance 10, impact 10, difficulty 6, time-to-value 7, risk reduction 10, leverage 9, downside 3, burden 7, reversibility 5. Start with 25–50 representative tasks plus held-out variants, including failures and ambiguous requests. Require deterministic assertions for critical outputs and no severe safety failures. **Stop** if judge-only metrics cannot be anchored to ground truth.
- **R7** — importance 10, impact 9, difficulty 5, time-to-value 8, risk reduction 10, leverage 8, downside 3, burden 5, reversibility 5. Validate by asserting that rules, permissions, acceptance criteria, and anchors survive five compaction rounds. **Stop** if recall of mandatory fields drops below threshold; **roll back** to no-compaction with shorter sessions.
- **R8** — importance 10, impact 9, difficulty 6, time-to-value 7, risk reduction 10, leverage 8, downside 3, burden 6, reversibility 4. Validate with injection attempts, forbidden-combination attempts, and mid-trajectory resource-access audits. **Stop** if the gateway blocks legitimate developer workflows; run observe-only mode first.
- **R9** — importance 8, impact 8, difficulty 5, time-to-value 7, risk reduction 7, leverage 8, downside 4, burden 5, reversibility 5. Measure handoff tax explicitly on escalate and downshift paths.
- **R10** — importance 9, impact 8, difficulty 6, time-to-value 6, risk reduction 9, leverage 7, downside 5, burden 6, reversibility 4. Validate with deliberate concurrent-write conflict tests.
- **R11** — importance 8, impact 8, difficulty 6, time-to-value 6, risk reduction 8, leverage 7, downside 4, burden 6, reversibility 5. Validate with failure-injection tests that replay a successful prefix and insert one known fault.
- **R5** — importance 8, impact 8, difficulty 7, time-to-value 5, risk reduction 7, leverage 8, downside 6, burden 8, reversibility 4. Compare against the single-agent baseline on quality, wall time, tokens, conflicts, and traceability. **Stop** if fan-out does not improve quality enough to offset cost and coordination failures.
- **R4** — importance 8, impact 8, difficulty 6, time-to-value 6, risk reduction 7, leverage 8, downside 5, burden 7, reversibility 4. Require review ownership, version diffs, held-out regression tests, bounded edit budgets, counterfactual A/B traces, and instant rollback. **Stop** after two updates with no held-out gain, or on any critical regression or clean-session carryover harm.
- **R12** — importance 7, impact 7, difficulty 7, time-to-value 5, risk reduction 6, leverage 8, downside 5, burden 7, reversibility 4. Requires a safe baseline, held-out evaluation, and bounded update policy first.
- **R6** — importance 6, impact 6, difficulty 7, time-to-value 4, risk reduction 4, leverage 6, downside 5, burden 7, reversibility 4. Research ideation only; measure portfolio yield, duplication, factual grounding, and human expert acceptance.
- **R13** — importance 6, impact 7, difficulty 8, time-to-value 3, risk reduction 4, leverage 7, downside 6, burden 8, reversibility 3. Requires module-scoped edits, one component per iteration, reviewed commits, frozen benchmark seeds, and a governance root outside the evolvable tree.

### Sequence

- **NOW:** R1, R3, R2, R7, R8.
- **NEXT:** R9, R10, R11.
- **EXPERIMENT:** R5, R4, R12.
- **DEFER:** R6, R13.

### DO NOT ADOPT

- Unbounded recursive self-improvement.
- A single shared conversation as the system of record.
- A large flat tool or skill catalog loaded into every run.
- Autonomous write or deploy authority enforced only by prompt instructions.
- LLM-as-judge as the sole approval gate for safety-critical outcomes.
- Continuous LLM rewriting of shared memory or skills without a gated consolidation step.
- Automated skill eviction driven by an uncalibrated judge.
- Comparing model or ecosystem variants without a pinned evaluation harness configuration.

---

# Part F — Seventeen-role implementation handoff

These are **proposals**. Nothing here authorizes implementation or side effects. Each applicable role receives the run manifest, recommendation IDs, source links, constraints, required outputs, dependencies, risks, and acceptance criteria.

| Role | Disposition | Objective and acceptance gate |
|---|---|---|
| **Master** | RECOMMENDED | Own the R1–R13 priorities, dependencies, budgets, and release gates. No autonomy expansion without baseline evidence. Gate: every NOW item has a named owner, a stop condition, and a rollback path. |
| **Planner** | RECOMMENDED | Produce the task DAG, the persisted plan, dependencies, serial-versus-parallel rationale, re-injection interval, and revision checkpoints. Gate: no task contains a hidden design decision. |
| **Worker** | RECOMMENDED | Execute one bounded contract with isolated context, tools, and worktree; return artifacts, evidence, trace, and verifier result. Gate: `PLAN_STALE` returned rather than improvised on precondition mismatch. |
| **Reviewer** | RECOMMENDED | Independently test invariants, unfavorable hypotheses, provenance, hidden cost, and rejection criteria. Gate: every finding cites a file, line, invariant, test, or repro; false-positive rate tracked. |
| **Test** | RECOMMENDED | Translate requirements into semantic assertions, negatives, adversarial cases, and mutation checks. Gate: every test fails if the change is reverted. |
| **Tester** | RECOMMENDED | Run authoritative commands in pinned environments and preserve raw, timestamped evidence. Gate: changed code is proven to have executed; coincidental green is ruled out. |
| **Question** | RECOMMENDED | Track the smallest decision-critical unknowns, the authoritative answer source, owner, and expiry. Gate: D.13 open decisions are resolved or explicitly accepted before the prototype starts. |
| **Idea** | RECOMMENDED | Generate alternatives with assumptions, reversibility, diversity, falsification, and selection criteria. Gate: label histograms monitored; `NO BETTER ALTERNATIVE FOUND` accepted as success. |
| **Debug** | RECOMMENDED | Maintain competing hypotheses, discriminating probes, controls, stop conditions, and incident artifacts. Gate: critical step and fault side identified, not just "the agent failed." |
| **Integration** | RECOMMENDED | Specify handoff schemas, lifecycle and ordering, compatibility, observability, retries, and failure propagation. Gate: every phase boundary has a typed contract and a validator. |
| **CARLA** | NOT_APPLICABLE | No CARLA simulator behavior is in scope for the orchestration ecosystem itself. Activate only when the assistant is pointed at vehicle-simulation runtime work, at which point API/version, world lifecycle, synchronization, ports, actors/sensors/Traffic Manager, and reproduction must be specified. |
| **Scenario** | RECOMMENDED | Define the evidence-packet, plan, task, and handoff schema meanings, producers and consumers, versioning, migrations, and behavioral negatives. Gate: schema changes are versioned with migrations. |
| **HMI** | NOT_APPLICABLE | No user-interface or warning-priority surface has been specified for this ecosystem. Activate when the assistant gains an operator-facing surface; then state meaning, warning priority, stale/unknown behavior, accessibility, and codec/transport must be defined. |
| **Performance** | RECOMMENDED | Benchmark latency, tokens, cost, success distribution, repeated runs, caching, and contamination. Gate: cost per verified pass reported with a pinned harness configuration and score bands. |
| **ROS2** | NOT_APPLICABLE | No ROS2 graph, QoS, frame, clock, or lifecycle scope appears in this specification. Activate only if the assistant is given ROS2 runtime responsibilities. |
| **Environment** | RECOMMENDED | Pin models, prompts, tools, dependencies, permissions, resources, sandbox memory budgets, and preflight checks. Gate: a run is reproducible from the ledger alone. |
| **GUI** | NOT_APPLICABLE | No GUI implementation target is in scope. Future activation requires parity, accessibility, state flow, IPC/security, fallback, and packaging contracts. |

---

# Part G — Limitations and research backlog

### Limitations of this document

- Status is `PARTIAL`. Of **324** catalogued sources, 27 were read as full text, **150** were verified at abstract level by direct fetch, and the remainder rest on curated-index metadata plus abstracts.
- Numbers are transcribed from their sources, **not independently reproduced**.
- Cross-source comparisons (for example, harness spread versus skill gain) mix benchmarks, models, and harnesses. They are **not** controlled comparisons.
- Most evidence comes from coding benchmarks, terminal and web agents, research ideation, or bounded specialist domains. External generalization to a specific daily-driver workload is unproven.
- The 2026-09 expansion papers were selected and summarized primarily from arXiv abstracts. **Read the full texts before locking any implementation detail on them.**
- One originally supplied source, the Hitchhiker's Guide manuscript (`2606.24937`), yielded no extractable body on first retrieval; only table-of-contents-level scope is recorded in the companion brief. Re-fetch before citing any specific claim from it.
- The title "Plans Don't Persist: Why Context Management Is Load Bearing for LLM Agents" was supplied without a URL. It resolved to **arXiv 2606.22953** (Aman Mehta and Anupam Datta, Snowflake AI Research) and was then read in full. Confirm that is the intended paper.

### Residual weaknesses that survive this analysis

1. **The token-frugality thesis is not proven for this workload.** The strongest supporting result (a small model recovering 89.7% of large-model performance at 4% of cost) was strongest on *repetitive business workflows*, and the single-agent-baseline paper found a single agent matching optimized multi-agent workflows more cheaply. Whether many weak agents plus one strong master beats one strong agent on *your* daily coding tasks is an open empirical question that only your baseline can answer.
2. **Adversarial-everywhere review has an unmeasured cost.** Review agents that hunt for every hidden issue produce noise, and judges flip verdicts 25–71% under pushback. The false-positive budget for "always adversarial" is not established.
3. **The alignment checker is asked to do a hard job with the cheapest model.** Monitoring research shows agent awareness of monitoring degrades monitor reliability more than monitor weakness does, and that weak monitors need hybrid scaffolding to supervise stronger agents. A lowest-tier zero-shot checker will probably underperform its spec.
4. **The recon-lane result may not survive the move to prompting.** The clearest validation of cheap read-only recon used a *trained* 4B–30B exploration model. Nothing in the corpus establishes that a prompted cheap model produces the same token reduction, and a weak prompted lane that returns paraphrase instead of locators would plausibly produce the opposite effect.
5. **Routing savings and routing evaluation are the same measurement.** The 85% cost reduction and the 88% oracle-bias cost inflation come from the same work. Until the debiasing procedure is implemented and validated locally, the router's reported savings should be treated as an upper bound, not an estimate.
6. **The field data undercuts the whole premise more than any benchmark does.** If only ~44% of agent-authored code survives to commit in real sessions, the dominant cost in a daily-driver assistant may be discarded work rather than tokens spent — in which case optimizing token economy is optimizing the smaller term. This spec does not currently measure discarded-work cost.

### Research backlog for the next agent

1. Read the full texts of all 2026-09 expansion papers before locking implementation details; verify whether reported results transfer to the target daily-coding workload, inspecting code and benchmarks where available.
2. Re-fetch `2606.24937` (Hitchhiker's Guide) for body-level claims.
3. Confirm `2606.22953` is the intended "Plans Don't Persist" paper.
4. Define the target orchestration's domain, users, risk classification, side effects, latency and cost envelope, and deployment environment.
5. Inventory the actual tools and data sources; measure registry size and response-token cost rather than importing generic thresholds.
6. Select 25–50 representative tasks with deterministic or human-verifiable outcomes, including failures and ambiguous requests.
7. **Establish the strong single-agent baseline before any multi-agent implementation.**
8. Decide whether durable workflow, typed shared state, streaming, and suspend/resume requirements justify a framework, or whether CLI/MCP/programmatic composition suffices.
9. Define the authorization model and human approval boundaries before enabling writes.
10. Determine memory retention, privacy, provenance, expiry, correction, and deletion rules.
11. Calibrate judge false-pass rate on a locked anchor set before enabling any automated skill eviction or self-improvement gate.
12. Run a harness-fragility check (multiple configurations, same items) before claiming any multi-agent or model-swap win.
13. Build failure-injection tests that preserve a successful prefix and insert one known fault, to measure whether diagnosis finds the correct step.
14. Produce a deployment-readiness checklist before granting broader permissions.
15. Measure whether a **prompt-only** recon lane reproduces any part of the trained-explorer token reduction, and whether requiring file-and-line locators is what carries the effect.
16. Implement and validate the router debiasing procedure before reporting any routing cost saving.
17. Instrument **survival rate** — the share of agent-produced changes that reach a committed revision — and the user correction rate, so the definition of done rests on field data rather than benchmark resolution.
18. Add the ten trust dimensions to the ledger's trace schema and check whether completion and trust diverge on this workload as they did in the source study.
19. Measure the cost of discarded work alongside token cost, and re-rank the token-economy constraint if discarded work dominates.
