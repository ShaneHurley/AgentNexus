# Design lineage — ideas, papers, and code

This document maps **intellectual influences** to **concrete mechanisms** in the `ai_agents` workspace. Entries are labeled:

- **Explicit** — referenced in repo docs, comments, or skill text shipped alongside the project
- **Analogous** — architectural similarity justified by structure, not a claim that authors cited the paper in code

Planning bibliography: [`REFERENCES.md`](../research/REFERENCES.md) and [`agent_orchestration_master_spec.md`](./agent_orchestration_master_spec.md).

---

## Orchestration and state

| Idea | Label | Mechanism in code |
|------|-------|-------------------|
| **Artifact-centric workflows** | Explicit in Daily Coder docs | SQLite authoritative; JSON artifacts evidence-only ([`docs/architecture.md`](../../agents/coding/daily-coder-ecosystem/docs/architecture.md)) |
| **Finite-state control** | Explicit | [`state_machine.py`](../../agents/coding/daily-coder-ecosystem/daily_coder/state_machine.py), Research Forge `RunState` / phase tuples |
| **MAPE-K style loop** | Analogous | Monitor: tool logs; Analyze: reviewers/skeptic; Plan: planner/charter; Execute: implementer/runner; Knowledge: artifacts + ledger |
| **Human-in-the-loop gates** | Explicit | Plan approval (`_ready_to_build`), experiment pre-review, Wave 5 approval tokens |

---

## Tool use and ReAct

| Idea | Label | Mechanism |
|------|-------|-----------|
| **ReAct (reason + act)** | Analogous | LLM turns with tool calls via `PolicyGateway`; bounded `max_tool_turns` / `role_tool_turns` in config |
| **Tool sandboxing** | Explicit | `ToolBroker` role allowlists; experiment runner typed kinds only (no shell) |

---

## Planning and decomposition

| Idea | Label | Mechanism |
|------|-------|-----------|
| **Plan before act** | Explicit | Master → planner → plan_reviewer → approval → implement |
| **Hierarchical task networks** | Analogous | Workflow profiles S–XL with optional research/brainstorm phases ([`workflow.py`](../../agents/coding/daily-coder-ecosystem/daily_coder/workflow.py)) |
| **Tree-of-Thoughts style branching** | Analogous | Brainstorm lanes + Wave 4 parallel ideators; not full ToT search tree |

Daily Coder package doc [`docs/research_basis.md`](../../agents/coding/daily-coder-ecosystem/docs/research_basis.md) ties requirements to sources — consult for traceability IDs.

---

## Multi-agent debate and critique

| Idea | Label | Mechanism |
|------|-------|-----------|
| **Multi-agent debate** | Analogous | Independent research lanes (`RESEARCH_ANGLES`), Wave 2 lanes, Wave 4 ideators — integration happens **after** lanes, not via round-robin dialogue |
| **Adversarial review / constitutional AI** | Analogous + partial explicit | `AdversarialSkeptic`, `plan_reviewer`, `code_reviewer`, skill `adversarial-review`; skeptic cannot search or override charter |
| **Self-refinement loops** | Explicit | `_repair` cycles with cap `max_repair_cycles` |

Research corpus mentions debate papers in `Documentation/` — use when locking future design; Wave 3 implements a **bounded** skeptic, not open-ended debate.

---

## Evidence and medicine-style grading

| Idea | Label | Mechanism |
|------|-------|-----------|
| **GRADE / evidence hierarchies** | Analogous | `claim_status.schema.json`; deep-research rubric (external); Daily Coder observation labels in researcher prompt |
| **Citation verification** | Explicit | Wave 1 `CitationVerifier` |
| **Contradiction matrix** | Explicit | Wave 3 `ContradictionMapper` → `evidence_matrix.schema.json` |

---

## Research retrieval and fan-out

| Idea | Label | Mechanism |
|------|-------|-----------|
| **Iterative retrieval** | Explicit | Wave 2 saturation + expansion coordinator |
| **Query decomposition** | Explicit | Charter questions → landscape lanes |
| **RAG** | Analogous | read → extract → compose; adapters in wave6 |

---

## Evaluation and handoffs

| Idea | Label | Mechanism |
|------|-------|-----------|
| **Matched comparison** | Explicit | `HandoffTaxonomy.run_matched_comparison` (Wave 5) |
| **Recommendation scoring** | Explicit (external skill) | `recommendation-scoring.md` in deep-research / research-messenger skills |
| **17-role ecosystem dispatch** | Explicit (external skill) | research-messenger handoffs ↔ Daily Coder role roster |

---

## Cost, safety, and operations

| Idea | Label | Mechanism |
|------|-------|-----------|
| **Budget-aware agents** | Explicit | `BudgetManager` (both packages) |
| **Fail-closed policy** | Explicit | Tool deny, gate blocks, mock default |
| **Drift detection** | Explicit | Wave 6 `DriftMonitor`; Daily Coder `drift_watchdog` |
| **Evolution with human promotion** | Explicit | `EvolutionManager`, `skill_curator`, config `human_promotion_required` |

---

## What we do not claim

- Research Forge does **not** implement full autonomous paper replication or live web scale without approved adapters.
- Deep-research **six-lane** procedure is **not** fully automated in one CLI command — waves compose incrementally.
- Numbers in `Documentation/agent_orchestration_research_brief.md` are **not** re-validated in this codebase.

---

## Cross-links

- [Research Forge deep dive](./research-forge-deep-dive.md)
- [Build roadmap narrative](./build-roadmap.md)
- [Documentation hub](../README.md)
