# References — Agent Orchestration & Daily-Driver Ecosystem

Curated bibliography for designing and planning the modular, token-frugal daily-driver agent ecosystem.

**Deep cards & implications:** [`sources/README.md`](sources/README.md)  
**Build contract:** [`agent_orchestration_master_spec.md`](agent_orchestration_master_spec.md) (Part D)  
**Full typed library (~324):** [`agent_orchestration_research_library.md`](agent_orchestration_research_library.md)  
**Discovery index:** [masamasa59/ai-agent-papers](https://github.com/masamasa59/ai-agent-papers)

---

## 1. Practitioner & vendor guidance

| Ref | Title | Link |
|---|---|---|
| P1 | How to write a great agents.md: Lessons from over 2,500 repositories | https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/ |
| P2 | Writing effective tools for agents — with agents | https://www.anthropic.com/engineering/writing-tools-for-agents |
| P3 | Best practices for coding with agents | https://cursor.com/blog/agent-best-practices |
| P4 | Building effective agents | https://www.anthropic.com/engineering/building-effective-agents |

---

## 2. Original research corpus (supplied links)

| Ref | Title | Link |
|---|---|---|
| R01 | AutoDesign: Meta-Harness Optimization for Long-Horizon Agentic Design | https://arxiv.org/abs/2608.13560 |
| R02 | The Hitchhiker's Guide to Agentic AI: From Foundations to Systems | https://arxiv.org/abs/2606.24937 |
| R03 | Agents All the Way Down: A Methodology for Building Custom AI Agents from Substrate to Production | https://arxiv.org/abs/2606.11869 |
| R04 | From Question Answering to Task Completion: A Survey on Agent System and Harness Design | https://arxiv.org/abs/2606.20683 |
| R05 | PHMForge: Evaluating LLM Agents on Industrial Prognostics through MCP-Native, Algorithm-Grounded Tools | https://arxiv.org/abs/2604.01532 |
| R06 | SkillAdam: Stable and Efficient Skill Evolution for Agents | https://arxiv.org/abs/2609.08944 |
| R07 | SkillGLoW: Procedural-Family Skill Consolidation for Self-Improving Agents | https://arxiv.org/abs/2609.02217 |
| R08 | Who Maintains Agent Skills? A Longitudinal Study of Human-Governed, AI-Assisted Skill Maintenance | https://arxiv.org/abs/2609.05677 |
| R09 | Break It Down, Pass It On: Cross-Task Skill Transfer in LLM Agents | https://arxiv.org/abs/2608.20274 |
| R10 | Demystifying Agent Skills: Why They Work—Until They Don't | https://arxiv.org/abs/2608.14036 |
| R11 | SkillGenBench: Benchmarking Skill Generation Pipelines for LLM Agents | https://arxiv.org/abs/2605.18693 |
| R12 | CRAFT: Learn the Schema, Execute the Plan | https://arxiv.org/abs/2607.22642 |
| R13 | Planning in the LLM Era: Building for Reliability and Efficiency | https://arxiv.org/abs/2605.21902 |
| R14 | Plans Don't Persist: Why Context Management Is Load Bearing for LLM Agents | https://arxiv.org/abs/2606.22953 |
| R15 | From Plan to Action: How Well Do Agents Follow the Plan? | https://arxiv.org/abs/2604.12147 |
| R16 | Self-Questioning Language Models | https://arxiv.org/abs/2508.03682 |
| R17 | DeepLens Diagnosis Agent: Agentic Workflow Design Lets a Small Reasoning Model Compete with Frontier LLMs | https://arxiv.org/abs/2607.22555 |
| R18 | Harnessing Pre-Resolution Signals for Future Prediction Agents | https://arxiv.org/abs/2604.15719 |
| R19 | Communicate–Predict–Act: Evaluating Social Intelligence of Agents | https://arxiv.org/abs/2604.08727 |
| R20 | AgentIdeaBench: Benchmarking Scientific Ideation in the Agent Era | https://arxiv.org/abs/2609.07611 |
| R21 | When AI Designs AI: Innovation or Imitation? | https://arxiv.org/abs/2608.17471 |
| R22 | IDEAgent: Agentic Quality-Diversity Search for Research Idea Generation | https://arxiv.org/abs/2607.22375 |
| R23 | Measuring the Gap Between Human and LLM Research Ideas | https://arxiv.org/abs/2607.01233 |

**Citation note:** The title *Plans Don't Persist…* was sometimes listed next to `2605.21902`. That ID is *Planning in the LLM Era* (R13). *Plans Don't Persist* is **R14** (`2606.22953`).

---

## 3. Priority additions (by design gap)

From [ai-agent-papers](https://github.com/masamasa59/ai-agent-papers). Full rationale: [`sources/priority_additions_by_plan_gap.md`](sources/priority_additions_by_plan_gap.md).

### 3.1 Fan-out vs strong single agent

| Ref | Title | Link |
|---|---|---|
| A01 | Rethinking the Value of Multi-Agent Workflow: A Strong Single Agent Baseline | https://arxiv.org/abs/2601.12307 |
| A02 | Can Small Agents Collaborate to Beat a Single Large Language Model? | https://arxiv.org/abs/2601.11327 |
| A03 | Towards a Science of Scaling Agent Systems | https://arxiv.org/abs/2512.08296 |
| A04 | Why Do Multi-Agent LLM Systems Fail? | https://arxiv.org/abs/2503.13657 |
| A05 | The Collaboration Gap | https://arxiv.org/abs/2511.02687 |
| A06 | Language Model Teams as Distributed Systems | https://arxiv.org/abs/2603.12229 |
| A07 | Position: Multi-Agent Systems Should Prioritize Concurrency Control | https://arxiv.org/abs/2608.18092 |
| A08 | Difficulty-Aware Agentic Orchestration for Query-Specific Multi-Agent Workflows | https://arxiv.org/abs/2509.11079 |
| A09 | AOrchestra: Automating Sub-Agent Creation for Agentic Orchestration | https://arxiv.org/abs/2602.03786 |
| A10 | Multi-Agent Design: Optimizing Agents with Better Prompts and Topologies | https://arxiv.org/abs/2502.02533 |
| A11 | Inference-Time Graph Engineering for Multi-Agent LLM Workflows | https://arxiv.org/abs/2609.05774 |
| A12 | When Agents Coordinate: Measuring Coordination in Multi-Agent AI Coding | https://arxiv.org/abs/2608.16801 |

### 3.2 Plans, context, state, handoffs

| Ref | Title | Link |
|---|---|---|
| C01 | Plans Don't Persist (see also R14) | https://arxiv.org/abs/2606.22953 |
| C02 | From Plan to Action (see also R15) | https://arxiv.org/abs/2604.12147 |
| C03 | The Handoff Tax: Continuing Non-Native Trajectories in LLM Agents | https://arxiv.org/abs/2608.24358 |
| C04 | Stay Focused: Problem Drift in Multi-Agent Debate | https://arxiv.org/abs/2502.19559 |
| C05 | The Compaction Cliff in Long-Running AI Agent Memory | https://arxiv.org/abs/2608.22752 |
| C06 | Context as an Environment: Programmatic Context Management for Long-Horizon Agents | https://arxiv.org/abs/2608.21690 |
| C07 | Detecting Silent Failures in Multi-Agentic AI Trajectories | https://arxiv.org/abs/2511.04032 |
| C08 | LEDGER: Claim-to-Evidence Trace Graphs for Auditing LLM Agents | https://arxiv.org/abs/2608.18398 |
| C09 | LLMs Get Lost in Evolving User Intent | https://arxiv.org/abs/2607.20734 |
| C10 | Federation over Text: Insight Sharing for Multi-Agent Reasoning | https://arxiv.org/abs/2604.16778 |

### 3.3 Routing, cost, low-tier volume

| Ref | Title | Link |
|---|---|---|
| K01 | FastContext: Training Efficient Repository Explorer for Coding Agents | https://arxiv.org/abs/2606.14066 |
| K02 | Agent-as-a-Router: Agentic Model Routing for Coding Tasks | https://arxiv.org/abs/2606.22902 |
| K03 | The Capability Frontier: Benchmarks Miss 82% of Model Performance | https://arxiv.org/abs/2606.26836 |
| K04 | BAGEN: Are LLM Agents Budget-Aware? | https://arxiv.org/abs/2606.00198 |
| K05 | Efficient Agents: Building Effective Agents While Reducing Cost | https://arxiv.org/abs/2508.02694 |
| K06 | Better Harnesses, Smaller Models: Building 90% Cheaper Agents via Automated Harness Adaptation | https://arxiv.org/abs/2607.08938 |
| K07 | Reward Modeling for Multi-Agent Orchestration | https://arxiv.org/abs/2606.13598 |
| K08 | Position: agentic AI orchestration should be Bayes-consistent | https://arxiv.org/abs/2605.00742 |
| K09 | Second Thought: Reasoning in Parallel as LLM Agents Act and Observe | https://arxiv.org/abs/2608.13667 |
| K10 | Memory Compression for High-Fanout Agent Sandboxes | https://arxiv.org/abs/2609.11294 |
| K11 | Is Grep All You Need? How Agent Harnesses Reshape Agentic Search | https://arxiv.org/abs/2605.15184 |

### 3.4 Skills, governance, safety

| Ref | Title | Link |
|---|---|---|
| S01 | The Regression Tax: Decomposing Why Skills Help — and Hurt — LLM Agents | https://arxiv.org/abs/2607.22520 |
| S02 | Practice Makes Unsafe: Skill Misevolution in Self-Improving LLM Agents | https://arxiv.org/abs/2608.12851 |
| S03 | EvoMal: Self-Poisoning in Self-Evolving Coding Agents | https://arxiv.org/abs/2608.25776 |
| S04 | SkillScope: Toward Fine-Grained Least-Privilege Enforcement for Agent Skills | https://arxiv.org/abs/2605.05868 |
| S05 | Counterfactual Trace Auditing of LLM Agent Skills | https://arxiv.org/abs/2605.11946 |
| S06 | SkillsVote: Lifecycle Governance of Agent Skills | https://arxiv.org/abs/2605.18401 |
| S07 | Who Grades the Grader? Co-Evolving Evaluation Metrics and Skills | https://arxiv.org/abs/2607.12790 |
| S08 | SWE-Skills-Bench: Do Agent Skills Actually Help in Real-World Software Engineering? | https://arxiv.org/abs/2603.15401 |
| S09 | What Keeps Agent Skills from Being Reusable? Evidence from 138K SKILL.md Files | https://arxiv.org/abs/2608.08453 |
| S10 | Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents? | https://arxiv.org/abs/2602.11988 |
| S11 | Act More, Decide Less: Skill-Guided Adaptive Action Chunking | https://arxiv.org/abs/2609.02042 |
| S12 | SKILLALIGN: Aligning Skill Interfaces for LLM-based Agents | https://arxiv.org/abs/2609.07255 |

### 3.5 Evaluation, failure attribution, coding reality

| Ref | Title | Link |
|---|---|---|
| E01 | Model or Harness? An Interaction-Centric Taxonomy for Localizing Agent Failures | https://arxiv.org/abs/2607.28802 |
| E02 | TrajDebug: Tracing Error Lifecycle to Identify Critical Failures | https://arxiv.org/abs/2608.06346 |
| E03 | Credit Without Ground Truth: Auditing Step-Level Credit Assignment | https://arxiv.org/abs/2608.19760 |
| E04 | CR-Bench: Evaluating the Real-World Utility of AI Code Review Agents | https://arxiv.org/abs/2603.11078 |
| E05 | Jagged Judges: Epistemic Stability Under Silence, Pressure, and Persistence | https://arxiv.org/abs/2608.12645 |
| E06 | SWE-chat: Coding Agent Interactions From Real Users in the Wild | https://arxiv.org/abs/2604.20779 |
| E07 | There Is No Neutral Harness: Modern LLM Leaderboards Are Manufactured by Config-Fragile Items | https://arxiv.org/abs/2608.21382 |
| E08 | One Success Isn't Reliability (Thinkingbox) | https://arxiv.org/abs/2608.19741 |
| E09 | AgentAudit: Full-Lifecycle Trust Evaluation of AI Agents | https://arxiv.org/abs/2609.09875 |
| E10 | A2E: An End-to-End Agent Auditing Engine | https://arxiv.org/abs/2608.07346 |
| E11 | CONTEXTBENCH: A Benchmark for Context Retrieval in Coding Agents | https://arxiv.org/abs/2602.05892 |
| E12 | Building Effective AI Coding Agents for the Terminal | https://arxiv.org/abs/2603.05344 |
| E13 | Measuring Agents in Production | https://arxiv.org/abs/2512.04123 |
| E14 | Tangent: Testing Practices for LLM-Based Agent Applications | https://arxiv.org/abs/2608.08413 |
| E15 | Harness-Bench: Measuring Harness Effects across Models | https://arxiv.org/abs/2605.27922 |

---

## 4. Quick topic map

| If you are deciding… | Start with |
|---|---|
| Specialist prompts / AGENTS.md | P1, S10 |
| Tool catalog shape | P2, R05 |
| Plan Mode / worktrees / loops | P3 |
| Workflow vs agent complexity | P4, R04 |
| Whether to fan out at all | A01–A05, A03 |
| Where reasoning lives | A02, A09 |
| External plans & context | R14, R15, C03–C06 |
| Model routing & cost | K01–K06, K08 |
| Skills lifecycle | R06–R11, S01–S07 |
| Adversarial review / eval | E01–E08, R05 |
| Ideation / brainstormer | R20–R23 |

---

## 5. Related internal docs

| Doc | Role |
|---|---|
| [`README.md`](README.md) | Documentation index |
| [`sources/README.md`](sources/README.md) | Sources hub |
| [`sources/original_corpus_S01-S26.md`](sources/original_corpus_S01-S26.md) | Per-source research cards |
| [`sources/architecture_synthesis.md`](sources/architecture_synthesis.md) | Cross-source architecture synthesis |
| [`sources/priority_additions_by_plan_gap.md`](sources/priority_additions_by_plan_gap.md) | Gap-ordered paper justifications |
| [`sources/next_agent_checklist.md`](sources/next_agent_checklist.md) | Investigation checklist |
| [`agent_orchestration_research_brief.md`](agent_orchestration_research_brief.md) | Deep methods/numbers for original corpus |
| [`GAP_AND_COST_PLAN.md`](GAP_AND_COST_PLAN.md) | Cost / gap planning |

---

*Numbers and claims in linked papers are not independently reproduced here. Prefer full-text review before locking implementation details. Category pages in ai-agent-papers refresh biweekly — re-sweep when updating this list.*
