# Priority Additions from ai-agent-papers (by plan gap)

**Discovery corpus:** [masamasa59/ai-agent-papers](https://github.com/masamasa59/ai-agent-papers)  
**Rule:** These are **additions** that constrain the daily-driver plan. Many already appear in [`../agent_orchestration_research_library.md`](../agent_orchestration_research_library.md). This file orders them by **the five gaps that decide your design**, not by publication date.

**Evidence depth:** Prefer `ABS-VERIFIED` / library TIER marks. Do not lock numbers from titles alone.

**Tiers here**

| Tier | Meaning |
|---|---|
| **A** | Changes a core decision for *this* ecosystem — read before building that subsystem |
| **B** | Strong implementation guidance — read while building |
| **C** | Specialized / optional — read when you hit that failure |

---

## Gap G1 — When is fan-out worth it? (vs strong single agent)

*Your plan fans out by default for research. Evidence says fan-out is a hypothesis.*

### A · Rethinking the Value of Multi-Agent Workflow: A Strong Single Agent Baseline
https://arxiv.org/abs/2601.12307  
Single agent matched homogeneous (and optimized heterogeneous) multi-agent workflows at lower cost on seven benchmarks.  
**Design:** Every multi-agent route must beat a strong single-agent baseline or **collapse**.

### A · Can Small Agents Collaborate to Beat a Single Large Language Model?
https://arxiv.org/abs/2601.11327  
Small-agent systems can win on tool-heavy work; gains concentrate in **orchestrator reasoning**; reasoning in sub-agents often limited/negative.  
**Design:** Master = reasoning center; workers = observe / retrieve / execute / report.

### A · Towards a Science of Scaling Agent Systems
https://arxiv.org/abs/2512.08296  
260 configs × 5 architectures × 6 agentic benchmarks. Capability ceiling: when single-agent already strong, extra agents can hurt. Tool-heavy tasks incur MAS overhead. Centralized verification reduces error amplification vs independent. Relative MAS delta spans ~+81% to ~−70% by task.  
**Design:** Size gate chooses architecture by **task structure**, not ceremony. Prefer centralized master for verification bottlenecks.

### A · Why Do Multi-Agent LLM Systems Fail?
https://arxiv.org/abs/2503.13657  
1,600+ traces; 14 failure modes in design / misalignment / verification.  
**Design:** Tag rejected runs with failure family; do not fix every failure by rewriting prompts.

### A · The Collaboration Gap
https://arxiv.org/abs/2511.02687  
Strong solo models often **degrade** when forced to collaborate; relay (strong leads → weak continues) mitigates.  
**Design:** Avoid unconstrained peer chat for recon; prefer master-mediated handoffs with compressed packets. Heterogeneous pairing needs deliberate initiator order.

### B · Language Model Teams as Distributed Systems
https://arxiv.org/abs/2603.12229  
Parallelizability vs coupling; stale reads; stragglers; sycophantic agreement.  
**Design:** Recon = message-passing, no shared writes; straggler timeouts; partial results with `UNKNOWN`.

### B · Position: Multi-Agent Systems Should Prioritize Concurrency Control
https://arxiv.org/abs/2608.18092  
Stale reads / lost updates dominate under long inference windows.  
**Design:** Worktree isolation per implementer; write-intent conflict detection.

### B · Difficulty-Aware Agentic Orchestration
https://arxiv.org/abs/2509.11079  
Query-specific routing with feedback.  
**Design:** Sizing gate estimates difficulty/uncertainty/risk/verifiability → route + tier.

### B · AOrchestra: Automating Sub-Agent Creation
https://arxiv.org/abs/2602.03786  
Sub-agent = ⟨Instruction, Context, Tools, Model⟩; orchestrator spawns, does not execute.  
**Design:** Template for per-folder specialist manifests.

### C · Multi-Agent Design: Optimizing Agents with Better Prompts and Topologies
https://arxiv.org/abs/2502.02533  
Topology as optimizable artifact.  
**Design:** Version and evaluate topology; do not hard-code one forever.

### C · Inference-Time Graph Engineering for Multi-Agent LLM Workflows
https://arxiv.org/abs/2609.05774  
Phase-conditioned workflow graphs.  
**Design:** Master emits DAG into ledger with edge message contracts.

### C · When Agents Coordinate: Measuring Coordination in Multi-Agent AI Coding
https://arxiv.org/abs/2608.16801  
Coordination metrics for coding MAS.  
**Design:** Instrument merge conflicts / duplicated work / ownership violations.

---

## Gap G2 — State, handoffs, plans, context (prevent silent drift)

*Your plan needs external plans, phase anchors, and alignment gates.*

### A · Plans Don't Persist
https://arxiv.org/abs/2606.22953  
Plan signal collapses across action–observation steps; naive eviction catastrophic; plan-pin alone insufficient.  
**Design:** External plan + re-inject plan **and** recent actions/observations; type-aware compaction.

### A · From Plan to Action
https://arxiv.org/abs/2604.12147  
Periodic reminders help; **bad plan worse than no plan**.  
**Design:** Plan review + evidence-triggered replan.

### A · The Handoff Tax
https://arxiv.org/abs/2608.24358  
Escalating with full weak trajectory recovers little of the quality gap at high cost.  
**Design:** Escalate with **fresh compressed decision brief**; retain strong trajectory on downshift.

### A · Stay Focused: Problem Drift in Multi-Agent Debate
https://arxiv.org/abs/2502.19559  
Debate drifts from the stated problem.  
**Design:** Alignment checker + task-anchor VALIDATE at every phase gate.

### A · The Compaction Cliff
https://arxiv.org/abs/2608.22752  
Naive compaction destroys safety/rules recall.  
**Design:** Non-evictable slots for rules, permissions, acceptance criteria, task anchor.

### A · Stateless Decision Memory / Log-as-Agent patterns
https://arxiv.org/abs/2605.22148 (see library Type 4) · https://arxiv.org/abs/2608.21690 (Context as Environment)  
Append-only log + deterministic projection beats mutable summarized memory under tight budgets.  
**Design:** Ledger is SoR; working context is a projection.

### B · Useful Memories Become Faulty When Continuously Updated by LLMs
https://arxiv.org/abs/2605.17453 (library Type 4)  
Continuous LLM rewrite of memory degrades even with ground truth.  
**Design:** Ban continuous shared-memory rewrite; gated consolidate only.

### B · Less Context, Better Agents
https://arxiv.org/abs/2608.15703 (HyMem / related Less-Context line in library)  
Keep last-N tool pairs; summarize evicted; never prune anchors.  
**Design:** Implementer context policy in gateway.

### B · Detecting Silent Failures in Multi-Agentic AI Trajectories
https://arxiv.org/abs/2511.04032  
Trajectory anomalies without obvious final failure.  
**Design:** Silent-failure detector before master synthesis.

### B · LEDGER: Claim-to-Evidence Trace Graphs
https://arxiv.org/abs/2608.18398  
Claim→evidence graphs for audit.  
**Design:** Require claim/evidence IDs in every packet.

### C · LLMs Get Lost in Evolving User Intent
https://arxiv.org/abs/2607.20734  
Intent drift over long sessions.  
**Design:** Immutable task anchor + clarification gate; restate acceptance criteria.

### C · Federation over Text / Belief graphs
https://arxiv.org/abs/2604.16778 · https://arxiv.org/abs/2604.23057  
Insight sharing without dumping full graphs into LLM context.  
**Design:** Structured handoff packets, not transcript forwarding.

---

## Gap G3 — Model routing, cost, and low-tier volume

*Your plan: many weak models for volume; rare frontier on compressed briefs.*

### A · FastContext: Training Efficient Repository Explorer
https://arxiv.org/abs/2606.14066  
Cheap exploration sub-agent (4B–30B) can raise resolution while cutting coding-agent tokens (up to ~60% in reported setting).  
**Design:** Recon returns **file/line citations**, not prose. Caveat: trained explorer — prompt-only may not match numbers.

### A · Agent-as-a-Router
https://arxiv.org/abs/2606.22902  
Routing models for coding tasks.  
**Design:** Log features → model → cost → verifier; learn only after safe baseline.

### A · The Capability Frontier
https://arxiv.org/abs/2606.26836  
Routing/selection savings large; **naive oracle bias** inflates reported gains.  
**Design:** Debias router self-measurement before trusting savings.

### A · BAGEN: Are LLM Agents Budget-Aware?
https://arxiv.org/abs/2606.00198  
Agents do not reliably know remaining budget.  
**Design:** Policy gateway enforces budgets; `BUDGET:` in prompts is documentation only.

### A · To CoT or not to CoT?
https://arxiv.org/abs/2501.17070 (see library A22 citation line)  
CoT gains concentrated in math/symbolic; elsewhere near flat; knowledge tasks can worsen with more thinking.  
**Design:** Extended reasoning **off** for recon/extract/transcribe; retrieve instead of think for knowledge gaps.

### B · Efficient Agents: Building Effective Agents While Reducing Cost
https://arxiv.org/abs/2508.02694  
Cost/quality trade-space for agent systems.  
**Design:** Primary metric = **cost per verified pass**.

### B · Better Harnesses, Smaller Models (~90% cheaper)
https://arxiv.org/abs/2607.08938  
Harness adaptation can substitute for larger models.  
**Design:** Optimize harness before defaulting to frontier.

### B · Reward Modeling for Multi-Agent Orchestration
https://arxiv.org/abs/2606.13598  
Orchestration-level reward model for BoN / continued orchestrator training; large token savings vs full sub-agent rollouts.  
**Design:** Later: score orchestration trajectories, not only final answers — after human-governed eval baseline exists.

### B · Position: agentic AI orchestration should be Bayes-consistent
https://arxiv.org/abs/2605.00742  
Belief + utility in control layer for routing/stopping/escalation.  
**Design:** Formal backbone for sizing gate and single frontier escalation.

### C · Second Thought: Reasoning in Parallel as Agents Act
https://arxiv.org/abs/2608.13667  
Idle-time parallel reasoning during tool waits.  
**Design:** Prefetch/alignment during IO waits; never replace master authority.

### C · Memory Compression for High-Fanout Agent Sandboxes
https://arxiv.org/abs/2609.11294  
Cap parallel sandboxes by memory, not only tokens.

---

## Gap G4 — Skills that are safe, subtask-grained, cost-aware

*Your plan will grow skills; corpus says skills can help or poison.*

### A · Demystifying Agent Skills / Break It Down / SkillGLoW / Who Maintains?
https://arxiv.org/abs/2608.14036 · https://arxiv.org/abs/2608.20274 · https://arxiv.org/abs/2609.02217 · https://arxiv.org/abs/2609.05677  
Procedural anchors; subtask > task-level; family consolidation; **100% human merge** in observed repos.  
**Design:** Already in original corpus — non-negotiable for skill lifecycle.

### A · The Regression Tax
https://arxiv.org/abs/2607.22520  
Decomposes when skills help vs hurt.  
**Design:** Reject skills that raise tokens/steps without outcome gain.

### A · Practice Makes Unsafe / EvoMal
https://arxiv.org/abs/2608.12851 · https://arxiv.org/abs/2608.25776  
Self-evolved skills as attack/carryover surface.  
**Design:** Provenance, quarantine, clean-session carryover tests; no autonomous shared rewrite.

### A · SkillScope (least privilege)
https://arxiv.org/abs/2605.05868  
Fine-grained privilege for skills.  
**Design:** Task-conditioned allowlists at action level.

### B · Counterfactual Trace Auditing of Skills
https://arxiv.org/abs/2605.11946  
A/B attribution before merge.

### B · SkillsVote / Who Grades the Grader?
https://arxiv.org/abs/2605.18401 · https://arxiv.org/abs/2607.12790  
Lifecycle governance; frozen holdout for metrics.  
**Design:** Never validate a self-evolved grader with the score it produces.

### B · SWE-Skills-Bench / What Keeps Skills from Being Reusable?
https://arxiv.org/abs/2603.15401 · https://arxiv.org/abs/2608.08453  
Real SWE helpfulness; 138K SKILL.md failure modes.  
**Design:** Cap library width; lint + execution gates.

### C · Act More, Decide Less / SKILLALIGN
https://arxiv.org/abs/2609.02042 · https://arxiv.org/abs/2609.07255  
Action chunking; interface alignment.  
**Design:** Skills as checklists/tool order, not encyclopedias.

### C · Evaluating AGENTS.md
https://arxiv.org/abs/2602.11988  
Always-on repo context can raise cost without general success gains.  
**Design:** Keep AGENTS.md / always-on rules short, unusual, enforceable.

---

## Gap G5 — Trajectory evaluation, review quality, coding reality

*Your plan: adversarial plan/code/test; meaningful tests; field expectations.*

### A · PHMForge (already S09)
https://arxiv.org/abs/2604.01532  
Orchestration/sequencing dominate; measure stages separately.

### A · Model or Harness? / TrajDebug / Credit Without Ground Truth
https://arxiv.org/abs/2607.28802 · https://arxiv.org/abs/2608.06346 · https://arxiv.org/abs/2608.19760  
Localize component × fault side; prefer executed replay over step-LLM judges.  
**Design:** Failure diagnostician phase; first-local vs critical error.

### A · CR-Bench / Jagged Judges
https://arxiv.org/abs/2603.11078 · https://arxiv.org/abs/2608.12645  
Review usefulness/SNR; judges flip under pressure.  
**Design:** ADVERSARIAL = evidence-bound; temperature-0 + challenge round; freeze packets during review.

### A · SWE-chat (field baseline)
https://arxiv.org/abs/2604.20779  
~44% agent code survives to commit; high user pushback.  
**Design:** Definition of done against field survival, not only SWE-bench.

### A · There Is No Neutral Harness
https://arxiv.org/abs/2608.21382  
Leaderboard scores are config-fragile.  
**Design:** Pin harness config in ledger; report bands.

### A · One Success Isn't Reliability
https://arxiv.org/abs/2608.19741  
Repeated trials required for stateful workflows.  
**Design:** pass-all-k; preserve raw traces.

### B · AgentAudit / A2E
https://arxiv.org/abs/2609.09875 · https://arxiv.org/abs/2608.07346  
Full-lifecycle trust / end-to-end audit.  
**Design:** Ten trust dimensions in ledger schema (see master spec A23).

### B · FastContext / CONTEXTBENCH / Is Grep All You Need?
https://arxiv.org/abs/2606.14066 · https://arxiv.org/abs/2602.05892 · https://arxiv.org/abs/2605.15184  
Recon tool defaults: grep/BM25 + pointers; vector RAG as escalation.

### B · Building Effective AI Coding Agents for the Terminal
https://arxiv.org/abs/2603.05344  
Scaffolding/harness/context lessons.  
**Design:** Practical coding-agent harness checklist.

### C · Measuring Agents in Production
https://arxiv.org/abs/2512.04123  
Production measurement practice.

### C · Tangent: Testing Practices for LLM Agent Applications
https://arxiv.org/abs/2608.08413  
How teams actually test agent apps.

---

## Practitioner anchors (already in original corpus; keep first)

| Link | Role |
|---|---|
| https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/ | Specialist instruction contracts |
| https://www.anthropic.com/engineering/writing-tools-for-agents | Tool surface |
| https://cursor.com/blog/agent-best-practices | Plan / worktrees / iteration caps |
| https://www.anthropic.com/engineering/building-effective-agents | Complexity ladder |

---

## Category pages to re-sweep when the index updates

From the repo taxonomy (re-open these when planning a subsystem):

| Gap | Category page |
|---|---|
| G1 | `architecture/multi-agent.md`, `architecture/harness.md` |
| G2 | `capabilities/knowledge-context/context-engineering.md`, `capabilities/knowledge-context/memory.md` |
| G3 | `capabilities/trust/evaluation.md` (cost/routing), harness optimization sections |
| G4 | `capabilities/action/skills.md`, `operations/governance.md` |
| G5 | `capabilities/adaptation/failure-attribution.md`, `applications/system/coding-agents.md` |

Newsletter deep-dives (Aug 2026): harness, safety, evaluation, self-evolution, skills, failure attribution, learning, governance under `newsletters/aug_2026/`.

---

## What not to add yet (noise relative to this plan)

- Pure GUI/mobile/web-computer-use agents unless the daily driver expands there.
- Finance/enterprise vertical agents without shared harness lessons.
- Ungated self-evolution papers as implementation recipes (use only as **warning + gate design**).
- Debate-as-default topologies (problem drift + collaboration gap argue against free debate for recon).

---

## Suggested next research actions

1. Full-text pass on any Gap G1–G5 **Tier A** item still `ABS`/`INDEX` in the library before locking that subsystem.
2. Confirm `2606.22953` is the intended *Plans Don't Persist* paper with the human owner.
3. After target requirements (G01/G05) exist, re-score recommendations in the master spec with domain-specific weights.
