# Glossary

Terms used across Daily Coder, Research Forge, and this documentation hub.

| Term | Definition |
|------|------------|
| **Artifact** | Immutable JSON (or hashed blob) stored by a run; evidence for gates — not authoritative for phase transitions in Daily Coder. |
| **Profile** | Sizing bucket (`S`, `M`, `L`, `XL`, …) selecting workflow phases and budgets. |
| **Phase** | Named step in workflow (`PLAN`, `RESEARCH`, …). Distinct from run **status**. |
| **Packet** | Bounded dict passed into a role invocation (digests + pinned fields). |
| **Plan hash** | SHA-256 of canonical plan JSON; required for writes and acceptance. |
| **Live mode** | Real providers/tools enabled; stricter approvals and `COMPLETE` vs `SIMULATED`. |
| **Mock mode** | Default; exercises contracts without certifying repo correctness. |
| **Repair cycle** | Orchestrator loop back to earlier phase after failed gate (`max_repair_cycles`). |
| **Lane** | Parallel research/scout unit with its own angle (Daily Coder or Wave 2). |
| **Charter** | Research Forge scoped question set and depth from Wave 1. |
| **Evidence card** | Structured extraction unit linked to a source record. |
| **Scrutiny** | Wave 3 post-retrieval review (methods, skeptic, audit). |
| **Director packet** | Token-bounded synthesis input for Wave 5 Principal Research Director. |
| **LOCAL_OBSERVATION** | Experiment result class — not promoted to global research fact without review. |
| **Decision gate** | Research Forge validated decision file for CLI modes (`validate_decisions_for_gate`). |
| **Skill (Daily Coder)** | `skills/*/SKILL.md` loaded by name into planner/implementer prompts. |
| **Skill (Forge Wave 6)** | Manifest routed by `SkillRouter` — different system from Daily Coder skills. |
| **Handoff (Messenger)** | External skill output: 17 engineering role proposals from a corpus. |
| **Steer** | Dashboard user message stored in `threads.jsonl` for an agent backend. |

---

## Cross-links

- [Documentation hub](../README.md)
- [Architecture overview](../architecture/architecture-overview.md)
